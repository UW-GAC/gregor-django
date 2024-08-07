import json
from datetime import date, timedelta
from unittest import skip

import responses
from anvil_consortium_manager import models as acm_models
from anvil_consortium_manager.models import AnVILProjectManagerAccess
from anvil_consortium_manager.tests import factories as acm_factories
from anvil_consortium_manager.tests.utils import AnVILAPIMockTestMixin
from constance.test import override_config
from django.conf import settings
from django.contrib.auth import get_user_model
from django.contrib.auth.models import Permission
from django.contrib.messages import get_messages
from django.core.exceptions import PermissionDenied
from django.http.response import Http404
from django.shortcuts import resolve_url
from django.test import RequestFactory, TestCase
from django.urls import reverse

from gregor_django.users.tables import UserTable
from gregor_django.users.tests.factories import UserFactory

from .. import forms, models, tables, views
from . import factories

# from .utils import AnVILAPIMockTestMixin

User = get_user_model()


class HomeTest(TestCase):
    """Tests for the home page related to anvil_consortium_manager content."""

    def get_url(self, *args):
        """Get the url for the view being tested."""
        return reverse("home", args=args)

    def test_acm_link_without_permission(self):
        """ACM link does not show up if you do not have view permission."""
        user = User.objects.create_user(username="test-none", password="test-none")
        self.client.force_login(user)
        response = self.client.get(self.get_url())
        self.assertNotIn("AnVIL Consortium Manager", response.rendered_content)
        self.assertNotIn(reverse("anvil_consortium_manager:index"), response.rendered_content)

    def test_acm_link_with_view_permission(self):
        """ACM link shows up if you have view permission."""
        user = User.objects.create_user(username="test-none", password="test-none")
        user.user_permissions.add(
            Permission.objects.get(codename=acm_models.AnVILProjectManagerAccess.STAFF_VIEW_PERMISSION_CODENAME)
        )
        self.client.force_login(user)
        response = self.client.get(self.get_url())
        self.assertIn("AnVIL Consortium Manager", response.rendered_content)
        self.assertIn(reverse("anvil_consortium_manager:index"), response.rendered_content)

    def test_acm_link_with_view_and_edit_permission(self):
        """ACM link shows up if you have view and edit permission."""
        user = User.objects.create_user(username="test-none", password="test-none")
        user.user_permissions.add(
            Permission.objects.get(codename=acm_models.AnVILProjectManagerAccess.STAFF_VIEW_PERMISSION_CODENAME)
        )
        user.user_permissions.add(
            Permission.objects.get(codename=acm_models.AnVILProjectManagerAccess.STAFF_EDIT_PERMISSION_CODENAME)
        )
        self.client.force_login(user)
        response = self.client.get(self.get_url())
        self.assertIn("AnVIL Consortium Manager", response.rendered_content)
        self.assertIn(reverse("anvil_consortium_manager:index"), response.rendered_content)

    def test_acm_link_with_edit_but_not_view_permission(self):
        """ACM link does not show up if you only have edit permission.

        This is something that shouldn't happen but could if admin only gave EDIT but not VIEW permission."""
        user = User.objects.create_user(username="test-none", password="test-none")
        user.user_permissions.add(
            Permission.objects.get(codename=acm_models.AnVILProjectManagerAccess.STAFF_EDIT_PERMISSION_CODENAME)
        )
        self.client.force_login(user)
        response = self.client.get(self.get_url())
        self.assertNotIn("AnVIL Consortium Manager", response.rendered_content)
        self.assertNotIn(reverse("anvil_consortium_manager:index"), response.rendered_content)

    def test_site_announcement_no_text(self):
        user = User.objects.create_user(username="test-none", password="test-none")
        self.client.force_login(user)
        response = self.client.get(self.get_url())
        self.assertNotContains(response, """id="alert-announcement""")

    @override_config(ANNOUNCEMENT_TEXT="This is a test announcement")
    def test_site_announcement_text(self):
        user = User.objects.create_user(username="test-none", password="test-none")
        self.client.force_login(user)
        response = self.client.get(self.get_url())
        self.assertContains(response, """id="alert-announcement""")
        self.assertContains(response, "This is a test announcement")

    @override_config(ANNOUNCEMENT_TEXT="This is a test announcement")
    def test_site_announcement_text_unauthenticated_user(self):
        response = self.client.get(self.get_url(), follow=True)
        self.assertContains(response, """id="alert-announcement""")
        self.assertContains(response, "This is a test announcement")


class ConsentGroupDetailTest(TestCase):
    """Tests for the ConsentGroupDetail view."""

    def setUp(self):
        """Set up test class."""
        self.factory = RequestFactory()
        self.model_factory = factories.ConsentGroupFactory
        # Create a user with both view and edit permission.
        self.user = User.objects.create_user(username="test", password="test")
        self.user.user_permissions.add(
            Permission.objects.get(codename=acm_models.AnVILProjectManagerAccess.STAFF_VIEW_PERMISSION_CODENAME)
        )

    def get_url(self, *args):
        """Get the url for the view being tested."""
        return reverse("gregor_anvil:consent_groups:detail", args=args)

    def get_view(self):
        """Return the view being tested."""
        return views.ConsentGroupDetail.as_view()

    def test_view_redirect_not_logged_in(self):
        "View redirects to login view when user is not logged in."
        # Need a client for redirects.
        response = self.client.get(self.get_url(1))
        self.assertRedirects(response, resolve_url(settings.LOGIN_URL) + "?next=" + self.get_url(1))

    def test_status_code_with_user_permission(self):
        """Returns successful response code."""
        obj = self.model_factory.create()
        self.client.force_login(self.user)
        response = self.client.get(self.get_url(obj.pk))
        self.assertEqual(response.status_code, 200)

    def test_access_without_user_permission(self):
        """Raises permission denied if user has no permissions."""
        user_no_perms = User.objects.create_user(username="test-none", password="test-none")
        request = self.factory.get(self.get_url(1))
        request.user = user_no_perms
        with self.assertRaises(PermissionDenied):
            self.get_view()(request)

    def test_view_status_code_with_invalid_pk(self):
        """Raises a 404 error with an invalid object pk."""
        obj = self.model_factory.create()
        request = self.factory.get(self.get_url(obj.pk + 1))
        request.user = self.user
        with self.assertRaises(Http404):
            self.get_view()(request, pk=obj.pk + 1)


class ConsentGroupListTest(TestCase):
    """Tests for the ConsentGroupList view."""

    def setUp(self):
        """Set up test class."""
        self.factory = RequestFactory()
        self.model_factory = factories.ConsentGroupFactory
        # Create a user with both view and edit permission.
        self.user = User.objects.create_user(username="test", password="test")
        self.user.user_permissions.add(
            Permission.objects.get(codename=acm_models.AnVILProjectManagerAccess.STAFF_VIEW_PERMISSION_CODENAME)
        )

    def get_url(self):
        """Get the url for the view being tested."""
        return reverse("gregor_anvil:consent_groups:list")

    def get_view(self):
        """Return the view being tested."""
        return views.ConsentGroupList.as_view()

    def test_view_redirect_not_logged_in(self):
        "View redirects to login view when user is not logged in."
        # Need a client for redirects.
        response = self.client.get(self.get_url())
        self.assertRedirects(response, resolve_url(settings.LOGIN_URL) + "?next=" + self.get_url())

    def test_status_code_with_user_permission(self):
        """Returns successful response code."""
        self.client.force_login(self.user)
        response = self.client.get(self.get_url())
        self.assertEqual(response.status_code, 200)

    def test_access_without_user_permission(self):
        """Raises permission denied if user has no permissions."""
        user_no_perms = User.objects.create_user(username="test-none", password="test-none")
        request = self.factory.get(self.get_url())
        request.user = user_no_perms
        with self.assertRaises(PermissionDenied):
            self.get_view()(request)

    def test_view_has_correct_table_class(self):
        self.client.force_login(self.user)
        response = self.client.get(self.get_url())
        self.assertIn("table", response.context_data)
        self.assertIsInstance(response.context_data["table"], tables.ConsentGroupTable)

    def test_view_with_no_objects(self):
        self.client.force_login(self.user)
        response = self.client.get(self.get_url())
        self.assertEqual(response.status_code, 200)
        self.assertIn("table", response.context_data)
        self.assertEqual(len(response.context_data["table"].rows), 0)

    def test_view_with_one_object(self):
        self.model_factory.create()
        self.client.force_login(self.user)
        response = self.client.get(self.get_url())
        self.assertEqual(response.status_code, 200)
        self.assertIn("table", response.context_data)
        self.assertEqual(len(response.context_data["table"].rows), 1)

    def test_view_with_two_objects(self):
        self.model_factory.create_batch(2)
        self.client.force_login(self.user)
        response = self.client.get(self.get_url())
        self.assertEqual(response.status_code, 200)
        self.assertIn("table", response.context_data)
        self.assertEqual(len(response.context_data["table"].rows), 2)


