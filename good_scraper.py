import pandas as pd

from Scraper.ScrapeBooks import ScrapeBooks
from Scraper.ScrapeRevies import ScrapeRevies


def main():
    print("Staring scraping books")
    books_scraper = ScrapeBooks()
    df_books = books_scraper.scrape_books()
    df_books.to_csv('data/books.csv', index=False)

    print("Starting scaping reviews")
    review_scraper = ScrapeRevies()
    df_books = None
    df_reviews = review_scraper.scrape_reviews(df_books)
    df_reviews.to_csv('data/review.csv', index=False)

if __name__ == '__main__':
    main()
