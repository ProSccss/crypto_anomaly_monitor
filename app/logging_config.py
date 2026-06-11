import logging
from logging.config import dictConfig

from pythonjsonlogger.json import JsonFormatter


def configure_logging(level: str) -> None:
    dictConfig(
        {
            "version": 1,
            "disable_existing_loggers": False,
            "formatters": {
                "json": {
                    "()": JsonFormatter,
                    "format": "%(asctime)s %(levelname)s %(name)s %(message)s",
                }
            },
            "handlers": {"default": {"class": "logging.StreamHandler", "formatter": "json"}},
            "root": {"handlers": ["default"], "level": level.upper()},
        }
    )
    logging.getLogger("httpx").setLevel(logging.WARNING)

