from .production import *  # noqa
from .production import LOGGING, SOCIALACCOUNT_PROVIDERS, env  # noqa

# Log to file if we are in mod_wsgi. How to determine if in mod_wsgi
# https://modwsgi.readthedocs.io/en/develop/user-guides/assorted-tips-and-tricks.html#determining-if-running-under-mod-wsgi
# Since log dir is owned by www-data management commands and cron cannot
# log there. So for now, log to console when not running under wsgi

try:
    from mod_wsgi import version  # noqa

    LOGGING["handlers"]["console"]["class"] = "logging.FileHandler"
    LOGGING["handlers"]["console"]["filename"] = "/var/log/django/gregor-apps.log"
except ImportError:
    LOGGING["handlers"]["console"]["class"] = "logging.StreamHandler"

# Update drupal oauth api url for production
DRUPAL_SITE_URL = "https://gregorconsortium.org"
SOCIALACCOUNT_PROVIDERS["drupal_oauth_provider"]["API_URL"] = DRUPAL_SITE_URL

LIVE_SITE = True
