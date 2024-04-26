import json

import pytest
from django.conf import settings
from django.contrib import messages
from django.contrib.auth import get_user_model
from django.contrib.auth.models import AnonymousUser
from django.contrib.messages.middleware import MessageMiddleware
from django.contrib.sessions.middleware import SessionMiddleware
from django.http import HttpRequest
from django.shortcuts import resolve_url
from django.test import RequestFactory, TestCase
from django.urls import reverse

from gregor_django.users.forms import UserChangeForm, UserLookupForm
from gregor_django.users.tests.factories import UserFactory
from gregor_django.users.views import UserRedirectView, UserUpdateView, user_detail_view

pytestmark = pytest.mark.django_db(transaction=True)

User = get_user_model()


class TestUserUpdateView:
    """
    TODO:
        extracting view initialization code as class-scoped fixture
        would be great if only pytest-django supported non-function-scoped
        fixture db access -- this is a work-in-progress for now:
        https://github.com/pytest-dev/pytest-django/pull/258
    """

    def dummy_get_response(self, request: HttpRequest):  # pragma: no cover
        return None

    def test_get_success_url(self, user: User, rf: RequestFactory):
        view = UserUpdateView()
        request = rf.get("/fake-url/")
        request.user = user

        view.request = request

        assert view.get_success_url() == f"/users/{user.username}/"

    def test_get_object(self, user: User, rf: RequestFactory):
        view = UserUpdateView()
        request = rf.get("/fake-url/")
        request.user = user

        view.request = request

        assert view.get_object() == user

    def test_user_update_view(self, client, user: User, rf: RequestFactory):
        client.force_login(user)
        user_detail_url = reverse("users:update")
        response = client.get(user_detail_url)

        assert response.status_code == 200

    def test_form_valid(self, user: User, rf: RequestFactory):
        view = UserUpdateView()
        request = rf.get("/fake-url/")

        # Add the session/message middleware to the request
        SessionMiddleware(self.dummy_get_response).process_request(request)
        MessageMiddleware(self.dummy_get_response).process_request(request)
        request.user = user

        view.request = request

        # Initialize the form
        form = UserChangeForm()
        form.cleaned_data = []
        view.form_valid(form)

        messages_sent = [m.message for m in messages.get_messages(request)]
        assert messages_sent == ["Information successfully updated"]


class TestUserRedirectView:
    def test_get_redirect_url(self, user: User, rf: RequestFactory):
        view = UserRedirectView()
        request = rf.get("/fake-url")
        request.user = user

        view.request = request

        assert view.get_redirect_url() == f"/users/{user.username}/"


class TestUserDetailView:
    def test_authenticated(self, client, user: User, rf: RequestFactory):
        client.force_login(user)
        user_detail_url = reverse("users:detail", kwargs=dict(username=user.username))
        response = client.get(user_detail_url)

        assert response.status_code == 200

    def test_not_authenticated(self, user: User, rf: RequestFactory):
        request = rf.get("/fake-url/")
        request.user = AnonymousUser()

        response = user_detail_view(request, username=user.username)
        login_url = reverse(settings.LOGIN_URL)

        assert response.status_code == 302
        assert response.url == f"{login_url}?next=/fake-url/"


