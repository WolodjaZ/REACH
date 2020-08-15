import argparse
from datetime import datetime
import json
import os
import re
import time

from urllib.request import urlopen
from urllib.request import HTTPError
import pandas as pd
import bs4

class ScrapeBooks(object):
    def __init__(self):
        self._base_url = "https://www.goodreads.com/"
        self._books_for_genre = 1000

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
                # _list_name = ' '.join(_list.split()[:-8])
                # _list_rank = int(_list.split()[-8][:-2])
                # _num_books_on_list = int(_list.split()[-5].replace(',', ''))
                # list_count_dict[_list_name] = _list_rank / float(_num_books_on_list)     # TODO: switch this back to raw counts
                _list_name = _list.split()[:-2][0]
                _list_count = int(_list.split()[-2].replace(',', ''))
                list_count_dict[_list_name] = _list_count

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

        return shelf_count_dict

    def _get_genres(self, soup):
        genres = []
        for node in soup.find_all('div', {'class': 'left'}):
            current_genres = node.find_all('a', {'class': 'actionLinkLite bookPageGenreLink'})
            current_genre = ' > '.join([g.text for g in current_genres])
            if current_genre.strip():
                genres.append(current_genre)
        return genres

    def _get_isbn(self, soup):
        isbn = ''
        isbn_node = soup.find('div', {'class': 'infoBoxRowTitle'}, text='ISBN')
        if not isbn_node:
            isbn_node = soup.find('div', {'class': 'infoBoxRowTitle'}, text='ISBN13')
        if isbn_node:
            isbn = ' '.join(isbn_node.find_next_sibling().text.strip().split())
        return isbn.split()[0]

    def _get_rating_distribution(self, soup):
        distribution = re.findall(r'renderRatingGraph\([\s]*\[[0-9,\s]+', str(soup))[0]
        distribution = ' '.join(distribution.split())
        distribution = [int(c.strip()) for c in distribution.split('[')[1].split(',')]
        distribution_dict = {'5 Stars': distribution[0],
                             '4 Stars': distribution[1],
                             '3 Stars': distribution[2],
                             '2 Stars': distribution[3],
                             '1 Star':  distribution[4]}
        return distribution_dict

    def _get_num_pages(self, soup):
        if soup.find('span', {'itemprop': 'numberOfPages'}):
            num_pages = soup.find('span', {'itemprop': 'numberOfPages'}).text.strip()
            return int(num_pages.split()[0])
        return ''

    def _get_year_first_published(self, soup):
        year_first_published = soup.find('nobr', attrs={'class':'greyText'}).string
        return re.search('([0-9]{3,4})', year_first_published).group(1)

    def _scrape_book_by_id(self, book_id):
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

    def _scrape_book_by_url(self, url):
        source = urlopen(url)
        soup = bs4.BeautifulSoup(source, 'html.parser')

        time.sleep(2)
        book_id_full = url.split('/')[-1]
        book_id = re.findall('\d+', book_id_full)[0]

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
                'rating_distribution':  self._get_rating_distribution(soup),
                'book_img':             soup.find('img', id='coverImage')['src']}

    def _get_genre_list(self, soup):
        genre_list = []

        genre_view_list = soup.find('div', {'id':'browseBox'})
        for tag in genre_view_list.find_all('a'):
            if tag.text:
                genre_list.append(tag.text)


        return genre_list

    def scrape_books(self):
        source = urlopen(self._base_url)
        soup = bs4.BeautifulSoup(source, 'html.parser')

        time.sleep(2)

        genre_list = self._get_genre_list(soup)

        columns = ["book_id", "isbn", "year_first_published", "title", "author", "num_pages",
        "genres", "shelves", "lists", "num_ratings", "num_reviews",
        "average_rating", "rating_distribution", "book_img"]
        df = pd.DataFrame(columns=columns)

        for genre in genre_list:
                link = self._base_url + "shelf/show/" + genre
                genre_source = urlopen(link)
                genre_soup = bs4.BeautifulSoup(genre_source, 'html.parser')

                time.sleep(2)
                start = time.time()

                books = genre_soup.find_all('a', {'class': 'bookTitle'}, href=True)
                for book in books[:self._books_for_genre]:
                    book_link = self._base_url[:-1] + book['href']
                    df = df.append(self._scrape_book_by_url(book_link), ignore_index=True)

                elapse = time.time() - start
                print(f"Procced with {genre}, time took {elapse}")

        print(f"FINISHED")
        return df
