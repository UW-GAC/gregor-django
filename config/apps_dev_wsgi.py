"""
WSGI config for gac-django project.

This module contains the WSGI application used by Django's development server
and any production WSGI deployments. It should expose a module-level variable
named ``application``. Django's ``runserver`` and ``runfcgi`` commands discover
this application via the ``WSGI_APPLICATION`` setting.

Usually you will have the standard Django WSGI application here, but it also
might make sense to replace the whole Django WSGI application with a custom one
that later delegates to the Django one. For example, you could introduce WSGI
middleware here, or combine a Django application with an application of another
framework.

"""

"""
Activate the virtualenv. Must happen before any imports.
This code assumes it is in a relative directory to the wsgi script.
"""

activate_file = "/var/www/django/apps_dev/venv/bin/activate_this.py"
exec(open(activate_file).read(), {"__file__": activate_file})

import os  # noqa: E402
import sys  # noqa: E402
from pathlib import Path  # noqa: E402

from django.core.wsgi import get_wsgi_application  # noqa: E402

ROOT_DIR = Path(__file__).resolve(strict=True).parent.parent

# This allows easy placement of apps within the interior
# gregor_django directory.

sys.path.append(str(ROOT_DIR / "gregor_django"))
sys.path.append(str(ROOT_DIR))

# Explicitly set the settings module for this wsgi app
os.environ["DJANGO_SETTINGS_MODULE"] = "config.settings.apps_dev"

# Enable dot env file reading by default for this environment
os.environ["DJANGO_READ_DOT_ENV_FILE"] = "True"

# This application object is used by any WSGI server configured to use this
# file. This includes Django's development server, if the WSGI_APPLICATION
# setting points here.
application = get_wsgi_application()
# Apply WSGI middleware here.
# from helloworld.wsgi import HelloWorldApplication
# application = HelloWorldApplication(application)