class ResearchCenterDetailTest(TestCase):
    """Tests for the ResearchCenterDetail view."""

    def setUp(self):
        """Set up test class."""
        self.factory = RequestFactory()
        self.model_factory = factories.ResearchCenterFactory
        # Create a user with both view and edit permission.
        self.user = User.objects.create_user(username="test", password="test")
        self.user.user_permissions.add(
            Permission.objects.get(codename=acm_models.AnVILProjectManagerAccess.STAFF_VIEW_PERMISSION_CODENAME)
        )

    def get_url(self, *args):
        """Get the url for the view being tested."""
        return reverse("gregor_anvil:research_centers:detail", args=args)

    def get_view(self):
        """Return the view being tested."""
        return views.ResearchCenterDetail.as_view()

    def test_view_redirect_not_logged_in(self):
        "View redirects to login view when user is not logged in."
        # Need a client for redirects.
        response = self.client.get(self.get_url(1))
        self.assertRedirects(response, resolve_url(settings.LOGIN_URL) + "?next=" + self.get_url(1))

    def test_status_code_with_user_permission(self):
        """Returns successful response code."""
        obj = self.model_factory.create()
        self.client.force_login(self.user)
        response = self.client.get(self.get_url(obj.pk))
        self.assertEqual(response.status_code, 200)

    def test_access_without_user_permission(self):
        """Raises permission denied if user has no permissions."""
        user_no_perms = User.objects.create_user(username="test-none", password="test-none")
        request = self.factory.get(self.get_url(1))
        request.user = user_no_perms
        with self.assertRaises(PermissionDenied):
            self.get_view()(request)

    def test_view_status_code_with_invalid_pk(self):
        """Raises a 404 error with an invalid object pk."""
        obj = self.model_factory.create()
        request = self.factory.get(self.get_url(obj.pk + 1))
        request.user = self.user
        with self.assertRaises(Http404):
            self.get_view()(request, pk=obj.pk + 1)

    def test_site_user_table(self):
        """Contains a table of site users with the correct users."""
        obj = self.model_factory.create()
        site_user = UserFactory.create()
        site_user.research_centers.set([obj])
        non_site_user = UserFactory.create()

        self.client.force_login(self.user)
        response = self.client.get(self.get_url(obj.pk))
        table = response.context_data["tables"][0]
        self.assertEqual(len(table.rows), 1)

        self.assertIn(site_user, table.data)
        self.assertNotIn(non_site_user, table.data)

    def test_site_user_table_does_not_include_inactive_users(self):
        """Site user table does not include inactive users."""
        obj = self.model_factory.create()
        inactive_site_user = UserFactory.create()
        inactive_site_user.research_centers.set([obj])
        inactive_site_user.is_active = False
        inactive_site_user.save()
        self.client.force_login(self.user)
        response = self.client.get(self.get_url(obj.pk))
        table = response.context_data["tables"][0]
        self.assertEqual(len(table.rows), 0)
        self.assertNotIn(inactive_site_user, table.data)

    def test_link_to_member_group(self):
        """Response includes a link to the members group if it exists."""
        member_group = acm_factories.ManagedGroupFactory.create()
        obj = self.model_factory.create(member_group=member_group)
        self.client.force_login(self.user)
        response = self.client.get(self.get_url(obj.pk))
        self.assertContains(response, member_group.get_absolute_url())

    def test_link_to_uploader_group(self):
        """Response includes a link to the uploader group if it exists."""
        uploader_group = acm_factories.ManagedGroupFactory.create()
        obj = self.model_factory.create(uploader_group=uploader_group)
        self.client.force_login(self.user)
        response = self.client.get(self.get_url(obj.pk))
        self.assertContains(response, uploader_group.get_absolute_url())

    def test_table_classes(self):
        """Table classes are correct."""
        obj = self.model_factory.create()
        self.client.force_login(self.user)
        response = self.client.get(self.get_url(obj.pk))
        self.assertIn("tables", response.context_data)
        self.assertEqual(len(response.context_data["tables"]), 3)
        self.assertIsInstance(response.context_data["tables"][0], UserTable)
        self.assertEqual(len(response.context_data["tables"][0].data), 0)
        self.assertIsInstance(response.context_data["tables"][1], tables.AccountTable)
        self.assertEqual(len(response.context_data["tables"][1].data), 0)
        self.assertIsInstance(response.context_data["tables"][2], tables.AccountTable)
        self.assertEqual(len(response.context_data["tables"][2].data), 0)

    def test_rc_member_table(self):
        member_group = acm_factories.ManagedGroupFactory.create()
        obj = self.model_factory.create(member_group=member_group)
        account = acm_factories.AccountFactory.create(verified=True)
        acm_factories.GroupAccountMembershipFactory.create(account=account, group=member_group)
        other_account = acm_factories.AccountFactory.create(verified=True)
        self.client.force_login(self.user)
        response = self.client.get(self.get_url(obj.pk))
        table = response.context_data["tables"][1]
        self.assertEqual(len(table.rows), 1)
        self.assertIn(account, table.data)
        self.assertNotIn(other_account, table.data)

    def test_member_table_group_not_set(self):
        obj = self.model_factory.create()
        acm_factories.AccountFactory.create(verified=True)
        self.client.force_login(self.user)
        response = self.client.get(self.get_url(obj.pk))
        table = response.context_data["tables"][1]
        self.assertEqual(len(table.rows), 0)

    def test_rc_uploader_table(self):
        uploader_group = acm_factories.ManagedGroupFactory.create()
        obj = self.model_factory.create(uploader_group=uploader_group)
        account = acm_factories.AccountFactory.create(verified=True)
        acm_factories.GroupAccountMembershipFactory.create(account=account, group=uploader_group)
        other_account = acm_factories.AccountFactory.create(verified=True)
        self.client.force_login(self.user)
        response = self.client.get(self.get_url(obj.pk))
        table = response.context_data["tables"][2]
        self.assertEqual(len(table.rows), 1)
        self.assertIn(account, table.data)
        self.assertNotIn(other_account, table.data)

    def test_upload_table_group_not_set(self):
        obj = self.model_factory.create()
        acm_factories.AccountFactory.create(verified=True)
        self.client.force_login(self.user)
        response = self.client.get(self.get_url(obj.pk))
        table = response.context_data["tables"][2]
        self.assertEqual(len(table.rows), 0)


class ResearchCenterListTest(TestCase):
    """Tests for the ResearchCenterList view."""

    def setUp(self):
        """Set up test class."""
        self.factory = RequestFactory()
        self.model_factory = factories.ResearchCenterFactory
        # Create a user with both view and edit permission.
        self.user = User.objects.create_user(username="test", password="test")
        self.user.user_permissions.add(
            Permission.objects.get(codename=acm_models.AnVILProjectManagerAccess.STAFF_VIEW_PERMISSION_CODENAME)
        )

    def get_url(self):
        """Get the url for the view being tested."""
        return reverse("gregor_anvil:research_centers:list")

    def get_view(self):
        """Return the view being tested."""
        return views.ResearchCenterList.as_view()

    def test_view_redirect_not_logged_in(self):
        "View redirects to login view when user is not logged in."
        # Need a client for redirects.
        response = self.client.get(self.get_url())
        self.assertRedirects(response, resolve_url(settings.LOGIN_URL) + "?next=" + self.get_url())

    def test_status_code_with_user_permission(self):
        """Returns successful response code."""
        self.client.force_login(self.user)
        response = self.client.get(self.get_url())
        self.assertEqual(response.status_code, 200)

    def test_access_without_user_permission(self):
        """Raises permission denied if user has no permissions."""
        user_no_perms = User.objects.create_user(username="test-none", password="test-none")
        request = self.factory.get(self.get_url())
        request.user = user_no_perms
        with self.assertRaises(PermissionDenied):
            self.get_view()(request)

    def test_view_has_correct_table_class(self):
        """View has the correct table class in the context."""
        self.client.force_login(self.user)
        response = self.client.get(self.get_url())
        self.assertIn("table", response.context_data)
        self.assertIsInstance(response.context_data["table"], tables.ResearchCenterTable)

    def test_view_with_no_objects(self):
        """The table has no rows when there are no ResearchCenter objects."""
        self.client.force_login(self.user)
        response = self.client.get(self.get_url())
        self.assertEqual(response.status_code, 200)
        self.assertIn("table", response.context_data)
        self.assertEqual(len(response.context_data["table"].rows), 0)

    def test_view_with_one_object(self):
        """The table has one row when there is one ResearchCenter object."""
        self.model_factory.create()
        self.client.force_login(self.user)
        response = self.client.get(self.get_url())
        self.assertEqual(response.status_code, 200)
        self.assertIn("table", response.context_data)
        self.assertEqual(len(response.context_data["table"].rows), 1)

    def test_view_with_two_objects(self):
        """The table has two rows when there are two ResearchCenter objects."""
        self.model_factory.create_batch(2)
        self.client.force_login(self.user)
        response = self.client.get(self.get_url())
        self.assertEqual(response.status_code, 200)
        self.assertIn("table", response.context_data)
        self.assertEqual(len(response.context_data["table"].rows), 2)


class PartnerGroupDetailTest(TestCase):
    """Tests for the PartnerGroupDetail view."""

    def setUp(self):
        """Set up test class."""
        self.factory = RequestFactory()
        self.model_factory = factories.PartnerGroupFactory
        # Create a user with both view and edit permission.
        self.user = User.objects.create_user(username="test", password="test")
        self.user.user_permissions.add(
            Permission.objects.get(codename=acm_models.AnVILProjectManagerAccess.STAFF_VIEW_PERMISSION_CODENAME)
        )

    def get_url(self, *args):
        """Get the url for the view being tested."""
        return reverse("gregor_anvil:partner_groups:detail", args=args)

    def get_view(self):
        """Return the view being tested."""
        return views.PartnerGroupDetail.as_view()

    def test_view_redirect_not_logged_in(self):
        "View redirects to login view when user is not logged in."
        # Need a client for redirects.
        response = self.client.get(self.get_url(1))
        self.assertRedirects(response, resolve_url(settings.LOGIN_URL) + "?next=" + self.get_url(1))

    def test_status_code_with_user_permission(self):
        """Returns successful response code."""
        obj = self.model_factory.create()
        self.client.force_login(self.user)
        response = self.client.get(self.get_url(obj.pk))
        self.assertEqual(response.status_code, 200)

    def test_access_without_user_permission(self):
        """Raises permission denied if user has no permissions."""
        user_no_perms = User.objects.create_user(username="test-none", password="test-none")
        request = self.factory.get(self.get_url(1))
        request.user = user_no_perms
        with self.assertRaises(PermissionDenied):
            self.get_view()(request)

    def test_view_status_code_with_invalid_pk(self):
        """Raises a 404 error with an invalid object pk."""
        obj = self.model_factory.create()
        request = self.factory.get(self.get_url(obj.pk + 1))
        request.user = self.user
        with self.assertRaises(Http404):
            self.get_view()(request, pk=obj.pk + 1)

    def test_site_user_table(self):
        """Contains a table of site users with the correct users."""
        obj = self.model_factory.create()
        pg_user = UserFactory.create()
        pg_user.partner_groups.set([obj])
        non_pg_user = UserFactory.create()

        self.client.force_login(self.user)
        response = self.client.get(self.get_url(obj.pk))
        self.assertIn("tables", response.context_data)
        table = response.context_data["tables"][0]
        self.assertEqual(len(table.rows), 1)

        self.assertIn(pg_user, table.data)
        self.assertNotIn(non_pg_user, table.data)

    def test_site_user_table_does_not_include_inactive_users(self):
        """Site user table does not include inactive users."""
        obj = self.model_factory.create()
        inactive_site_user = UserFactory.create()
        inactive_site_user.partner_groups.set([obj])
        inactive_site_user.is_active = False
        inactive_site_user.save()
        self.client.force_login(self.user)
        response = self.client.get(self.get_url(obj.pk))
        table = response.context_data["tables"][0]
        self.assertEqual(len(table.rows), 0)
        self.assertNotIn(inactive_site_user, table.data)

    def test_table_classes(self):
        """Table classes are correct."""
        obj = self.model_factory.create()
        self.client.force_login(self.user)
        response = self.client.get(self.get_url(obj.pk))
        self.assertIn("tables", response.context_data)
        self.assertEqual(len(response.context_data["tables"]), 3)
        self.assertIsInstance(response.context_data["tables"][0], UserTable)
        self.assertIsInstance(response.context_data["tables"][1], tables.AccountTable)
        self.assertIsInstance(response.context_data["tables"][2], tables.AccountTable)

    def test_member_table(self):
        member_group = acm_factories.ManagedGroupFactory.create()
        obj = self.model_factory.create(member_group=member_group)
        account = acm_factories.AccountFactory.create(verified=True)
        acm_factories.GroupAccountMembershipFactory.create(account=account, group=member_group)
        other_account = acm_factories.AccountFactory.create(verified=True)
        self.client.force_login(self.user)
        response = self.client.get(self.get_url(obj.pk))
        table = response.context_data["tables"][1]
        self.assertEqual(len(table.rows), 1)
        self.assertIn(account, table.data)
        self.assertNotIn(other_account, table.data)

    def test_member_table_group_not_set(self):
        obj = self.model_factory.create()
        acm_factories.AccountFactory.create(verified=True)
        self.client.force_login(self.user)
        response = self.client.get(self.get_url(obj.pk))
        table = response.context_data["tables"][1]
        self.assertEqual(len(table.rows), 0)

    def test_uploader_table(self):
        uploader_group = acm_factories.ManagedGroupFactory.create()
        obj = self.model_factory.create(uploader_group=uploader_group)
        account = acm_factories.AccountFactory.create(verified=True)
        acm_factories.GroupAccountMembershipFactory.create(account=account, group=uploader_group)
        other_account = acm_factories.AccountFactory.create(verified=True)
        self.client.force_login(self.user)
        response = self.client.get(self.get_url(obj.pk))
        table = response.context_data["tables"][2]
        self.assertEqual(len(table.rows), 1)
        self.assertIn(account, table.data)
        self.assertNotIn(other_account, table.data)

    def test_upload_table_group_not_set(self):
        obj = self.model_factory.create()
        acm_factories.AccountFactory.create(verified=True)
        self.client.force_login(self.user)
        response = self.client.get(self.get_url(obj.pk))
        table = response.context_data["tables"][2]
        self.assertEqual(len(table.rows), 0)


