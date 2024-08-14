import sys

from .production import *  # noqa
from .production import LOGGING, env  # noqa

# Log to file if we are in mod_wsgi. How to determine if in mod_wsgi
# https://modwsgi.readthedocs.io/en/develop/user-guides/assorted-tips-and-tricks.html#determining-if-running-under-mod-wsgi

try:
    from mod_wsgi import version  # noqa

    LOGGING["handlers"]["console"]["class"] = "logging.FileHandler"
    LOGGING["handlers"]["console"]["filename"] = "/var/log/django/gregor-app-dev.log"
except ImportError:
    LOGGING["handlers"]["console"]["class"] = "logging.StreamHandler"
    # Send stream logging to stdout so we can redirect exceptions to email
    LOGGING["handlers"]["console"]["stream"] = sys.stdout
