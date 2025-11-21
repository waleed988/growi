"""
Logging configuration for Instagram scraper.
"""

import logging
import sys
from typing import Optional
import coloredlogs

from config.settings import ScraperConfig


def setup_logger(
    name: str = "instagram_scraper",
    log_file: Optional[str] = None,
    level: Optional[str] = None
) -> logging.Logger:
    """
    Setup and configure logger with colored output and file logging.

    Args:
        name: Logger name
        log_file: Path to log file (optional)
        level: Log level (optional, defaults to config)

    Returns:
        Configured logger instance
    """
    logger = logging.getLogger(name)

    # Set level from config or parameter
    log_level = level or ScraperConfig.LOG_LEVEL
    logger.setLevel(getattr(logging, log_level.upper()))

    # Clear existing handlers
    logger.handlers = []

    # Create formatters
    detailed_formatter = logging.Formatter(
        fmt="%(asctime)s | %(levelname)-8s | %(name)s | %(funcName)s:%(lineno)d | %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S"
    )

    simple_formatter = logging.Formatter(
        fmt="%(asctime)s | %(levelname)-8s | %(message)s",
        datefmt="%H:%M:%S"
    )

    # Console handler with colored logs
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setLevel(logging.DEBUG)
    console_handler.setFormatter(simple_formatter)

    # Install coloredlogs for console
    coloredlogs.install(
        level=log_level.upper(),
        logger=logger,
        fmt="%(asctime)s | %(levelname)-8s | %(message)s",
        datefmt="%H:%M:%S",
        field_styles={
            'asctime': {'color': 'green'},
            'levelname': {'bold': True, 'color': 'black'},
        },
        level_styles={
            'debug': {'color': 'cyan'},
            'info': {'color': 'blue'},
            'warning': {'color': 'yellow'},
            'error': {'color': 'red'},
            'critical': {'bold': True, 'color': 'red'},
        }
    )

    # File handler (if log file specified)
    log_file_path = log_file or ScraperConfig.LOG_FILE
    if log_file_path:
        try:
            file_handler = logging.FileHandler(log_file_path, mode='a', encoding='utf-8')
            file_handler.setLevel(logging.DEBUG)
            file_handler.setFormatter(detailed_formatter)
            logger.addHandler(file_handler)
            logger.info(f"Logging to file: {log_file_path}")
        except Exception as e:
            logger.warning(f"Failed to setup file logging: {e}")

    # Prevent propagation to root logger
    logger.propagate = False

    return logger


def get_logger(name: str) -> logging.Logger:
    """
    Get logger instance by name.

    Args:
        name: Logger name

    Returns:
        Logger instance
    """
    return logging.getLogger(name)