class PartnerGroupListTest(TestCase):
    """Tests for the ResearchCenterList view."""

    def setUp(self):
        """Set up test class."""
        self.factory = RequestFactory()
        self.model_factory = factories.PartnerGroupFactory
        # Create a user with both view and edit permission.
        self.user = User.objects.create_user(username="test", password="test")
        self.user.user_permissions.add(
            Permission.objects.get(codename=acm_models.AnVILProjectManagerAccess.STAFF_VIEW_PERMISSION_CODENAME)
        )

    def get_url(self):
        """Get the url for the view being tested."""
        return reverse("gregor_anvil:partner_groups:list")

    def get_view(self):
        """Return the view being tested."""
        return views.PartnerGroupList.as_view()

    def test_view_redirect_not_logged_in(self):
        "View redirects to login view when user is not logged in."
        # Need a client for redirects.
        response = self.client.get(self.get_url())
        self.assertRedirects(response, resolve_url(settings.LOGIN_URL) + "?next=" + self.get_url())

    def test_status_code_with_user_permission(self):
        """Returns successful response code."""
        self.client.force_login(self.user)
        response = self.client.get(self.get_url())
        self.assertEqual(response.status_code, 200)

    def test_access_without_user_permission(self):
        """Raises permission denied if user has no permissions."""
        user_no_perms = User.objects.create_user(username="test-none", password="test-none")
        request = self.factory.get(self.get_url())
        request.user = user_no_perms
        with self.assertRaises(PermissionDenied):
            self.get_view()(request)

    def test_view_has_correct_table_class(self):
        """View has the correct table class in the context."""
        self.client.force_login(self.user)
        response = self.client.get(self.get_url())
        self.assertIn("table", response.context_data)
        self.assertIsInstance(response.context_data["table"], tables.PartnerGroupTable)

    def test_view_with_no_objects(self):
        """The table has no rows when there are no ResearchCenter objects."""
        self.client.force_login(self.user)
        response = self.client.get(self.get_url())
        self.assertEqual(response.status_code, 200)
        self.assertIn("table", response.context_data)
        self.assertEqual(len(response.context_data["table"].rows), 0)

    def test_view_with_one_object(self):
        """The table has one row when there is one ResearchCenter object."""
        self.model_factory.create()
        self.client.force_login(self.user)
        response = self.client.get(self.get_url())
        self.assertEqual(response.status_code, 200)
        self.assertIn("table", response.context_data)
        self.assertEqual(len(response.context_data["table"].rows), 1)

    def test_view_with_two_objects(self):
        """The table has two rows when there are two ResearchCenter objects."""
        self.model_factory.create_batch(2)
        self.client.force_login(self.user)
        response = self.client.get(self.get_url())
        self.assertEqual(response.status_code, 200)
        self.assertIn("table", response.context_data)
        self.assertEqual(len(response.context_data["table"].rows), 2)


class UploadCycleCreateTest(TestCase):
    def setUp(self):
        """Set up test class."""
        self.factory = RequestFactory()
        # Create a user with both view and edit permissions.
        self.user = User.objects.create_user(username="test", password="test")
        self.user.user_permissions.add(
            Permission.objects.get(codename=AnVILProjectManagerAccess.STAFF_VIEW_PERMISSION_CODENAME)
        )
        self.user.user_permissions.add(
            Permission.objects.get(codename=AnVILProjectManagerAccess.STAFF_EDIT_PERMISSION_CODENAME)
        )
        # Data for forms
        self.start_date = date.today()
        self.end_date = self.start_date + timedelta(days=10)

    def get_url(self, *args):
        """Get the url for the view being tested."""
        return reverse("gregor_anvil:upload_cycles:new", args=args)

    def get_view(self):
        """Return the view being tested."""
        return views.UploadCycleCreate.as_view()

    def test_view_redirect_not_logged_in(self):
        "View redirects to login view when user is not logged in."
        # Need a client for redirects.
        response = self.client.get(self.get_url())
        self.assertRedirects(response, resolve_url(settings.LOGIN_URL) + "?next=" + self.get_url())

    def test_status_code_with_user_permission(self):
        """Returns successful response code."""
        self.client.force_login(self.user)
        response = self.client.get(self.get_url())
        self.assertEqual(response.status_code, 200)

    def test_access_with_view_permission(self):
        """Raises permission denied if user has only view permission."""
        user_with_view_perm = User.objects.create_user(username="test-other", password="test-other")
        user_with_view_perm.user_permissions.add(
            Permission.objects.get(codename=AnVILProjectManagerAccess.STAFF_VIEW_PERMISSION_CODENAME)
        )
        request = self.factory.get(self.get_url())
        request.user = user_with_view_perm
        with self.assertRaises(PermissionDenied):
            self.get_view()(request)

    def test_access_without_user_permission(self):
        """Raises permission denied if user has no permissions."""
        user_no_perms = User.objects.create_user(username="test-none", password="test-none")
        request = self.factory.get(self.get_url())
        request.user = user_no_perms
        with self.assertRaises(PermissionDenied):
            self.get_view()(request)

    def test_has_form_in_context(self):
        """Response includes a form."""
        self.client.force_login(self.user)
        response = self.client.get(self.get_url())
        self.assertTrue("form" in response.context_data)
        self.assertIsInstance(response.context_data["form"], forms.UploadCycleForm)

    def test_can_create_an_object(self):
        """Posting valid data to the form creates an object."""
        self.client.force_login(self.user)
        response = self.client.post(
            self.get_url(),
            {"cycle": 1, "start_date": self.start_date, "end_date": self.end_date},
        )
        self.assertEqual(response.status_code, 302)
        new_object = models.UploadCycle.objects.latest("pk")
        self.assertIsInstance(new_object, models.UploadCycle)
        self.assertEqual(new_object.cycle, 1)
        self.assertEqual(new_object.start_date, self.start_date)
        self.assertEqual(new_object.end_date, self.end_date)
        # History is added.
        self.assertEqual(new_object.history.count(), 1)
        self.assertEqual(new_object.history.latest().history_type, "+")

    def test_can_create_an_object_with_note(self):
        """Can create an object with a note."""
        self.client.force_login(self.user)
        response = self.client.post(
            self.get_url(),
            {
                "cycle": 1,
                "start_date": self.start_date,
                "end_date": self.end_date,
                "note": "a test note",
            },
        )
        self.assertEqual(response.status_code, 302)
        new_object = models.UploadCycle.objects.latest("pk")
        self.assertIsInstance(new_object, models.UploadCycle)
        self.assertEqual(new_object.note, "a test note")

    def test_success_message(self):
        """Response includes a success message if successful."""
        self.client.force_login(self.user)
        response = self.client.post(
            self.get_url(),
            {"cycle": 1, "start_date": self.start_date, "end_date": self.end_date},
            follow=True,
        )
        messages = [m.message for m in get_messages(response.wsgi_request)]
        self.assertEqual(len(messages), 1)
        self.assertEqual(views.UploadCycleCreate.success_message, str(messages[0]))

    def test_redirects_to_new_object_detail(self):
        """After successfully creating an object, view redirects to the object's detail page."""
        self.client.force_login(self.user)
        response = self.client.post(
            self.get_url(),
            {"cycle": 1, "start_date": self.start_date, "end_date": self.end_date},
        )
        new_object = models.UploadCycle.objects.latest("pk")
        self.assertRedirects(response, new_object.get_absolute_url())

    def test_cannot_create_duplicate_object(self):
        """Cannot create a duplicate object."""
        obj = factories.UploadCycleFactory.create()
        self.client.force_login(self.user)
        response = self.client.post(
            self.get_url(),
            {
                "cycle": obj.cycle,
                "start_date": self.start_date,
                "end_date": self.end_date,
            },
        )
        self.assertEqual(response.status_code, 200)
        form = response.context_data["form"]
        self.assertFalse(form.is_valid())
        self.assertIn("cycle", form.errors.keys())
        self.assertIn("already exists", form.errors["cycle"][0])
        self.assertEqual(models.UploadCycle.objects.count(), 1)
        self.assertEqual(models.UploadCycle.objects.get(), obj)

    def test_invalid_input(self):
        """Posting invalid data does not create an object."""
        self.client.force_login(self.user)
        response = self.client.post(
            self.get_url(),
            {"cycle": -1, "start_date": self.start_date, "end_date": self.end_date},
        )
        self.assertEqual(response.status_code, 200)
        form = response.context_data["form"]
        self.assertFalse(form.is_valid())
        self.assertEqual(len(form.errors.keys()), 1)
        self.assertIn("cycle", form.errors.keys())
        self.assertEqual(len(form.errors["cycle"]), 1)
        self.assertEqual(models.UploadCycle.objects.count(), 0)

    def test_post_blank_data(self):
        """Posting blank data does not create an object."""
        self.client.force_login(self.user)
        response = self.client.post(self.get_url(), {})
        self.assertEqual(response.status_code, 200)
        form = response.context_data["form"]
        self.assertFalse(form.is_valid())
        self.assertEqual(models.UploadCycle.objects.count(), 0)


