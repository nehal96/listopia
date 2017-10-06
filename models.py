import sys

from sqlalchemy import Column, ForeignKey, Integer, String
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import relationship
from sqlalchemy import create_engine


Base = declarative_base()


class User(Base):
    __tablename__ = 'user'

    id = Column(Integer, primary_key=True)
    name = Column(String(250), nullable=False)
    email = Column(String(250), nullable=False)
    picture = Column(String)


class Book(Base):
    __tablename__ = 'books'

    id = Column(Integer, primary_key=True)
    googleID = Column(String)
    title = Column(String, nullable=False)
    subtitle = Column(String)
    author = Column(String) # For now let's only take the first author
    publisher = Column(String)
    publishDate = Column(String)
    description = Column(String)
    ISBN_10 = Column(String)
    ISBN_13 = Column(String)
    pageCount = Column(Integer)
    category = Column(String)
    buyLinkGoogle = Column(String)
    imageLink = Column(String)
    user_id = Column(Integer, ForeignKey('user.id'))
    user = relationship(User)

    @property
    def serialize(self):

        return {
            'id': self.id,
            #'googleID': self.googleID,
            'title': self.title,
            'subtitle': self.subtitle,
            'author': self.author,
            'publisher': self.publisher,
            'publishDate': self.publishDate,
            'description': self.description,
            #'ISBN_10': self.ISBN_10,
            #'ISBN_13': self.ISBN_13,
            #'pageCount': self.pageCount,
            'category': self.category,
            'buyLinkGoogle': self.buyLinkGoogle,
            'imageLink': self.imageLink
        }


engine = create_engine('sqlite:///books.db')

Base.metadata.create_all(engine)
