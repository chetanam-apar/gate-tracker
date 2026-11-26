"""
One place to set up logs for the whole app.

Logs are better than print() because each line has a time, a level
(INFO / WARNING / ERROR) and which module wrote it. On the server
this is how we find out what happened at 12 AM while we were asleep.
"""
import logging
import os

LOG_FORMAT = "%(asctime)s | %(levelname)-7s | %(name)s | %(message)s"


def setup_logging() -> None:
    level = os.getenv("LOG_LEVEL", "INFO").upper()
    logging.basicConfig(level=level, format=LOG_FORMAT, datefmt="%Y-%m-%d %H:%M:%S")
    # httpx logs every request at INFO, which is too noisy
    logging.getLogger("httpx").setLevel(logging.WARNING)


def get_logger(name: str) -> logging.Logger:
    return logging.getLogger(name)