class UploadCycleDetailTest(TestCase):
    """Tests for the UploadCycle view."""

    def setUp(self):
        """Set up test class."""
        self.factory = RequestFactory()
        self.model_factory = factories.UploadCycleFactory
        # Create a user with both view and edit permission.
        self.user = User.objects.create_user(username="test", password="test")
        self.user.user_permissions.add(
            Permission.objects.get(codename=acm_models.AnVILProjectManagerAccess.STAFF_VIEW_PERMISSION_CODENAME)
        )

    def get_url(self, *args):
        """Get the url for the view being tested."""
        return reverse("gregor_anvil:upload_cycles:detail", args=args)

    def get_view(self):
        """Return the view being tested."""
        return views.UploadCycleDetail.as_view()

    def test_view_redirect_not_logged_in(self):
        "View redirects to login view when user is not logged in."
        # Need a client for redirects.
        response = self.client.get(self.get_url(1))
        self.assertRedirects(response, resolve_url(settings.LOGIN_URL) + "?next=" + self.get_url(1))

    def test_status_code_with_user_permission(self):
        """Returns successful response code."""
        obj = self.model_factory.create()
        self.client.force_login(self.user)
        response = self.client.get(self.get_url(obj.cycle))
        self.assertEqual(response.status_code, 200)

    def test_access_without_user_permission(self):
        """Raises permission denied if user has no permissions."""
        user_no_perms = User.objects.create_user(username="test-none", password="test-none")
        request = self.factory.get(self.get_url(1))
        request.user = user_no_perms
        with self.assertRaises(PermissionDenied):
            self.get_view()(request)

    def test_view_status_code_with_invalid_pk(self):
        """Raises a 404 error with an invalid object pk."""
        obj = self.model_factory.create()
        request = self.factory.get(self.get_url(obj.cycle + 1))
        request.user = self.user
        with self.assertRaises(Http404):
            self.get_view()(request, slug=obj.cycle + 1)

    def test_uses_cycle_instead_of_pk(self):
        """Raises a 404 error with an invalid object pk."""
        self.model_factory.create(pk=1, cycle=10)
        obj = self.model_factory.create(pk=2, cycle=1)
        self.client.force_login(self.user)
        response = self.client.get(self.get_url(1))
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.context_data["object"], obj)

    def test_table_classes(self):
        obj = self.model_factory.create()
        self.client.force_login(self.user)
        response = self.client.get(self.get_url(obj.cycle))
        self.assertIn("tables", response.context_data)
        self.assertEqual(len(response.context_data["tables"]), 6)
        self.assertIsInstance(response.context_data["tables"][0], tables.UploadWorkspaceTable)
        self.assertIsInstance(
            response.context_data["tables"][1],
            tables.CombinedConsortiumDataWorkspaceTable,
        )
        self.assertIsInstance(response.context_data["tables"][2], tables.ReleaseWorkspaceTable)
        self.assertIsInstance(response.context_data["tables"][3], tables.DCCProcessingWorkspaceTable)
        self.assertIsInstance(response.context_data["tables"][4], tables.DCCProcessedDataWorkspaceTable)
        self.assertIsInstance(response.context_data["tables"][5], tables.PartnerUploadWorkspaceTable)

    def test_upload_workspace_table(self):
        """Contains a table of UploadWorkspaces from this upload cycle."""
        obj = self.model_factory.create()
        workspace = factories.UploadWorkspaceFactory.create(upload_cycle=obj)
        other_workspace = factories.UploadWorkspaceFactory.create()
        self.client.force_login(self.user)
        response = self.client.get(self.get_url(obj.cycle))
        table = response.context_data["tables"][0]
        self.assertEqual(len(table.rows), 1)
        self.assertIn(workspace.workspace, table.data)
        self.assertNotIn(other_workspace.workspace, table.data)

    def test_combined_workspace_table(self):
        """Contains a table of CombinedConsortiumDataWorkspaces from this upload cycle."""
        obj = self.model_factory.create()
        workspace = factories.CombinedConsortiumDataWorkspaceFactory.create(upload_cycle=obj)
        other_workspace = factories.CombinedConsortiumDataWorkspaceFactory.create()
        self.client.force_login(self.user)
        response = self.client.get(self.get_url(obj.cycle))
        table = response.context_data["tables"][1]
        self.assertEqual(len(table.rows), 1)
        self.assertIn(workspace.workspace, table.data)
        self.assertNotIn(other_workspace.workspace, table.data)

    def test_release_workspace_table(self):
        """Contains a table of ReleaseWorkspaces from this upload cycle."""
        obj = self.model_factory.create()
        workspace = factories.ReleaseWorkspaceFactory.create(upload_cycle=obj)
        other_workspace = factories.ReleaseWorkspaceFactory.create()
        self.client.force_login(self.user)
        response = self.client.get(self.get_url(obj.cycle))
        table = response.context_data["tables"][2]
        self.assertEqual(len(table.rows), 1)
        self.assertIn(workspace.workspace, table.data)
        self.assertNotIn(other_workspace.workspace, table.data)

    def test_dcc_processing_workspace_table(self):
        """Contains a table of DCCProcessingWorkspaces from this upload cycle."""
        obj = self.model_factory.create()
        workspace = factories.DCCProcessingWorkspaceFactory.create(upload_cycle=obj)
        other_workspace = factories.DCCProcessingWorkspaceFactory.create()
        self.client.force_login(self.user)
        response = self.client.get(self.get_url(obj.cycle))
        table = response.context_data["tables"][3]
        self.assertEqual(len(table.rows), 1)
        self.assertIn(workspace.workspace, table.data)
        self.assertNotIn(other_workspace.workspace, table.data)

    def test_dcc_processed_data_workspace_table(self):
        """Contains a table of DCCProcessedDataWorkspaces from this upload cycle."""
        obj = self.model_factory.create()
        workspace = factories.DCCProcessedDataWorkspaceFactory.create(upload_cycle=obj)
        other_workspace = factories.DCCProcessedDataWorkspaceFactory.create()
        self.client.force_login(self.user)
        response = self.client.get(self.get_url(obj.cycle))
        table = response.context_data["tables"][4]
        self.assertEqual(len(table.rows), 1)
        self.assertIn(workspace.workspace, table.data)
        self.assertNotIn(other_workspace.workspace, table.data)

    def test_partner_upload_workspace_table(self):
        """Contains a table of PartnerUploadWorkspaces for this upload cycle."""
        obj = self.model_factory.create()
        obj.end_date
        # Make sure the partner upload workspace has an end date before the end of this upload cycle.
        workspace = factories.PartnerUploadWorkspaceFactory.create(date_completed=obj.end_date - timedelta(days=1))
        other_workspace = factories.PartnerUploadWorkspaceFactory.create(
            date_completed=obj.end_date + timedelta(days=1)
        )
        self.client.force_login(self.user)
        response = self.client.get(self.get_url(obj.cycle))
        table = response.context_data["tables"][5]
        self.assertEqual(len(table.rows), 1)
        self.assertIn(workspace.workspace, table.data)
        self.assertNotIn(other_workspace.workspace, table.data)


class UploadCycleListTest(TestCase):
    """Tests for the UploadCycleList view."""

    def setUp(self):
        """Set up test class."""
        self.factory = RequestFactory()
        self.model_factory = factories.UploadCycleFactory
        # Create a user with both view and edit permission.
        self.user = User.objects.create_user(username="test", password="test")
        self.user.user_permissions.add(
            Permission.objects.get(codename=acm_models.AnVILProjectManagerAccess.STAFF_VIEW_PERMISSION_CODENAME)
        )

    def get_url(self):
        """Get the url for the view being tested."""
        return reverse("gregor_anvil:upload_cycles:list")

    def get_view(self):
        """Return the view being tested."""
        return views.UploadCycleList.as_view()

    def test_view_redirect_not_logged_in(self):
        "View redirects to login view when user is not logged in."
        # Need a client for redirects.
        response = self.client.get(self.get_url())
        self.assertRedirects(response, resolve_url(settings.LOGIN_URL) + "?next=" + self.get_url())

    def test_status_code_with_user_permission(self):
        """Returns successful response code."""
        self.client.force_login(self.user)
        response = self.client.get(self.get_url())
        self.assertEqual(response.status_code, 200)

    def test_access_without_user_permission(self):
        """Raises permission denied if user has no permissions."""
        user_no_perms = User.objects.create_user(username="test-none", password="test-none")
        request = self.factory.get(self.get_url())
        request.user = user_no_perms
        with self.assertRaises(PermissionDenied):
            self.get_view()(request)

    def test_view_has_correct_table_class(self):
        """View has the correct table class in the context."""
        self.client.force_login(self.user)
        response = self.client.get(self.get_url())
        self.assertIn("table", response.context_data)
        self.assertIsInstance(response.context_data["table"], tables.UploadCycleTable)

    def test_view_with_no_objects(self):
        """The table has no rows when there are no UploadCycle objects."""
        self.client.force_login(self.user)
        response = self.client.get(self.get_url())
        self.assertEqual(response.status_code, 200)
        self.assertIn("table", response.context_data)
        self.assertEqual(len(response.context_data["table"].rows), 0)

    def test_view_with_one_object(self):
        """The table has one row when there is one UploadCycle object."""
        self.model_factory.create()
        self.client.force_login(self.user)
        response = self.client.get(self.get_url())
        self.assertEqual(response.status_code, 200)
        self.assertIn("table", response.context_data)
        self.assertEqual(len(response.context_data["table"].rows), 1)

    def test_view_with_two_objects(self):
        """The table has two rows when there are two UploadCycle objects."""
        self.model_factory.create_batch(2)
        self.client.force_login(self.user)
        response = self.client.get(self.get_url())
        self.assertEqual(response.status_code, 200)
        self.assertIn("table", response.context_data)
        self.assertEqual(len(response.context_data["table"].rows), 2)


class AccountListTest(TestCase):
    def setUp(self):
        """Set up test class."""
        self.factory = RequestFactory()
        # Create a user with both view and edit permission.
        self.user = User.objects.create_user(username="test", password="test")
        self.user.user_permissions.add(
            Permission.objects.get(codename=acm_models.AnVILProjectManagerAccess.STAFF_VIEW_PERMISSION_CODENAME)
        )

    def test_filter_by_name(self):
        """Filtering by name works as expected."""
        user = UserFactory.create(name="First Last")
        account = acm_factories.AccountFactory.create(user=user)
        other_account = acm_factories.AccountFactory.create(verified=True)
        self.client.force_login(self.user)
        response = self.client.get(
            reverse("anvil_consortium_manager:accounts:list"),
            {"user__name__icontains": "First"},
        )
        self.assertIn("table", response.context_data)
        self.assertEqual(len(response.context_data["table"].rows), 1)
        self.assertIn(account, response.context_data["table"].data)
        self.assertNotIn(other_account, response.context_data["table"].data)


class UploadWorkspaceDetailTest(TestCase):
    """Tests of the anvil_consortium_manager WorkspaceDetail view using the UploadWorkspace adapter."""

    def setUp(self):
        """Set up test class."""
        self.factory = RequestFactory()
        # Create a user with both view and edit permission.
        self.user = User.objects.create_user(username="test", password="test")
        self.user.user_permissions.add(
            Permission.objects.get(codename=acm_models.AnVILProjectManagerAccess.STAFF_VIEW_PERMISSION_CODENAME)
        )
        self.user.user_permissions.add(
            Permission.objects.get(codename=acm_models.AnVILProjectManagerAccess.STAFF_EDIT_PERMISSION_CODENAME)
        )
        self.object = factories.UploadWorkspaceFactory.create()

    def get_url(self, *args):
        """Get the url for the view being tested."""
        return reverse("anvil_consortium_manager:workspaces:detail", args=args)

    def test_status_code(self):
        """Response has a status code of 200."""
        self.client.force_login(self.user)
        response = self.client.get(self.get_url(self.object.workspace.billing_project.name, self.object.workspace.name))
        self.assertEqual(response.status_code, 200)

    def test_contains_share_with_auth_domain_button(self):
        acm_factories.WorkspaceAuthorizationDomainFactory.create(
            workspace=self.object.workspace, group__name="test_auth"
        )
        self.client.force_login(self.user)
        response = self.client.get(self.get_url(self.object.workspace.billing_project.name, self.object.workspace.name))
        url = reverse(
            "anvil_consortium_manager:workspaces:sharing:new_by_group",
            args=[
                self.object.workspace.billing_project.name,
                self.object.workspace.name,
                "test_auth",
            ],
        )
        self.assertContains(response, url)


