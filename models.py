from sqlalchemy import Column, Integer, String
from sqlalchemy.orm import relationship
from sqlalchemy.sql.schema import ForeignKey, Table
from sqlalchemy.ext.declarative import declarative_base


Base = declarative_base()

quotes_to_tags = Table(
    "quotes_to_tags",
    Base.metadata,
    Column("id", Integer, primary_key=True),
    Column("quote", Integer, ForeignKey("quotes.id", ondelete="CASCADE")),
    Column("tag", Integer, ForeignKey("tags.id", ondelete="CASCADE")),
)


class Author(Base):
    __tablename__ = "authors"
    id = Column(Integer, primary_key=True)
    name = Column(String(50), nullable=False, unique=True)
    birthday = Column(String)
    born_in = Column(String)
    bio = Column(String)


class Quote(Base):
    __tablename__ = "quotes"
    id = Column(Integer, primary_key=True)
    author = Column("Author", ForeignKey("authors.id"))
    text = Column(String)
    link_to_author = Column(String)
    tags = relationship("Tag", secondary=quotes_to_tags)


class Tag(Base):
    __tablename__ = "tags"
    id = Column(Integer, primary_key=True)
    name = Column(String(25), nullable=False)
