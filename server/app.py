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

logging.config.dictConfig(logging_config)


def create_app() -> FastAPI:
    app = FastAPI()
    app.include_router(parents_router, prefix='/api', tags=['ParentsSearch'])
    app.include_router(weather_router, prefix='/api', tags=['WeatherReport'])
    return app
