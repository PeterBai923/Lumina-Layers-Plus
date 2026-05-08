# -*- coding: utf-8 -*-
"""
Lumina Studio - Centralized Logging Module

Provides unified logging infrastructure with console and file output.
"""

import os
import sys
import logging
from logging.handlers import RotatingFileHandler
from typing import Optional

_LOG_INITIALIZED = False


class _ConsoleFormatter(logging.Formatter):
    """Format logs as: 14:06:09-813289 INFO     [TAG] message (with ANSI colors)"""

    _COLORS = {
        logging.DEBUG: '\033[36m',       # Cyan
        logging.INFO: '\033[32m',        # Green
        logging.WARNING: '\033[33m',     # Yellow
        logging.ERROR: '\033[31m',       # Red
        logging.CRITICAL: '\033[1;31m',  # Bold Red
    }
    _RESET = '\033[0m'

    def format(self, record):
        ct = self.converter(record.created)
        t = f"{ct.tm_hour:02d}:{ct.tm_min:02d}:{ct.tm_sec:02d}"
        level = f"{record.levelname:>8}"
        tag = record.name
        color = self._COLORS.get(record.levelno, self._RESET)
        return f"{t} {color}{level}{self._RESET} \033[1;37m[{tag}]{self._RESET} {record.getMessage()}"


class _FileFormatter(logging.Formatter):
    """Format logs with full timestamp for archival: 2025-05-08 14:30:01,123 [TAG] INFO     message"""

    def format(self, record):
        ct = self.converter(record.created)
        timestamp = f"{ct.tm_year:04d}-{ct.tm_mon:02d}-{ct.tm_mday:02d} {ct.tm_hour:02d}:{ct.tm_min:02d}:{ct.tm_sec:02d},{int(record.created % 1 * 1000):03d}"
        level = f"{record.levelname:>8}"
        tag = record.name
        return f"{timestamp} [{tag}] {level} {record.getMessage()}"


def get_logger(name: str) -> logging.Logger:
    """
    Get a logger with bracket-tag formatting.

    Args:
        name: The tag name, appears as [NAME] in log output.

    Returns:
        Configured Logger instance.
    """
    logger = logging.getLogger(name)
    if not logger.handlers and not _LOG_INITIALIZED:
        logger.addHandler(logging.NullHandler())
    return logger


def init_logging(
    log_path: Optional[str] = None,
    level: Optional[str] = None,
    max_bytes: int = 10 * 1024 * 1024,
    backup_count: int = 5,
) -> None:
    """
    Initialize logging system. Idempotent - safe to call multiple times.

    Args:
        log_path: Path to log file. If None, no file handler is created.
        level: Log level (DEBUG, INFO, WARNING, ERROR, CRITICAL). Defaults to INFO or LUMINA_LOG_LEVEL env var.
        max_bytes: Max size of each log file before rotation. Default 10MB.
        backup_count: Number of backup files to keep. Default 5.
    """
    global _LOG_INITIALIZED
    if _LOG_INITIALIZED:
        return

    import multiprocessing as mp
    is_main_process = mp.current_process().name == "MainProcess"

    log_level_str = level or os.environ.get("LUMINA_LOG_LEVEL", "INFO")
    log_level = getattr(logging, log_level_str.upper(), logging.INFO)

    root = logging.getLogger()
    root.setLevel(logging.DEBUG)

    # Console handler (stdout)
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setLevel(log_level)
    console_handler.setFormatter(_ConsoleFormatter())
    root.addHandler(console_handler)

    # File handler with rotation (main process only)
    if log_path and is_main_process:
        log_dir = os.path.dirname(log_path)
        if log_dir:
            os.makedirs(log_dir, exist_ok=True)
        file_handler = RotatingFileHandler(
            log_path, maxBytes=max_bytes, backupCount=backup_count
        )
        file_handler.setLevel(logging.DEBUG)
        file_handler.setFormatter(_FileFormatter())
        root.addHandler(file_handler)

    _LOG_INITIALIZED = True


# Module-level convenience functions
def log_debug(msg, *args, **kwargs):
    logging.getLogger().debug(msg, *args, **kwargs)


def log_info(msg, *args, **kwargs):
    logging.getLogger().info(msg, *args, **kwargs)


def log_warning(msg, *args, **kwargs):
    logging.getLogger().warning(msg, *args, **kwargs)


def log_error(msg, *args, **kwargs):
    logging.getLogger().error(msg, *args, **kwargs)


def log_critical(msg, *args, **kwargs):
    logging.getLogger().critical(msg, *args, **kwargs)


def log_exception(exc: Exception, context: str = "", logger: Optional[logging.Logger] = None):
    """
    Log an exception with traceback at ERROR level.

    Args:
        exc: The exception to log.
        context: Optional context message to prepend.
        logger: Optional logger to use. If None, uses root logger.
    """
    target = logger or logging.getLogger()
    msg = f"{context}: {exc}" if context else str(exc)
    target.exception(msg)