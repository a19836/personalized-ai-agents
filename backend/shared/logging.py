from __future__ import annotations

import logging

from shared.config import get_settings

_LEVELS = {
    "CRITICAL": logging.CRITICAL,
    "ERROR": logging.ERROR,
    "WARNING": logging.WARNING,
    "INFO": logging.INFO,
    "DEBUG": logging.DEBUG,
}


def resolve_log_level() -> int:
    level = get_settings().log_level
    return _LEVELS.get(level, logging.INFO)


def configure_logging() -> None:
    logging.basicConfig(
        level=resolve_log_level(),
        format="%(asctime)s %(levelname)s [%(name)s] %(message)s",
        force=True,
    )
    logging.getLogger().setLevel(resolve_log_level())


def get_logger(name: str) -> logging.Logger:
    return logging.getLogger(name)
