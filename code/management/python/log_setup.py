# log_setup.py
import logging
import sys
from logging.handlers import TimedRotatingFileHandler
import os

# --- Configuration ---
LOG_LEVEL = logging.INFO
LOG_DIR = ".logs"
LOG_FILE = f"{LOG_DIR}/homelab.log"
ERROR_LOG_FILE = f"{LOG_DIR}/homelab.err"  # <-- Path for the error-specific log

os.makedirs(LOG_DIR, exist_ok=True)

# --- Formatter ---
FORMATTER = logging.Formatter("%(asctime)s — %(name)s — %(levelname)s — %(message)s")


def get_console_handler():
    """Returns a handler that prints to the console (stdout)."""
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setFormatter(FORMATTER)
    return console_handler


def get_file_handler():
    """Returns a timed rotating file handler for general logs."""
    file_handler = TimedRotatingFileHandler(LOG_FILE, when="midnight", backupCount=30)
    file_handler.setFormatter(FORMATTER)
    return file_handler


def get_error_file_handler():
    """
    Returns a file handler that logs only ERROR and CRITICAL messages.
    This file will only be created if an error occurs.
    """
    error_handler = logging.FileHandler(ERROR_LOG_FILE)
    error_handler.setLevel(logging.ERROR)
    error_handler.setFormatter(FORMATTER)
    return error_handler


# ---------------------------

# --- Setup ---
logger = logging.getLogger()
logger.setLevel(LOG_LEVEL)  # The lowest level the logger will handle

# Add all handlers to the root logger
logger.addHandler(get_console_handler())
logger.addHandler(get_file_handler())
logger.addHandler(get_error_file_handler())  # <-- NEW: Add the error handler

logger.propagate = False

print("Logger configured!")
