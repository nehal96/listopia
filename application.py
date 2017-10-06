# -*- coding: utf-8 -*-

from flask import Flask
from flask import render_template, url_for, request, redirect, jsonify
from flask import make_response, flash
from flask import session as login_session

from oauth2client import client
from oauth2client.client import flow_from_clientsecrets
from oauth2client.client import FlowExchangeError

from datetime import datetime
import httplib2
import json
import ast
import requests
import random, string

from sqlalchemy import create_engine, asc
from sqlalchemy.orm import sessionmaker

from models import Base, Book, User
from helper import getBookInfo, chunkify, getGenreList


GOOGLE_CLIENT_ID = json.loads(
        open('client_secrets.json', 'r').read())['web']['client_id']

engine = create_engine('sqlite:///books.db')
Base.metadata.bind = engine

DBSession = sessionmaker(bind=engine)
session = DBSession()

app = Flask(__name__)


# Helper functions for queries to User database
def createUser(login_session):
    newUser = User(name=login_session['username'], email=login_session['email'],
                 picture=login_session['picture'])
    session.add(newUser)
    session.commit()
    user = session.query(User).filter_by(email=login_session['email']).one()
    return user.id


def getUserInfo(user_id):
    user = session.query(User).filter_by(id=user_id).one()
    return user


def getUserID(email):
    try:
        user = session.query(User).filter_by(email=email).one()
        return user.id
    except:
        return None


@app.route('/')
@app.route('/books')
def showLandingPage():
    if 'username' not in login_session:
        return render_template('landingpage.html')
    else:
        user_id = getUserID(login_session['email'])
        books = session.query(Book).filter_by(user_id=user_id).all()
        book_chunks = chunkify(books, 4)
        genres = getGenreList(books)
        return render_template('mainpage.html', book_chunks=book_chunks,
                                                genres=genres,
                                                login_session=login_session)


@app.route('/login/')
def showLogin():
    state = ''.join(random.choice(string.ascii_uppercase + string.digits)
                for x in xrange(32))
    login_session['state'] = state
    return render_template('login.html', STATE=state)


@app.route('/gconnect', methods=['POST'])
def gconnect():
    # If request doesn't have 'X-Requested-With' header, could be a CSRF
    if not request.headers.get('X-Requested-With'):
        abort(403)

    # Validate state token
    if request.args.get('state') != login_session['state']:
        response = make_response(json.dumps('Invalid state parameter.'), 401)
        response.headers['Content-Type'] = 'application/json'
        return response
    # Obtain authorization code
    code = request.data

    try:
        # Upgrade the authorization code into a credentials object
        oauth_flow = flow_from_clientsecrets('client_secrets.json', scope='')
        oauth_flow.redirect_uri = 'postmessage'
        credentials = oauth_flow.step2_exchange(code)
    except FlowExchangeError:

        response = make_response(
            json.dumps('Failed to upgrade the authorization code.'), 401)
        response.headers['Content-Type'] = 'application/json'
        return response

    # Check that the access token is valid.
    access_token = credentials.access_token
    url = ('https://www.googleapis.com/oauth2/v1/tokeninfo?access_token=%s'
           % access_token)
    h = httplib2.Http()
    result = json.loads(h.request(url, 'GET')[1])
    # If there was an error in the access token info, abort.
    if result.get('error') is not None:
        response = make_response(json.dumps(result.get('error')), 500)
        response.headers['Content-Type'] = 'application/json'
        return response

    # Verify that the access token is used for the intended user.
    gplus_id = credentials.id_token['sub']
    if result['user_id'] != gplus_id:
        response = make_response(
            json.dumps("Token's user ID doesn't match given user ID."), 401)
        response.headers['Content-Type'] = 'application/json'
        return response

    # Verify that the access token is valid for this app.
    if result['issued_to'] != GOOGLE_CLIENT_ID:
        response = make_response(
            json.dumps("Token's client ID does not match app's."), 401)
        print "Token's client ID does not match app's."
        response.headers['Content-Type'] = 'application/json'
        return response

    stored_access_token = login_session.get('access_token')
    stored_gplus_id = login_session.get('gplus_id')
    if stored_access_token is not None and gplus_id == stored_gplus_id:
        response = make_response(
                json.dumps('Current user is already connected.'), 200)
        response.headers['Content-Type'] = 'application/json'
        return response

    # Store the access token in the session for later use.
    login_session['credentials'] = credentials.to_json()
    login_session['access_token'] = credentials.access_token
    login_session['gplus_id'] = gplus_id

    # Get user info
    userinfo_url = "https://www.googleapis.com/oauth2/v1/userinfo"
    params = {'access_token': credentials.access_token, 'alt': 'json'}
    answer = requests.get(userinfo_url, params=params)

    data = answer.json()

    login_session['provider'] = 'google'
    login_session['username'] = data['name']
    login_session['picture'] = data['picture']
    login_session['email'] = data['email']

    # Check if user exists. If not, create a new user.
    user_id = getUserID(login_session['email'])
    if not user_id:
        user_id = createUser(login_session)

    login_session['user_id'] = user_id

    output = ''
    output += '<h4>Welcome, '
    output += login_session['username']
    output += '!</h4>'
    return output


