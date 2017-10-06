# -*- coding: utf-8 -*-

import httplib2
import json
from flask import jsonify

GOOGLE_API_KEY = 'AIzaSyAoP6d5rxc2yN3584UVfRdSGuU6fmwyKOI'

search_term = 'American Kingpin'

def getBookInfo(search_term):
    """
        Sends a request to Google Books API and gets information for the first
        book in the search result based on the 'search_term' query. Returns a
        JSON object with just the information required and in a simpler format
        than the API response.
    """

    # Replace spaces with + so they can be placed into API request url
    search_term_query = search_term.replace(' ', '+')

    # Send request to Google Books API and save response as JSON object.
    search_url = ('https://www.googleapis.com/books/v1/volumes?q=%s&key=%s' % (search_term_query, GOOGLE_API_KEY))
    h = httplib2.Http()
    response, content = h.request(search_url, 'GET')
    result = json.loads(content)

    try:
        first_item = result['items'][0]
    except (IndexError, KeyError, ValueError):
        first_item = None

    # Get only the book information required
    if first_item is not None:
        id = first_item['id']

        try:
            title = first_item['volumeInfo']['title']
        except KeyError:
            title = None

        try:
            subtitle = first_item['volumeInfo']['subtitle']
        except KeyError:
            subtitle = None

        try:
            authors = first_item['volumeInfo']['authors']
        except KeyError:
            authors = None

        try:
            publisher = first_item['volumeInfo']['publisher']
        except KeyError:
            publisher = None

        try:
            publish_date = first_item['volumeInfo']['publishedDate']
        except KeyError:
            publish_date = None

        try:
            description = first_item['volumeInfo']['description']
        except KeyError:
            description = None

        # Need to make sure ISBN-10 and ISBN-13 are always in that order
        try:
            ISBN_10 = first_item['volumeInfo']['industryIdentifiers'][1]['identifier']
        except (IndexError, KeyError):
            ISBN_10 = None

        try:
            ISBN_13 = first_item['volumeInfo']['industryIdentifiers'][0]['identifier']
        except (IndexError, KeyError):
            ISBN_13 = None

        try:
            page_count = first_item['volumeInfo']['pageCount']
        except KeyError:
            page_count = None

        try:
            categories = first_item['volumeInfo']['categories']
        except KeyError:
            categories = None

        try:
            buy_link_google = first_item['saleInfo']['buyLink']
        except KeyError:
            buy_link_google = None

        try:
            image_url = ('https://books.google.com/books/content/images/frontcover/%s?fife=w300' % id)
        except:
            image_url = None

        book_info = {
            "id": id,
            "title": title,
            "subtitle": subtitle,
            "authors": authors,
            "publisher": publisher,
            "publishDate": publish_date,
            "description": description,
            "ISBN_10": ISBN_10,
            "ISBN_13": ISBN_13,
            "pageCount": page_count,
            "categories": categories,
            "buyLinkGoogle": buy_link_google,
            "imageLink": image_url
        }

        return book_info
    else:
        return None


def chunkify(l, chunk_size):
    """Return list of evenly sized lists"""
    book_chunks = []
    for i in xrange(0, len(l), chunk_size):
        book_chunks.append(l[i:i + chunk_size])

    return book_chunks


def getGenreList(books):
    """
        Return the list of genres/categories of the books given a books object
        (from database query).
    """
    genres = []
    for book in books:
        if book.category:
            genre = book.category
            if genre not in genres:
                genres.append(genre)

    return genres
