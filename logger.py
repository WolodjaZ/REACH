import logging

def get_scrapper_logger():
    logger=logging.getLogger("scraper")

    file_handler=logging.FileHandler('data/scraper.log')
    stream_handler=logging.StreamHandler()

    stream_formatter=logging.Formatter(
        '%(asctime)-15s %(levelname)-8s %(message)s')
    file_formatter=logging.Formatter(
        "%(asctime)s : %(name)s : %(levelname)s : %(message)s"
    )

    file_handler.setFormatter(file_formatter)
    stream_handler.setFormatter(stream_formatter)

    logger.addHandler(file_handler)
    logger.addHandler(stream_handler)

    return logger