@app.route('/fbconnect', methods=['POST'])
def fbconnect():
    # If request doesn't have 'X-Requested-With' header, could be a CSRF
    if not request.headers.get('X-Requested-With'):
        abort(403)

    # Validate state token
    if request.args.get('state') != login_session['state']:
        response = make_response(json.dumps('Invalid state parameter.'), 401)
        response.headers['Content-Type'] = 'application/json'
        return response

    access_token = request.data
    print "access token received %s " % access_token

    app_id = json.loads(open('fb_client_secrets.json', 'r').read())[
        'web']['app_id']
    app_secret = json.loads(
        open('fb_client_secrets.json', 'r').read())['web']['app_secret']
    url = 'https://graph.facebook.com/oauth/access_token?grant_type=fb_exchange_token&client_id=%s&client_secret=%s&fb_exchange_token=%s' % (
        app_id, app_secret, access_token)
    h = httplib2.Http()
    result = h.request(url, 'GET')[1]


    # Use token to get user info from API
    userinfo_url = "https://graph.facebook.com/v2.10/me"
    '''
        Due to the formatting for the result from the server token exchange we have to
        split the token first on commas and select the first index which gives us the key : value
        for the server access token then we split it on colons to pull out the actual token value
        and replace the remaining quotes with nothing so that it can be used directly in the graph
        api calls
    '''
    token = result.split(',')[0].split(':')[1].replace('"', '')

    url = 'https://graph.facebook.com/v2.10/me?access_token=%s&fields=name,id,email' % token
    h = httplib2.Http()
    result = h.request(url, 'GET')[1]
    # print "url sent for API access:%s"% url
    # print "API JSON result: %s" % result
    data = json.loads(result)
    login_session['provider'] = 'facebook'
    login_session['username'] = data["name"]
    login_session['email'] = data["email"]
    login_session['facebook_id'] = data["id"]

    # The token must be stored in the login_session in order to properly logout
    login_session['access_token'] = token

    # Get user picture
    url = 'https://graph.facebook.com/v2.10/me/picture?access_token=%s&redirect=0&height=200&width=200' % token
    h = httplib2.Http()
    result = h.request(url, 'GET')[1]
    data = json.loads(result)

    login_session['picture'] = data["data"]["url"]

    # see if user exists
    user_id = getUserID(login_session['email'])
    if not user_id:
        user_id = createUser(login_session)
    login_session['user_id'] = user_id

    output = ''
    output += '<h1>Welcome, '
    output += login_session['username']

    output += '!</h1>'

    return output


# Disconnect - revoke a current user's token and reset their login session
@app.route('/gdisconnect')
def gdisconnect():
    access_token = login_session.get('access_token')
    if access_token is None:
        print 'Access token is None'
        response = make_response(
                json.dumps('Current user is not connected.'), 401)
        response.headers['Content-Type'] = 'application/json'
        return response
    #print 'In gdisconnect access token is %s' % access_token
    #print 'User name is: '
    #print login_session['username']
    url = 'https://accounts.google.com/o/oauth2/revoke?token=%s' % access_token
    h = httplib2.Http()


    #credentials = login_session['credentials']
    #print credentials
    #if credentials:
    #    credentials.revoke(h)
    #    reponse = make_response(json.dumps('Successfully disconnected'), 200)
    #    response.headers['Content-Type'] = 'application/json'
    #    return response
    #else:
    #    response = make_response(
    #        json.dumps('Failed to revoke token for given user.'), 400)
    #    response.headers['Content-Type'] = 'application/json'
    #    return response


    result = h.request(url, 'GET')[0]
    print result

    if result['status'] == '200':
        del login_session['provider']
        del login_session['credentials']
        del login_session['access_token']
        del login_session['gplus_id']
        del login_session['user_id']
        del login_session['username']
        del login_session['email']
        del login_session['picture']
        response = make_response(json.dumps('Successfully disconnected.'), 200)
        response.headers['Content-Type'] = 'application/json'
        return redirect(url_for('showLandingPage'))
    else:
        del login_session['provider']
        del login_session['credentials']
        del login_session['access_token']
        del login_session['gplus_id']
        del login_session['user_id']
        del login_session['username']
        del login_session['email']
        del login_session['picture']
        response = make_response(
                json.dumps('Failed to revoke token for given user.'), 400)
        response.headers['Content-Type'] = 'application/json'
        return response


@app.route('/fbdisconnect')
def fbdisconnect():
    facebook_id = login_session['facebook_id']
    # The access token must me included to successfully logout
    access_token = login_session['access_token']
    url = 'https://graph.facebook.com/%s/permissions?access_token=%s' % (facebook_id,access_token)
    h = httplib2.Http()
    result = h.request(url, 'DELETE')[1]
    del login_session['provider']
    del login_session['access_token']
    del login_session['facebook_id']
    del login_session['user_id']
    del login_session['username']
    del login_session['email']
    del login_session['picture']
    return redirect(url_for('showLandingPage'))