class UserAutocompleteViewTest(TestCase):
    def setUp(self):
        """Set up test class."""
        self.factory = RequestFactory()
        # Create a user with the correct permissions.
        self.user = User.objects.create_user(username="test", password="test", email="test@example.com")

    def get_url(self, *args):
        """Get the url for the view being tested."""
        return reverse("users:autocomplete", args=args)

    def test_view_redirect_not_logged_in(self):
        "View redirects to login view when user is not logged in."
        # Need a client for redirects.
        response = self.client.get(self.get_url())
        self.assertRedirects(response, resolve_url(settings.LOGIN_URL) + "?next=" + self.get_url())

    def test_status_code_logged_in(self):
        """Returns successful response code."""
        self.client.force_login(self.user)
        response = self.client.get(self.get_url())
        self.assertEqual(response.status_code, 200)

    def test_returns_all_objects(self):
        """Returns all objects when there is no query."""
        UserFactory.create_batch(9)
        self.client.force_login(self.user)
        response = self.client.get(self.get_url())
        returned_ids = [int(x["id"]) for x in json.loads(response.content.decode("utf-8"))["results"]]
        self.assertEqual(len(returned_ids), User.objects.count())
        self.assertEqual(
            sorted(returned_ids),
            sorted(User.objects.values_list("id", flat=True)),
        )

    def test_returns_correct_object_match(self):
        """Returns the correct objects when query matches the name."""
        object = UserFactory.create(
            username="another-user",
            password="another-passwd",
            email="another-user@example.com",
        )
        self.client.force_login(self.user)
        response = self.client.get(self.get_url(), {"q": "another-user"})
        returned_ids = [int(x["id"]) for x in json.loads(response.content.decode("utf-8"))["results"]]

        self.assertEqual(len(returned_ids), 1)
        self.assertEqual(returned_ids[0], object.pk)

    def test_returns_correct_object_starting_with_query(self):
        """Returns the correct objects when query matches the beginning of the name."""
        object = UserFactory.create(
            username="another-user",
            password="another-passwd",
            email="another-user@example.com",
        )
        self.client.force_login(self.user)
        response = self.client.get(self.get_url(), {"q": "another"})
        returned_ids = [int(x["id"]) for x in json.loads(response.content.decode("utf-8"))["results"]]
        self.assertEqual(len(returned_ids), 1)
        self.assertEqual(returned_ids[0], object.pk)

    def test_returns_correct_object_containing_query(self):
        """Returns the correct objects when the name contains the query."""
        object = UserFactory.create(
            username="another-user",
            password="another-passwd",
            email="another-user@example.com",
        )
        self.client.force_login(self.user)
        response = self.client.get(self.get_url(), {"q": "use"})
        returned_ids = [int(x["id"]) for x in json.loads(response.content.decode("utf-8"))["results"]]
        self.assertEqual(len(returned_ids), 1)
        self.assertEqual(returned_ids[0], object.pk)

    def test_returns_correct_object_case_insensitive(self):
        """Returns the correct objects when query matches the beginning of the name."""
        object = UserFactory.create(
            username="another-user",
            password="another-passwd",
            email="another-user@example.com",
        )
        self.client.force_login(self.user)
        response = self.client.get(self.get_url(), {"q": "ANOTHER-USER"})
        returned_ids = [int(x["id"]) for x in json.loads(response.content.decode("utf-8"))["results"]]
        self.assertEqual(len(returned_ids), 1)
        self.assertEqual(returned_ids[0], object.pk)


class UserLookupTest(TestCase):
    """Test for UserLookup view"""

    def setUp(self):
        """Set up test class."""
        self.factory = RequestFactory()
        self.model_factory = UserFactory
        # Create a user.
        self.user = User.objects.create_user(username="test", password="test")

    def get_url(self):
        """Get the url for the view being tested."""
        return reverse("users:lookup")

    def test_view_redirect_not_logged_in(self):
        "View redirects to login view when user is not logged in."
        response = self.client.get(self.get_url())
        self.assertRedirects(response, resolve_url(settings.LOGIN_URL) + "?next=" + self.get_url())

    def test_status_code_with_user_permission(self):
        """Returns successful response code."""
        self.client.force_login(self.user)
        response = self.client.get(self.get_url())
        self.assertEqual(response.status_code, 200)

    def test_form_class(self):
        """The form class is as expected."""
        self.client.force_login(self.user)
        response = self.client.get(self.get_url())
        self.assertIn("form", response.context_data)
        self.assertIsInstance(response.context_data["form"], UserLookupForm)

    def test_redirect_to_the_correct_profile_page(self):
        """The search view correctly redirect to the user profile page"""
        object = UserFactory.create(
            username="user1",
            password="passwd",
            email="user1@example.com",
        )
        self.client.force_login(self.user)
        response = self.client.post(self.get_url(), {"user": object.pk})
        self.assertRedirects(
            response,
            resolve_url(reverse("users:detail", kwargs={"username": object.username})),
        )

    def test_invalid_input(self):
        """Posting invalid data re-renders the form with an error."""
        self.client.force_login(self.user)
        response = self.client.post(
            self.get_url(),
            {"user": -1},
        )
        self.assertEqual(response.status_code, 200)
        form = response.context_data["form"]
        self.assertFalse(form.is_valid())
        self.assertEqual(len(form.errors.keys()), 1)
        self.assertIn("user", form.errors.keys())
        self.assertEqual(len(form.errors["user"]), 1)
        self.assertIn("valid choice", form.errors["user"][0])

    def test_blank_user(self):
        """Posting invalid data does not create an object."""
        self.client.force_login(self.user)
        response = self.client.post(
            self.get_url(),
            {},
        )
        self.assertEqual(response.status_code, 200)
        form = response.context_data["form"]
        self.assertFalse(form.is_valid())
        self.assertEqual(len(form.errors.keys()), 1)
        self.assertIn("user", form.errors.keys())
        self.assertEqual(len(form.errors["user"]), 1)
        self.assertIn("required", form.errors["user"][0])
