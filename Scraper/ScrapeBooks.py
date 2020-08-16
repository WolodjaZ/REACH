import argparse
from datetime import datetime
import json
import os
import re
import time

from urllib.request import urlopen
from urllib.request import HTTPError
from tqdm import tqdm
import pandas as pd
import bs4

import logger


_COLUMNS = ["book_id", "isbn", "year_first_published", "title", "author", "num_pages",
"genres", "shelves", "lists", "num_ratings", "num_reviews",
"average_rating", "rating_distribution", "book_img"]


class ScrapeBooks(object):
    def __init__(self):
        self._base_url = "https://www.goodreads.com/"
        self._books_for_genre = 1000
        self._logger = logger.get_scrapper_logger()

    def _get_all_lists(self, soup):

        lists = []
        list_count_dict = {}

        if soup.find('a', text='More lists with this book...'):

            lists_url = soup.find('a', text='More lists with this book...')['href']

            source = urlopen('https://www.goodreads.com' + lists_url)
            soup = bs4.BeautifulSoup(source, 'lxml')
            lists += [' '.join(node.text.strip().split()) for node in soup.find_all('div', {'class': 'cell'})]

            i = 0
            while soup.find('a', {'class': 'next_page'}) and i <= 10:

                time.sleep(2)
                next_url = 'https://www.goodreads.com' + soup.find('a', {'class': 'next_page'})['href']
                source = urlopen(next_url)
                soup = bs4.BeautifulSoup(source, 'lxml')

                lists += [node.text for node in soup.find_all('div', {'class': 'cell'})]
                i += 1

            # Format lists text.
            for _list in lists:
                _list_name = _list.split()[:-2][0]
                _list_count = int(_list.split()[-2].replace(',', ''))
                list_count_dict[_list_name] = _list_count
        else:
            id = self._extract_book_id_from_url(soup.text)
            self._logger.warning(f"Lists not found for {id}")

        return list_count_dict

    def _get_shelves(self, soup):

        shelf_count_dict = {}

        if soup.find('a', text='See top shelves…'):

            # Find shelves text.
            shelves_url = soup.find('a', text='See top shelves…')['href']
            source = urlopen('https://www.goodreads.com' + shelves_url)
            soup = bs4.BeautifulSoup(source, 'lxml')
            shelves = [' '.join(node.text.strip().split()) for node in soup.find_all('div', {'class': 'shelfStat'})]

            # Format shelves text.
            shelf_count_dict = {}
            for _shelf in shelves:
                _shelf_name = _shelf.split()[:-2][0]
                _shelf_count = int(_shelf.split()[-2].replace(',', ''))
                shelf_count_dict[_shelf_name] = _shelf_count

        else:
            id = self._extract_book_id_from_url(soup.text)
            self._logger.warning(f"shelves not found for {id}")

        return shelf_count_dict

    def _get_genres(self, soup):
        genres = []
        for node in soup.find_all('div', {'class': 'left'}):
            current_genres = node.find_all('a', {'class': 'actionLinkLite bookPageGenreLink'})
            current_genre = ' > '.join([g.text for g in current_genres])
            if current_genre.strip():
                genres.append(current_genre)

        if len(genres) == 0:
            id = self._extract_book_id_from_url(soup.text)
            self._logger.warning(f"Genres not found for {id}")

        return genres

    def _get_isbn(self, soup):
        isbn = ''
        isbn_node = soup.find('div', {'class': 'infoBoxRowTitle'}, text='ISBN')
        if not isbn_node:
            isbn_node = soup.find('div', {'class': 'infoBoxRowTitle'}, text='ISBN13')
        if isbn_node:
            isbn = ' '.join(isbn_node.find_next_sibling().text.strip().split())
        if isbn:
            isbn_number = isbn.split()[0]
        else:
            id = self._extract_book_id_from_url(soup.text)
            self._logger.warning(f"isbn not found for {id}")
            isbn_number = ""

        return isbn_number

    def _get_rating_distribution(self, soup):
        try:
            distribution = re.findall(r'renderRatingGraph\([\s]*\[[0-9,\s]+', str(soup))[0]
            distribution = ' '.join(distribution.split())
            distribution = [int(c.strip()) for c in distribution.split('[')[1].split(',')]
            distribution_dict = {'5 Stars': distribution[0],
                                 '4 Stars': distribution[1],
                                 '3 Stars': distribution[2],
                                 '2 Stars': distribution[3],
                                 '1 Star':  distribution[4]}
        except:
            id = self._extract_book_id_from_url(soup.text)
            self._logger.exception(f"Rating distribution not found for {id}")
            distribution_dict = {'5 Stars': "-1",
                                 '4 Stars': "-1",
                                 '3 Stars': "-1",
                                 '2 Stars': "-1",
                                 '1 Star':  "-1"}

        return distribution_dict

    def _get_num_pages(self, soup):
        if soup.find('span', {'itemprop': 'numberOfPages'}):
            num_pages = soup.find('span', {'itemprop': 'numberOfPages'}).text.strip()
            num_pages = int(num_pages.split()[0])
        else:
            id = self._extract_book_id_from_url(soup.text)
            self._logger.warning(f"isbn not found for {id}")
            num_pages = ''

        return num_pages

    def _get_year_first_published(self, soup):
        try:
            year_first_published = soup.find('nobr', attrs={'class':'greyText'}).string
            year = re.search('([0-9]{3,4})', year_first_published).group(1)
        except:
            id = self._extract_book_id_from_url(soup.text)
            self._logger.exception(f"First year published not found for {id}")
            year = ""

        return year

    def _extract_book_id_from_url(self, url):
        try:
            book_id_full = url.split('/')[-1]
            book_id = re.findall('\d+', book_id_full)[0]
        except:
            self._logger.error("book id not found")
            book_id = None
        return book_id

    def _get_book_list(self, url):
        lists = []
        page = 1
        while True:
            try:
                book_source = urlopen(url + f"?page={page}")
                book_soup = bs4.BeautifulSoup(book_source, 'html.parser')
                time.sleep(2)
            except:
                self._logger.info(f"Found {page} list of books")
                break

            for tag in book_soup.find_all('a', {'class':'listTitle'}, href=True):
                lists.append(self._base_url + tag['href'])

            page += 1

        return lists

    def _get_book_id_from_list(self, url):
        books = []
        page = 1
        book_list_title = url.strp('/')[-1]
        while True:
            try:
                book_source = urlopen(url + f"?page={page}")
                book_soup = bs4.BeautifulSoup(book_source, 'html.parser')
                time.sleep(2)
            except:
                self._logger.info(f"Found {page} books in {book_list_title}")
                break

            for tag in book_soup.find_all('a', {'class': 'bookTitle'}, href=True):
                bookd_id = self._extract_book_id_from_url(tag['href'])
                if book_id:
                    books.append(book_id)

            page += 1

        return books

    def _scrape_book_by_url(self, book_id):
        url = self._base_url + '/book/show/' + book_id
        source = urlopen(url)
        soup = bs4.BeautifulSoup(source, 'html.parser')

        time.sleep(2)

        return {'book_id':              book_id,
                'isbn':                 self._get_isbn(soup),
                'year_first_published': self._get_year_first_published(soup),
                'title':                ' '.join(soup.find('h1', {'id': 'bookTitle'}).text.split()),
                'author':               ' '.join(soup.find('span', {'itemprop': 'name'}).text.split()),
                'num_pages':            self._get_num_pages(soup),
                'genres':               self._get_genres(soup),
                'shelves':              self._get_shelves(soup),
                'lists':                self._get_all_lists(soup),
                'num_ratings':          soup.find('meta', {'itemprop': 'ratingCount'})['content'].strip(),
                'num_reviews':          soup.find('meta', {'itemprop': 'reviewCount'})['content'].strip(),
                'average_rating':       soup.find('span', {'itemprop': 'ratingValue'}).text.strip(),
                'rating_distribution':  self._get_rating_distribution(soup)}


    def scrape_books(self):
        self._logger.info("Staring scraping books")

        try:
            url = self._base_url + 'list/popular_lists'
            source = urlopen(url)
        except:
            self._logger.exception(f"Url is not vaild {self._base_url}list/popular_lists")
            raise

        book_list = self._get_book_list(url)

        df = pd.DataFrame(columns=_COLUMNS)

        for book_list in tqdm(book_list, desc="Book lists"):
                books = self._get_book_id_from_list(book_list)
                book_list_title = re.find('\d+', book_list.strip('/')[-1]).group(1)[1:]
                self._logger.debug(book_list_title)
                for book in tqdm(books, desc=book_list_title):
                    try:
                        df = df.append(self._scrape_book_by_url(book), ignore_index=True)
                        self._logger.info(f"Book {book} scraped")
                    except:
                        self._logger.warning(f"Getting book {book} data failed")

        self._logger.info("FINISHED")
        return df