@app.route('/book/<title>/<int:id>/')
def showBook(title, id):
    if 'username' not in login_session:
        return redirect('/login')
    book = session.query(Book).filter_by(id=id).one()
    publish_date_str = book.publishDate
    publish_date_dttm = datetime.strptime(publish_date_str, '%Y-%m-%d')
    publish_date_format = publish_date_dttm.strftime("%d %b %Y")

    return render_template('showBook.html', book=book,
                                            publishDate=publish_date_format,
                                            login_session=login_session)


@app.route('/books/<genre>/')
def showGenre(genre):
    if 'username' not in login_session:
        return redirect('/login')

    genre_frmt = genre.replace('+', ' ').title()
    books_by_genre = session.query(Book).filter_by(category=genre_frmt).all()
    book_chunks = chunkify(books_by_genre, 4)

    return render_template('showGenre.html', genre=genre_frmt,
                                             book_chunks=book_chunks,
                                             login_session=login_session)


@app.route('/book/add/', methods=['GET', 'POST'])
def addBook():
    if 'username' not in login_session:
        return redirect('/login')
    if request.method == 'POST':
        if request.form['search']:
            search_query = request.form['search']
            book_info = getBookInfo(search_query)
            if book_info is not None:
                return redirect(url_for('showSearchedBook', book_info=book_info,
                                                login_session=login_session))
            else:
                return render_template('nomatches.html',
                            search_query=search_query,
                            login_session=login_session)
        else:
            return render_template('addBook.html', login_session=login_session)
    else:
        return render_template('addBook.html', login_session=login_session)


@app.route('/book/add/show')
def showSearchedBook():
    book_info = request.args.get('book_info')
    book_info = ast.literal_eval(book_info)
    response = make_response(render_template('showSearchedBook.html',
                                    book_info=book_info,
                                    login_session=login_session))
    return response


@app.route('/book/add/confirm/', methods=['POST'])
def confirmBook():
    if 'username' not in login_session:
        return redirect('/login')

    user_id = getUserID(login_session['email'])
    login_session['user_id'] = user_id

    if request.method == 'POST':
        if request.form['confirmation']:
            book_info = request.args.get('book_info')
            book_info = ast.literal_eval(book_info)
            newBook = Book(googleID=book_info['id'],
                           title=book_info['title'],
                           subtitle=book_info['subtitle'],
                           author=book_info['authors'][0],
                           publisher=book_info['publisher'],
                           publishDate=book_info['publishDate'],
                           description=book_info['description'],
                           ISBN_10=book_info['ISBN_10'],
                           ISBN_13=book_info['ISBN_13'],
                           pageCount=book_info['pageCount'],
                           category=book_info['categories'][0],
                           buyLinkGoogle=book_info['buyLinkGoogle'],
                           imageLink=book_info['imageLink'],
                           user_id=login_session['user_id'])
            session.add(newBook)
            session.commit()
            return redirect(url_for('showLandingPage'))


@app.route('/book/edit/<int:book_id>', methods=['GET', 'POST'])
def editBook(book_id):
    if 'username' not in login_session:
        return redirect('/login')

    book = session.query(Book).filter_by(id=book_id).one()
    publish_date_str = book.publishDate
    publish_date_dttm = datetime.strptime(publish_date_str, '%Y-%m-%d')
    publish_date_format = publish_date_dttm.strftime("%d %b %Y")
    if request.method == 'POST':
        if request.form['description']:
            book.description = request.form['description']
        if request.form['imageurl']:
            book.imageLink = request.form['imageurl']
        session.add(book)
        session.commit()
        return render_template('showBook.html', book=book,
                                                publishDate=publish_date_format,
                                                login_session=login_session)
    else:
        return render_template('editBook.html', book=book,
                                                login_session=login_session)


@app.route('/book/delete/<int:book_id>', methods=['POST'])
def deleteBook(book_id):
    if 'username' not in login_session:
        return redirect('login')

    book = session.query(Book).filter_by(id=book_id).one()
    if request.method == 'POST':
        session.delete(book)
        session.commit()
        return redirect(url_for('showLandingPage'))


# APIs
@app.route('/api/v1/books')
def booksJSON():
    if 'username' in login_session:
        user_id = getUserID(login_session['email'])
        books = session.query(Book).filter_by(user_id=user_id).all()

        return jsonify(books=[book.serialize for book in books])


@app.route('/api/v1/genres')
def genresJSON():
    if 'username' in login_session:
        user_id = getUserID(login_session['email'])
        books = session.query(Book).filter_by(user_id=user_id).all()
        genres = getGenreList(books)

        for genre in genres:
            return jsonify(genres={book.category:
            [book.serialize for book in
            session.query(Book).filter_by(category=genre).all()]
            for genre in genres})





if __name__ == '__main__':
    app.secret_key = 'super_secret_key'
    app.debug = True
    app.run(host='0.0.0.0', port=8000)