class UploadWorkspaceListTest(TestCase):
    """Tests of the anvil_consortium_manager WorkspaceList view using this app's adapter."""

    def setUp(self):
        """Set up test class."""
        self.factory = RequestFactory()
        # Create a user with both view and edit permission.
        self.user = User.objects.create_user(username="test", password="test")
        self.user.user_permissions.add(
            Permission.objects.get(codename=acm_models.AnVILProjectManagerAccess.STAFF_VIEW_PERMISSION_CODENAME)
        )
        self.workspace_type = "upload"

    def get_url(self, *args):
        """Get the url for the view being tested."""
        return reverse("anvil_consortium_manager:workspaces:list", args=args)

    def test_view_has_correct_table_class(self):
        """The view has the correct table class in the context."""
        self.client.force_login(self.user)
        response = self.client.get(self.get_url(self.workspace_type))
        self.assertIn("table", response.context_data)
        self.assertIsInstance(response.context_data["table"], tables.UploadWorkspaceTable)


class UploadWorkspaceCreateTest(AnVILAPIMockTestMixin, TestCase):
    """Tests of the WorkspaceCreate view from ACM with extra UploadWorkspace model."""

    api_success_code = 201

    def setUp(self):
        """Set up test class."""
        # The superclass uses the responses package to mock API responses.
        super().setUp()
        # Create a user with both view and edit permissions.
        self.user = User.objects.create_user(username="test", password="test")
        self.user.user_permissions.add(
            Permission.objects.get(codename=acm_models.AnVILProjectManagerAccess.STAFF_VIEW_PERMISSION_CODENAME)
        )
        self.user.user_permissions.add(
            Permission.objects.get(codename=acm_models.AnVILProjectManagerAccess.STAFF_EDIT_PERMISSION_CODENAME)
        )
        self.workspace_type = "upload"
        # Create the admins group.
        self.admins_group = acm_factories.ManagedGroupFactory.create(name=settings.ANVIL_DCC_ADMINS_GROUP_NAME)

    def get_url(self, *args):
        """Get the url for the view being tested."""
        return reverse("anvil_consortium_manager:workspaces:new", args=args)

    def test_creates_upload_workspace(self):
        """Posting valid data to the form creates a workspace data object when using a custom adapter."""
        research_center = factories.ResearchCenterFactory.create()
        consent_group = factories.ConsentGroupFactory.create()
        upload_cycle = factories.UploadCycleFactory.create()
        billing_project = acm_factories.BillingProjectFactory.create(name="test-billing-project")
        url = self.api_client.rawls_entry_point + "/api/workspaces"
        json_data = {
            "namespace": "test-billing-project",
            "name": "test-workspace",
            "attributes": {},
        }
        self.anvil_response_mock.add(
            responses.POST,
            url,
            status=self.api_success_code,
            match=[responses.matchers.json_params_matcher(json_data)],
        )
        # API response for GREGOR admins workspace owner.
        acls = [
            {
                "email": "TEST_GREGOR_DCC_ADMINS@firecloud.org",
                "accessLevel": "OWNER",
                "canShare": False,
                "canCompute": True,
            }
        ]
        self.anvil_response_mock.add(
            responses.PATCH,
            self.api_client.rawls_entry_point
            + "/api/workspaces/test-billing-project/test-workspace/acl?inviteUsersNotFound=false",
            status=200,
            match=[responses.matchers.json_params_matcher(acls)],
            json={"invitesSent": {}, "usersNotFound": {}, "usersUpdated": acls},
        )
        self.client.force_login(self.user)
        response = self.client.post(
            self.get_url(self.workspace_type),
            {
                "billing_project": billing_project.pk,
                "name": "test-workspace",
                # Workspace data form.
                "workspacedata-TOTAL_FORMS": 1,
                "workspacedata-INITIAL_FORMS": 0,
                "workspacedata-MIN_NUM_FORMS": 1,
                "workspacedata-MAX_NUM_FORMS": 1,
                "workspacedata-0-research_center": research_center.pk,
                "workspacedata-0-consent_group": consent_group.pk,
                "workspacedata-0-upload_cycle": upload_cycle.pk,
            },
        )
        self.assertEqual(response.status_code, 302)
        # The workspace is created.
        new_workspace = acm_models.Workspace.objects.latest("pk")
        # Workspace data is added.
        self.assertEqual(models.UploadWorkspace.objects.count(), 1)
        new_workspace_data = models.UploadWorkspace.objects.latest("pk")
        self.assertEqual(new_workspace_data.workspace, new_workspace)
        self.assertEqual(new_workspace_data.research_center, research_center)
        self.assertEqual(new_workspace_data.consent_group, consent_group)
        self.assertEqual(new_workspace_data.upload_cycle, upload_cycle)


class UploadWorkspaceAutocompleteByTypeTest(TestCase):
    def setUp(self):
        """Set up test class."""
        self.factory = RequestFactory()
        # Create a user with the correct permissions.
        self.user = User.objects.create_user(username="test", password="test")
        self.user.user_permissions.add(
            Permission.objects.get(codename=acm_models.AnVILProjectManagerAccess.STAFF_VIEW_PERMISSION_CODENAME)
        )

    def get_url(self, *args):
        """Get the url for the view being tested."""
        return reverse("anvil_consortium_manager:workspaces:autocomplete_by_type", args=args)

    def test_returns_all_objects(self):
        """Queryset returns all objects when there is no query."""
        workspaces = factories.UploadWorkspaceFactory.create_batch(10)
        self.client.force_login(self.user)
        response = self.client.get(self.get_url("upload"))
        returned_ids = [int(x["id"]) for x in json.loads(response.content.decode("utf-8"))["results"]]
        self.assertEqual(len(returned_ids), 10)
        self.assertEqual(sorted(returned_ids), sorted([x.pk for x in workspaces]))

    def test_returns_correct_object_match(self):
        """Queryset returns the correct objects when query matches the name."""
        factories.UploadWorkspaceFactory.create(workspace__name="other")
        workspace = factories.UploadWorkspaceFactory.create(workspace__name="test-workspace")
        self.client.force_login(self.user)
        response = self.client.get(self.get_url("upload"), {"q": "test-workspace"})
        returned_ids = [int(x["id"]) for x in json.loads(response.content.decode("utf-8"))["results"]]
        self.assertEqual(len(returned_ids), 1)
        self.assertEqual(returned_ids[0], workspace.pk)

    def test_returns_correct_object_starting_with_query(self):
        """Queryset returns the correct objects when query matches the beginning of the name."""
        factories.UploadWorkspaceFactory.create(workspace__name="other")
        workspace = factories.UploadWorkspaceFactory.create(workspace__name="test-workspace")
        self.client.force_login(self.user)
        response = self.client.get(self.get_url("upload"), {"q": "test"})
        returned_ids = [int(x["id"]) for x in json.loads(response.content.decode("utf-8"))["results"]]
        self.assertEqual(len(returned_ids), 1)
        self.assertEqual(returned_ids[0], workspace.pk)

    def test_returns_correct_object_containing_query(self):
        """Queryset returns the correct objects when the name contains the query."""
        factories.UploadWorkspaceFactory.create(workspace__name="other")
        workspace = factories.UploadWorkspaceFactory.create(workspace__name="test-workspace")
        self.client.force_login(self.user)
        response = self.client.get(self.get_url("upload"), {"q": "work"})
        returned_ids = [int(x["id"]) for x in json.loads(response.content.decode("utf-8"))["results"]]
        self.assertEqual(len(returned_ids), 1)
        self.assertEqual(returned_ids[0], workspace.pk)

    def test_returns_correct_object_case_insensitive(self):
        """Queryset returns the correct objects when query matches the beginning of the name."""
        factories.UploadWorkspaceFactory.create(workspace__name="other")
        workspace = factories.UploadWorkspaceFactory.create(workspace__name="test-workspace")
        self.client.force_login(self.user)
        response = self.client.get(self.get_url("upload"), {"q": "TEST-WORKSPACE"})
        returned_ids = [int(x["id"]) for x in json.loads(response.content.decode("utf-8"))["results"]]
        self.assertEqual(len(returned_ids), 1)
        self.assertEqual(returned_ids[0], workspace.pk)

    def test_forwarded_consent_group(self):
        """Queryset is filtered to consent groups matching the forwarded value if specified."""
        workspace = factories.UploadWorkspaceFactory.create()
        other_workspace = factories.UploadWorkspaceFactory.create()
        self.client.force_login(self.user)
        response = self.client.get(
            self.get_url("upload"),
            {"forward": json.dumps({"consent_group": workspace.consent_group.pk})},
        )
        returned_ids = [int(x["id"]) for x in json.loads(response.content.decode("utf-8"))["results"]]
        self.assertEqual(len(returned_ids), 1)
        self.assertIn(workspace.pk, returned_ids)
        self.assertNotIn(other_workspace.pk, returned_ids)

    def test_forwarded_upload_cycle(self):
        """Queryset is filtered to upload cycles matching the forwarded value if specified."""
        workspace = factories.UploadWorkspaceFactory.create()
        other_workspace = factories.UploadWorkspaceFactory.create()
        self.client.force_login(self.user)
        response = self.client.get(
            self.get_url("upload"),
            {"forward": json.dumps({"upload_cycle": workspace.upload_cycle.pk})},
        )
        returned_ids = [int(x["id"]) for x in json.loads(response.content.decode("utf-8"))["results"]]
        self.assertEqual(len(returned_ids), 1)
        self.assertIn(workspace.pk, returned_ids)
        self.assertNotIn(other_workspace.pk, returned_ids)

    def test_forwarded_consent_group_and_upload_cycle(self):
        """Queryset is filtered to upload_cycle and consent_groups matching the forwarded value if specified."""
        workspace = factories.UploadWorkspaceFactory.create()
        other_workspace_1 = factories.UploadWorkspaceFactory.create(upload_cycle=workspace.upload_cycle)
        other_workspace_2 = factories.UploadWorkspaceFactory.create(consent_group=workspace.consent_group)
        self.client.force_login(self.user)
        response = self.client.get(
            self.get_url("upload"),
            {
                "forward": json.dumps(
                    {
                        "consent_group": workspace.consent_group.pk,
                        "upload_cycle": workspace.upload_cycle.pk,
                    }
                )
            },
        )
        returned_ids = [int(x["id"]) for x in json.loads(response.content.decode("utf-8"))["results"]]
        self.assertEqual(len(returned_ids), 1)
        self.assertIn(workspace.pk, returned_ids)
        self.assertNotIn(other_workspace_1.pk, returned_ids)
        self.assertNotIn(other_workspace_2.pk, returned_ids)


class ResourceWorkspaceDetailTest(TestCase):
    """Tests of the anvil_consortium_manager WorkspaceDetail view using the TemplateWorkspace adapter."""

    def setUp(self):
        """Set up test class."""
        self.factory = RequestFactory()
        # Create a user with both view and edit permission.
        self.user = User.objects.create_user(username="test", password="test")
        self.user.user_permissions.add(
            Permission.objects.get(codename=acm_models.AnVILProjectManagerAccess.STAFF_VIEW_PERMISSION_CODENAME)
        )
        self.object = factories.ResourceWorkspaceFactory.create()

    def get_url(self, *args):
        """Get the url for the view being tested."""
        return reverse("anvil_consortium_manager:workspaces:detail", args=args)

    def test_status_code(self):
        """Response has a status code of 200."""
        self.client.force_login(self.user)
        response = self.client.get(self.get_url(self.object.workspace.billing_project.name, self.object.workspace.name))
        self.assertEqual(response.status_code, 200)

    def test_brief_description(self):
        self.object.brief_description = "testing brief description in template"
        self.object.save()
        self.client.force_login(self.user)
        response = self.client.get(self.get_url(self.object.workspace.billing_project.name, self.object.workspace.name))
        self.assertContains(response, "testing brief description in template")


