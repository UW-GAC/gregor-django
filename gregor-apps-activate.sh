export DJANGO_SITE_DIR=/var/www/django/gregor_apps/
export DJANGO_SITE_USER=gregorweb
export DJANGO_SETTINGS_MODULE=config.settings.apps
export DJANGO_WSGI_FILE=config/gregor_apps_wsgi.py
export DJANGO_CRONTAB=gregor_apps.cron
export GAC_ENV=gregor_apps

cd $DJANGO_SITE_DIR
. venv/bin/activate
