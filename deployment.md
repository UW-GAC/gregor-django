# Deployment

## Directory Structure

All django sites are located in /var/www/django

Each django site is self contained within a sub directory eg /var/www/django/site1

## Initial Deployment

- Clone repository into site directory
```
$ cd /var/www/django
$ git clone git@github.com:UW-GAC/gregor-django.git test_site
$ cd test_site
```
- Checkout appropriate deployment branch for your site
```
$ git checkout deploy
```
- Create a virtualenv
    - Note we use virtualenv instead of python -m venv as only virtualenv creates the activate_this.py file
```
$ virtualenv venv
```
- Install requirements
```
$ venv/bin/pip install -r requirements/production.txt
```
- Fixup permissions
```
$ chmod -R g+w /var/www/django/test_site
```
- Set up .env file at the root of your site /var/www/django/test_site/.env
    - Required .env settings should be maintained in .env.dist file in github

- Check your installation
```
$ DJANGO_SETTINGS_MODULE=config.settings.production venv/bin/python manage.py check –deploy
System check identified no issues (0 silenced).
```
- Apply migrations
```
$ DJANGO_SETTINGS_MODULE=config.settings.production /venv/bin/python manage.py migrate
```
- Touch site wsgi file to restart mod wsgi
```
$ touch config/test_site_wsgi.py
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
$ (umask g+w && git pull) # we use the umask temporarily here to be sure we don't cause permissions issues
```
- Apply any pip updates
```
$ (umask g+w && venv/bin/pip install -r requirements/production.txt)
```
- Apply any django migrations
```
$ venv/bin/python manage.py migrate
```
- Check for deployment issues
```
$ DJANGO_SETTINGS_MODULE=config.settings.production venv/bin/python manage.py check --deploy
```
- Restart site by touching wsgi file
```
$ touch config/test_site_wsgi.py
```
- Take out of maintenance mode (TBD)
