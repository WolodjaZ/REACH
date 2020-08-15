import argparse
from collections import Counter
from datetime import datetime
import json
import os
import re
import time

import bs4
import pandas as pd
from selenium import webdriver
from selenium.webdriver.common.action_chains import ActionChains
from selenium.common.exceptions import NoSuchElementException, ElementNotInteractableException, ElementClickInterceptedException, ElementNotVisibleException
from selenium.webdriver.support.ui import Select
from urllib.request import urlopen
from urllib.request import HTTPError

from webdriver_manager.chrome import ChromeDriverManager
from webdriver_manager.firefox import GeckoDriverManager


RATING_STARS_DICT = {'it was amazing': 5,
                     'really liked it': 4,
                     'liked it': 3,
                     'it was ok': 2,
                     'did not like it': 1,
                     '': None}


class ScrapeRevies(object):
    def __init__(self):
        self._base_url = "https://www.goodreads.com/"
        self._browser = 'chrome'

    def _switch_reviews_mode(self, driver, book_id, sort_order, rating=''):
        """
        Copyright (C) 2019 by Omar Einea: https://github.com/OmarEinea/GoodReadsScraper
        Licensed under GPL v3.0: https://github.com/OmarEinea/GoodReadsScraper/blob/master/LICENSE.md
        Accessed on 2019-12-01.
        """

        SORTS = ['default', 'newest', 'oldest']
        edition_reviews=False
        driver.execute_script(
            'document.getElementById("reviews").insertAdjacentHTML("beforeend", \'<a data-remote="true" rel="nofollow"'
            f'class="actionLinkLite loadingLink" data-keep-on-success="true" id="switch{rating}{sort_order}"' +
            f'href="/book/reviews/{book_id}?rating={rating}&sort={SORTS[sort_order]}' +
            ('&edition_reviews=true' if edition_reviews else '') + '">Switch Mode</a>\');' +
            f'document.getElementById("switch{rating}{sort_order}").click()'
        )
        return True


    def _get_rating(self, node):
        if len(node.find_all('span', {'class': 'staticStars'})) > 0:
            rating = node.find_all('span', {'class': 'staticStars'})[0]['title']
            return RATING_STARS_DICT[rating]
        return ''


    def _get_user(self, node):
        if len(node.find_all('a', {'class': 'user'})) > 0:
            return node.find_all('a', {'class': 'user'})[0]['href']
        return ''


    def _get_date(self, node):
        if len(node.find_all('a', {'class': 'reviewDate createdAt right'})) > 0:
            return node.find_all('a', {'class': 'reviewDate createdAt right'})[0].text
        return ''


    def _get_text(self, node):

        display_text = ''
        full_text = ''

        if len(node.find_all('span', {'class': 'readable'})) > 0:
            for child in node.find_all('span', {'class': 'readable'})[0].children:
                if child.name == 'span' and 'style' not in child:
                    display_text = child.text
                if child.name == 'span' and 'style' in child and child['style'] == 'display:none':
                    full_text = child.text

        if full_text:
            return full_text

        return display_text


    def _get_num_likes(self, node):
        if node.find('span', {'class': 'likesCount'}) and len(node.find('span', {'class': 'likesCount'})) > 0:
            likes = node.find('span', {'class': 'likesCount'}).text
            if 'likes' in likes:
                return int(likes.split()[0])
        return 0


    def _get_shelves(self, node):
        shelves = []
        if node.find('div', {'class': 'uitext greyText bookshelves'}):
            _shelves_node = node.find('div', {'class': 'uitext greyText bookshelves'})
            for _shelf_node in _shelves_node.find_all('a'):
                shelves.append(_shelf_node.text)
        return shelves


    def _scrape_reviews_on_current_page(self, driver, url, book_id):

        reviews = []

        # Disable pop up
        try:
             button = driver.find_element_by_xpath("//button[@class='gr-iconButton']")
             driver.execute_script("arguments[0].click();", button)

        except Exception as ex:
            print(ex)
            pass

        # Pull the page source, load into BeautifulSoup, and find all review nodes.
        source = driver.page_source
        soup = bs4.BeautifulSoup(source, 'lxml')
        nodes = soup.find_all('div', {'class': 'review'})

        # Iterate through and parse the reviews.
        for node in nodes:
            reviews.append({'book_id': book_id,
                            'review_url': url,
                            'review_id': node['id'],
                            'date': self._get_date(node),
                            'rating': self._get_rating(node),
                            'user': self._get_user(node),
                            'text': self._get_text(node),
                            'num_likes': self._get_num_likes(node),
                            'shelves': self._get_shelves(node)})

        return reviews


    def _check_for_duplicates(self, reviews):
        review_ids = [r['review_id'] for r in reviews]
        num_duplicates = len([_id for _id, _count in Counter(review_ids).items() if _count > 1])
        if num_duplicates >= 30:
            return True
        return False


    def _get_reviews_first_ten_pages(self, driver, book_id, sort_order):

        reviews = []
        url = self._base_url + 'book/show/' + book_id
        driver.get(url)

        source = driver.page_source

        try:


            # Re-order the reviews so that we scrape the newest or oldest reviews instead of the default.
            if sort_order != 0:
                self._switch_reviews_mode(driver, book_id, sort_order)
                time.sleep(2)

            # Filter to only English reviews (need extra step for most liked reviews).
            if sort_order == 0:
                select = Select(driver.find_element_by_name('language_code'))
                select.select_by_value('es')
                time.sleep(4)
            select = Select(driver.find_element_by_name('language_code'))
            select.select_by_value('en')
            time.sleep(4)

            # Scrape the first page of reviews.
            reviews = self._scrape_reviews_on_current_page(driver, url, book_id)

            # GoodReads will only load the first 10 pages of reviews.
            # Click through each of the following nine pages and scrape each page.
            for i in range(2, 11):
                try:
                    if driver.find_element_by_xpath("//a[@rel='next'][text()=" + str(i) + "]"):
                        driver.find_element_by_xpath("//a[@rel='next'][text()=" + str(i) + "]").click()
                        time.sleep(2)
                        reviews += self._scrape_reviews_on_current_page(driver, url, book_id)
                    else:
                        return reviews
                except NoSuchElementException or ElementNotInteractableException:
                    print('ERROR: Could not find next page link! Re-scraping this book.')
                    reviews = self._get_reviews_first_ten_pages(driver, book_id, sort_order)
                    return reviews
                except ElementNotVisibleException:
                    print('ERROR: Pop-up detected, reloading the page.')
                    reviews = self._get_reviews_first_ten_pages(driver, book_id, sort_order)
                    return reviews

        except ElementClickInterceptedException:
            print('ERROR: Pop-up detected, reloading the page.')
            reviews = self._get_reviews_first_ten_pages(driver, book_id, sort_order)
            return reviews

        if self._check_for_duplicates(reviews):
            print('ERROR: Duplicates found! Re-scraping this book.')
            reviews = self._get_reviews_first_ten_pages(driver, book_id, sort_order)
            return reviews

        return reviews

    def scrape_reviews(self, df_books):
        if self._browser.lower() == 'chrome':
            try:
                driver = webdriver.Chrome()
            except:
                driver = webdriver.Chrome(ChromeDriverManager().install())
        else:
            try:
                driver = webdriver.Firefox()
            except:
                driver = webdriver.Firefox(executable_path=GeckoDriverManager().install())

        columns = ["book_id", "review_url", "review_id",
        "rating", "user", "text", "num_likes", "shelves"]
        df_reviews = pd.DataFrame(columns=columns)

        for book_id in df_books['book_id']:
            start = time.time()
            try:
                reviews = self._get_reviews_first_ten_pages(driver, book_id, 0)

                if reviews:
                    for review in reviews:
                        df_reviews = df_reviews.append(review, ignore_index=True)

            except HTTPError:
                pass

            elapse = time.time() - start
            print(f"Procced with {book_id}, time took {elapse}")

        driver.quit()
        print(f"FINISHED")
        return df_reviews
