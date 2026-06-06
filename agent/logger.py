"""
agent/logger.py
--------------
Centralized logging setup for the Website Automation Agent.

Provides a pre-configured logger that writes to both the console
(INFO level) and a rotating log file (DEBUG level) so every agent
action can be traced after a run.
"""

import logging
import os
from logging.handlers import RotatingFileHandler

LOG_FILE = "agent.log"
LOG_FORMAT = "%(asctime)s | %(levelname)-8s | %(name)s | %(message)s"
DATE_FORMAT = "%Y-%m-%d %H:%M:%S"


def get_logger(name: str = "automation_agent") -> logging.Logger:
    """
    Return a named logger with console + file handlers attached.

    If a logger with the given name already exists (e.g. called from
    multiple modules), the existing one is returned without adding
    duplicate handlers.

    Args:
        name: Logger name, defaults to 'automation_agent'.

    Returns:
        A fully configured logging.Logger instance.
    """
    logger = logging.getLogger(name)

    # Avoid adding handlers multiple times when module is re-imported
    if logger.handlers:
        return logger

    logger.setLevel(logging.DEBUG)  # capture everything at root level

    # ── Console handler (INFO and above) ──────────────────────────────
    console_handler = logging.StreamHandler()
    console_handler.setLevel(logging.INFO)
    console_handler.setFormatter(logging.Formatter(LOG_FORMAT, datefmt=DATE_FORMAT))

    # ── File handler (DEBUG and above, rotating at 5 MB, keep 3 backups)
    file_handler = RotatingFileHandler(
        LOG_FILE,
        maxBytes=5 * 1024 * 1024,  # 5 MB
        backupCount=3,
        encoding="utf-8",
    )
    file_handler.setLevel(logging.DEBUG)
    file_handler.setFormatter(logging.Formatter(LOG_FORMAT, datefmt=DATE_FORMAT))

    logger.addHandler(console_handler)
    logger.addHandler(file_handler)

    return logger
