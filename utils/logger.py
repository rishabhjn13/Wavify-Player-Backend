import logging
import os
from logging.handlers import RotatingFileHandler

LOG_FILE = os.getenv("LOG_FILE", "logs/app.log")
LOG_LEVEL = os.getenv("LOG_LEVEL", "INFO").upper()

def _setup_logger() -> logging.Logger:
    logger = logging.getLogger("wavify")

    if logger.handlers:
        return logger  # Already configured — don't add duplicate handlers

    logger.setLevel(LOG_LEVEL)

    fmt = logging.Formatter(
        "%(asctime)s - %(name)s - %(levelname)s - %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )

    # Console
    stream_handler = logging.StreamHandler()
    stream_handler.setFormatter(fmt)

    # File — rotates at 5MB, keeps 3 backups
    file_handler = RotatingFileHandler(LOG_FILE, maxBytes=5 * 1024 * 1024, backupCount=3)
    file_handler.setFormatter(fmt)

    logger.addHandler(stream_handler)
    logger.addHandler(file_handler)

    return logger

logger = _setup_logger()


def get_logger(name: str) -> logging.Logger:
    """
    Get a child logger for a specific module.
    Inherits all handlers and level from the root 'wavify' logger.
    Usage:
    from logger import get_logger
    logger = get_logger(__name__)
    """
    return logging.getLogger(f"wavify.{name}")