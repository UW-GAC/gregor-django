gac-django
==========

GAC Dynamic Oauth Client Proof of Concept!

.. image:: https://img.shields.io/badge/code%20style-black-000000.svg
     :target: https://github.com/ambv/black
     :alt: Black code style

:License: MIT


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

The following details how to deploy this application in dev:
* Create virtualenv (python 3.8 or greater required), recommend python -m venv venv
* Clone repository
* python manage.py migrate
* python manage.py createsuperuser
* 

