import logging

def setup_logger(level=logging.INFO):
    logging.basicConfig(level)

def get_logger(name: str) -> logging.Logger:
    return logging.getLogger(name)