class ResourceWorkspaceListTest(TestCase):
    """Tests of the anvil_consortium_manager WorkspaceList view using the ResourceWorkspace adapter."""

    def setUp(self):
        """Set up test class."""
        self.factory = RequestFactory()
        # Create a user with both view and edit permission.
        self.user = User.objects.create_user(username="test", password="test")
        self.user.user_permissions.add(
            Permission.objects.get(codename=acm_models.AnVILProjectManagerAccess.STAFF_VIEW_PERMISSION_CODENAME)
        )
        self.workspace_type = "resource"

    def get_url(self, *args):
        """Get the url for the view being tested."""
        return reverse("anvil_consortium_manager:workspaces:list", args=args)

    def test_view_has_correct_table_class(self):
        """The view has the correct table class in the context."""
        self.client.force_login(self.user)
        response = self.client.get(self.get_url(self.workspace_type))
        self.assertIn("table", response.context_data)
        self.assertIsInstance(response.context_data["table"], tables.DefaultWorkspaceTable)


class ResourceWorkspaceCreateTest(AnVILAPIMockTestMixin, TestCase):
    """Tests of the WorkspaceCreate view from ACM with extra ResourceWorkspace model."""

    api_success_code = 201

    def setUp(self):
        """Set up test class."""
        # The superclass uses the responses package to mock API responses.
        super().setUp()
        # Create a user with both view and edit permissions.
        self.user = User.objects.create_user(username="test", password="test")
        self.user.user_permissions.add(
            Permission.objects.get(codename=acm_models.AnVILProjectManagerAccess.STAFF_VIEW_PERMISSION_CODENAME)
        )
        self.user.user_permissions.add(
            Permission.objects.get(codename=acm_models.AnVILProjectManagerAccess.STAFF_EDIT_PERMISSION_CODENAME)
        )
        self.workspace_type = "resource"
        # Create the admins group.
        self.admins_group = acm_factories.ManagedGroupFactory.create(name=settings.ANVIL_DCC_ADMINS_GROUP_NAME)

    def get_url(self, *args):
        """Get the url for the view being tested."""
        return reverse("anvil_consortium_manager:workspaces:new", args=args)

    def test_creates_upload_workspace(self):
        """Posting valid data to the form creates a workspace data object when using a custom adapter."""
        billing_project = acm_factories.BillingProjectFactory.create(name="test-billing-project")
        url = self.api_client.rawls_entry_point + "/api/workspaces"
        json_data = {
            "namespace": "test-billing-project",
            "name": "test-workspace",
            "attributes": {},
        }
        self.anvil_response_mock.add(
            responses.POST,
            url,
            status=self.api_success_code,
            match=[responses.matchers.json_params_matcher(json_data)],
        )
        # API response for GREGOR admins workspace owner.
        acls = [
            {
                "email": "TEST_GREGOR_DCC_ADMINS@firecloud.org",
                "accessLevel": "OWNER",
                "canShare": False,
                "canCompute": True,
            }
        ]
        self.anvil_response_mock.add(
            responses.PATCH,
            self.api_client.rawls_entry_point
            + "/api/workspaces/test-billing-project/test-workspace/acl?inviteUsersNotFound=false",
            status=200,
            match=[responses.matchers.json_params_matcher(acls)],
            json={"invitesSent": {}, "usersNotFound": {}, "usersUpdated": acls},
        )
        self.client.force_login(self.user)
        response = self.client.post(
            self.get_url(self.workspace_type),
            {
                "billing_project": billing_project.pk,
                "name": "test-workspace",
                # Workspace data form.
                "workspacedata-TOTAL_FORMS": 1,
                "workspacedata-INITIAL_FORMS": 0,
                "workspacedata-MIN_NUM_FORMS": 1,
                "workspacedata-MAX_NUM_FORMS": 1,
                "workspacedata-0-brief_description": "Test use",
            },
        )
        self.assertEqual(response.status_code, 302)
        # The workspace is created.
        new_workspace = acm_models.Workspace.objects.latest("pk")
        # Workspace data is added.
        self.assertEqual(models.ResourceWorkspace.objects.count(), 1)
        new_workspace_data = models.ResourceWorkspace.objects.latest("pk")
        self.assertEqual(new_workspace_data.workspace, new_workspace)
        self.assertEqual(new_workspace_data.brief_description, "Test use")


class TemplateWorkspaceDetailTest(TestCase):
    """Tests of the anvil_consortium_manager WorkspaceDetail view using the TemplateWorkspace adapter."""

    def setUp(self):
        """Set up test class."""
        self.factory = RequestFactory()
        # Create a user with both view and edit permission.
        self.user = User.objects.create_user(username="test", password="test")
        self.user.user_permissions.add(
            Permission.objects.get(codename=acm_models.AnVILProjectManagerAccess.STAFF_VIEW_PERMISSION_CODENAME)
        )
        self.object = factories.TemplateWorkspaceFactory.create()

    def get_url(self, *args):
        """Get the url for the view being tested."""
        return reverse("anvil_consortium_manager:workspaces:detail", args=args)

    def test_status_code(self):
        """Response has a status code of 200."""
        self.client.force_login(self.user)
        response = self.client.get(self.get_url(self.object.workspace.billing_project.name, self.object.workspace.name))
        self.assertEqual(response.status_code, 200)


class TemplateWorkspaceListTest(TestCase):
    """Tests of the anvil_consortium_manager WorkspaceList view using the TemplateWorkspace adapter."""

    def setUp(self):
        """Set up test class."""
        self.factory = RequestFactory()
        # Create a user with both view and edit permission.
        self.user = User.objects.create_user(username="test", password="test")
        self.user.user_permissions.add(
            Permission.objects.get(codename=acm_models.AnVILProjectManagerAccess.STAFF_VIEW_PERMISSION_CODENAME)
        )
        self.workspace_type = "template"

    def get_url(self, *args):
        """Get the url for the view being tested."""
        return reverse("anvil_consortium_manager:workspaces:list", args=args)

    def test_view_has_correct_table_class(self):
        """The view has the correct table class in the context."""
        self.client.force_login(self.user)
        response = self.client.get(self.get_url(self.workspace_type))
        self.assertIn("table", response.context_data)
        self.assertIsInstance(response.context_data["table"], tables.TemplateWorkspaceTable)


class TemplateWorkspaceCreateTest(AnVILAPIMockTestMixin, TestCase):
    """Tests of the WorkspaceCreate view from ACM with extra TemplateWorkspace model."""

    api_success_code = 201

    def setUp(self):
        """Set up test class."""
        # The superclass uses the responses package to mock API responses.
        super().setUp()
        # Create a user with both view and edit permissions.
        self.user = User.objects.create_user(username="test", password="test")
        self.user.user_permissions.add(
            Permission.objects.get(codename=acm_models.AnVILProjectManagerAccess.STAFF_VIEW_PERMISSION_CODENAME)
        )
        self.user.user_permissions.add(
            Permission.objects.get(codename=acm_models.AnVILProjectManagerAccess.STAFF_EDIT_PERMISSION_CODENAME)
        )
        self.workspace_type = "template"
        # Create the admins group.
        self.admins_group = acm_factories.ManagedGroupFactory.create(name=settings.ANVIL_DCC_ADMINS_GROUP_NAME)

    def get_url(self, *args):
        """Get the url for the view being tested."""
        return reverse("anvil_consortium_manager:workspaces:new", args=args)

    def test_creates_upload_workspace(self):
        """Posting valid data to the form creates a workspace data object when using a custom adapter."""
        billing_project = acm_factories.BillingProjectFactory.create(name="test-billing-project")
        url = self.api_client.rawls_entry_point + "/api/workspaces"
        json_data = {
            "namespace": "test-billing-project",
            "name": "test-workspace",
            "attributes": {},
        }
        self.anvil_response_mock.add(
            responses.POST,
            url,
            status=self.api_success_code,
            match=[responses.matchers.json_params_matcher(json_data)],
        )
        # API response for GREGOR admins workspace owner.
        acls = [
            {
                "email": "TEST_GREGOR_DCC_ADMINS@firecloud.org",
                "accessLevel": "OWNER",
                "canShare": False,
                "canCompute": True,
            }
        ]
        self.anvil_response_mock.add(
            responses.PATCH,
            self.api_client.rawls_entry_point
            + "/api/workspaces/test-billing-project/test-workspace/acl?inviteUsersNotFound=false",
            status=200,
            match=[responses.matchers.json_params_matcher(acls)],
            json={"invitesSent": {}, "usersNotFound": {}, "usersUpdated": acls},
        )
        self.client.force_login(self.user)
        response = self.client.post(
            self.get_url(self.workspace_type),
            {
                "billing_project": billing_project.pk,
                "name": "test-workspace",
                # Workspace data form.
                "workspacedata-TOTAL_FORMS": 1,
                "workspacedata-INITIAL_FORMS": 0,
                "workspacedata-MIN_NUM_FORMS": 1,
                "workspacedata-MAX_NUM_FORMS": 1,
                "workspacedata-0-intended_use": "foo bar",
            },
        )
        self.assertEqual(response.status_code, 302)
        # The workspace is created.
        new_workspace = acm_models.Workspace.objects.latest("pk")
        # Workspace data is added.
        self.assertEqual(models.TemplateWorkspace.objects.count(), 1)
        new_workspace_data = models.TemplateWorkspace.objects.latest("pk")
        self.assertEqual(new_workspace_data.workspace, new_workspace)
        self.assertEqual(new_workspace_data.intended_use, "foo bar")


class ConsortiumCombinedDataWorkspaceDetailTest(TestCase):
    """Tests of the anvil_consortium_manager WorkspaceDetail view using the CombinedConsortiumDataWorkspace adapter."""

    def setUp(self):
        """Set up test class."""
        self.factory = RequestFactory()
        # Create a user with both view and edit permission.
        self.user = User.objects.create_user(username="test", password="test")
        self.user.user_permissions.add(
            Permission.objects.get(codename=acm_models.AnVILProjectManagerAccess.STAFF_VIEW_PERMISSION_CODENAME)
        )
        self.user.user_permissions.add(
            Permission.objects.get(codename=acm_models.AnVILProjectManagerAccess.STAFF_EDIT_PERMISSION_CODENAME)
        )
        self.object = factories.CombinedConsortiumDataWorkspaceFactory.create()

    def get_url(self, *args):
        """Get the url for the view being tested."""
        return reverse("anvil_consortium_manager:workspaces:detail", args=args)

    def test_status_code(self):
        """Response has a status code of 200."""
        self.client.force_login(self.user)
        response = self.client.get(self.get_url(self.object.workspace.billing_project.name, self.object.workspace.name))
        self.assertEqual(response.status_code, 200)

    @skip("Need to allow extra context in ACM.")
    def test_contains_upload_workspaces(self):
        """Response contains the upload workspaces."""
        upload_workspace_1 = factories.UploadWorkspaceFactory.create(upload_cycle=self.object.upload_cycle)
        upload_workspace_2 = factories.UploadWorkspaceFactory.create(upload_cycle=self.object.upload_cycle)
        self.client.force_login(self.user)
        response = self.client.get(self.get_url(self.object.workspace.billing_project.name, self.object.workspace.name))
        self.assertIn("upload_workspace_table", response.context_data)
        self.assertIn(upload_workspace_1, response.context_data["upload_workspace_table"].data)
        self.assertIn(upload_workspace_2, response.context_data["upload_workspace_table"].data)

    @skip("Need to allow extra context in ACM.")
    def test_contains_upload_workspaces_from_previous_cycles(self):
        """Response contains the upload workspaces."""
        upload_cycle_1 = factories.UploadCycleFactory.create(upload_cycle=1)
        upload_cycle_2 = factories.UploadCycleFactory.create(upload_cycle=2)
        combined_workspace = factories.CombinedConsortiumDataWorkspaceFactory.create(upload_cycle=upload_cycle_2)
        upload_workspace_1 = factories.UploadWorkspaceFactory.create(upload_cycle=upload_cycle_1)
        upload_workspace_2 = factories.UploadWorkspaceFactory.create(upload_cycle=upload_cycle_2)
        self.client.force_login(self.user)
        response = self.client.get(
            self.get_url(
                combined_workspace.workspace.billing_project.name,
                combined_workspace.workspace.name,
            )
        )
        self.assertIn("upload_workspace_table", response.context_data)
        self.assertIn(upload_workspace_1, response.context_data["upload_workspace_table"].data)
        self.assertIn(upload_workspace_2, response.context_data["upload_workspace_table"].data)

    def test_contains_share_with_auth_domain_button(self):
        acm_factories.WorkspaceAuthorizationDomainFactory.create(
            workspace=self.object.workspace, group__name="test_auth"
        )
        self.client.force_login(self.user)
        response = self.client.get(self.get_url(self.object.workspace.billing_project.name, self.object.workspace.name))
        url = reverse(
            "anvil_consortium_manager:workspaces:sharing:new_by_group",
            args=[
                self.object.workspace.billing_project.name,
                self.object.workspace.name,
                "test_auth",
            ],
        )
        self.assertContains(response, url)


