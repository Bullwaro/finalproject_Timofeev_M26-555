import logging
import os
from logging.handlers import RotatingFileHandler

from valutatrade_hub.infra.settings import SettingsLoader


def get_action_logger():
    settings = SettingsLoader()

    log_file = settings.get("log_file", "logs/actions.log")
    log_level = settings.get("log_level", "INFO").upper()
    log_format = settings.get("log_format", "%(levelname)s %(message)s")

    os.makedirs(os.path.dirname(log_file) or ".", exist_ok=True)

    logger = logging.getLogger("valutatrade_hub.actions")
    logger.setLevel(getattr(logging, log_level, logging.INFO))
    logger.propagate = False

    if not logger.handlers:
        handler = RotatingFileHandler(
            log_file,
            maxBytes=5 * 1024 * 1024,
            backupCount=3,
            encoding="utf-8",
        )
        handler.setFormatter(logging.Formatter(log_format))
        logger.addHandler(handler)

    return logger
