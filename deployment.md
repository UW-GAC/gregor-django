# Deployment

## Directory Structure

All django sites are located in /var/www/django

Each django site is self contained within a sub directory eg /var/www/django/site1

## Initial Deployment as shared user gregorweb
- Generate deployment key for shared user
```
$ sudo -u gregorweb ssh-keygen (if not generated)
```
- Capture new pub key (default id_rsa.pub) and add as a read only deployment key at https://github.com/UW-GAC/gregor-django/settings/keys

- Clone repository into site directory
```
$ cd /var/www/django
$ sudo -u gregorweb git clone git@github.com:UW-GAC/gregor-django.git test_site
$ cd test_site
```
- Checkout appropriate deployment branch for your site
```
$ sudo -u gregorweb git checkout deploy
```
- Create a virtualenv
    - Note we use virtualenv instead of python -m venv as only virtualenv creates the activate_this.py file
```
$ sudo -u gregorweb virtualenv venv
```
- Install requirements
```
$ sudo -u gregorweb venv/bin/pip install -r requirements/production.txt
```
- Fixup permissions (skip for shared deployment user)
```
$ XXXXXXXXXXXX chmod -R g+w /var/www/django/test_site
```
- Set up .env file at the root of your site /var/www/django/test_site/.env
    - Required .env settings should be maintained in .env.dist file in github

- Check your installation
```
$ sudo -u gregorweb DJANGO_SETTINGS_MODULE=config.settings.test_site venv/bin/python manage.py check –deploy
System check identified no issues (0 silenced).
```
- Apply migrations
```
$ sudo -u gregorweb DJANGO_SETTINGS_MODULE=config.settings.test_site /venv/bin/python manage.py migrate
```
- Collect static files
```
$ sudo -u gregorweb DJANGO_SETTINGS_MODULE=config.settings.test_site /venv/bin/python manage.py collecstatic
```

- Touch site wsgi file to restart mod wsgi
```
$ sudo -u gregorweb touch config/test_site_wsgi.py
```
> ## How does this work?
> The apache mod_wsgi process is set up to load a particular wsgi file for a particular virtual host, in this case test_site_wsgi.py
>
> The wsgi file contains code to 1) activate the virtual environment using the venv/bin/activate_this.py file and
> 2) set the DJANGO_SETTINGS_MODULE

## Applying Updates
- Put site in maintenance mode (TBD)
- Move to site directory
`$ cd /var/www/django/test_site`
- Update code
```
$ (umask g+w && git pull) # FOR MULTI USER we use the umask temporarily here to be sure we don't cause permissions issues
$ sudo -u gregorweb git pull # FOR SHARED USER
```
- Apply any pip updates
```
$ (umask g+w && venv/bin/pip install -r requirements/production.txt)
$ sudo -u gregorweb venv/bin/pip install -r requirements/production.txt
```
- Apply any django migrations
```
$ venv/bin/python manage.py migrate
$ sudo -u gregorweb DJANGO_SETTINGS_MODULE=config.settings.test_site venv/bin/python manage.py migrate
```
- Check for deployment issues
```
$ DJANGO_SETTINGS_MODULE=config.settings.test_site venv/bin/python manage.py check --deploy
$ sudo -u gregorweb DJANGO_SETTINGS_MODULE=config.settings.test_site venv/bin/python manage.py check --deploy
```
- Restart site by touching wsgi file
```
$ sudo -u gregorweb touch config/test_site_wsgi.py
```
- If an apache restart is needed. You should have priveleges to restart:
```
$ sudo systemctl reload apache2
```
- Take out of maintenance mode (TBD)
