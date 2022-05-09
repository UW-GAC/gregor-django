from .production import *  # noqa
from .production import env  # noqa

# apps_dev specific config

LOGGING = {
    "version": 1,
    "disable_existing_loggers": False,
    "formatters": {
        "verbose": {
            "format": "%(levelname)s %(asctime)s %(module)s %(process)d %(thread)d %(message)s"
        },
        "simple": {"format": "%(levelname)s %(message)s"},
    },
    "handlers": {
        "console": {
            "level": "DEBUG",
            "class": "logging.FileHandler",
            "filename": "/var/log/django/gregor-app-dev.log",  # noqa F405
            "formatter": "verbose",
        },
    },
    "loggers": {
        "": {
            "handlers": ["console"],
            "level": env("DJANGO_LOG_LEVEL", default="DEBUG"),
        },
    },
}
