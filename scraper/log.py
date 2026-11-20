"""Shared logger: timestamped lines to the screen and to a rotating file (idea from job_applier)."""
import logging
from functools import lru_cache
from logging.handlers import RotatingFileHandler
from pathlib import Path

LOG_FILE = Path("logs/agent.log")        # logs/ is git-ignored


@lru_cache(maxsize=None)                 # configure once; later calls return the same logger
def get_logger(name="experis"):
    logger = logging.getLogger(name)
    logger.setLevel(logging.INFO)
    logger.propagate = False             # don't print twice through Python's root logger

    fmt = logging.Formatter("%(asctime)s %(levelname)-7s %(module)s: %(message)s",
                            "%Y-%m-%d %H:%M:%S")
    LOG_FILE.parent.mkdir(parents=True, exist_ok=True)
    file_handler = RotatingFileHandler(LOG_FILE, maxBytes=2_000_000, backupCount=5, encoding="utf-8")
    console_handler = logging.StreamHandler()
    for handler in (file_handler, console_handler):
        handler.setFormatter(fmt)
        logger.addHandler(handler)
    return logger
