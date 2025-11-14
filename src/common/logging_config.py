"""Centralized logging configuration for all services."""

import logging
import sys
from pathlib import Path
from typing import Optional

from common.config import settings
from common.utils import DateTimeUtils


def setup_logging(
    service_name: str, log_file: Optional[str] = None, log_level: Optional[str] = None
) -> logging.Logger:
    """
    Configure logging for a service with consistent formatting.

    Args:
        service_name: Name of the service (e.g., 'manager', 'downloader', 'translator')
        log_file: Optional log file path. If None, logs only to console
        log_level: Optional log level override. If None, uses settings.log_level

    Returns:
        Configured logger instance
    """
    # Determine log level
    level = log_level or settings.log_level
    log_level_value = getattr(logging, level.upper(), logging.INFO)

    # Create logger
    logger = logging.getLogger(service_name)
    logger.setLevel(log_level_value)

    # Remove existing handlers to avoid duplicates
    logger.handlers.clear()

    # Create formatters
    detailed_formatter = logging.Formatter(
        fmt="%(asctime)s - %(name)s - %(levelname)s - [%(filename)s:%(lineno)d] - %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )

    simple_formatter = logging.Formatter(
        fmt="%(asctime)s - %(levelname)s - %(message)s", datefmt="%Y-%m-%d %H:%M:%S"
    )

    # Console handler (stdout)
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setLevel(log_level_value)
    console_handler.setFormatter(simple_formatter)
    logger.addHandler(console_handler)

    # File handler (if log_file specified)
    if log_file:
        # Create logs directory if it doesn't exist
        log_path = Path(log_file)
        log_path.parent.mkdir(parents=True, exist_ok=True)

        file_handler = logging.FileHandler(log_file, mode="a")
        file_handler.setLevel(log_level_value)
        file_handler.setFormatter(detailed_formatter)
        logger.addHandler(file_handler)

    # Prevent propagation to root logger
    logger.propagate = False

    return logger


def get_log_file_path(service_name: str) -> str:
    """
    Generate a log file path for a service.

    Args:
        service_name: Name of the service

    Returns:
        Path to log file
    """
    date_string = DateTimeUtils.get_date_string_for_log_file()
    return f"./logs/{service_name}_{date_string}.log"


class ServiceLogger:
    """Convenience class for service-specific logging."""

    def __init__(self, service_name: str, enable_file_logging: bool = True):
        """
        Initialize service logger.

        Args:
            service_name: Name of the service
            enable_file_logging: Whether to enable file logging
        """
        self.service_name = service_name
        log_file = get_log_file_path(service_name) if enable_file_logging else None
        self.logger = setup_logging(service_name, log_file)

    def info(self, message: str, **kwargs) -> None:
        """Log info message."""
        self.logger.info(message, **kwargs)

    def debug(self, message: str, **kwargs) -> None:
        """Log debug message."""
        self.logger.debug(message, **kwargs)

    def warning(self, message: str, **kwargs) -> None:
        """Log warning message."""
        self.logger.warning(message, **kwargs)

    def error(self, message: str, **kwargs) -> None:
        """Log error message."""
        self.logger.error(message, **kwargs)

    def critical(self, message: str, **kwargs) -> None:
        """Log critical message."""
        self.logger.critical(message, **kwargs)

    def exception(self, message: str, **kwargs) -> None:
        """Log exception with traceback."""
        self.logger.exception(message, **kwargs)


# Log level constants
LOG_LEVELS = {
    "DEBUG": logging.DEBUG,
    "INFO": logging.INFO,
    "WARNING": logging.WARNING,
    "ERROR": logging.ERROR,
    "CRITICAL": logging.CRITICAL,
}


def configure_third_party_loggers(level: str = "WARNING") -> None:
    """
    Configure logging levels for third-party libraries to reduce noise.

    Args:
        level: Log level for third-party libraries
    """
    third_party_loggers = [
        "aio_pika",
        "aiormq",
        "openai",
        "httpx",
        "httpcore",
        "urllib3",
        "redis",
        "asyncio",
    ]

    log_level = getattr(logging, level.upper(), logging.WARNING)

    for logger_name in third_party_loggers:
        logging.getLogger(logger_name).setLevel(log_level)


def setup_service_logging(
    service_name: str, enable_file_logging: bool = True
) -> ServiceLogger:
    """
    Convenience function to set up logging for a service.

    Args:
        service_name: Name of the service
        enable_file_logging: Whether to enable file logging

    Returns:
        ServiceLogger instance
    """
    # Configure third-party loggers to reduce noise
    configure_third_party_loggers()

    # Create and return service logger
    return ServiceLogger(service_name, enable_file_logging)


# Example usage in services:
# from common.logging_config import setup_service_logging
# logger = setup_service_logging('manager')
# logger.info("Service started")