class ReleaseWorkspaceDetailTest(TestCase):
    """Tests of the anvil_consortium_manager WorkspaceDetail view using the ReleaseWorkspaceAdapter."""

    def setUp(self):
        """Set up test class."""
        self.factory = RequestFactory()
        # Create a user with both view and edit permission.
        self.user = User.objects.create_user(username="test", password="test")
        self.user.user_permissions.add(
            Permission.objects.get(codename=acm_models.AnVILProjectManagerAccess.STAFF_VIEW_PERMISSION_CODENAME)
        )
        self.object = factories.ReleaseWorkspaceFactory.create()

    def get_url(self, *args):
        """Get the url for the view being tested."""
        return reverse("anvil_consortium_manager:workspaces:detail", args=args)

    def test_status_code(self):
        """Response has a status code of 200."""
        self.client.force_login(self.user)
        response = self.client.get(self.get_url(self.object.workspace.billing_project.name, self.object.workspace.name))
        self.assertEqual(response.status_code, 200)

    @skip("Need to allow extra context in ACM.")
    def test_contains_upload_workspaces(self):
        """Response contains the upload workspaces."""
        upload_workspace_1 = factories.UploadWorkspaceFactory.create(upload_cycle=self.object.upload_cycle)
        upload_workspace_2 = factories.UploadWorkspaceFactory.create(upload_cycle=self.object.upload_cycle)
        self.client.force_login(self.user)
        response = self.client.get(self.get_url(self.object.workspace.billing_project.name, self.object.workspace.name))
        self.assertIn("included_workspace_table", response.context_data)
        self.assertIn(
            upload_workspace_1.workspace,
            response.context_data["included_workspace_table"].data,
        )
        self.assertIn(
            upload_workspace_2.workspace,
            response.context_data["included_workspace_table"].data,
        )

    @skip("Need to allow extra context in ACM.")
    def test_contains_upload_workspaces_from_previous_cycles(self):
        """Response contains the upload workspaces."""
        upload_cycle_1 = factories.UploadCycleFactory.create(upload_cycle=1)
        upload_cycle_2 = factories.UploadCycleFactory.create(upload_cycle=2)
        combined_workspace = factories.CombinedConsortiumDataWorkspaceFactory.create(upload_cycle=upload_cycle_2)
        upload_workspace_1 = factories.UploadWorkspaceFactory.create(upload_cycle=upload_cycle_1)
        upload_workspace_2 = factories.UploadWorkspaceFactory.create(upload_cycle=upload_cycle_2)
        self.client.force_login(self.user)
        response = self.client.get(
            self.get_url(
                combined_workspace.workspace.billing_project.name,
                combined_workspace.workspace.name,
            )
        )
        self.assertIn("included_workspace_table", response.context_data)
        self.assertIn(
            upload_workspace_1.workspace,
            response.context_data["included_workspace_table"].data,
        )
        self.assertIn(
            upload_workspace_2.workspace,
            response.context_data["included_workspace_table"].data,
        )


class WorkspaceReportTest(TestCase):
    def setUp(self):
        """Set up test class."""
        self.factory = RequestFactory()
        # self.model_factory = factories.ResearchCenterFactory
        # Create a user with both view and edit permission.
        self.user = User.objects.create_user(username="test", password="test")
        self.user.user_permissions.add(
            Permission.objects.get(codename=acm_models.AnVILProjectManagerAccess.STAFF_VIEW_PERMISSION_CODENAME)
        )

    def get_url(self, *args):
        """Get the url for the view being tested."""
        return reverse("gregor_anvil:reports:workspace")

    def get_view(self):
        """Return the view being tested."""
        return views.WorkspaceReport.as_view()

    def test_status_code_with_user_permission(self):
        """Returns successful response code."""
        self.client.force_login(self.user)
        response = self.client.get(self.get_url())
        self.assertEqual(response.status_code, 200)

    def test_view_redirect_not_logged_in(self):
        "View redirects to login view when user is not logged in."
        # Need a client for redirects.
        response = self.client.get(self.get_url())
        self.assertRedirects(response, resolve_url(settings.LOGIN_URL) + "?next=" + self.get_url())

    def test_access_without_user_permission(self):
        """Raises permission denied if user has no permissions."""
        user_no_perms = User.objects.create_user(username="test-none", password="test-none")
        request = self.factory.get(self.get_url())
        request.user = user_no_perms
        with self.assertRaises(PermissionDenied):
            self.get_view()(request)

    def test_workspace_count_table_no_workspaces(self):
        """Workspace table has no rows when there are no workspaces."""  # noqa: E501
        self.client.force_login(self.user)
        response = self.client.get(self.get_url())
        # workspace table
        self.assertIn("workspace_count_table", response.context_data)
        table = response.context_data["workspace_count_table"]
        self.assertEqual(len(table.data), 0)

    def test_workspace_count_table_one_workspace_type_not_shared_with_consortium(self):
        """Response includes no workspace shared with the consortium in context when workspace is not shared with the consortium"""  # noqa: E501
        upload_workspace = factories.UploadWorkspaceFactory.create()
        group = acm_factories.ManagedGroupFactory.create(name="group1")
        acm_factories.WorkspaceGroupSharingFactory.create(workspace=upload_workspace.workspace, group=group)
        self.client.force_login(self.user)
        response = self.client.get(self.get_url())
        # workspace table
        self.assertIn("workspace_count_table", response.context_data)
        table = response.context_data["workspace_count_table"]
        self.assertEqual(len(table.data), 1)
        self.assertIn({"workspace_type": "upload", "n_total": 1, "n_shared": 0}, table.data)

    def test_workspace_count_table_one_workspace_type_some_shared(self):
        """Workspace table includes correct values for one workspace type where only some workspaces are shared."""  # noqa: E501
        upload_workspace_1 = factories.UploadWorkspaceFactory.create()
        # Workspaces that won't be shared.
        factories.UploadWorkspaceFactory.create_batch(2)
        group = acm_factories.ManagedGroupFactory.create(name="GREGOR_ALL")
        acm_factories.WorkspaceGroupSharingFactory.create(workspace=upload_workspace_1.workspace, group=group)
        self.client.force_login(self.user)
        response = self.client.get(self.get_url())
        # workspace table
        self.assertIn("workspace_count_table", response.context_data)
        table = response.context_data["workspace_count_table"]
        self.assertEqual(len(table.data), 1)
        self.assertIn({"workspace_type": "upload", "n_total": 3, "n_shared": 1}, table.data)

    def test_workspace_count_table_two_workspace_types_some_shared(self):
        """Workspace table includes correct values for one workspace type where only some workspaces are shared."""  # noqa: E501
        upload_workspace_1 = factories.UploadWorkspaceFactory.create()
        factories.UploadWorkspaceFactory.create_batch(2)
        example_workspace_1 = factories.ResourceWorkspaceFactory.create()
        example_workspace_2 = factories.ResourceWorkspaceFactory.create()
        factories.ResourceWorkspaceFactory.create_batch(3)
        group = acm_factories.ManagedGroupFactory.create(name="GREGOR_ALL")
        acm_factories.WorkspaceGroupSharingFactory.create(workspace=upload_workspace_1.workspace, group=group)
        acm_factories.WorkspaceGroupSharingFactory.create(workspace=example_workspace_1.workspace, group=group)
        acm_factories.WorkspaceGroupSharingFactory.create(workspace=example_workspace_2.workspace, group=group)
        self.client.force_login(self.user)
        response = self.client.get(self.get_url())
        # workspace table
        self.assertIn("workspace_count_table", response.context_data)
        table = response.context_data["workspace_count_table"]
        self.assertEqual(len(table.data), 2)
        self.assertIn({"workspace_type": "upload", "n_total": 3, "n_shared": 1}, table.data)
        self.assertIn({"workspace_type": "resource", "n_total": 5, "n_shared": 2}, table.data)

    def test_workspace_count_table_one_workspace_shared_twice(self):
        """Workspace table includes correct values for one workspace  that has been shared twice."""  # noqa: E501
        upload_workspace_1 = factories.UploadWorkspaceFactory.create()
        # Create the sharing record with GREGOR_ALL.
        acm_factories.WorkspaceGroupSharingFactory.create(
            workspace=upload_workspace_1.workspace, group__name="GREGOR_ALL"
        )
        # Create a sharing record with another group.
        acm_factories.WorkspaceGroupSharingFactory.create(workspace=upload_workspace_1.workspace)
        self.client.force_login(self.user)
        response = self.client.get(self.get_url())
        # workspace table
        self.assertIn("workspace_count_table", response.context_data)
        table = response.context_data["workspace_count_table"]
        self.assertEqual(len(table.data), 1)
        self.assertIn({"workspace_type": "upload", "n_total": 1, "n_shared": 1}, table.data)

    def test_has_no_workspace_when_shared_with_different_group_in_context(self):
        upload_workspace = factories.UploadWorkspaceFactory.create()
        group = acm_factories.ManagedGroupFactory.create(name="ANOTHER_GROUP")
        acm_factories.WorkspaceGroupSharingFactory.create(workspace=upload_workspace.workspace, group=group)
        self.client.force_login(self.user)
        response = self.client.get(self.get_url())
        table = response.context_data["workspace_count_table"]
        self.assertEqual(len(table.data), 1)
        self.assertIn({"workspace_type": "upload", "n_total": 1, "n_shared": 0}, table.data)

    def test_no_consortium_members_with_access_to_workspaces_in_context(self):
        """Response includes no consortium members with access to any workspaces in context"""
        self.client.force_login(self.user)
        response = self.client.get(self.get_url())
        self.assertTrue("verified_linked_accounts" in response.context_data)
        self.assertEqual(response.context_data["verified_linked_accounts"], 0)

    def test_one_consortium_member_with_access_to_workspaces_in_context(self):
        """Response includes one consortium member with access to any workspaces in context"""
        acm_factories.AccountFactory.create(user=self.user, verified=True)
        self.client.force_login(self.user)
        response = self.client.get(self.get_url())
        self.assertTrue("verified_linked_accounts" in response.context_data)
        self.assertEqual(response.context_data["verified_linked_accounts"], 1)

    def test_two_consortium_members_with_access_to_workspaces_in_context(self):
        """Response includes two consortium members with access to any workspaces in context"""
        acm_factories.AccountFactory.create(user=self.user, verified=True)
        another_user = User.objects.create_user(username="another_user", password="another_user")
        acm_factories.AccountFactory.create(user=another_user, verified=True)
        self.client.force_login(self.user)
        response = self.client.get(self.get_url())
        self.assertTrue("verified_linked_accounts" in response.context_data)
        self.assertEqual(response.context_data["verified_linked_accounts"], 2)

    def test_correct_count_consortium_members_with_access_to_workspaces_in_context(
        self,
    ):
        """Response includes only verified linked account in context"""
        acm_factories.AccountFactory.create(user=self.user, verified=True)
        another_user = User.objects.create_user(username="another_user", password="another_user")
        acm_factories.AccountFactory.create(user=another_user, verified=False)
        self.client.force_login(self.user)
        response = self.client.get(self.get_url())
        self.assertTrue("verified_linked_accounts" in response.context_data)
        self.assertEqual(response.context_data["verified_linked_accounts"], 1)


