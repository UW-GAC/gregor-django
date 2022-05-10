from .production import *  # noqa
from .production import LOGGING, env  # noqa

# Log to file

LOGGING["handlers"]["console"]["class"] = "logging.FileHandler"
LOGGING["handlers"]["console"]["filename"] = "/var/log/django/gregor-app-dev.log"
