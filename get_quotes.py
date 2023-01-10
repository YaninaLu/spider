import re
from multiprocessing import Process
from scrapy.crawler import CrawlerProcess
import scrapy
from itemadapter import ItemAdapter
from scrapy import signals

from models import Base, Quote, Tag, Author
from sqlalchemy import create_engine
from sqlalchemy.pool import NullPool
from sqlalchemy.orm import sessionmaker

base_url = 'http://quotes.toscrape.com/'


class QuoteItem(scrapy.Item):
    author = scrapy.Field()
    text = scrapy.Field()
    tags = scrapy.Field()
    link_to_author = scrapy.Field()


class AuthorItem(scrapy.Item):
    fullname = scrapy.Field()
    birth_date = scrapy.Field()
    born_in = scrapy.Field()
    bio = scrapy.Field()


class DbSavePipeline(object):
    def __init__(self, settings):
        self.database = "sqlite:///quotes.db"
        self.sessions = {}

    @classmethod
    def from_crawler(cls, crawler):
        pipeline = cls(crawler.settings)
        crawler.signals.connect(pipeline.spider_opened, signals.spider_opened)
        crawler.signals.connect(pipeline.spider_closed, signals.spider_closed)
        return pipeline

    def create_engine(self):
        engine = create_engine(self.database, echo=True, poolclass=NullPool)
        return engine

    def create_tables(self, engine):
        Base.metadata.create_all(engine, checkfirst=True)

    def create_session(self, engine):
        session = sessionmaker(bind=engine)()
        return session

    def spider_opened(self, spider):
        engine = self.create_engine()
        self.create_tables(engine)
        session = self.create_session(engine)
        self.sessions[spider] = session

    def spider_closed(self, spider):
        session = self.sessions.pop(spider)
        session.close()


class QuotesPipeline(DbSavePipeline):

    @staticmethod
    def add_tags(quote, tags, session):
        for tag in tags:
            tag_query = session.query(Tag).filter(Tag.name == tag)
            existing_tag = tag_query.first()

            if existing_tag:
                quote.tags.append(existing_tag)
            else:
                tag = Tag(name=tag)
                session.add(tag)
                quote.tags.append(tag)
                continue

    def process_item(self, item, spider):
        adapter = ItemAdapter(item)
        session = self.sessions[spider]
        quote = Quote(author=adapter['author'], text=re.sub(r'[“”\n]', '', adapter['text']),
                      link_to_author=base_url + adapter['link_to_author'])

        try:
            session.add(quote)
            self.add_tags(quote, adapter['tags'], session)
            session.commit()
        except Exception as err:
            raise f'Something went wrong: {err}'

        return item


class AuthorsPipeline(DbSavePipeline):

    def process_item(self, item, spider):
        adapter = ItemAdapter(item)
        session = self.sessions[spider]
        author = Author(name=adapter['fullname'], birthday=adapter['birth_date'], born_in=adapter['born_in'],
                        bio=adapter['bio'])

        try:
            session.add(author)
            session.commit()
        except Exception as err:
            raise f'Something went wrong: {err}'

        return item


class QuotesSpider(scrapy.Spider):
    name = 'quotes'
    allowed_domains = ['quotes.toscrape.com']
    start_urls = ['http://quotes.toscrape.com/']
    custom_settings = {
        'ITEM_PIPELINES': {
            QuotesPipeline: 300,
        }
    }

    def parse(self, response, **kwargs):
        for quote in response.xpath("/html//div[@class='quote']"):
            tags = quote.xpath("div[@class='tags']/a/text()").extract()
            author = quote.xpath("span/small/text()").get()
            link = quote.xpath("span[2]/a/@href").get()
            text = quote.xpath("span[@class='text']/text()").get()
            yield QuoteItem(author=author, text=text, tags=tags, link_to_author=link)

        next_link = response.xpath("//li[@class='next']/a/@href").get()
        if next_link:
            yield scrapy.Request(url=self.start_urls[0] + next_link)


class AuthorsSpider(scrapy.Spider):
    name = 'authors'
    allowed_domains = ['quotes.toscrape.com']
    start_urls = ['http://quotes.toscrape.com/']
    custom_settings = {
        'ITEM_PIPELINES': {
            AuthorsPipeline: 300,
        }
    }

    def parse(self, response, **kwargs):
        for quote in response.xpath("/html//div[@class='quote']"):
            yield response.follow(url=self.start_urls[0] + quote.xpath('span/a/@href').get(),
                                  callback=self.parse_author)
        next_link = response.xpath("//li[@class='next']/a/@href").get()
        if next_link:
            yield scrapy.Request(url=self.start_urls[0] + next_link)

    def parse_author(self, response):
        content = response.xpath("/html//div[@class='author-details']")
        fullname = content.xpath("h3/text()").get().strip()
        birth_date = content.xpath("p/span[@class='author-born-date']/text()").get().strip()
        born_in = content.xpath("p/span[@class='author-born-location']/text()").get().strip()
        bio = content.xpath("div[@class='author-description']/text()").get().strip()
        yield AuthorItem(fullname=fullname, birth_date=birth_date, bio=bio, born_in=born_in)


if __name__ == '__main__':
    process = CrawlerProcess()
    process.crawl(AuthorsSpider)
    process.crawl(QuotesSpider)
    process.start()