class DCCProcessingWorkspaceDetailTest(TestCase):
    """Tests of the anvil_consortium_manager WorkspaceDetail view using the DCCProcessingWorkspace adapter."""

    def setUp(self):
        """Set up test class."""
        self.factory = RequestFactory()
        # Create a user with both view and edit permission.
        self.user = User.objects.create_user(username="test", password="test")
        self.user.user_permissions.add(
            Permission.objects.get(codename=acm_models.AnVILProjectManagerAccess.STAFF_VIEW_PERMISSION_CODENAME)
        )
        self.object = factories.DCCProcessingWorkspaceFactory.create()

    def get_url(self, *args):
        """Get the url for the view being tested."""
        return reverse("anvil_consortium_manager:workspaces:detail", args=args)

    def test_status_code(self):
        """Response has a status code of 200."""
        self.client.force_login(self.user)
        response = self.client.get(self.get_url(self.object.workspace.billing_project.name, self.object.workspace.name))
        self.assertEqual(response.status_code, 200)


class DCCProcessedDataWorkspaceDetailTest(TestCase):
    """Tests of the anvil_consortium_manager WorkspaceDetail view using the DCCProcessedDataWorkspace adapter."""

    def setUp(self):
        """Set up test class."""
        self.factory = RequestFactory()
        # Create a user with both view and edit permission.
        self.user = User.objects.create_user(username="test", password="test")
        self.user.user_permissions.add(
            Permission.objects.get(codename=acm_models.AnVILProjectManagerAccess.STAFF_VIEW_PERMISSION_CODENAME)
        )
        self.object = factories.DCCProcessedDataWorkspaceFactory.create()

    def get_url(self, *args):
        """Get the url for the view being tested."""
        return reverse("anvil_consortium_manager:workspaces:detail", args=args)

    def test_status_code(self):
        """Response has a status code of 200."""
        self.client.force_login(self.user)
        response = self.client.get(self.get_url(self.object.workspace.billing_project.name, self.object.workspace.name))
        self.assertEqual(response.status_code, 200)


class ExchangeWorkspaceDetailTest(TestCase):
    """Tests of the anvil_consortium_manager WorkspaceDetail view using the ExchangeWorkspace adapter."""

    def setUp(self):
        """Set up test class."""
        self.factory = RequestFactory()
        # Create a user with both view and edit permission.
        self.user = User.objects.create_user(username="test", password="test")
        self.user.user_permissions.add(
            Permission.objects.get(codename=acm_models.AnVILProjectManagerAccess.STAFF_VIEW_PERMISSION_CODENAME)
        )
        self.user.user_permissions.add(
            Permission.objects.get(codename=acm_models.AnVILProjectManagerAccess.STAFF_EDIT_PERMISSION_CODENAME)
        )
        self.object = factories.ExchangeWorkspaceFactory.create()

    def get_url(self, *args):
        """Get the url for the view being tested."""
        return reverse("anvil_consortium_manager:workspaces:detail", args=args)

    def test_status_code(self):
        """Response has a status code of 200."""
        self.client.force_login(self.user)
        response = self.client.get(self.get_url(self.object.workspace.billing_project.name, self.object.workspace.name))
        self.assertEqual(response.status_code, 200)


class ExchangeWorkspaceListTest(TestCase):
    """Tests of the anvil_consortium_manager WorkspaceList view using this app's adapter."""

    def setUp(self):
        """Set up test class."""
        self.factory = RequestFactory()
        # Create a user with both view and edit permission.
        self.user = User.objects.create_user(username="test", password="test")
        self.user.user_permissions.add(
            Permission.objects.get(codename=acm_models.AnVILProjectManagerAccess.STAFF_VIEW_PERMISSION_CODENAME)
        )
        self.workspace_type = "exchange"

    def get_url(self, *args):
        """Get the url for the view being tested."""
        return reverse("anvil_consortium_manager:workspaces:list", args=args)

    def test_view_has_correct_table_class(self):
        """The view has the correct table class in the context."""
        self.client.force_login(self.user)
        response = self.client.get(self.get_url(self.workspace_type))
        self.assertIn("table", response.context_data)
        self.assertIsInstance(response.context_data["table"], tables.ExchangeWorkspaceTable)


class ExchangeWorkspaceCreateTest(AnVILAPIMockTestMixin, TestCase):
    """Tests of the WorkspaceCreate view from ACM with extra ExchangeWorkspace model."""

    api_success_code = 201

    def setUp(self):
        """Set up test class."""
        # The superclass uses the responses package to mock API responses.
        super().setUp()
        # Create a user with both view and edit permissions.
        self.user = User.objects.create_user(username="test", password="test")
        self.user.user_permissions.add(
            Permission.objects.get(codename=acm_models.AnVILProjectManagerAccess.STAFF_VIEW_PERMISSION_CODENAME)
        )
        self.user.user_permissions.add(
            Permission.objects.get(codename=acm_models.AnVILProjectManagerAccess.STAFF_EDIT_PERMISSION_CODENAME)
        )
        self.workspace_type = "exchange"
        # Create the admins group.
        self.admins_group = acm_factories.ManagedGroupFactory.create(name=settings.ANVIL_DCC_ADMINS_GROUP_NAME)

    def get_url(self, *args):
        """Get the url for the view being tested."""
        return reverse("anvil_consortium_manager:workspaces:new", args=args)

    def test_creates_upload_workspace(self):
        """Posting valid data to the form creates a workspace data object when using a custom adapter."""
        research_center = factories.ResearchCenterFactory.create()
        billing_project = acm_factories.BillingProjectFactory.create(name="test-billing-project")
        url = self.api_client.rawls_entry_point + "/api/workspaces"
        json_data = {
            "namespace": "test-billing-project",
            "name": "test-workspace",
            "attributes": {},
        }
        self.anvil_response_mock.add(
            responses.POST,
            url,
            status=self.api_success_code,
            match=[responses.matchers.json_params_matcher(json_data)],
        )
        # API response for GREGOR admins workspace owner.
        acls = [
            {
                "email": "TEST_GREGOR_DCC_ADMINS@firecloud.org",
                "accessLevel": "OWNER",
                "canShare": False,
                "canCompute": True,
            }
        ]
        self.anvil_response_mock.add(
            responses.PATCH,
            self.api_client.rawls_entry_point
            + "/api/workspaces/test-billing-project/test-workspace/acl?inviteUsersNotFound=false",
            status=200,
            match=[responses.matchers.json_params_matcher(acls)],
            json={"invitesSent": {}, "usersNotFound": {}, "usersUpdated": acls},
        )
        self.client.force_login(self.user)
        response = self.client.post(
            self.get_url(self.workspace_type),
            {
                "billing_project": billing_project.pk,
                "name": "test-workspace",
                # Workspace data form.
                "workspacedata-TOTAL_FORMS": 1,
                "workspacedata-INITIAL_FORMS": 0,
                "workspacedata-MIN_NUM_FORMS": 1,
                "workspacedata-MAX_NUM_FORMS": 1,
                "workspacedata-0-research_center": research_center.pk,
            },
        )
        self.assertEqual(response.status_code, 302)
        # The workspace is created.
        new_workspace = acm_models.Workspace.objects.latest("pk")
        # Workspace data is added.
        self.assertEqual(models.ExchangeWorkspace.objects.count(), 1)
        new_workspace_data = models.ExchangeWorkspace.objects.latest("pk")
        self.assertEqual(new_workspace_data.workspace, new_workspace)
        self.assertEqual(new_workspace_data.research_center, research_center)


class ManagedGroupCreateTest(AnVILAPIMockTestMixin, TestCase):
    """Tests for custom ManagedGroup behavior."""

    def get_url(self, *args):
        """Get the url for the view being tested."""
        return reverse("anvil_consortium_manager:managed_groups:new", args=args)

    def setUp(self):
        """Set up test class."""
        # The superclass uses the responses package to mock API responses.
        super().setUp()
        self.factory = RequestFactory()
        # Create a user with both view and edit permissions.
        self.user = User.objects.create_user(username="test", password="test")
        self.user.user_permissions.add(
            Permission.objects.get(codename=acm_models.AnVILProjectManagerAccess.STAFF_VIEW_PERMISSION_CODENAME)
        )
        self.user.user_permissions.add(
            Permission.objects.get(codename=acm_models.AnVILProjectManagerAccess.STAFF_EDIT_PERMISSION_CODENAME)
        )
        # Create the admins group.
        self.admins_group = acm_factories.ManagedGroupFactory.create(name="TEST_GREGOR_DCC_ADMINS")

    def test_cc_admins_membership(self):
        """The after_anvil_create method is run after a managed group is created."""
        # API response for group creation.
        api_url = self.api_client.sam_entry_point + "/api/groups/v1/test-group"
        self.anvil_response_mock.add(responses.POST, api_url, status=201)
        # API response for auth domain PRIMED_ADMINS membership.
        self.anvil_response_mock.add(
            responses.PUT,
            self.api_client.sam_entry_point + "/api/groups/v1/test-group/admin/TEST_GREGOR_DCC_ADMINS@firecloud.org",
            status=204,
        )
        # Submit the form to django.
        self.client.force_login(self.user)
        response = self.client.post(self.get_url(), {"name": "test-group"})
        self.assertEqual(response.status_code, 302)
        # Check that the admin group was added.
        new_group = acm_models.ManagedGroup.objects.latest("pk")
        self.assertEqual(acm_models.GroupGroupMembership.objects.count(), 1)
        membership = acm_models.GroupGroupMembership.objects.first()
        self.assertEqual(membership.parent_group, new_group)
        self.assertEqual(membership.child_group, self.admins_group)
        self.assertEqual(membership.role, acm_models.GroupGroupMembership.ADMIN)
