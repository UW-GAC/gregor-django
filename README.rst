gregor-django
==========

GREGoR Dynamic Oauth Client Proof of Concept

.. image:: https://img.shields.io/badge/code%20style-black-000000.svg
     :target: https://github.com/ambv/black
     :alt: Black code style
.. image:: https://img.shields.io/badge/License-MIT-blue.svg
       :target: https://lbesson.mit-license.org/
.. image:: https://img.shields.io/badge/built%20with-Cookiecutter%20Django-ff69b4.svg?logo=cookiecutter
     :target: https://github.com/pydanny/cookiecutter-django/
     :alt: Built with Cookiecutter Django

Basic Commands
--------------

Setting Up Your Users
^^^^^^^^^^^^^^^^^^^^^

* To create a local **normal user account**, just go to Sign Up and fill out the form. Once you submit it, you'll see a "Verify Your E-mail Address" page. Go to your console to see a simulated email verification message. Copy the link into your browser. Now the user's email should be verified and ready to go.
* To create a oauth **normal user account**, go to Sign In, select oauth provider and sign in. This will create a local user and you will see a "Verify Your E-Mail Address" page.
* To create an **superuser account**, use this command::

    $ python manage.py createsuperuser

For convenience, you can keep your normal user logged in on Chrome and your superuser logged in on Firefox (or similar), so that you can see how the site behaves for both kinds of users.

Type checks
^^^^^^^^^^^

Running type checks with mypy:

::

  $ mypy gregor_django

Test coverage
^^^^^^^^^^^^^

To run the tests, check your test coverage, and generate an HTML coverage report::

    $ coverage run -m pytest
    $ coverage html
    $ open htmlcov/index.html (git bash on windows use start instead of open)

Running tests with py.test
~~~~~~~~~~~~~~~~~~~~~~~~~~

::

  $ pytest

Deployment
----------

The following details how to deploy this application in dev to try third party oauth::


* Create virtualenv (python 3.8 or greater required), recommend python -m venv venv
* Clone repository
* python -m pip install -r requirements/local.txt
* python manage.py migrate
* python manage.py createsuperuser
* python manage.py runserver_plus
* visit <site url>/admin - login as super user
* add 'Social Application' enter github client id and secret, select site_id 1
* sign out as super user
* visit <site_url>, select 'Sign In'
* choose sign in via github, follow instructions to creat oauth account

Want to contribute
----------

* pre-commit install (add git pre-commit hooks for black, flake8, etc)
* git checkout -b <feature_branch_name> (Create and switch to feature branch)
* make changes
* tests: pytest
* test coverage: (see above)
* type checks: mypy gregor_django
* manually run pre-commit if you did not install or if you just want to check
* git add your changes
* git commit your changes
* git push origin <feature_branch_name>
* review or request review of changes in github
* submit push request
