# Sets environment variables, changes directory and activates venv
# for gregor apps dev env
# Used by crontab, validate any changes

export DJANGO_SITE_DIR=/var/www/django/gregor_apps_dev/
export DJANGO_SITE_USER=gregorweb
export DJANGO_SETTINGS_MODULE=config.settings.apps_dev
export DJANGO_WSGI_FILE=config/apps_dev_wsgi.py
export DJANGO_CRONTAB=gregor_apps_dev.cron
export GAC_ENV=gregor_apps_dev

cd $DJANGO_SITE_DIR
. venv/bin/activate
