from __future__ import annotations

import logging.config

from fastapi import FastAPI

from config.settings import app_settings
from server.api.parents import router as parents_router
from server.api.weather import router as weather_router

logging_config = {
    "version": 1,
    "disable_existing_loggers": False,
    "handlers": {
        "console": {
            "class": "logging.StreamHandler",
            "level": app_settings.log_level,
        },
    },
    "root": {
        "handlers": ["console"],
        "level": app_settings.log_level,
    },
}


class AppBuilder:
    def __init__(self):
        self._app = FastAPI()
        self._api_prefix = "/api"
        self._log_to_file = False
        self._log_file_path = None
        self._file_log_level = None

    def set_api_prefix(self, prefix: str) -> AppBuilder:
        self._api_prefix = prefix
        return self

    def enable_file_logging(self, filename: str, log_level: str) -> AppBuilder:
        self._log_to_file = True
        self._log_file_path = filename
        self._file_log_level = log_level
        return self

    def _configure_file_logging(self):
        file_handler = {
            "class": "logging.FileHandler",
            "level": self._file_log_level,
            "filename": self._log_file_path,
        }
        logging_config['handlers']['file'] = file_handler
        logging_config['root']['handlers'].append('file')
        logging.config.dictConfig(logging_config)

    def build(self) -> FastAPI:
        if self._log_to_file:
            self._configure_file_logging()
        self._app.include_router(
            parents_router, prefix=self._api_prefix, tags=['ParentsSearch']
        )
        self._app.include_router(
            weather_router, prefix=self._api_prefix, tags=['WeatherReport']
        )
        return self._app


def create_app() -> FastAPI:
    logging.config.dictConfig(logging_config)
    builder = AppBuilder().set_api_prefix('/api/v1')
    if app_settings.enable_file_logging:
        builder.enable_file_logging(
            filename=app_settings.log_file_path,
            log_level=app_settings.log_level,
        )
    app = builder.build()
    return app
