import json
from datetime import date, timedelta
from unittest import skip

import responses
from anvil_consortium_manager import models as acm_models
from anvil_consortium_manager.models import AnVILProjectManagerAccess
from anvil_consortium_manager.tests import factories as acm_factories
from anvil_consortium_manager.tests.api_factories import ErrorResponseFactory
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
from django.utils import timezone
from freezegun import freeze_time

from gregor_django.users.tables import UserTable
from gregor_django.users.tests.factories import UserFactory

from .. import forms, models, tables, views
from ..audit import (
    combined_workspace_audit,
    upload_workspace_audit,
    workspace_auth_domain_audit_results,
    workspace_sharing_audit_results,
)
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

    def test_link_to_non_member_group(self):
        """Response includes a link to the non-members group if it exists."""
        non_member_group = acm_factories.ManagedGroupFactory.create()
        obj = self.model_factory.create(non_member_group=non_member_group)
        self.client.force_login(self.user)
        response = self.client.get(self.get_url(obj.pk))
        self.assertContains(response, non_member_group.get_absolute_url())

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
        self.assertIsInstance(response.context_data["form"], forms.UploadCycleCreateForm)

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


class UploadCycleUpdateTest(TestCase):
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
        return reverse("gregor_anvil:upload_cycles:update", args=args)

    def get_view(self):
        """Return the view being tested."""
        return views.UploadCycleUpdate.as_view()

    def test_view_redirect_not_logged_in(self):
        "View redirects to login view when user is not logged in."
        # Need a client for redirects.
        response = self.client.get(self.get_url(1))
        self.assertRedirects(response, resolve_url(settings.LOGIN_URL) + "?next=" + self.get_url(1))

    def test_status_code_with_user_permission(self):
        """Returns successful response code."""
        obj = factories.UploadCycleFactory.create()
        self.client.force_login(self.user)
        response = self.client.get(self.get_url(obj.cycle))
        self.assertEqual(response.status_code, 200)

    def test_access_with_view_permission(self):
        """Raises permission denied if user has only view permission."""
        user_with_view_perm = User.objects.create_user(username="test-other", password="test-other")
        user_with_view_perm.user_permissions.add(
            Permission.objects.get(codename=AnVILProjectManagerAccess.STAFF_VIEW_PERMISSION_CODENAME)
        )
        request = self.factory.get(self.get_url(1))
        request.user = user_with_view_perm
        with self.assertRaises(PermissionDenied):
            self.get_view()(request, pk=1)

    def test_access_without_user_permission(self):
        """Raises permission denied if user has no permissions."""
        user_no_perms = User.objects.create_user(username="test-none", password="test-none")
        request = self.factory.get(self.get_url(1))
        request.user = user_no_perms
        with self.assertRaises(PermissionDenied):
            self.get_view()(request, pk=1)

    def test_has_form_in_context(self):
        """Response includes a form."""
        obj = factories.UploadCycleFactory.create()
        self.client.force_login(self.user)
        response = self.client.get(self.get_url(obj.cycle))
        self.assertTrue("form" in response.context_data)
        self.assertIsInstance(response.context_data["form"], forms.UploadCycleUpdateForm)

    def test_can_update_an_object(self):
        """Posting valid data to the form creates an object."""
        obj = factories.UploadCycleFactory.create(is_current=True)
        self.client.force_login(self.user)
        response = self.client.post(
            self.get_url(obj.cycle),
            {
                "start_date": obj.start_date,
                "end_date": obj.end_date,
                "date_ready_for_compute": timezone.localdate(),
                "note": "",
            },
        )
        self.assertEqual(response.status_code, 302)
        self.assertEqual(models.UploadCycle.objects.count(), 1)
        obj.refresh_from_db()
        self.assertEqual(obj.date_ready_for_compute, timezone.localdate())
        # History is added.
        self.assertEqual(obj.history.count(), 2)
        self.assertEqual(obj.history.latest().history_type, "~")

    def test_success_message(self):
        """Response includes a success message if successful."""
        obj = factories.UploadCycleFactory.create(is_current=True)
        self.client.force_login(self.user)
        response = self.client.post(
            self.get_url(obj.cycle),
            {
                "start_date": obj.start_date,
                "end_date": obj.end_date,
                "date_ready_for_compute": timezone.localdate(),
                "note": "",
            },
        )
        self.assertEqual(response.status_code, 302)
        messages = [m.message for m in get_messages(response.wsgi_request)]
        self.assertEqual(len(messages), 1)
        self.assertEqual(views.UploadCycleUpdate.success_message, str(messages[0]))

    def test_redirects_to_object_detail(self):
        """After successfully creating an object, view redirects to the object's detail page."""
        obj = factories.UploadCycleFactory.create(is_current=True)
        self.client.force_login(self.user)
        response = self.client.post(
            self.get_url(obj.cycle),
            {
                "start_date": obj.start_date,
                "end_date": obj.end_date,
                "date_ready_for_compute": timezone.localdate(),
                "note": "",
            },
        )
        self.assertRedirects(response, obj.get_absolute_url())

    def test_object_does_not_exist(self):
        """Raises 404 when object doesn't exist."""
        request = self.factory.get(self.get_url(1))
        request.user = self.user
        with self.assertRaises(Http404):
            self.get_view()(request, pk=1)

    def test_invalid_input(self):
        """Posting invalid data does not create an object."""
        obj = factories.UploadCycleFactory.create(is_current=True)
        self.client.force_login(self.user)
        response = self.client.post(
            self.get_url(obj.cycle),
            {"start_date": self.start_date, "end_date": self.end_date, "date_ready_for_compute": "foo"},
        )
        self.assertEqual(response.status_code, 200)
        form = response.context_data["form"]
        self.assertFalse(form.is_valid())
        self.assertEqual(len(form.errors.keys()), 1)
        self.assertIn("date_ready_for_compute", form.errors.keys())
        self.assertEqual(len(form.errors["date_ready_for_compute"]), 1)
        obj.refresh_from_db()
        self.assertIsNone(obj.date_ready_for_compute)

    def test_post_blank_data_ready_for_compute(self):
        """Can successfully post blank data for date_ready_for_compute."""
        obj = factories.UploadCycleFactory.create(is_current=True)
        start_date = obj.start_date
        end_date = obj.end_date
        self.client.force_login(self.user)
        response = self.client.post(
            self.get_url(obj.cycle),
            {
                "start_date": start_date + timedelta(days=1),
                "end_date": end_date + timedelta(days=1),
            },
        )
        self.assertEqual(response.status_code, 302)
        obj.refresh_from_db()
        self.assertEqual(obj.start_date, start_date + timedelta(days=1))
        self.assertEqual(obj.end_date, end_date + timedelta(days=1))
        self.assertIsNone(obj.date_ready_for_compute)


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

    def test_link_to_audit(self):
        """Response includes a link to the audit page."""
        obj = self.model_factory.create()
        self.client.force_login(self.user)
        response = self.client.get(self.get_url(obj.cycle))
        self.assertContains(
            response, reverse("gregor_anvil:audit:upload_workspaces:sharing:by_upload_cycle", args=[obj.cycle])
        )

    def test_link_to_update_view_staff_edit(self):
        """Response includes a link to the update view for staff edit users."""
        obj = self.model_factory.create()
        self.user.user_permissions.add(
            Permission.objects.get(codename=acm_models.AnVILProjectManagerAccess.STAFF_EDIT_PERMISSION_CODENAME)
        )
        self.client.force_login(self.user)
        response = self.client.get(self.get_url(obj.cycle))
        self.assertContains(response, reverse("gregor_anvil:upload_cycles:update", args=[obj.cycle]))

    def test_link_to_update_view_staff_view(self):
        """Response includes a link to the update view for staff edit users."""
        obj = self.model_factory.create()
        self.client.force_login(self.user)
        response = self.client.get(self.get_url(obj.cycle))
        self.assertNotContains(response, reverse("gregor_anvil:upload_cycles:update", args=[obj.cycle]))

    def test_contains_sharing_audit_button(self):
        obj = self.model_factory.create()
        self.client.force_login(self.user)
        response = self.client.get(self.get_url(obj.cycle))
        url = reverse("gregor_anvil:audit:upload_workspaces:sharing:by_upload_cycle", args=[obj.cycle])
        self.assertContains(response, url)

    def test_contains_auth_domain_audit_button(self):
        obj = self.model_factory.create()
        self.client.force_login(self.user)
        response = self.client.get(self.get_url(obj.cycle))
        url = reverse("gregor_anvil:audit:upload_workspaces:auth_domains:by_upload_cycle", args=[obj.cycle])
        self.assertContains(response, url)

    def test_includes_date_ready_for_compute(self):
        obj = self.model_factory.create(is_past=True, date_ready_for_compute="2022-01-01")
        self.client.force_login(self.user)
        response = self.client.get(self.get_url(obj.cycle))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Jan. 1, 2022")


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

    def test_contains_sharing_audit_button(self):
        self.client.force_login(self.user)
        response = self.client.get(self.get_url(self.object.workspace.billing_project.name, self.object.workspace.name))
        url = reverse(
            "gregor_anvil:audit:upload_workspaces:sharing:by_upload_workspace",
            args=[
                self.object.workspace.billing_project.name,
                self.object.workspace.name,
            ],
        )
        self.assertContains(response, url)

    def test_contains_auth_domain_audit_button(self):
        self.client.force_login(self.user)
        response = self.client.get(self.get_url(self.object.workspace.billing_project.name, self.object.workspace.name))
        url = reverse(
            "gregor_anvil:audit:upload_workspaces:auth_domains:by_upload_workspace",
            args=[
                self.object.workspace.billing_project.name,
                self.object.workspace.name,
            ],
        )
        self.assertContains(response, url)

    def test_includes_date_qc_completed(self):
        self.object.date_qc_completed = "2022-01-01"
        self.object.save()
        self.client.force_login(self.user)
        response = self.client.get(self.get_url(self.object.workspace.billing_project.name, self.object.workspace.name))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Jan. 1, 2022")


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

    def test_includes_date_completed(self):
        self.object.date_completed = "2022-01-01"
        self.object.save()
        self.client.force_login(self.user)
        response = self.client.get(self.get_url(self.object.workspace.billing_project.name, self.object.workspace.name))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Jan. 1, 2022")


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


class UploadWorkspaceSharingAuditTest(AnVILAPIMockTestMixin, TestCase):
    """Tests for the UploadWorkspaceSharingAudit view."""

    def setUp(self):
        """Set up test class."""
        super().setUp()
        self.factory = RequestFactory()
        # Create a user with both view and edit permission.
        self.user = User.objects.create_user(username="test", password="test")
        self.user.user_permissions.add(
            Permission.objects.get(codename=AnVILProjectManagerAccess.STAFF_VIEW_PERMISSION_CODENAME)
        )

    def get_url(self, *args):
        """Get the url for the view being tested."""
        return reverse(
            "gregor_anvil:audit:upload_workspaces:sharing:all",
            args=args,
        )

    def get_view(self):
        """Return the view being tested."""
        return views.UploadWorkspaceSharingAudit.as_view()

    def test_view_redirect_not_logged_in(self):
        "View redirects to login view when user is not logged in."
        # Need a client for redirects.
        response = self.client.get(self.get_url())
        self.assertRedirects(
            response,
            resolve_url(settings.LOGIN_URL) + "?next=" + self.get_url(),
        )

    def test_status_code_with_user_permission_view(self):
        """Returns successful response code if the user has view permission."""
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

    def test_context_audit_results_no_upload_workspaces(self):
        """The audit_results exists in the context."""
        self.client.force_login(self.user)
        response = self.client.get(self.get_url())
        self.assertIn("audit_results", response.context_data)
        audit_results = response.context_data["audit_results"]
        self.assertIsInstance(
            audit_results,
            upload_workspace_audit.UploadWorkspaceSharingAudit,
        )
        self.assertTrue(audit_results.completed)
        self.assertEqual(audit_results.queryset.count(), 0)

    def test_context_audit_results_one_upload_workspace(self):
        """The audit_results exists in the context."""
        upload_workspace = factories.UploadWorkspaceFactory.create()
        self.client.force_login(self.user)
        response = self.client.get(self.get_url())
        self.assertIn("audit_results", response.context_data)
        audit_results = response.context_data["audit_results"]
        self.assertIsInstance(
            audit_results,
            upload_workspace_audit.UploadWorkspaceSharingAudit,
        )
        self.assertTrue(audit_results.completed)
        self.assertEqual(audit_results.queryset.count(), 1)
        self.assertIn(upload_workspace, audit_results.queryset)

    def test_context_audit_results_two_upload_workspaces(self):
        """The audit_results exists in the context."""
        upload_workspace_1 = factories.UploadWorkspaceFactory.create()
        upload_workspace_2 = factories.UploadWorkspaceFactory.create()
        self.client.force_login(self.user)
        response = self.client.get(self.get_url())
        self.assertIn("audit_results", response.context_data)
        audit_results = response.context_data["audit_results"]
        self.assertIsInstance(
            audit_results,
            upload_workspace_audit.UploadWorkspaceSharingAudit,
        )
        self.assertTrue(audit_results.completed)
        self.assertEqual(audit_results.queryset.count(), 2)
        self.assertIn(upload_workspace_1, audit_results.queryset)
        self.assertIn(upload_workspace_2, audit_results.queryset)

    def test_context_verified_table_access(self):
        """verified_table shows a record when audit has verified access."""
        upload_workspace = factories.UploadWorkspaceFactory.create()
        group = acm_factories.ManagedGroupFactory.create(name=settings.ANVIL_DCC_ADMINS_GROUP_NAME)
        acm_factories.WorkspaceGroupSharingFactory.create(
            workspace=upload_workspace.workspace, group=group, access=acm_models.WorkspaceGroupSharing.OWNER
        )
        # Check the table in the context.
        self.client.force_login(self.user)
        response = self.client.get(self.get_url())
        self.assertIn("verified_table", response.context_data)
        table = response.context_data["verified_table"]
        self.assertIsInstance(
            table,
            upload_workspace_audit.UploadWorkspaceSharingAuditTable,
        )
        self.assertEqual(len(table.rows), 1)
        self.assertEqual(table.rows[0].get_cell_value("workspace"), upload_workspace.workspace)
        self.assertEqual(table.rows[0].get_cell_value("managed_group"), group)
        self.assertEqual(table.rows[0].get_cell_value("access"), acm_models.WorkspaceGroupSharing.OWNER)
        self.assertEqual(
            table.rows[0].get_cell_value("note"),
            upload_workspace_audit.UploadWorkspaceSharingAudit.DCC_ADMIN_AS_OWNER,
        )
        self.assertEqual(table.rows[0].get_cell_value("action"), "&mdash;")

    def test_context_needs_action_table_share_as_reader(self):
        """needs_action_table shows a record when audit finds that access needs to be granted."""
        upload_workspace = factories.UploadWorkspaceFactory.create()
        group = upload_workspace.workspace.authorization_domains.first()
        # Check the table in the context.
        self.client.force_login(self.user)
        response = self.client.get(self.get_url())
        self.assertIn("needs_action_table", response.context_data)
        table = response.context_data["needs_action_table"]
        self.assertIsInstance(
            table,
            upload_workspace_audit.UploadWorkspaceSharingAuditTable,
        )
        self.assertEqual(len(table.rows), 1)
        self.assertEqual(table.rows[0].get_cell_value("workspace"), upload_workspace.workspace)
        self.assertEqual(table.rows[0].get_cell_value("managed_group"), group)
        self.assertIsNone(table.rows[0].get_cell_value("access"))
        self.assertEqual(
            table.rows[0].get_cell_value("note"),
            upload_workspace_audit.UploadWorkspaceSharingAudit.AUTH_DOMAIN_AS_READER,
        )
        self.assertNotEqual(table.rows[0].get_cell_value("action"), "&mdash;")

    def test_context_needs_action_table_share_as_writer(self):
        """needs_action_table shows a record when audit finds that access needs to be granted."""
        group = acm_factories.ManagedGroupFactory.create()
        upload_workspace = factories.UploadWorkspaceFactory.create(
            upload_cycle__is_current=True,
            research_center__uploader_group=group,
        )
        # Share with the auth domain to prevent that audit error.
        acm_factories.WorkspaceGroupSharingFactory.create(
            workspace=upload_workspace.workspace,
            group=upload_workspace.workspace.authorization_domains.first(),
            access=acm_models.WorkspaceGroupSharing.READER,
        )
        # Check the table in the context.
        self.client.force_login(self.user)
        response = self.client.get(self.get_url())
        self.assertIn("needs_action_table", response.context_data)
        table = response.context_data["needs_action_table"]
        self.assertIsInstance(
            table,
            upload_workspace_audit.UploadWorkspaceSharingAuditTable,
        )
        self.assertEqual(len(table.rows), 1)
        self.assertEqual(table.rows[0].get_cell_value("workspace"), upload_workspace.workspace)
        self.assertEqual(table.rows[0].get_cell_value("managed_group"), group)
        self.assertIsNone(table.rows[0].get_cell_value("access"))
        self.assertEqual(
            table.rows[0].get_cell_value("note"),
            upload_workspace_audit.UploadWorkspaceSharingAudit.RC_UPLOADERS_CURRENT_CYCLE_BEFORE_COMPUTE,
        )
        self.assertNotEqual(table.rows[0].get_cell_value("action"), "&mdash;")

    def test_context_needs_action_table_share_with_compute(self):
        """needs_action_table shows a record when audit finds that access needs to be granted."""
        upload_workspace = factories.UploadWorkspaceFactory.create(upload_cycle__is_future=True)
        group = acm_factories.ManagedGroupFactory.create(name="GREGOR_DCC_WRITERS")
        # Share with the auth domain to prevent that audit error.
        acm_factories.WorkspaceGroupSharingFactory.create(
            workspace=upload_workspace.workspace,
            group=upload_workspace.workspace.authorization_domains.first(),
            access=acm_models.WorkspaceGroupSharing.READER,
        )
        # Check the table in the context.
        self.client.force_login(self.user)
        response = self.client.get(self.get_url())
        self.assertIn("needs_action_table", response.context_data)
        table = response.context_data["needs_action_table"]
        self.assertIsInstance(
            table,
            upload_workspace_audit.UploadWorkspaceSharingAuditTable,
        )
        self.assertEqual(len(table.rows), 1)
        self.assertEqual(table.rows[0].get_cell_value("workspace"), upload_workspace.workspace)
        self.assertEqual(table.rows[0].get_cell_value("managed_group"), group)
        self.assertIsNone(table.rows[0].get_cell_value("access"))
        self.assertEqual(
            table.rows[0].get_cell_value("note"),
            upload_workspace_audit.UploadWorkspaceSharingAudit.DCC_WRITERS_FUTURE_CYCLE,
        )
        self.assertNotEqual(table.rows[0].get_cell_value("action"), "&mdash;")

    def test_context_needs_action_table_share_as_owner(self):
        """needs_action_table shows a record when audit finds that access needs to be granted."""
        upload_workspace = factories.UploadWorkspaceFactory.create()
        group = acm_factories.ManagedGroupFactory.create(name=settings.ANVIL_DCC_ADMINS_GROUP_NAME)
        # Share with the auth domain to prevent that audit error.
        acm_factories.WorkspaceGroupSharingFactory.create(
            workspace=upload_workspace.workspace,
            group=upload_workspace.workspace.authorization_domains.first(),
            access=acm_models.WorkspaceGroupSharing.READER,
        )
        # Check the table in the context.
        self.client.force_login(self.user)
        response = self.client.get(self.get_url())
        self.assertIn("needs_action_table", response.context_data)
        table = response.context_data["needs_action_table"]
        self.assertIsInstance(
            table,
            upload_workspace_audit.UploadWorkspaceSharingAuditTable,
        )
        self.assertEqual(len(table.rows), 1)
        self.assertEqual(table.rows[0].get_cell_value("workspace"), upload_workspace.workspace)
        self.assertEqual(table.rows[0].get_cell_value("managed_group"), group)
        self.assertIsNone(table.rows[0].get_cell_value("access"))
        self.assertEqual(
            table.rows[0].get_cell_value("note"),
            upload_workspace_audit.UploadWorkspaceSharingAudit.DCC_ADMIN_AS_OWNER,
        )
        self.assertNotEqual(table.rows[0].get_cell_value("action"), "&mdash;")

    def test_context_needs_action_table_stop_sharing(self):
        """needs_action_table shows a record when audit finds that access needs to be granted."""
        # Change upload workspace end dates so it's in the past.
        group = acm_factories.ManagedGroupFactory.create()
        upload_workspace = factories.UploadWorkspaceFactory.create(
            upload_cycle__is_past=True,
            research_center__uploader_group=group,
            date_qc_completed=timezone.localdate() - timedelta(days=1),
        )
        # Create a sharing record.
        acm_factories.WorkspaceGroupSharingFactory.create(
            workspace=upload_workspace.workspace,
            group=group,
            access=acm_models.WorkspaceGroupSharing.READER,
        )
        # Share with the auth domain to prevent that audit error.
        acm_factories.WorkspaceGroupSharingFactory.create(
            workspace=upload_workspace.workspace,
            group=upload_workspace.workspace.authorization_domains.first(),
            access=acm_models.WorkspaceGroupSharing.READER,
        )
        # Check the table in the context.
        self.client.force_login(self.user)
        response = self.client.get(self.get_url())
        self.assertIn("needs_action_table", response.context_data)
        table = response.context_data["needs_action_table"]
        self.assertIsInstance(
            table,
            upload_workspace_audit.UploadWorkspaceSharingAuditTable,
        )
        self.assertEqual(len(table.rows), 1)
        self.assertEqual(table.rows[0].get_cell_value("workspace"), upload_workspace.workspace)
        self.assertEqual(table.rows[0].get_cell_value("managed_group"), group)
        self.assertEqual(table.rows[0].get_cell_value("access"), "READER")
        self.assertEqual(
            table.rows[0].get_cell_value("note"),
            upload_workspace_audit.UploadWorkspaceSharingAudit.RC_UPLOADERS_PAST_CYCLE_AFTER_QC_COMPLETE,
        )
        self.assertNotEqual(table.rows[0].get_cell_value("action"), "&mdash;")

    def test_context_error_table_stop_sharing(self):
        """error_table shows a record when an audit error is detected."""
        upload_workspace = factories.UploadWorkspaceFactory.create()
        group = acm_factories.ManagedGroupFactory.create()
        # Create a sharing record.
        acm_factories.WorkspaceGroupSharingFactory.create(
            workspace=upload_workspace.workspace,
            group=group,
            access=acm_models.WorkspaceGroupSharing.READER,
        )
        # Share with the auth domain to prevent that audit error.
        acm_factories.WorkspaceGroupSharingFactory.create(
            workspace=upload_workspace.workspace,
            group=upload_workspace.workspace.authorization_domains.first(),
            access=acm_models.WorkspaceGroupSharing.READER,
        )
        # Check the table in the context.
        self.client.force_login(self.user)
        response = self.client.get(self.get_url())
        self.assertIn("errors_table", response.context_data)
        table = response.context_data["errors_table"]
        self.assertIsInstance(
            table,
            upload_workspace_audit.UploadWorkspaceSharingAuditTable,
        )
        self.assertEqual(len(table.rows), 1)
        self.assertEqual(table.rows[0].get_cell_value("workspace"), upload_workspace.workspace)
        self.assertEqual(table.rows[0].get_cell_value("managed_group"), group)
        self.assertEqual(table.rows[0].get_cell_value("access"), "READER")
        self.assertEqual(
            table.rows[0].get_cell_value("note"),
            upload_workspace_audit.UploadWorkspaceSharingAudit.OTHER_GROUP_NO_ACCESS,
        )
        self.assertNotEqual(table.rows[0].get_cell_value("action"), "&mdash;")

    def test_title(self):
        self.client.force_login(self.user)
        response = self.client.get(self.get_url())
        # self.assertContains(response, str(self.upload_workspace))
        self.assertIn("all upload workspaces", response.content.decode().lower())


class UploadWorkspaceSharingAuditByWorkspaceTest(AnVILAPIMockTestMixin, TestCase):
    """Tests for the UploadWorkspaceSharingAuditByWorkspace view."""

    def setUp(self):
        """Set up test class."""
        super().setUp()
        self.factory = RequestFactory()
        # Create a user with both view and edit permission.
        self.user = User.objects.create_user(username="test", password="test")
        self.user.user_permissions.add(
            Permission.objects.get(codename=AnVILProjectManagerAccess.STAFF_VIEW_PERMISSION_CODENAME)
        )
        self.upload_workspace = factories.UploadWorkspaceFactory.create(upload_cycle__is_future=True)

    def get_url(self, *args):
        """Get the url for the view being tested."""
        return reverse(
            "gregor_anvil:audit:upload_workspaces:sharing:by_upload_workspace",
            args=args,
        )

    def get_view(self):
        """Return the view being tested."""
        return views.UploadWorkspaceSharingAuditByWorkspace.as_view()

    def test_view_redirect_not_logged_in(self):
        "View redirects to login view when user is not logged in."
        # Need a client for redirects.
        response = self.client.get(self.get_url("foo", "bar"))
        self.assertRedirects(
            response,
            resolve_url(settings.LOGIN_URL) + "?next=" + self.get_url("foo", "bar"),
        )

    def test_status_code_with_user_permission_view(self):
        """Returns successful response code if the user has view permission."""
        self.client.force_login(self.user)
        response = self.client.get(
            self.get_url(
                self.upload_workspace.workspace.billing_project.name,
                self.upload_workspace.workspace.name,
            )
        )
        self.assertEqual(response.status_code, 200)

    def test_access_without_user_permission(self):
        """Raises permission denied if user has no permissions."""
        user_no_perms = User.objects.create_user(username="test-none", password="test-none")
        request = self.factory.get(
            self.get_url(
                self.upload_workspace.workspace.billing_project.name,
                self.upload_workspace.workspace.name,
            )
        )
        request.user = user_no_perms
        with self.assertRaises(PermissionDenied):
            self.get_view()(
                request,
                billing_project_slug=self.upload_workspace.workspace.billing_project.name,
                workspace_slug=self.upload_workspace.workspace.name,
            )

    def test_invalid_billing_project_name(self):
        """Raises a 404 error with an invalid object billing project."""
        request = self.factory.get(self.get_url("foo", self.upload_workspace.workspace.name))
        request.user = self.user
        with self.assertRaises(Http404):
            self.get_view()(
                request,
                billing_project_slug="foo",
                workspace_slug=self.upload_workspace.workspace.name,
            )

    def test_invalid_workspace_name(self):
        """Raises a 404 error with an invalid workspace name."""
        request = self.factory.get(self.get_url(self.upload_workspace.workspace.billing_project.name, "foo"))
        request.user = self.user
        with self.assertRaises(Http404):
            self.get_view()(
                request,
                billing_project_slug=self.upload_workspace.workspace.billing_project.name,
                workspace_slug="foo",
            )

    def test_context_audit_results(self):
        """The audit_results exists in the context."""
        self.client.force_login(self.user)
        response = self.client.get(
            self.get_url(
                self.upload_workspace.workspace.billing_project.name,
                self.upload_workspace.workspace.name,
            )
        )
        self.assertIn("audit_results", response.context_data)
        audit_results = response.context_data["audit_results"]
        self.assertIsInstance(
            audit_results,
            upload_workspace_audit.UploadWorkspaceSharingAudit,
        )
        self.assertTrue(audit_results.completed)
        self.assertEqual(audit_results.queryset.count(), 1)
        self.assertIn(self.upload_workspace, audit_results.queryset)

    def test_context_audit_results_does_not_include_other_workspaces(self):
        """The audit_results does not include other workspaces."""
        other_workspace = factories.UploadWorkspaceFactory.create()
        self.client.force_login(self.user)
        response = self.client.get(
            self.get_url(
                self.upload_workspace.workspace.billing_project.name,
                self.upload_workspace.workspace.name,
            )
        )
        audit_results = response.context_data["audit_results"]
        self.assertEqual(audit_results.queryset.count(), 1)
        self.assertNotIn(other_workspace, audit_results.queryset)

    def test_context_verified_table_access(self):
        """verified_table shows a record when audit has verified access."""
        group = acm_factories.ManagedGroupFactory.create(name=settings.ANVIL_DCC_ADMINS_GROUP_NAME)
        acm_factories.WorkspaceGroupSharingFactory.create(
            workspace=self.upload_workspace.workspace, group=group, access=acm_models.WorkspaceGroupSharing.OWNER
        )
        # Check the table in the context.
        self.client.force_login(self.user)
        response = self.client.get(
            self.get_url(
                self.upload_workspace.workspace.billing_project.name,
                self.upload_workspace.workspace.name,
            )
        )
        self.assertIn("verified_table", response.context_data)
        table = response.context_data["verified_table"]
        self.assertIsInstance(
            table,
            upload_workspace_audit.UploadWorkspaceSharingAuditTable,
        )
        self.assertEqual(len(table.rows), 1)
        self.assertEqual(table.rows[0].get_cell_value("workspace"), self.upload_workspace.workspace)
        self.assertEqual(table.rows[0].get_cell_value("managed_group"), group)
        self.assertEqual(table.rows[0].get_cell_value("access"), acm_models.WorkspaceGroupSharing.OWNER)
        self.assertEqual(
            table.rows[0].get_cell_value("note"),
            upload_workspace_audit.UploadWorkspaceSharingAudit.DCC_ADMIN_AS_OWNER,
        )
        self.assertEqual(table.rows[0].get_cell_value("action"), "&mdash;")

    def test_context_needs_action_table_share_as_reader(self):
        """needs_action_table shows a record when audit finds that access needs to be granted."""
        group = self.upload_workspace.workspace.authorization_domains.first()
        # Check the table in the context.
        self.client.force_login(self.user)
        response = self.client.get(
            self.get_url(
                self.upload_workspace.workspace.billing_project.name,
                self.upload_workspace.workspace.name,
            )
        )
        self.assertIn("needs_action_table", response.context_data)
        table = response.context_data["needs_action_table"]
        self.assertIsInstance(
            table,
            upload_workspace_audit.UploadWorkspaceSharingAuditTable,
        )
        self.assertEqual(len(table.rows), 1)
        self.assertEqual(table.rows[0].get_cell_value("workspace"), self.upload_workspace.workspace)
        self.assertEqual(table.rows[0].get_cell_value("managed_group"), group)
        self.assertIsNone(table.rows[0].get_cell_value("access"))
        self.assertEqual(
            table.rows[0].get_cell_value("note"),
            upload_workspace_audit.UploadWorkspaceSharingAudit.AUTH_DOMAIN_AS_READER,
        )
        self.assertNotEqual(table.rows[0].get_cell_value("action"), "&mdash;")

    def test_context_needs_action_table_share_as_writer(self):
        """needs_action_table shows a record when audit finds that access needs to be granted."""
        group = acm_factories.ManagedGroupFactory.create()
        upload_workspace = factories.UploadWorkspaceFactory.create(
            upload_cycle__is_current=True,
            research_center__uploader_group=group,
        )
        # Share with the auth domain to prevent that audit error.
        acm_factories.WorkspaceGroupSharingFactory.create(
            workspace=upload_workspace.workspace,
            group=upload_workspace.workspace.authorization_domains.first(),
            access=acm_models.WorkspaceGroupSharing.READER,
        )
        # Check the table in the context.
        self.client.force_login(self.user)
        response = self.client.get(
            self.get_url(
                upload_workspace.workspace.billing_project.name,
                upload_workspace.workspace.name,
            )
        )
        self.assertIn("needs_action_table", response.context_data)
        table = response.context_data["needs_action_table"]
        self.assertIsInstance(
            table,
            upload_workspace_audit.UploadWorkspaceSharingAuditTable,
        )
        self.assertEqual(len(table.rows), 1)
        self.assertEqual(table.rows[0].get_cell_value("workspace"), upload_workspace.workspace)
        self.assertEqual(table.rows[0].get_cell_value("managed_group"), group)
        self.assertIsNone(table.rows[0].get_cell_value("access"))
        self.assertEqual(
            table.rows[0].get_cell_value("note"),
            upload_workspace_audit.UploadWorkspaceSharingAudit.RC_UPLOADERS_CURRENT_CYCLE_BEFORE_COMPUTE,
        )
        self.assertNotEqual(table.rows[0].get_cell_value("action"), "&mdash;")

    def test_context_needs_action_table_share_with_compute(self):
        """needs_action_table shows a record when audit finds that access needs to be granted."""
        group = acm_factories.ManagedGroupFactory.create(name="GREGOR_DCC_WRITERS")
        # Share with the auth domain to prevent that audit error.
        acm_factories.WorkspaceGroupSharingFactory.create(
            workspace=self.upload_workspace.workspace,
            group=self.upload_workspace.workspace.authorization_domains.first(),
            access=acm_models.WorkspaceGroupSharing.READER,
        )
        # Check the table in the context.
        self.client.force_login(self.user)
        response = self.client.get(
            self.get_url(
                self.upload_workspace.workspace.billing_project.name,
                self.upload_workspace.workspace.name,
            )
        )
        self.assertIn("needs_action_table", response.context_data)
        table = response.context_data["needs_action_table"]
        self.assertIsInstance(
            table,
            upload_workspace_audit.UploadWorkspaceSharingAuditTable,
        )
        self.assertEqual(len(table.rows), 1)
        self.assertEqual(table.rows[0].get_cell_value("workspace"), self.upload_workspace.workspace)
        self.assertEqual(table.rows[0].get_cell_value("managed_group"), group)
        self.assertIsNone(table.rows[0].get_cell_value("access"))
        self.assertEqual(
            table.rows[0].get_cell_value("note"),
            upload_workspace_audit.UploadWorkspaceSharingAudit.DCC_WRITERS_FUTURE_CYCLE,
        )
        self.assertNotEqual(table.rows[0].get_cell_value("action"), "&mdash;")

    def test_context_needs_action_table_share_as_owner(self):
        """needs_action_table shows a record when audit finds that access needs to be granted."""
        group = acm_factories.ManagedGroupFactory.create(name=settings.ANVIL_DCC_ADMINS_GROUP_NAME)
        # Share with the auth domain to prevent that audit error.
        acm_factories.WorkspaceGroupSharingFactory.create(
            workspace=self.upload_workspace.workspace,
            group=self.upload_workspace.workspace.authorization_domains.first(),
            access=acm_models.WorkspaceGroupSharing.READER,
        )
        # Check the table in the context.
        self.client.force_login(self.user)
        response = self.client.get(
            self.get_url(
                self.upload_workspace.workspace.billing_project.name,
                self.upload_workspace.workspace.name,
            )
        )
        self.assertIn("needs_action_table", response.context_data)
        table = response.context_data["needs_action_table"]
        self.assertIsInstance(
            table,
            upload_workspace_audit.UploadWorkspaceSharingAuditTable,
        )
        self.assertEqual(len(table.rows), 1)
        self.assertEqual(table.rows[0].get_cell_value("workspace"), self.upload_workspace.workspace)
        self.assertEqual(table.rows[0].get_cell_value("managed_group"), group)
        self.assertIsNone(table.rows[0].get_cell_value("access"))
        self.assertEqual(
            table.rows[0].get_cell_value("note"),
            upload_workspace_audit.UploadWorkspaceSharingAudit.DCC_ADMIN_AS_OWNER,
        )
        self.assertNotEqual(table.rows[0].get_cell_value("action"), "&mdash;")

    def test_context_needs_action_table_stop_sharing(self):
        """needs_action_table shows a record when audit finds that access needs to be granted."""
        # Change upload workspace end dates so it's in the past.
        self.upload_workspace.upload_cycle.start_date = timezone.now() - timedelta(days=20)
        self.upload_workspace.upload_cycle.end_date = timezone.now() - timedelta(days=10)
        self.upload_workspace.upload_cycle.save()
        self.upload_workspace.date_qc_completed = timezone.localdate() - timedelta(days=1)
        self.upload_workspace.save()
        group = acm_factories.ManagedGroupFactory.create()
        rc = self.upload_workspace.research_center
        rc.uploader_group = group
        rc.save()
        # Create a sharing record.
        acm_factories.WorkspaceGroupSharingFactory.create(
            workspace=self.upload_workspace.workspace,
            group=group,
            access=acm_models.WorkspaceGroupSharing.READER,
        )
        # Share with the auth domain to prevent that audit error.
        acm_factories.WorkspaceGroupSharingFactory.create(
            workspace=self.upload_workspace.workspace,
            group=self.upload_workspace.workspace.authorization_domains.first(),
            access=acm_models.WorkspaceGroupSharing.READER,
        )
        # Check the table in the context.
        self.client.force_login(self.user)
        response = self.client.get(
            self.get_url(
                self.upload_workspace.workspace.billing_project.name,
                self.upload_workspace.workspace.name,
            )
        )
        self.assertIn("needs_action_table", response.context_data)
        table = response.context_data["needs_action_table"]
        self.assertIsInstance(
            table,
            upload_workspace_audit.UploadWorkspaceSharingAuditTable,
        )
        self.assertEqual(len(table.rows), 1)
        self.assertEqual(table.rows[0].get_cell_value("workspace"), self.upload_workspace.workspace)
        self.assertEqual(table.rows[0].get_cell_value("managed_group"), group)
        self.assertEqual(table.rows[0].get_cell_value("access"), "READER")
        self.assertEqual(
            table.rows[0].get_cell_value("note"),
            upload_workspace_audit.UploadWorkspaceSharingAudit.RC_UPLOADERS_PAST_CYCLE_AFTER_QC_COMPLETE,
        )
        self.assertNotEqual(table.rows[0].get_cell_value("action"), "&mdash;")

    def test_context_error_table_stop_sharing(self):
        """error_table shows a record when an audit error is detected."""
        # Change upload workspace end dates so it's in the past.
        group = acm_factories.ManagedGroupFactory.create()
        # Create a sharing record.
        acm_factories.WorkspaceGroupSharingFactory.create(
            workspace=self.upload_workspace.workspace,
            group=group,
            access=acm_models.WorkspaceGroupSharing.READER,
        )
        # Share with the auth domain to prevent that audit error.
        acm_factories.WorkspaceGroupSharingFactory.create(
            workspace=self.upload_workspace.workspace,
            group=self.upload_workspace.workspace.authorization_domains.first(),
            access=acm_models.WorkspaceGroupSharing.READER,
        )
        # Check the table in the context.
        self.client.force_login(self.user)
        response = self.client.get(
            self.get_url(
                self.upload_workspace.workspace.billing_project.name,
                self.upload_workspace.workspace.name,
            )
        )
        self.assertIn("errors_table", response.context_data)
        table = response.context_data["errors_table"]
        self.assertIsInstance(
            table,
            upload_workspace_audit.UploadWorkspaceSharingAuditTable,
        )
        self.assertEqual(len(table.rows), 1)
        self.assertEqual(table.rows[0].get_cell_value("workspace"), self.upload_workspace.workspace)
        self.assertEqual(table.rows[0].get_cell_value("managed_group"), group)
        self.assertEqual(table.rows[0].get_cell_value("access"), "READER")
        self.assertEqual(
            table.rows[0].get_cell_value("note"),
            upload_workspace_audit.UploadWorkspaceSharingAudit.OTHER_GROUP_NO_ACCESS,
        )
        self.assertNotEqual(table.rows[0].get_cell_value("action"), "&mdash;")

    def test_title(self):
        self.client.force_login(self.user)
        response = self.client.get(
            self.get_url(
                self.upload_workspace.workspace.billing_project.name,
                self.upload_workspace.workspace.name,
            )
        )
        self.assertContains(response, str(self.upload_workspace))
        # self.assertNotIn("all upload workspaces", response.content.decode().lower())


class UploadWorkspaceSharingAuditByUploadCycleTest(AnVILAPIMockTestMixin, TestCase):
    """Tests for the UploadWorkspaceSharingAuditByUploadCycle view."""

    def setUp(self):
        """Set up test class."""
        super().setUp()
        self.factory = RequestFactory()
        # Create a user with both view and edit permission.
        self.user = User.objects.create_user(username="test", password="test")
        self.user.user_permissions.add(
            Permission.objects.get(codename=AnVILProjectManagerAccess.STAFF_VIEW_PERMISSION_CODENAME)
        )
        self.upload_cycle = factories.UploadCycleFactory.create(is_future=True)

    def get_url(self, *args):
        """Get the url for the view being tested."""
        return reverse(
            "gregor_anvil:audit:upload_workspaces:sharing:by_upload_cycle",
            args=args,
        )

    def get_view(self):
        """Return the view being tested."""
        return views.UploadWorkspaceSharingAuditByUploadCycle.as_view()

    def test_view_redirect_not_logged_in(self):
        "View redirects to login view when user is not logged in."
        # Need a client for redirects.
        response = self.client.get(self.get_url(self.upload_cycle.cycle + 1))
        self.assertRedirects(
            response,
            resolve_url(settings.LOGIN_URL) + "?next=" + self.get_url(self.upload_cycle.cycle + 1),
        )

    def test_status_code_with_user_permission_view(self):
        """Returns successful response code if the user has view permission."""
        self.client.force_login(self.user)
        response = self.client.get(self.get_url(self.upload_cycle.cycle))
        self.assertEqual(response.status_code, 200)

    def test_access_without_user_permission(self):
        """Raises permission denied if user has no permissions."""
        user_no_perms = User.objects.create_user(username="test-none", password="test-none")
        request = self.factory.get(self.get_url(self.upload_cycle.cycle))
        request.user = user_no_perms
        with self.assertRaises(PermissionDenied):
            self.get_view()(request, cycle=self.upload_cycle.cycle)

    def test_invalid_upload_cycle(self):
        """Raises a 404 error with an invalid upload cycle."""
        request = self.factory.get(self.get_url(self.upload_cycle.cycle + 1))
        request.user = self.user
        with self.assertRaises(Http404):
            self.get_view()(request, cycle=self.upload_cycle.cycle + 1)

    def test_context_audit_results_no_upload_workspaces(self):
        """The audit_results exists in the context."""
        self.client.force_login(self.user)
        response = self.client.get(self.get_url(self.upload_cycle.cycle))
        self.assertIn("audit_results", response.context_data)
        audit_results = response.context_data["audit_results"]
        self.assertIsInstance(
            audit_results,
            upload_workspace_audit.UploadWorkspaceSharingAudit,
        )
        self.assertTrue(audit_results.completed)
        self.assertEqual(audit_results.queryset.count(), 0)

    def test_context_audit_results_one_upload_workspace(self):
        """The audit_results exists in the context."""
        upload_workspace = factories.UploadWorkspaceFactory.create(upload_cycle=self.upload_cycle)
        self.client.force_login(self.user)
        response = self.client.get(self.get_url(self.upload_cycle.cycle))
        self.assertIn("audit_results", response.context_data)
        audit_results = response.context_data["audit_results"]
        self.assertIsInstance(
            audit_results,
            upload_workspace_audit.UploadWorkspaceSharingAudit,
        )
        self.assertTrue(audit_results.completed)
        self.assertEqual(audit_results.queryset.count(), 1)
        self.assertIn(upload_workspace, audit_results.queryset)

    def test_context_audit_results_two_upload_workspaces(self):
        """The audit_results exists in the context."""
        upload_workspace_1 = factories.UploadWorkspaceFactory.create(upload_cycle=self.upload_cycle)
        upload_workspace_2 = factories.UploadWorkspaceFactory.create(upload_cycle=self.upload_cycle)
        self.client.force_login(self.user)
        response = self.client.get(self.get_url(self.upload_cycle.cycle))
        self.assertIn("audit_results", response.context_data)
        audit_results = response.context_data["audit_results"]
        self.assertIsInstance(
            audit_results,
            upload_workspace_audit.UploadWorkspaceSharingAudit,
        )
        self.assertTrue(audit_results.completed)
        self.assertEqual(audit_results.queryset.count(), 2)
        self.assertIn(upload_workspace_1, audit_results.queryset)
        self.assertIn(upload_workspace_2, audit_results.queryset)

    def test_context_audit_results_ignores_other_upload_cycles(self):
        """The audit_results exists in the context."""
        upload_workspace = factories.UploadWorkspaceFactory.create(upload_cycle__cycle=self.upload_cycle.cycle + 1)
        self.client.force_login(self.user)
        response = self.client.get(self.get_url(self.upload_cycle.cycle))
        self.assertIn("audit_results", response.context_data)
        audit_results = response.context_data["audit_results"]
        self.assertIsInstance(
            audit_results,
            upload_workspace_audit.UploadWorkspaceSharingAudit,
        )
        self.assertTrue(audit_results.completed)
        self.assertEqual(audit_results.queryset.count(), 0)
        self.assertNotIn(upload_workspace, audit_results.queryset)

    def test_context_verified_table_access(self):
        """verified_table shows a record when audit has verified access."""
        upload_workspace = factories.UploadWorkspaceFactory.create(upload_cycle=self.upload_cycle)
        group = acm_factories.ManagedGroupFactory.create(name=settings.ANVIL_DCC_ADMINS_GROUP_NAME)
        acm_factories.WorkspaceGroupSharingFactory.create(
            workspace=upload_workspace.workspace, group=group, access=acm_models.WorkspaceGroupSharing.OWNER
        )
        # Check the table in the context.
        self.client.force_login(self.user)
        response = self.client.get(self.get_url(self.upload_cycle.cycle))
        self.assertIn("verified_table", response.context_data)
        table = response.context_data["verified_table"]
        self.assertIsInstance(
            table,
            upload_workspace_audit.UploadWorkspaceSharingAuditTable,
        )
        self.assertEqual(len(table.rows), 1)
        self.assertEqual(table.rows[0].get_cell_value("workspace"), upload_workspace.workspace)
        self.assertEqual(table.rows[0].get_cell_value("managed_group"), group)
        self.assertEqual(table.rows[0].get_cell_value("access"), acm_models.WorkspaceGroupSharing.OWNER)
        self.assertEqual(
            table.rows[0].get_cell_value("note"),
            upload_workspace_audit.UploadWorkspaceSharingAudit.DCC_ADMIN_AS_OWNER,
        )
        self.assertEqual(table.rows[0].get_cell_value("action"), "&mdash;")

    def test_context_needs_action_table_share_as_reader(self):
        """needs_action_table shows a record when audit finds that access needs to be granted."""
        upload_workspace = factories.UploadWorkspaceFactory.create(upload_cycle=self.upload_cycle)
        group = upload_workspace.workspace.authorization_domains.first()
        # Check the table in the context.
        self.client.force_login(self.user)
        response = self.client.get(self.get_url(self.upload_cycle.cycle))
        self.assertIn("needs_action_table", response.context_data)
        table = response.context_data["needs_action_table"]
        self.assertIsInstance(
            table,
            upload_workspace_audit.UploadWorkspaceSharingAuditTable,
        )
        self.assertEqual(len(table.rows), 1)
        self.assertEqual(table.rows[0].get_cell_value("workspace"), upload_workspace.workspace)
        self.assertEqual(table.rows[0].get_cell_value("managed_group"), group)
        self.assertIsNone(table.rows[0].get_cell_value("access"))
        self.assertEqual(
            table.rows[0].get_cell_value("note"),
            upload_workspace_audit.UploadWorkspaceSharingAudit.AUTH_DOMAIN_AS_READER,
        )
        self.assertNotEqual(table.rows[0].get_cell_value("action"), "&mdash;")

    def test_context_needs_action_table_share_as_writer(self):
        """needs_action_table shows a record when audit finds that access needs to be granted."""
        group = acm_factories.ManagedGroupFactory.create()
        upload_workspace = factories.UploadWorkspaceFactory.create(
            upload_cycle__is_current=True,
            research_center__uploader_group=group,
        )
        # Share with the auth domain to prevent that audit error.
        acm_factories.WorkspaceGroupSharingFactory.create(
            workspace=upload_workspace.workspace,
            group=upload_workspace.workspace.authorization_domains.first(),
            access=acm_models.WorkspaceGroupSharing.READER,
        )
        # Check the table in the context.
        self.client.force_login(self.user)
        response = self.client.get(self.get_url(upload_workspace.upload_cycle.cycle))
        self.assertIn("needs_action_table", response.context_data)
        table = response.context_data["needs_action_table"]
        self.assertIsInstance(
            table,
            upload_workspace_audit.UploadWorkspaceSharingAuditTable,
        )
        self.assertEqual(len(table.rows), 1)
        self.assertEqual(table.rows[0].get_cell_value("workspace"), upload_workspace.workspace)
        self.assertEqual(table.rows[0].get_cell_value("managed_group"), group)
        self.assertIsNone(table.rows[0].get_cell_value("access"))
        self.assertEqual(
            table.rows[0].get_cell_value("note"),
            upload_workspace_audit.UploadWorkspaceSharingAudit.RC_UPLOADERS_CURRENT_CYCLE_BEFORE_COMPUTE,
        )
        self.assertNotEqual(table.rows[0].get_cell_value("action"), "&mdash;")

    def test_context_needs_action_table_share_with_compute(self):
        """needs_action_table shows a record when audit finds that access needs to be granted."""
        upload_workspace = factories.UploadWorkspaceFactory.create(upload_cycle=self.upload_cycle)
        group = acm_factories.ManagedGroupFactory.create(name="GREGOR_DCC_WRITERS")
        # Share with the auth domain to prevent that audit error.
        acm_factories.WorkspaceGroupSharingFactory.create(
            workspace=upload_workspace.workspace,
            group=upload_workspace.workspace.authorization_domains.first(),
            access=acm_models.WorkspaceGroupSharing.READER,
        )
        # Check the table in the context.
        self.client.force_login(self.user)
        response = self.client.get(self.get_url(self.upload_cycle.cycle))
        self.assertIn("needs_action_table", response.context_data)
        table = response.context_data["needs_action_table"]
        self.assertIsInstance(
            table,
            upload_workspace_audit.UploadWorkspaceSharingAuditTable,
        )
        self.assertEqual(len(table.rows), 1)
        self.assertEqual(table.rows[0].get_cell_value("workspace"), upload_workspace.workspace)
        self.assertEqual(table.rows[0].get_cell_value("managed_group"), group)
        self.assertIsNone(table.rows[0].get_cell_value("access"))
        self.assertEqual(
            table.rows[0].get_cell_value("note"),
            upload_workspace_audit.UploadWorkspaceSharingAudit.DCC_WRITERS_FUTURE_CYCLE,
        )
        self.assertNotEqual(table.rows[0].get_cell_value("action"), "&mdash;")

    def test_context_needs_action_table_share_as_owner(self):
        """needs_action_table shows a record when audit finds that access needs to be granted."""
        upload_workspace = factories.UploadWorkspaceFactory.create(upload_cycle=self.upload_cycle)
        group = acm_factories.ManagedGroupFactory.create(name=settings.ANVIL_DCC_ADMINS_GROUP_NAME)
        # Share with the auth domain to prevent that audit error.
        acm_factories.WorkspaceGroupSharingFactory.create(
            workspace=upload_workspace.workspace,
            group=upload_workspace.workspace.authorization_domains.first(),
            access=acm_models.WorkspaceGroupSharing.READER,
        )
        # Check the table in the context.
        self.client.force_login(self.user)
        response = self.client.get(self.get_url(self.upload_cycle.cycle))
        self.assertIn("needs_action_table", response.context_data)
        table = response.context_data["needs_action_table"]
        self.assertIsInstance(
            table,
            upload_workspace_audit.UploadWorkspaceSharingAuditTable,
        )
        self.assertEqual(len(table.rows), 1)
        self.assertEqual(table.rows[0].get_cell_value("workspace"), upload_workspace.workspace)
        self.assertEqual(table.rows[0].get_cell_value("managed_group"), group)
        self.assertIsNone(table.rows[0].get_cell_value("access"))
        self.assertEqual(
            table.rows[0].get_cell_value("note"),
            upload_workspace_audit.UploadWorkspaceSharingAudit.DCC_ADMIN_AS_OWNER,
        )
        self.assertNotEqual(table.rows[0].get_cell_value("action"), "&mdash;")

    def test_context_needs_action_table_stop_sharing(self):
        """needs_action_table shows a record when audit finds that access needs to be granted."""
        # Change upload workspace end dates so it's in the past.
        group = acm_factories.ManagedGroupFactory.create()
        upload_workspace = factories.UploadWorkspaceFactory.create(
            upload_cycle=self.upload_cycle,
            research_center__uploader_group=group,
            date_qc_completed=timezone.localdate() - timedelta(days=1),
        )
        self.upload_cycle.start_date = timezone.now() - timedelta(days=20)
        self.upload_cycle.end_date = timezone.now() - timedelta(days=10)
        self.upload_cycle.save()
        # Create a sharing record.
        acm_factories.WorkspaceGroupSharingFactory.create(
            workspace=upload_workspace.workspace,
            group=group,
            access=acm_models.WorkspaceGroupSharing.READER,
        )
        # Share with the auth domain to prevent that audit error.
        acm_factories.WorkspaceGroupSharingFactory.create(
            workspace=upload_workspace.workspace,
            group=upload_workspace.workspace.authorization_domains.first(),
            access=acm_models.WorkspaceGroupSharing.READER,
        )
        # Check the table in the context.
        self.client.force_login(self.user)
        response = self.client.get(self.get_url(self.upload_cycle.cycle))
        self.assertIn("needs_action_table", response.context_data)
        table = response.context_data["needs_action_table"]
        self.assertIsInstance(
            table,
            upload_workspace_audit.UploadWorkspaceSharingAuditTable,
        )
        self.assertEqual(len(table.rows), 1)
        self.assertEqual(table.rows[0].get_cell_value("workspace"), upload_workspace.workspace)
        self.assertEqual(table.rows[0].get_cell_value("managed_group"), group)
        self.assertEqual(table.rows[0].get_cell_value("access"), "READER")
        self.assertEqual(
            table.rows[0].get_cell_value("note"),
            upload_workspace_audit.UploadWorkspaceSharingAudit.RC_UPLOADERS_PAST_CYCLE_AFTER_QC_COMPLETE,
        )
        self.assertNotEqual(table.rows[0].get_cell_value("action"), "&mdash;")

    def test_context_error_table_stop_sharing(self):
        """error_table shows a record when an audit error is detected."""
        # Change upload workspace end dates so it's in the past.
        upload_workspace = factories.UploadWorkspaceFactory.create(upload_cycle=self.upload_cycle)
        group = acm_factories.ManagedGroupFactory.create()
        # Create a sharing record.
        acm_factories.WorkspaceGroupSharingFactory.create(
            workspace=upload_workspace.workspace,
            group=group,
            access=acm_models.WorkspaceGroupSharing.READER,
        )
        # Share with the auth domain to prevent that audit error.
        acm_factories.WorkspaceGroupSharingFactory.create(
            workspace=upload_workspace.workspace,
            group=upload_workspace.workspace.authorization_domains.first(),
            access=acm_models.WorkspaceGroupSharing.READER,
        )
        # Check the table in the context.
        self.client.force_login(self.user)
        response = self.client.get(self.get_url(self.upload_cycle.cycle))
        self.assertIn("errors_table", response.context_data)
        table = response.context_data["errors_table"]
        self.assertIsInstance(
            table,
            upload_workspace_audit.UploadWorkspaceSharingAuditTable,
        )
        self.assertEqual(len(table.rows), 1)
        self.assertEqual(table.rows[0].get_cell_value("workspace"), upload_workspace.workspace)
        self.assertEqual(table.rows[0].get_cell_value("managed_group"), group)
        self.assertEqual(table.rows[0].get_cell_value("access"), "READER")
        self.assertEqual(
            table.rows[0].get_cell_value("note"),
            upload_workspace_audit.UploadWorkspaceSharingAudit.OTHER_GROUP_NO_ACCESS,
        )
        self.assertNotEqual(table.rows[0].get_cell_value("action"), "&mdash;")

    def test_title(self):
        self.client.force_login(self.user)
        response = self.client.get(self.get_url(self.upload_cycle.cycle))
        self.assertContains(response, str(self.upload_cycle))
        self.assertNotIn("all upload workspaces", response.content.decode().lower())


class UploadWorkspaceSharingAuditResolveTest(AnVILAPIMockTestMixin, TestCase):
    def setUp(self):
        """Set up test class."""
        super().setUp()
        self.factory = RequestFactory()
        # Create a user with both view and edit permission.
        self.user = User.objects.create_user(username="test", password="test")
        self.user.user_permissions.add(
            Permission.objects.get(codename=AnVILProjectManagerAccess.STAFF_VIEW_PERMISSION_CODENAME)
        )
        self.user.user_permissions.add(
            Permission.objects.get(codename=AnVILProjectManagerAccess.STAFF_EDIT_PERMISSION_CODENAME)
        )

    def get_url(self, *args):
        """Get the url for the view being tested."""
        return reverse(
            "gregor_anvil:audit:upload_workspaces:sharing:resolve",
            args=args,
        )

    def get_view(self):
        """Return the view being tested."""
        return views.UploadWorkspaceSharingAuditResolve.as_view()

    def test_view_redirect_not_logged_in(self):
        "View redirects to login view when user is not logged in."
        # Need a client for redirects.
        response = self.client.get(self.get_url("foo", "bar", "foobar"))
        self.assertRedirects(
            response,
            resolve_url(settings.LOGIN_URL) + "?next=" + self.get_url("foo", "bar", "foobar"),
        )

    def test_status_code_with_user_permission_staff_edit(self):
        """Returns successful response code if the user has staff edit permission."""
        upload_workspace = factories.UploadWorkspaceFactory.create()
        group = acm_factories.ManagedGroupFactory.create()
        self.client.force_login(self.user)
        response = self.client.get(
            self.get_url(upload_workspace.workspace.billing_project.name, upload_workspace.workspace.name, group.name)
        )
        self.assertEqual(response.status_code, 200)

    def test_status_code_with_user_permission_staff_view(self):
        """Returns 403 response code if the user has staff view permission."""
        user_view = User.objects.create_user(username="test-view", password="test-view")
        user_view.user_permissions.add(
            Permission.objects.get(codename=AnVILProjectManagerAccess.STAFF_VIEW_PERMISSION_CODENAME)
        )
        self.client.force_login(self.user)
        request = self.factory.get(self.get_url("foo", "bar", "foobar"))
        request.user = user_view
        with self.assertRaises(PermissionDenied):
            self.get_view()(request)

    def test_status_code_with_user_permission_view(self):
        """Returns forbidden response code if the user has view permission."""
        user = User.objects.create_user(username="test-none", password="test-none")
        user.user_permissions.add(Permission.objects.get(codename=AnVILProjectManagerAccess.VIEW_PERMISSION_CODENAME))
        request = self.factory.get(self.get_url("foo", "bar", "foobar"))
        request.user = user
        with self.assertRaises(PermissionDenied):
            self.get_view()(request)

    def test_access_without_user_permission(self):
        """Raises permission denied if user has no permissions."""
        user_no_perms = User.objects.create_user(username="test-none", password="test-none")
        request = self.factory.get(self.get_url("foo", "bar", "foobar"))
        request.user = user_no_perms
        with self.assertRaises(PermissionDenied):
            self.get_view()(request)

    def test_get_billing_project_does_not_exist(self):
        """Raises a 404 error with an invalid billing project."""
        upload_workspace = factories.UploadWorkspaceFactory.create()
        group = acm_factories.ManagedGroupFactory.create()
        self.client.force_login(self.user)
        response = self.client.get(self.get_url("foo", upload_workspace.workspace.name, group.name))
        self.assertEqual(response.status_code, 404)

    def test_get_workspace_name_does_not_exist(self):
        """Raises a 404 error with an invalid billing project."""
        upload_workspace = factories.UploadWorkspaceFactory.create()
        group = acm_factories.ManagedGroupFactory.create()
        self.client.force_login(self.user)
        response = self.client.get(self.get_url(upload_workspace.workspace.billing_project.name, "foo", group.name))
        self.assertEqual(response.status_code, 404)

    def test_get_group_does_not_exist(self):
        """get request raises a 404 error with an non-existent email."""
        upload_workspace = factories.UploadWorkspaceFactory.create()
        self.client.force_login(self.user)
        response = self.client.get(
            self.get_url(
                upload_workspace.workspace.billing_project.name,
                upload_workspace.workspace.name,
                "foo",
            )
        )
        self.assertEqual(response.status_code, 404)

    def test_get_context_audit_result(self):
        """The audit_results exists in the context."""
        upload_workspace = factories.UploadWorkspaceFactory.create()
        group = acm_factories.ManagedGroupFactory.create()
        self.client.force_login(self.user)
        response = self.client.get(
            self.get_url(upload_workspace.workspace.billing_project.name, upload_workspace.workspace.name, group.name)
        )
        self.assertIn("audit_result", response.context_data)
        self.assertIsInstance(
            response.context_data["audit_result"],
            workspace_sharing_audit_results.WorkspaceSharingAuditResult,
        )

    def test_get_verified_shared(self):
        """Get request with VerifiedShared result."""
        upload_workspace = factories.UploadWorkspaceFactory.create()
        group = upload_workspace.workspace.authorization_domains.first()
        acm_factories.WorkspaceGroupSharingFactory.create(
            workspace=upload_workspace.workspace,
            group=group,
            access=acm_models.WorkspaceGroupSharing.READER,
        )
        self.client.force_login(self.user)
        response = self.client.get(
            self.get_url(upload_workspace.workspace.billing_project.name, upload_workspace.workspace.name, group.name)
        )
        self.assertIn("audit_result", response.context_data)
        audit_result = response.context_data["audit_result"]
        self.assertIsInstance(audit_result, workspace_sharing_audit_results.VerifiedShared)
        self.assertEqual(audit_result.workspace, upload_workspace.workspace)
        self.assertEqual(audit_result.managed_group, group)
        self.assertEqual(audit_result.note, upload_workspace_audit.UploadWorkspaceSharingAudit.AUTH_DOMAIN_AS_READER)

    def test_get_verified_not_shared(self):
        """Get request with VerifiedNotShared result."""
        upload_workspace = factories.UploadWorkspaceFactory.create()
        group = acm_factories.ManagedGroupFactory.create()
        self.client.force_login(self.user)
        response = self.client.get(
            self.get_url(upload_workspace.workspace.billing_project.name, upload_workspace.workspace.name, group.name)
        )
        self.assertIn("audit_result", response.context_data)
        audit_result = response.context_data["audit_result"]
        self.assertIsInstance(audit_result, workspace_sharing_audit_results.VerifiedNotShared)
        self.assertEqual(audit_result.workspace, upload_workspace.workspace)
        self.assertEqual(audit_result.managed_group, group)
        self.assertEqual(audit_result.note, upload_workspace_audit.UploadWorkspaceSharingAudit.OTHER_GROUP_NO_ACCESS)

    def test_get_share_as_reader(self):
        """Get request with ShareAsReader result."""
        upload_workspace = factories.UploadWorkspaceFactory.create()
        group = upload_workspace.workspace.authorization_domains.first()
        self.client.force_login(self.user)
        response = self.client.get(
            self.get_url(upload_workspace.workspace.billing_project.name, upload_workspace.workspace.name, group.name)
        )
        self.assertIn("audit_result", response.context_data)
        audit_result = response.context_data["audit_result"]
        self.assertIsInstance(audit_result, workspace_sharing_audit_results.ShareAsReader)
        self.assertEqual(audit_result.workspace, upload_workspace.workspace)
        self.assertEqual(audit_result.managed_group, group)
        self.assertEqual(audit_result.note, upload_workspace_audit.UploadWorkspaceSharingAudit.AUTH_DOMAIN_AS_READER)

    def test_get_share_as_writer(self):
        group = acm_factories.ManagedGroupFactory.create()
        upload_workspace = factories.UploadWorkspaceFactory.create(
            upload_cycle__is_current=True,
            research_center__uploader_group=group,
        )
        self.client.force_login(self.user)
        response = self.client.get(
            self.get_url(upload_workspace.workspace.billing_project.name, upload_workspace.workspace.name, group.name)
        )
        self.assertIn("audit_result", response.context_data)
        audit_result = response.context_data["audit_result"]
        self.assertIsInstance(audit_result, workspace_sharing_audit_results.ShareAsWriter)
        self.assertEqual(audit_result.workspace, upload_workspace.workspace)
        self.assertEqual(audit_result.managed_group, group)
        self.assertEqual(
            audit_result.note,
            upload_workspace_audit.UploadWorkspaceSharingAudit.RC_UPLOADERS_CURRENT_CYCLE_BEFORE_COMPUTE,
        )

    def test_get_share_with_compute(self):
        group = acm_factories.ManagedGroupFactory.create(name="GREGOR_DCC_WRITERS")
        upload_workspace = factories.UploadWorkspaceFactory.create(upload_cycle__is_future=True)
        self.client.force_login(self.user)
        response = self.client.get(
            self.get_url(upload_workspace.workspace.billing_project.name, upload_workspace.workspace.name, group.name)
        )
        self.assertIn("audit_result", response.context_data)
        audit_result = response.context_data["audit_result"]
        self.assertIsInstance(audit_result, workspace_sharing_audit_results.ShareWithCompute)
        self.assertEqual(audit_result.workspace, upload_workspace.workspace)
        self.assertEqual(audit_result.managed_group, group)
        self.assertEqual(audit_result.note, upload_workspace_audit.UploadWorkspaceSharingAudit.DCC_WRITERS_FUTURE_CYCLE)

    def test_get_share_as_owner(self):
        group = acm_factories.ManagedGroupFactory.create(name=settings.ANVIL_DCC_ADMINS_GROUP_NAME)
        upload_workspace = factories.UploadWorkspaceFactory.create()
        self.client.force_login(self.user)
        response = self.client.get(
            self.get_url(upload_workspace.workspace.billing_project.name, upload_workspace.workspace.name, group.name)
        )
        self.assertIn("audit_result", response.context_data)
        audit_result = response.context_data["audit_result"]
        self.assertIsInstance(audit_result, workspace_sharing_audit_results.ShareAsOwner)
        self.assertEqual(audit_result.workspace, upload_workspace.workspace)
        self.assertEqual(audit_result.managed_group, group)
        self.assertEqual(audit_result.note, upload_workspace_audit.UploadWorkspaceSharingAudit.DCC_ADMIN_AS_OWNER)

    def test_post_billing_project_does_not_exist(self):
        """Raises a 404 error with an invalid billing project."""
        upload_workspace = factories.UploadWorkspaceFactory.create()
        group = acm_factories.ManagedGroupFactory.create()
        self.client.force_login(self.user)
        response = self.client.post(self.get_url("foo", upload_workspace.workspace.name, group.name))
        self.assertEqual(response.status_code, 404)

    def test_post_workspace_name_does_not_exist(self):
        """Raises a 404 error with an invalid billing project."""
        upload_workspace = factories.UploadWorkspaceFactory.create()
        group = acm_factories.ManagedGroupFactory.create()
        self.client.force_login(self.user)
        response = self.client.post(self.get_url(upload_workspace.workspace.billing_project.name, "foo", group.name))
        self.assertEqual(response.status_code, 404)

    def test_post_group_does_not_exist(self):
        """post request raises a 404 error with an non-existent email."""
        upload_workspace = factories.UploadWorkspaceFactory.create()
        self.client.force_login(self.user)
        response = self.client.post(
            self.get_url(
                upload_workspace.workspace.billing_project.name,
                upload_workspace.workspace.name,
                "foo",
            )
        )
        self.assertEqual(response.status_code, 404)

    def test_post_verified_shared(self):
        """Post request with VerifiedShared result."""
        upload_workspace = factories.UploadWorkspaceFactory.create()
        group = upload_workspace.workspace.authorization_domains.first()
        date_created = timezone.now() - timedelta(weeks=3)
        with freeze_time(date_created):
            sharing = acm_factories.WorkspaceGroupSharingFactory.create(
                workspace=upload_workspace.workspace,
                group=group,
                access=acm_models.WorkspaceGroupSharing.READER,
            )
        self.client.force_login(self.user)
        response = self.client.post(
            self.get_url(upload_workspace.workspace.billing_project.name, upload_workspace.workspace.name, group.name)
        )
        self.assertRedirects(response, upload_workspace.get_absolute_url())
        self.assertEqual(acm_models.WorkspaceGroupSharing.objects.count(), 1)
        sharing.refresh_from_db()
        self.assertEqual(sharing.created, date_created)
        self.assertEqual(sharing.modified, date_created)

    def test_post_verified_not_shared(self):
        """Post request with VerifiedNotShared result."""
        upload_workspace = factories.UploadWorkspaceFactory.create()
        group = acm_factories.ManagedGroupFactory.create()
        self.client.force_login(self.user)
        response = self.client.post(
            self.get_url(upload_workspace.workspace.billing_project.name, upload_workspace.workspace.name, group.name)
        )
        self.assertRedirects(response, upload_workspace.get_absolute_url())
        self.assertEqual(acm_models.WorkspaceGroupSharing.objects.count(), 0)

    def test_post_new_share_as_reader(self):
        """Post request with ShareAsReader result."""
        upload_workspace = factories.UploadWorkspaceFactory.create(
            workspace__billing_project__name="test-bp", workspace__name="test-ws"
        )
        group = upload_workspace.workspace.authorization_domains.first()
        # Add the mocked API response.
        acls = [
            {
                "email": group.email,
                "accessLevel": "READER",
                "canShare": False,
                "canCompute": False,
            }
        ]
        self.anvil_response_mock.add(
            responses.PATCH,
            self.api_client.rawls_entry_point + "/api/workspaces/test-bp/test-ws/acl?inviteUsersNotFound=false",
            status=200,
            match=[responses.matchers.json_params_matcher(acls)],
            json={"invitesSent": {}, "usersNotFound": {}, "usersUpdated": acls},
        )
        self.client.force_login(self.user)
        response = self.client.post(
            self.get_url(upload_workspace.workspace.billing_project.name, upload_workspace.workspace.name, group.name)
        )
        self.assertRedirects(response, upload_workspace.get_absolute_url())
        self.assertEqual(acm_models.WorkspaceGroupSharing.objects.count(), 1)
        sharing = acm_models.WorkspaceGroupSharing.objects.get(workspace=upload_workspace.workspace, group=group)
        self.assertEqual(sharing.access, acm_models.WorkspaceGroupSharing.READER)
        self.assertFalse(sharing.can_compute)

    def test_post_new_share_as_writer(self):
        group = acm_factories.ManagedGroupFactory.create()
        upload_workspace = factories.UploadWorkspaceFactory.create(
            workspace__billing_project__name="test-bp",
            workspace__name="test-ws",
            upload_cycle__is_current=True,
            research_center__uploader_group=group,
        )
        # Add the mocked API response.
        acls = [
            {
                "email": group.email,
                "accessLevel": "WRITER",
                "canShare": False,
                "canCompute": False,
            }
        ]
        self.anvil_response_mock.add(
            responses.PATCH,
            self.api_client.rawls_entry_point + "/api/workspaces/test-bp/test-ws/acl?inviteUsersNotFound=false",
            status=200,
            match=[responses.matchers.json_params_matcher(acls)],
            json={"invitesSent": {}, "usersNotFound": {}, "usersUpdated": acls},
        )
        self.client.force_login(self.user)
        response = self.client.post(
            self.get_url(upload_workspace.workspace.billing_project.name, upload_workspace.workspace.name, group.name)
        )
        self.assertRedirects(response, upload_workspace.get_absolute_url())
        self.assertEqual(acm_models.WorkspaceGroupSharing.objects.count(), 1)
        sharing = acm_models.WorkspaceGroupSharing.objects.get(workspace=upload_workspace.workspace, group=group)
        self.assertEqual(sharing.access, acm_models.WorkspaceGroupSharing.WRITER)
        self.assertFalse(sharing.can_compute)

    def test_post_new_share_with_compute(self):
        group = acm_factories.ManagedGroupFactory.create(name="GREGOR_DCC_WRITERS")
        upload_workspace = factories.UploadWorkspaceFactory.create(
            workspace__billing_project__name="test-bp",
            workspace__name="test-ws",
            upload_cycle__is_future=True,
        )
        # Add the mocked API response.
        acls = [
            {
                "email": group.email,
                "accessLevel": "WRITER",
                "canShare": False,
                "canCompute": True,
            }
        ]
        self.anvil_response_mock.add(
            responses.PATCH,
            self.api_client.rawls_entry_point + "/api/workspaces/test-bp/test-ws/acl?inviteUsersNotFound=false",
            status=200,
            match=[responses.matchers.json_params_matcher(acls)],
            json={"invitesSent": {}, "usersNotFound": {}, "usersUpdated": acls},
        )
        self.client.force_login(self.user)
        response = self.client.post(
            self.get_url(upload_workspace.workspace.billing_project.name, upload_workspace.workspace.name, group.name)
        )
        self.assertRedirects(response, upload_workspace.get_absolute_url())
        self.assertEqual(acm_models.WorkspaceGroupSharing.objects.count(), 1)
        sharing = acm_models.WorkspaceGroupSharing.objects.get(workspace=upload_workspace.workspace, group=group)
        self.assertEqual(sharing.access, acm_models.WorkspaceGroupSharing.WRITER)
        self.assertTrue(sharing.can_compute)

    def test_post_new_share_as_owner(self):
        group = acm_factories.ManagedGroupFactory.create(name=settings.ANVIL_DCC_ADMINS_GROUP_NAME)
        upload_workspace = factories.UploadWorkspaceFactory.create(
            workspace__billing_project__name="test-bp",
            workspace__name="test-ws",
            upload_cycle__is_future=True,
        )
        # Add the mocked API response.
        acls = [
            {
                "email": group.email,
                "accessLevel": "OWNER",
                "canShare": False,  # We're not tracking this in ACM so we always send False.
                "canCompute": True,
            }
        ]
        self.anvil_response_mock.add(
            responses.PATCH,
            self.api_client.rawls_entry_point + "/api/workspaces/test-bp/test-ws/acl?inviteUsersNotFound=false",
            status=200,
            match=[responses.matchers.json_params_matcher(acls)],
            json={"invitesSent": {}, "usersNotFound": {}, "usersUpdated": acls},
        )
        self.client.force_login(self.user)
        response = self.client.post(
            self.get_url(upload_workspace.workspace.billing_project.name, upload_workspace.workspace.name, group.name)
        )
        self.assertRedirects(response, upload_workspace.get_absolute_url())
        self.assertEqual(acm_models.WorkspaceGroupSharing.objects.count(), 1)
        sharing = acm_models.WorkspaceGroupSharing.objects.get(workspace=upload_workspace.workspace, group=group)
        self.assertEqual(sharing.access, acm_models.WorkspaceGroupSharing.OWNER)
        self.assertTrue(sharing.can_compute)

    def test_post_new_stop_sharing(self):
        group = acm_factories.ManagedGroupFactory.create()
        upload_workspace = factories.UploadWorkspaceFactory.create(
            workspace__billing_project__name="test-bp",
            workspace__name="test-ws",
            upload_cycle__is_future=True,
        )
        acm_factories.WorkspaceGroupSharingFactory.create(
            workspace=upload_workspace.workspace,
            group=group,
        )
        # Add the mocked API response.
        acls = [
            {
                "email": group.email,
                "accessLevel": "NO ACCESS",
                "canShare": False,  # We're not tracking this in ACM so we always send False.
                "canCompute": False,
            }
        ]
        self.anvil_response_mock.add(
            responses.PATCH,
            self.api_client.rawls_entry_point + "/api/workspaces/test-bp/test-ws/acl?inviteUsersNotFound=false",
            status=200,
            match=[responses.matchers.json_params_matcher(acls)],
            json={"invitesSent": {}, "usersNotFound": {}, "usersUpdated": acls},
        )
        self.client.force_login(self.user)
        response = self.client.post(
            self.get_url(upload_workspace.workspace.billing_project.name, upload_workspace.workspace.name, group.name)
        )
        self.assertRedirects(response, upload_workspace.get_absolute_url())
        self.assertEqual(acm_models.WorkspaceGroupSharing.objects.count(), 0)

    def test_post_update_share_as_reader(self):
        """Post request with ShareAsReader result."""
        upload_workspace = factories.UploadWorkspaceFactory.create(
            workspace__billing_project__name="test-bp", workspace__name="test-ws"
        )
        group = upload_workspace.workspace.authorization_domains.first()
        date_created = timezone.now() - timedelta(weeks=3)
        with freeze_time(date_created):
            sharing = acm_factories.WorkspaceGroupSharingFactory.create(
                workspace=upload_workspace.workspace,
                group=group,
                access=acm_models.WorkspaceGroupSharing.WRITER,
            )
        # Add the mocked API response.
        acls = [
            {
                "email": group.email,
                "accessLevel": "READER",
                "canShare": False,
                "canCompute": False,
            }
        ]
        self.anvil_response_mock.add(
            responses.PATCH,
            self.api_client.rawls_entry_point + "/api/workspaces/test-bp/test-ws/acl?inviteUsersNotFound=false",
            status=200,
            match=[responses.matchers.json_params_matcher(acls)],
            json={"invitesSent": {}, "usersNotFound": {}, "usersUpdated": acls},
        )
        self.client.force_login(self.user)
        response = self.client.post(
            self.get_url(upload_workspace.workspace.billing_project.name, upload_workspace.workspace.name, group.name)
        )
        self.assertRedirects(response, upload_workspace.get_absolute_url())
        self.assertEqual(acm_models.WorkspaceGroupSharing.objects.count(), 1)
        sharing.refresh_from_db()
        self.assertEqual(sharing.created, date_created)
        self.assertGreater(sharing.modified, date_created)
        self.assertEqual(sharing.access, acm_models.WorkspaceGroupSharing.READER)
        self.assertFalse(sharing.can_compute)

    def test_post_update_share_as_writer(self):
        group = acm_factories.ManagedGroupFactory.create()
        upload_workspace = factories.UploadWorkspaceFactory.create(
            workspace__billing_project__name="test-bp",
            workspace__name="test-ws",
            upload_cycle__is_current=True,
            research_center__uploader_group=group,
        )
        date_created = timezone.now() - timedelta(weeks=3)
        with freeze_time(date_created):
            sharing = acm_factories.WorkspaceGroupSharingFactory.create(
                workspace=upload_workspace.workspace,
                group=group,
                access=acm_models.WorkspaceGroupSharing.READER,
            )
        # Add the mocked API response.
        acls = [
            {
                "email": group.email,
                "accessLevel": "WRITER",
                "canShare": False,
                "canCompute": False,
            }
        ]
        self.anvil_response_mock.add(
            responses.PATCH,
            self.api_client.rawls_entry_point + "/api/workspaces/test-bp/test-ws/acl?inviteUsersNotFound=false",
            status=200,
            match=[responses.matchers.json_params_matcher(acls)],
            json={"invitesSent": {}, "usersNotFound": {}, "usersUpdated": acls},
        )
        self.client.force_login(self.user)
        response = self.client.post(
            self.get_url(upload_workspace.workspace.billing_project.name, upload_workspace.workspace.name, group.name)
        )
        self.assertRedirects(response, upload_workspace.get_absolute_url())
        self.assertEqual(acm_models.WorkspaceGroupSharing.objects.count(), 1)
        sharing.refresh_from_db()
        self.assertEqual(sharing.created, date_created)
        self.assertGreater(sharing.modified, date_created)
        self.assertEqual(sharing.access, acm_models.WorkspaceGroupSharing.WRITER)
        self.assertFalse(sharing.can_compute)

    def test_post_update_share_with_compute(self):
        group = acm_factories.ManagedGroupFactory.create(name="GREGOR_DCC_WRITERS")
        upload_workspace = factories.UploadWorkspaceFactory.create(
            workspace__billing_project__name="test-bp",
            workspace__name="test-ws",
            upload_cycle__is_future=True,
        )
        date_created = timezone.now() - timedelta(weeks=3)
        with freeze_time(date_created):
            sharing = acm_factories.WorkspaceGroupSharingFactory.create(
                workspace=upload_workspace.workspace,
                group=group,
                access=acm_models.WorkspaceGroupSharing.READER,
            )
        # Add the mocked API response.
        acls = [
            {
                "email": group.email,
                "accessLevel": "WRITER",
                "canShare": False,
                "canCompute": True,
            }
        ]
        self.anvil_response_mock.add(
            responses.PATCH,
            self.api_client.rawls_entry_point + "/api/workspaces/test-bp/test-ws/acl?inviteUsersNotFound=false",
            status=200,
            match=[responses.matchers.json_params_matcher(acls)],
            json={"invitesSent": {}, "usersNotFound": {}, "usersUpdated": acls},
        )
        self.client.force_login(self.user)
        response = self.client.post(
            self.get_url(upload_workspace.workspace.billing_project.name, upload_workspace.workspace.name, group.name)
        )
        self.assertRedirects(response, upload_workspace.get_absolute_url())
        self.assertEqual(acm_models.WorkspaceGroupSharing.objects.count(), 1)
        sharing.refresh_from_db()
        self.assertEqual(sharing.created, date_created)
        self.assertGreater(sharing.modified, date_created)
        self.assertEqual(sharing.access, acm_models.WorkspaceGroupSharing.WRITER)
        self.assertTrue(sharing.can_compute)

    def test_post_update_share_as_owner(self):
        group = acm_factories.ManagedGroupFactory.create(name=settings.ANVIL_DCC_ADMINS_GROUP_NAME)
        upload_workspace = factories.UploadWorkspaceFactory.create(
            workspace__billing_project__name="test-bp",
            workspace__name="test-ws",
            upload_cycle__is_future=True,
        )
        date_created = timezone.now() - timedelta(weeks=3)
        with freeze_time(date_created):
            sharing = acm_factories.WorkspaceGroupSharingFactory.create(
                workspace=upload_workspace.workspace,
                group=group,
                access=acm_models.WorkspaceGroupSharing.READER,
            )
        # Add the mocked API response.
        acls = [
            {
                "email": group.email,
                "accessLevel": "OWNER",
                "canShare": False,  # We're not tracking this in ACM so we always send False.
                "canCompute": True,
            }
        ]
        self.anvil_response_mock.add(
            responses.PATCH,
            self.api_client.rawls_entry_point + "/api/workspaces/test-bp/test-ws/acl?inviteUsersNotFound=false",
            status=200,
            match=[responses.matchers.json_params_matcher(acls)],
            json={"invitesSent": {}, "usersNotFound": {}, "usersUpdated": acls},
        )
        self.client.force_login(self.user)
        response = self.client.post(
            self.get_url(upload_workspace.workspace.billing_project.name, upload_workspace.workspace.name, group.name)
        )
        self.assertRedirects(response, upload_workspace.get_absolute_url())
        self.assertEqual(acm_models.WorkspaceGroupSharing.objects.count(), 1)
        sharing.refresh_from_db()
        self.assertEqual(sharing.created, date_created)
        self.assertGreater(sharing.modified, date_created)
        self.assertEqual(sharing.access, acm_models.WorkspaceGroupSharing.OWNER)
        self.assertTrue(sharing.can_compute)

    def test_post_share_as_reader_htmx(self):
        upload_workspace = factories.UploadWorkspaceFactory.create(
            workspace__billing_project__name="test-bp", workspace__name="test-ws"
        )
        group = upload_workspace.workspace.authorization_domains.first()
        # Add the mocked API response.
        acls = [
            {
                "email": group.email,
                "accessLevel": "READER",
                "canShare": False,
                "canCompute": False,
            }
        ]
        self.anvil_response_mock.add(
            responses.PATCH,
            self.api_client.rawls_entry_point + "/api/workspaces/test-bp/test-ws/acl?inviteUsersNotFound=false",
            status=200,
            match=[responses.matchers.json_params_matcher(acls)],
            json={"invitesSent": {}, "usersNotFound": {}, "usersUpdated": acls},
        )
        self.client.force_login(self.user)
        header = {"HTTP_HX-Request": "true"}
        response = self.client.post(
            self.get_url(upload_workspace.workspace.billing_project.name, upload_workspace.workspace.name, group.name),
            **header,
        )
        self.assertEqual(response.content.decode(), views.UploadWorkspaceSharingAuditResolve.htmx_success)
        self.assertEqual(acm_models.WorkspaceGroupSharing.objects.count(), 1)
        sharing = acm_models.WorkspaceGroupSharing.objects.get(workspace=upload_workspace.workspace, group=group)
        self.assertEqual(sharing.access, acm_models.WorkspaceGroupSharing.READER)
        self.assertFalse(sharing.can_compute)

    def test_post_new_share_as_writer_htmx(self):
        group = acm_factories.ManagedGroupFactory.create()
        upload_workspace = factories.UploadWorkspaceFactory.create(
            workspace__billing_project__name="test-bp",
            workspace__name="test-ws",
            upload_cycle__is_current=True,
            research_center__uploader_group=group,
        )
        # Add the mocked API response.
        acls = [
            {
                "email": group.email,
                "accessLevel": "WRITER",
                "canShare": False,
                "canCompute": False,
            }
        ]
        self.anvil_response_mock.add(
            responses.PATCH,
            self.api_client.rawls_entry_point + "/api/workspaces/test-bp/test-ws/acl?inviteUsersNotFound=false",
            status=200,
            match=[responses.matchers.json_params_matcher(acls)],
            json={"invitesSent": {}, "usersNotFound": {}, "usersUpdated": acls},
        )
        self.client.force_login(self.user)
        header = {"HTTP_HX-Request": "true"}
        response = self.client.post(
            self.get_url(upload_workspace.workspace.billing_project.name, upload_workspace.workspace.name, group.name),
            **header,
        )
        self.assertEqual(response.content.decode(), views.UploadWorkspaceSharingAuditResolve.htmx_success)
        self.assertEqual(acm_models.WorkspaceGroupSharing.objects.count(), 1)
        sharing = acm_models.WorkspaceGroupSharing.objects.get(workspace=upload_workspace.workspace, group=group)
        self.assertEqual(sharing.access, acm_models.WorkspaceGroupSharing.WRITER)
        self.assertFalse(sharing.can_compute)

    def test_post_new_share_with_compute_htmx(self):
        group = acm_factories.ManagedGroupFactory.create(name="GREGOR_DCC_WRITERS")
        upload_workspace = factories.UploadWorkspaceFactory.create(
            workspace__billing_project__name="test-bp",
            workspace__name="test-ws",
            upload_cycle__is_future=True,
        )
        # Add the mocked API response.
        acls = [
            {
                "email": group.email,
                "accessLevel": "WRITER",
                "canShare": False,
                "canCompute": True,
            }
        ]
        self.anvil_response_mock.add(
            responses.PATCH,
            self.api_client.rawls_entry_point + "/api/workspaces/test-bp/test-ws/acl?inviteUsersNotFound=false",
            status=200,
            match=[responses.matchers.json_params_matcher(acls)],
            json={"invitesSent": {}, "usersNotFound": {}, "usersUpdated": acls},
        )
        self.client.force_login(self.user)
        header = {"HTTP_HX-Request": "true"}
        response = self.client.post(
            self.get_url(upload_workspace.workspace.billing_project.name, upload_workspace.workspace.name, group.name),
            **header,
        )
        self.assertEqual(response.content.decode(), views.UploadWorkspaceSharingAuditResolve.htmx_success)
        self.assertEqual(acm_models.WorkspaceGroupSharing.objects.count(), 1)
        sharing = acm_models.WorkspaceGroupSharing.objects.get(workspace=upload_workspace.workspace, group=group)
        self.assertEqual(sharing.access, acm_models.WorkspaceGroupSharing.WRITER)
        self.assertTrue(sharing.can_compute)

    def test_post_new_share_as_owner_htmx(self):
        group = acm_factories.ManagedGroupFactory.create(name=settings.ANVIL_DCC_ADMINS_GROUP_NAME)
        upload_workspace = factories.UploadWorkspaceFactory.create(
            workspace__billing_project__name="test-bp",
            workspace__name="test-ws",
            upload_cycle__is_future=True,
        )
        # Add the mocked API response.
        acls = [
            {
                "email": group.email,
                "accessLevel": "OWNER",
                "canShare": False,  # We're not tracking this in ACM so we always send False.
                "canCompute": True,
            }
        ]
        self.anvil_response_mock.add(
            responses.PATCH,
            self.api_client.rawls_entry_point + "/api/workspaces/test-bp/test-ws/acl?inviteUsersNotFound=false",
            status=200,
            match=[responses.matchers.json_params_matcher(acls)],
            json={"invitesSent": {}, "usersNotFound": {}, "usersUpdated": acls},
        )
        self.client.force_login(self.user)
        header = {"HTTP_HX-Request": "true"}
        response = self.client.post(
            self.get_url(upload_workspace.workspace.billing_project.name, upload_workspace.workspace.name, group.name),
            **header,
        )
        self.assertEqual(response.content.decode(), views.UploadWorkspaceSharingAuditResolve.htmx_success)
        self.assertEqual(acm_models.WorkspaceGroupSharing.objects.count(), 1)
        sharing = acm_models.WorkspaceGroupSharing.objects.get(workspace=upload_workspace.workspace, group=group)
        self.assertEqual(sharing.access, acm_models.WorkspaceGroupSharing.OWNER)
        self.assertTrue(sharing.can_compute)

    def test_post_new_stop_sharing_htmx(self):
        group = acm_factories.ManagedGroupFactory.create()
        upload_workspace = factories.UploadWorkspaceFactory.create(
            workspace__billing_project__name="test-bp",
            workspace__name="test-ws",
            upload_cycle__is_future=True,
        )
        acm_factories.WorkspaceGroupSharingFactory.create(
            workspace=upload_workspace.workspace,
            group=group,
        )
        # Add the mocked API response.
        acls = [
            {
                "email": group.email,
                "accessLevel": "NO ACCESS",
                "canShare": False,  # We're not tracking this in ACM so we always send False.
                "canCompute": False,
            }
        ]
        self.anvil_response_mock.add(
            responses.PATCH,
            self.api_client.rawls_entry_point + "/api/workspaces/test-bp/test-ws/acl?inviteUsersNotFound=false",
            status=200,
            match=[responses.matchers.json_params_matcher(acls)],
            json={"invitesSent": {}, "usersNotFound": {}, "usersUpdated": acls},
        )
        self.client.force_login(self.user)
        header = {"HTTP_HX-Request": "true"}
        response = self.client.post(
            self.get_url(upload_workspace.workspace.billing_project.name, upload_workspace.workspace.name, group.name),
            **header,
        )
        self.assertEqual(response.content.decode(), views.UploadWorkspaceSharingAuditResolve.htmx_success)
        self.assertEqual(acm_models.WorkspaceGroupSharing.objects.count(), 0)

    def test_post_share_as_reader_anvil_api_error(self):
        upload_workspace = factories.UploadWorkspaceFactory.create(
            workspace__billing_project__name="test-bp", workspace__name="test-ws"
        )
        group = upload_workspace.workspace.authorization_domains.first()
        # Add the mocked API response.
        self.anvil_response_mock.add(
            responses.PATCH,
            self.api_client.rawls_entry_point + "/api/workspaces/test-bp/test-ws/acl?inviteUsersNotFound=false",
            status=500,
            json=ErrorResponseFactory().response,
        )
        self.client.force_login(self.user)
        response = self.client.post(
            self.get_url(upload_workspace.workspace.billing_project.name, upload_workspace.workspace.name, group.name)
        )
        self.assertEqual(response.status_code, 200)
        # No sharing object was created.
        self.assertEqual(acm_models.WorkspaceGroupSharing.objects.count(), 0)
        # Audit result is still as expected.
        self.assertIn("audit_result", response.context_data)
        audit_result = response.context_data["audit_result"]
        self.assertIsInstance(audit_result, workspace_sharing_audit_results.ShareAsReader)
        # A message was added.
        messages = [m.message for m in get_messages(response.wsgi_request)]
        self.assertEqual(len(messages), 1)
        self.assertIn("AnVIL API Error", str(messages[0]))

    def test_post_new_share_as_writer_anvil_api_error(self):
        group = acm_factories.ManagedGroupFactory.create()
        upload_workspace = factories.UploadWorkspaceFactory.create(
            workspace__billing_project__name="test-bp",
            workspace__name="test-ws",
            upload_cycle__is_current=True,
            research_center__uploader_group=group,
        )
        # Add the mocked API response.
        self.anvil_response_mock.add(
            responses.PATCH,
            self.api_client.rawls_entry_point + "/api/workspaces/test-bp/test-ws/acl?inviteUsersNotFound=false",
            status=500,
            json=ErrorResponseFactory().response,
        )
        self.client.force_login(self.user)
        response = self.client.post(
            self.get_url(upload_workspace.workspace.billing_project.name, upload_workspace.workspace.name, group.name)
        )
        self.assertEqual(response.status_code, 200)
        # No sharing object was created.
        self.assertEqual(acm_models.WorkspaceGroupSharing.objects.count(), 0)
        # Audit result is still as expected.
        self.assertIn("audit_result", response.context_data)
        audit_result = response.context_data["audit_result"]
        self.assertIsInstance(audit_result, workspace_sharing_audit_results.ShareAsWriter)
        # A message was added.
        messages = [m.message for m in get_messages(response.wsgi_request)]
        self.assertEqual(len(messages), 1)
        self.assertIn("AnVIL API Error", str(messages[0]))

    def test_post_new_share_with_compute_anvil_api_error(self):
        group = acm_factories.ManagedGroupFactory.create(name="GREGOR_DCC_WRITERS")
        upload_workspace = factories.UploadWorkspaceFactory.create(
            workspace__billing_project__name="test-bp",
            workspace__name="test-ws",
            upload_cycle__is_future=True,
        )
        # Add the mocked API response.
        self.anvil_response_mock.add(
            responses.PATCH,
            self.api_client.rawls_entry_point + "/api/workspaces/test-bp/test-ws/acl?inviteUsersNotFound=false",
            status=500,
            json=ErrorResponseFactory().response,
        )
        self.client.force_login(self.user)
        response = self.client.post(
            self.get_url(upload_workspace.workspace.billing_project.name, upload_workspace.workspace.name, group.name)
        )
        self.assertEqual(response.status_code, 200)
        # No sharing object was created.
        self.assertEqual(acm_models.WorkspaceGroupSharing.objects.count(), 0)
        # Audit result is still as expected.
        self.assertIn("audit_result", response.context_data)
        audit_result = response.context_data["audit_result"]
        self.assertIsInstance(audit_result, workspace_sharing_audit_results.ShareWithCompute)
        # A message was added.
        messages = [m.message for m in get_messages(response.wsgi_request)]
        self.assertEqual(len(messages), 1)
        self.assertIn("AnVIL API Error", str(messages[0]))

    def test_post_new_share_as_owner_anvil_api_error(self):
        group = acm_factories.ManagedGroupFactory.create(name=settings.ANVIL_DCC_ADMINS_GROUP_NAME)
        upload_workspace = factories.UploadWorkspaceFactory.create(
            workspace__billing_project__name="test-bp",
            workspace__name="test-ws",
            upload_cycle__is_future=True,
        )
        # Add the mocked API response.
        self.anvil_response_mock.add(
            responses.PATCH,
            self.api_client.rawls_entry_point + "/api/workspaces/test-bp/test-ws/acl?inviteUsersNotFound=false",
            status=500,
            json=ErrorResponseFactory().response,
        )
        self.client.force_login(self.user)
        response = self.client.post(
            self.get_url(upload_workspace.workspace.billing_project.name, upload_workspace.workspace.name, group.name)
        )
        self.assertEqual(response.status_code, 200)
        # No sharing object was created.
        self.assertEqual(acm_models.WorkspaceGroupSharing.objects.count(), 0)
        # Audit result is still as expected.
        self.assertIn("audit_result", response.context_data)
        audit_result = response.context_data["audit_result"]
        self.assertIsInstance(audit_result, workspace_sharing_audit_results.ShareAsOwner)
        # A message was added.
        messages = [m.message for m in get_messages(response.wsgi_request)]
        self.assertEqual(len(messages), 1)
        self.assertIn("AnVIL API Error", str(messages[0]))

    def test_post_new_stop_sharing_anvil_api_error(self):
        group = acm_factories.ManagedGroupFactory.create()
        upload_workspace = factories.UploadWorkspaceFactory.create(
            workspace__billing_project__name="test-bp",
            workspace__name="test-ws",
            upload_cycle__is_future=True,
        )
        date_created = timezone.now() - timedelta(weeks=3)
        with freeze_time(date_created):
            sharing = acm_factories.WorkspaceGroupSharingFactory.create(
                workspace=upload_workspace.workspace,
                group=group,
            )
        # Add the mocked API response.
        self.anvil_response_mock.add(
            responses.PATCH,
            self.api_client.rawls_entry_point + "/api/workspaces/test-bp/test-ws/acl?inviteUsersNotFound=false",
            status=500,
            json=ErrorResponseFactory().response,
        )
        self.client.force_login(self.user)
        response = self.client.post(
            self.get_url(upload_workspace.workspace.billing_project.name, upload_workspace.workspace.name, group.name)
        )
        self.assertEqual(response.status_code, 200)
        # The sharing object was not deleted.
        self.assertEqual(acm_models.WorkspaceGroupSharing.objects.count(), 1)
        sharing.refresh_from_db()
        self.assertEqual(sharing.created, date_created)
        self.assertEqual(sharing.modified, date_created)
        # Audit result is still as expected.
        self.assertIn("audit_result", response.context_data)
        audit_result = response.context_data["audit_result"]
        self.assertIsInstance(audit_result, workspace_sharing_audit_results.StopSharing)
        # A message was added.
        messages = [m.message for m in get_messages(response.wsgi_request)]
        self.assertEqual(len(messages), 1)
        self.assertIn("AnVIL API Error", str(messages[0]))

    def test_post_share_as_reader_anvil_api_error_htmx(self):
        upload_workspace = factories.UploadWorkspaceFactory.create(
            workspace__billing_project__name="test-bp", workspace__name="test-ws"
        )
        group = upload_workspace.workspace.authorization_domains.first()
        # Add the mocked API response.
        self.anvil_response_mock.add(
            responses.PATCH,
            self.api_client.rawls_entry_point + "/api/workspaces/test-bp/test-ws/acl?inviteUsersNotFound=false",
            status=500,
            json=ErrorResponseFactory().response,
        )
        self.client.force_login(self.user)
        header = {"HTTP_HX-Request": "true"}
        response = self.client.post(
            self.get_url(upload_workspace.workspace.billing_project.name, upload_workspace.workspace.name, group.name),
            **header,
        )
        self.assertEqual(response.content.decode(), views.UploadWorkspaceSharingAuditResolve.htmx_error)
        # No sharing object was created.
        self.assertEqual(acm_models.WorkspaceGroupSharing.objects.count(), 0)
        # No messages were added.
        messages = [m.message for m in get_messages(response.wsgi_request)]
        self.assertEqual(len(messages), 0)

    def test_post_new_share_as_writer_anvil_api_error_htmx(self):
        group = acm_factories.ManagedGroupFactory.create()
        upload_workspace = factories.UploadWorkspaceFactory.create(
            workspace__billing_project__name="test-bp",
            workspace__name="test-ws",
            upload_cycle__is_current=True,
            research_center__uploader_group=group,
        )
        # Add the mocked API response.
        self.anvil_response_mock.add(
            responses.PATCH,
            self.api_client.rawls_entry_point + "/api/workspaces/test-bp/test-ws/acl?inviteUsersNotFound=false",
            status=500,
            json=ErrorResponseFactory().response,
        )
        self.client.force_login(self.user)
        header = {"HTTP_HX-Request": "true"}
        response = self.client.post(
            self.get_url(upload_workspace.workspace.billing_project.name, upload_workspace.workspace.name, group.name),
            **header,
        )
        self.assertEqual(response.content.decode(), views.UploadWorkspaceSharingAuditResolve.htmx_error)
        # No sharing object was created.
        self.assertEqual(acm_models.WorkspaceGroupSharing.objects.count(), 0)
        # No messages were added.
        messages = [m.message for m in get_messages(response.wsgi_request)]
        self.assertEqual(len(messages), 0)

    def test_post_new_share_with_compute_anvil_api_error_htmx(self):
        group = acm_factories.ManagedGroupFactory.create(name="GREGOR_DCC_WRITERS")
        upload_workspace = factories.UploadWorkspaceFactory.create(
            workspace__billing_project__name="test-bp",
            workspace__name="test-ws",
            upload_cycle__is_future=True,
        )
        # Add the mocked API response.
        self.anvil_response_mock.add(
            responses.PATCH,
            self.api_client.rawls_entry_point + "/api/workspaces/test-bp/test-ws/acl?inviteUsersNotFound=false",
            status=500,
            json=ErrorResponseFactory().response,
        )
        self.client.force_login(self.user)
        header = {"HTTP_HX-Request": "true"}
        response = self.client.post(
            self.get_url(upload_workspace.workspace.billing_project.name, upload_workspace.workspace.name, group.name),
            **header,
        )
        self.assertEqual(response.content.decode(), views.UploadWorkspaceSharingAuditResolve.htmx_error)
        # No sharing object was created.
        self.assertEqual(acm_models.WorkspaceGroupSharing.objects.count(), 0)
        # No messages were added.
        messages = [m.message for m in get_messages(response.wsgi_request)]
        self.assertEqual(len(messages), 0)

    def test_post_new_share_as_owner_anvil_api_error_htmx(self):
        group = acm_factories.ManagedGroupFactory.create(name=settings.ANVIL_DCC_ADMINS_GROUP_NAME)
        upload_workspace = factories.UploadWorkspaceFactory.create(
            workspace__billing_project__name="test-bp",
            workspace__name="test-ws",
            upload_cycle__is_future=True,
        )
        # Add the mocked API response.
        self.anvil_response_mock.add(
            responses.PATCH,
            self.api_client.rawls_entry_point + "/api/workspaces/test-bp/test-ws/acl?inviteUsersNotFound=false",
            status=500,
            json=ErrorResponseFactory().response,
        )
        self.client.force_login(self.user)
        header = {"HTTP_HX-Request": "true"}
        response = self.client.post(
            self.get_url(upload_workspace.workspace.billing_project.name, upload_workspace.workspace.name, group.name),
            **header,
        )
        self.assertEqual(response.content.decode(), views.UploadWorkspaceSharingAuditResolve.htmx_error)
        # No sharing object was created.
        self.assertEqual(acm_models.WorkspaceGroupSharing.objects.count(), 0)
        # No messages were added.
        messages = [m.message for m in get_messages(response.wsgi_request)]
        self.assertEqual(len(messages), 0)

    def test_post_new_stop_sharing_anvil_api_error_htmx(self):
        group = acm_factories.ManagedGroupFactory.create()
        upload_workspace = factories.UploadWorkspaceFactory.create(
            workspace__billing_project__name="test-bp",
            workspace__name="test-ws",
            upload_cycle__is_future=True,
        )
        date_created = timezone.now() - timedelta(weeks=3)
        with freeze_time(date_created):
            sharing = acm_factories.WorkspaceGroupSharingFactory.create(
                workspace=upload_workspace.workspace,
                group=group,
            )
        # Add the mocked API response.
        self.anvil_response_mock.add(
            responses.PATCH,
            self.api_client.rawls_entry_point + "/api/workspaces/test-bp/test-ws/acl?inviteUsersNotFound=false",
            status=500,
            json=ErrorResponseFactory().response,
        )
        self.client.force_login(self.user)
        header = {"HTTP_HX-Request": "true"}
        response = self.client.post(
            self.get_url(upload_workspace.workspace.billing_project.name, upload_workspace.workspace.name, group.name),
            **header,
        )
        self.assertEqual(response.content.decode(), views.UploadWorkspaceSharingAuditResolve.htmx_error)
        # The sharing object was not deleted.
        self.assertEqual(acm_models.WorkspaceGroupSharing.objects.count(), 1)
        sharing.refresh_from_db()
        self.assertEqual(sharing.created, date_created)
        self.assertEqual(sharing.modified, date_created)
        # No messages were added.
        messages = [m.message for m in get_messages(response.wsgi_request)]
        self.assertEqual(len(messages), 0)

    def test_post_new_share_as_writer_group_not_found_on_anvil_htmx(self):
        group = acm_factories.ManagedGroupFactory.create()
        upload_workspace = factories.UploadWorkspaceFactory.create(
            workspace__billing_project__name="test-bp",
            workspace__name="test-ws",
            upload_cycle__is_current=True,
            research_center__uploader_group=group,
        )
        acls = [
            {
                "email": group.email,
                "accessLevel": "WRITER",
                "canShare": False,
                "canCompute": False,
            }
        ]
        self.anvil_response_mock.add(
            responses.PATCH,
            self.api_client.rawls_entry_point + "/api/workspaces/test-bp/test-ws/acl?inviteUsersNotFound=false",
            # Successful error code, but with usersNotFound
            status=200,
            json={"invitesSent": [], "usersNotFound": acls, "usersUpdated": []},
        )
        self.client.force_login(self.user)
        header = {"HTTP_HX-Request": "true"}
        response = self.client.post(
            self.get_url(upload_workspace.workspace.billing_project.name, upload_workspace.workspace.name, group.name),
            **header,
        )
        self.assertEqual(response.content.decode(), views.UploadWorkspaceSharingAuditResolve.htmx_error)
        # The sharing object was not deleted.
        self.assertEqual(acm_models.WorkspaceGroupSharing.objects.count(), 0)
        # sharing.refresh_from_db()
        # self.assertEqual(sharing.created, date_created)
        # self.assertEqual(sharing.modified, date_created)
        # No messages were added.
        messages = [m.message for m in get_messages(response.wsgi_request)]
        self.assertEqual(len(messages), 0)


class UploadWorkspaceAuthDomainAuditTest(AnVILAPIMockTestMixin, TestCase):
    """Tests for the UploadWorkspaceSharingAudit view."""

    def setUp(self):
        """Set up test class."""
        super().setUp()
        self.factory = RequestFactory()
        # Create a user with both view and edit permission.
        self.user = User.objects.create_user(username="test", password="test")
        self.user.user_permissions.add(
            Permission.objects.get(codename=AnVILProjectManagerAccess.STAFF_VIEW_PERMISSION_CODENAME)
        )

    def get_url(self, *args):
        """Get the url for the view being tested."""
        return reverse(
            "gregor_anvil:audit:upload_workspaces:auth_domains:all",
            args=args,
        )

    def get_view(self):
        """Return the view being tested."""
        return views.UploadWorkspaceAuthDomainAuditByUploadCycle.as_view()

    def test_view_redirect_not_logged_in(self):
        "View redirects to login view when user is not logged in."
        # Need a client for redirects.
        response = self.client.get(self.get_url())
        self.assertRedirects(
            response,
            resolve_url(settings.LOGIN_URL) + "?next=" + self.get_url(),
        )

    def test_status_code_with_user_permission_view(self):
        """Returns successful response code if the user has view permission."""
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

    def test_invalid_upload_cycle(self):
        """Raises a 404 error with an invalid upload cycle."""
        request = self.factory.get(self.get_url())
        request.user = self.user
        with self.assertRaises(Http404):
            self.get_view()(request)

    def test_context_audit_results_no_upload_workspaces(self):
        """The audit_results exists in the context."""
        self.client.force_login(self.user)
        response = self.client.get(self.get_url())
        self.assertIn("audit_results", response.context_data)
        audit_results = response.context_data["audit_results"]
        self.assertIsInstance(
            audit_results,
            upload_workspace_audit.UploadWorkspaceAuthDomainAudit,
        )
        self.assertTrue(audit_results.completed)
        self.assertEqual(audit_results.queryset.count(), 0)

    def test_context_audit_results_one_upload_workspace(self):
        """The audit_results exists in the context."""
        upload_workspace = factories.UploadWorkspaceFactory.create()
        self.client.force_login(self.user)
        response = self.client.get(self.get_url())
        self.assertIn("audit_results", response.context_data)
        audit_results = response.context_data["audit_results"]
        self.assertIsInstance(
            audit_results,
            upload_workspace_audit.UploadWorkspaceAuthDomainAudit,
        )
        self.assertTrue(audit_results.completed)
        self.assertEqual(audit_results.queryset.count(), 1)
        self.assertIn(upload_workspace, audit_results.queryset)

    def test_context_audit_results_two_upload_workspaces(self):
        """The audit_results exists in the context."""
        upload_workspace_1 = factories.UploadWorkspaceFactory.create()
        upload_workspace_2 = factories.UploadWorkspaceFactory.create()
        self.client.force_login(self.user)
        response = self.client.get(self.get_url())
        self.assertIn("audit_results", response.context_data)
        audit_results = response.context_data["audit_results"]
        self.assertIsInstance(
            audit_results,
            upload_workspace_audit.UploadWorkspaceAuthDomainAudit,
        )
        self.assertTrue(audit_results.completed)
        self.assertEqual(audit_results.queryset.count(), 2)
        self.assertIn(upload_workspace_1, audit_results.queryset)
        self.assertIn(upload_workspace_2, audit_results.queryset)

    def test_context_verified_table_access(self):
        """verified_table shows a record when audit has verified access."""
        upload_workspace = factories.UploadWorkspaceFactory.create()
        group = acm_factories.ManagedGroupFactory.create(name=settings.ANVIL_DCC_ADMINS_GROUP_NAME)
        acm_factories.GroupGroupMembershipFactory.create(
            parent_group=upload_workspace.workspace.authorization_domains.first(),
            child_group=group,
            role=acm_models.GroupGroupMembership.ADMIN,
        )
        # Check the table in the context.
        self.client.force_login(self.user)
        response = self.client.get(self.get_url())
        self.assertIn("verified_table", response.context_data)
        table = response.context_data["verified_table"]
        self.assertIsInstance(
            table,
            upload_workspace_audit.UploadWorkspaceAuthDomainAuditTable,
        )
        self.assertEqual(len(table.rows), 1)
        self.assertEqual(table.rows[0].get_cell_value("workspace"), upload_workspace.workspace)
        self.assertEqual(table.rows[0].get_cell_value("managed_group"), group)
        self.assertEqual(table.rows[0].get_cell_value("role"), acm_models.GroupGroupMembership.ADMIN)
        self.assertEqual(
            table.rows[0].get_cell_value("note"),
            upload_workspace_audit.UploadWorkspaceAuthDomainAudit.DCC_ADMINS,
        )
        self.assertEqual(table.rows[0].get_cell_value("action"), "&mdash;")

    def test_context_verified_table_no_access(self):
        """verified_table shows a record when audit has verifiednotmember."""
        upload_workspace = factories.UploadWorkspaceFactory.create(upload_cycle__is_past=True)
        # Create and share a combined workspace.
        factories.CombinedConsortiumDataWorkspaceFactory(
            upload_cycle=upload_workspace.upload_cycle,
            date_completed=timezone.localdate() - timedelta(days=1),
        )
        group = acm_factories.ManagedGroupFactory.create(name="GREGOR_DCC_WRITERS")
        # Check the table in the context.
        self.client.force_login(self.user)
        response = self.client.get(self.get_url())
        self.assertIn("verified_table", response.context_data)
        table = response.context_data["verified_table"]
        self.assertIsInstance(
            table,
            upload_workspace_audit.UploadWorkspaceAuthDomainAuditTable,
        )
        self.assertEqual(len(table.rows), 1)
        self.assertEqual(table.rows[0].get_cell_value("workspace"), upload_workspace.workspace)
        self.assertEqual(table.rows[0].get_cell_value("managed_group"), group)
        self.assertEqual(table.rows[0].get_cell_value("role"), None)
        self.assertEqual(
            table.rows[0].get_cell_value("note"),
            upload_workspace_audit.UploadWorkspaceAuthDomainAudit.DCC_AFTER_COMBINED,
        )
        self.assertEqual(table.rows[0].get_cell_value("action"), "&mdash;")

    def test_context_needs_action_table_add_member(self):
        """needs_action_table shows a record when audit finds that access needs to be granted."""
        upload_workspace = factories.UploadWorkspaceFactory.create(upload_cycle__is_future=True)
        group = acm_factories.ManagedGroupFactory.create(name="GREGOR_DCC_WRITERS")
        # Check the table in the context.
        self.client.force_login(self.user)
        response = self.client.get(self.get_url())
        self.assertIn("needs_action_table", response.context_data)
        table = response.context_data["needs_action_table"]
        self.assertIsInstance(
            table,
            upload_workspace_audit.UploadWorkspaceAuthDomainAuditTable,
        )
        self.assertEqual(len(table.rows), 1)
        self.assertEqual(table.rows[0].get_cell_value("workspace"), upload_workspace.workspace)
        self.assertEqual(table.rows[0].get_cell_value("managed_group"), group)
        self.assertIsNone(table.rows[0].get_cell_value("role"))
        self.assertEqual(
            table.rows[0].get_cell_value("note"),
            upload_workspace_audit.UploadWorkspaceAuthDomainAudit.DCC_BEFORE_COMBINED,
        )
        self.assertNotEqual(table.rows[0].get_cell_value("action"), "&mdash;")

    def test_context_needs_action_table_add_admin(self):
        """needs_action_table shows a record when audit finds that access needs to be granted."""
        upload_workspace = factories.UploadWorkspaceFactory.create()
        group = acm_factories.ManagedGroupFactory.create(name=settings.ANVIL_DCC_ADMINS_GROUP_NAME)
        # Check the table in the context.
        self.client.force_login(self.user)
        response = self.client.get(self.get_url())
        self.assertIn("needs_action_table", response.context_data)
        table = response.context_data["needs_action_table"]
        self.assertIsInstance(
            table,
            upload_workspace_audit.UploadWorkspaceAuthDomainAuditTable,
        )
        self.assertEqual(len(table.rows), 1)
        self.assertEqual(table.rows[0].get_cell_value("workspace"), upload_workspace.workspace)
        self.assertEqual(table.rows[0].get_cell_value("managed_group"), group)
        self.assertIsNone(table.rows[0].get_cell_value("role"))
        self.assertEqual(
            table.rows[0].get_cell_value("note"),
            upload_workspace_audit.UploadWorkspaceAuthDomainAudit.DCC_ADMINS,
        )
        self.assertNotEqual(table.rows[0].get_cell_value("action"), "&mdash;")

    def test_context_needs_action_table_remove(self):
        """needs_action_table shows a record when audit finds that access needs to be removed."""
        upload_workspace = factories.UploadWorkspaceFactory.create(upload_cycle__is_past=True)
        # Create and share a combined workspace.
        factories.CombinedConsortiumDataWorkspaceFactory(
            upload_cycle=upload_workspace.upload_cycle,
            date_completed=timezone.localdate() - timedelta(days=1),
        )
        group = acm_factories.ManagedGroupFactory.create(name="GREGOR_DCC_WRITERS")
        acm_factories.GroupGroupMembershipFactory.create(
            parent_group=upload_workspace.workspace.authorization_domains.first(),
            child_group=group,
            role=acm_models.GroupGroupMembership.MEMBER,
        )
        # Check the table in the context.
        self.client.force_login(self.user)
        response = self.client.get(self.get_url())
        self.assertIn("needs_action_table", response.context_data)
        table = response.context_data["needs_action_table"]
        self.assertIsInstance(
            table,
            upload_workspace_audit.UploadWorkspaceAuthDomainAuditTable,
        )
        self.assertEqual(len(table.rows), 1)
        self.assertEqual(table.rows[0].get_cell_value("workspace"), upload_workspace.workspace)
        self.assertEqual(table.rows[0].get_cell_value("managed_group"), group)
        self.assertEqual(table.rows[0].get_cell_value("role"), acm_models.GroupGroupMembership.MEMBER)
        self.assertEqual(
            table.rows[0].get_cell_value("note"),
            upload_workspace_audit.UploadWorkspaceAuthDomainAudit.DCC_AFTER_COMBINED,
        )
        self.assertNotEqual(table.rows[0].get_cell_value("action"), "&mdash;")

    def test_context_error_table_remove(self):
        """error table shows a record when audit finds that access needs to be removed."""
        upload_workspace = factories.UploadWorkspaceFactory.create()
        group = acm_factories.ManagedGroupFactory.create()
        acm_factories.GroupGroupMembershipFactory.create(
            parent_group=upload_workspace.workspace.authorization_domains.first(),
            child_group=group,
            role=acm_models.GroupGroupMembership.MEMBER,
        )
        # Check the table in the context.
        self.client.force_login(self.user)
        response = self.client.get(self.get_url())
        self.assertIn("errors_table", response.context_data)
        table = response.context_data["errors_table"]
        self.assertIsInstance(
            table,
            upload_workspace_audit.UploadWorkspaceAuthDomainAuditTable,
        )
        self.assertEqual(len(table.rows), 1)
        self.assertEqual(table.rows[0].get_cell_value("workspace"), upload_workspace.workspace)
        self.assertEqual(table.rows[0].get_cell_value("managed_group"), group)
        self.assertEqual(table.rows[0].get_cell_value("role"), acm_models.GroupGroupMembership.MEMBER)
        self.assertEqual(
            table.rows[0].get_cell_value("note"),
            upload_workspace_audit.UploadWorkspaceAuthDomainAudit.OTHER_GROUP,
        )
        self.assertNotEqual(table.rows[0].get_cell_value("action"), "&mdash;")

    def test_context_errors_table_change_to_member(self):
        """errors table shows a record when audit finds that access needs to be removed."""
        upload_workspace = factories.UploadWorkspaceFactory.create()
        group = acm_factories.ManagedGroupFactory.create(name="GREGOR_DCC_WRITERS")
        acm_factories.GroupGroupMembershipFactory.create(
            parent_group=upload_workspace.workspace.authorization_domains.first(),
            child_group=group,
            role=acm_models.GroupGroupMembership.ADMIN,
        )
        # Check the table in the context.
        self.client.force_login(self.user)
        response = self.client.get(self.get_url())
        self.assertIn("errors_table", response.context_data)
        table = response.context_data["errors_table"]
        self.assertIsInstance(
            table,
            upload_workspace_audit.UploadWorkspaceAuthDomainAuditTable,
        )
        self.assertEqual(len(table.rows), 1)
        self.assertEqual(table.rows[0].get_cell_value("workspace"), upload_workspace.workspace)
        self.assertEqual(table.rows[0].get_cell_value("managed_group"), group)
        self.assertEqual(table.rows[0].get_cell_value("role"), acm_models.GroupGroupMembership.ADMIN)
        self.assertEqual(
            table.rows[0].get_cell_value("note"),
            upload_workspace_audit.UploadWorkspaceAuthDomainAudit.DCC_BEFORE_COMBINED,
        )
        self.assertNotEqual(table.rows[0].get_cell_value("action"), "&mdash;")

    def test_context_needs_action_table_change_to_admin(self):
        """error table shows a record when audit finds that access needs to be removed."""
        upload_workspace = factories.UploadWorkspaceFactory.create()
        group = acm_factories.ManagedGroupFactory.create(name=settings.ANVIL_DCC_ADMINS_GROUP_NAME)
        acm_factories.GroupGroupMembershipFactory.create(
            parent_group=upload_workspace.workspace.authorization_domains.first(),
            child_group=group,
            role=acm_models.GroupGroupMembership.MEMBER,
        )
        # Check the table in the context.
        self.client.force_login(self.user)
        response = self.client.get(self.get_url())
        self.assertIn("needs_action_table", response.context_data)
        table = response.context_data["needs_action_table"]
        self.assertIsInstance(
            table,
            upload_workspace_audit.UploadWorkspaceAuthDomainAuditTable,
        )
        self.assertEqual(len(table.rows), 1)
        self.assertEqual(table.rows[0].get_cell_value("workspace"), upload_workspace.workspace)
        self.assertEqual(table.rows[0].get_cell_value("managed_group"), group)
        self.assertEqual(table.rows[0].get_cell_value("role"), acm_models.GroupGroupMembership.MEMBER)
        self.assertEqual(
            table.rows[0].get_cell_value("note"),
            upload_workspace_audit.UploadWorkspaceAuthDomainAudit.DCC_ADMINS,
        )
        self.assertNotEqual(table.rows[0].get_cell_value("action"), "&mdash;")

    def test_title(self):
        self.client.force_login(self.user)
        response = self.client.get(self.get_url())
        # self.assertContains(response, str(self.upload_workspace))
        self.assertIn("all upload workspaces", response.content.decode().lower())


class UploadWorkspaceAuthDomainAuditByWorkspaceTest(AnVILAPIMockTestMixin, TestCase):
    """Tests for the UploadWorkspaceAuthDomainAuditByWorkspace view."""

    def setUp(self):
        """Set up test class."""
        super().setUp()
        self.factory = RequestFactory()
        # Create a user with both view and edit permission.
        self.user = User.objects.create_user(username="test", password="test")
        self.user.user_permissions.add(
            Permission.objects.get(codename=AnVILProjectManagerAccess.STAFF_VIEW_PERMISSION_CODENAME)
        )
        self.user.user_permissions.add(
            Permission.objects.get(codename=AnVILProjectManagerAccess.STAFF_EDIT_PERMISSION_CODENAME)
        )
        self.upload_workspace = factories.UploadWorkspaceFactory.create(upload_cycle__is_future=True)

    def get_url(self, *args):
        """Get the url for the view being tested."""
        return reverse(
            "gregor_anvil:audit:upload_workspaces:auth_domains:by_upload_workspace",
            args=args,
        )

    def get_view(self):
        """Return the view being tested."""
        return views.UploadWorkspaceAuthDomainAuditByWorkspace.as_view()

    def test_view_redirect_not_logged_in(self):
        "View redirects to login view when user is not logged in."
        # Need a client for redirects.
        response = self.client.get(self.get_url("foo", "bar"))
        self.assertRedirects(
            response,
            resolve_url(settings.LOGIN_URL) + "?next=" + self.get_url("foo", "bar"),
        )

    def test_status_code_with_user_permission_view(self):
        """Returns successful response code if the user has view permission."""
        self.client.force_login(self.user)
        response = self.client.get(
            self.get_url(
                self.upload_workspace.workspace.billing_project.name,
                self.upload_workspace.workspace.name,
            )
        )
        self.assertEqual(response.status_code, 200)

    def test_access_without_user_permission(self):
        """Raises permission denied if user has no permissions."""
        user_no_perms = User.objects.create_user(username="test-none", password="test-none")
        request = self.factory.get(
            self.get_url(
                self.upload_workspace.workspace.billing_project.name,
                self.upload_workspace.workspace.name,
            )
        )
        request.user = user_no_perms
        with self.assertRaises(PermissionDenied):
            self.get_view()(
                request,
                billing_project_slug=self.upload_workspace.workspace.billing_project.name,
                workspace_slug=self.upload_workspace.workspace.name,
            )

    def test_invalid_billing_project_name(self):
        """Raises a 404 error with an invalid object billing project."""
        request = self.factory.get(self.get_url("foo", self.upload_workspace.workspace.name))
        request.user = self.user
        with self.assertRaises(Http404):
            self.get_view()(
                request,
                billing_project_slug="foo",
                workspace_slug=self.upload_workspace.workspace.name,
            )

    def test_invalid_workspace_name(self):
        """Raises a 404 error with an invalid workspace name."""
        request = self.factory.get(self.get_url(self.upload_workspace.workspace.billing_project.name, "foo"))
        request.user = self.user
        with self.assertRaises(Http404):
            self.get_view()(
                request,
                billing_project_slug=self.upload_workspace.workspace.billing_project.name,
                workspace_slug="foo",
            )

    def test_context_audit_results(self):
        """The audit_results exists in the context."""
        self.client.force_login(self.user)
        response = self.client.get(
            self.get_url(
                self.upload_workspace.workspace.billing_project.name,
                self.upload_workspace.workspace.name,
            )
        )
        self.assertIn("audit_results", response.context_data)
        audit_results = response.context_data["audit_results"]
        self.assertIsInstance(
            audit_results,
            upload_workspace_audit.UploadWorkspaceAuthDomainAudit,
        )
        self.assertTrue(audit_results.completed)
        self.assertEqual(audit_results.queryset.count(), 1)
        self.assertIn(self.upload_workspace, audit_results.queryset)

    def test_context_audit_results_does_not_include_other_workspaces(self):
        """The audit_results does not include other workspaces."""
        other_workspace = factories.UploadWorkspaceFactory.create()
        self.client.force_login(self.user)
        response = self.client.get(
            self.get_url(
                self.upload_workspace.workspace.billing_project.name,
                self.upload_workspace.workspace.name,
            )
        )
        audit_results = response.context_data["audit_results"]
        self.assertEqual(audit_results.queryset.count(), 1)
        self.assertNotIn(other_workspace, audit_results.queryset)

    def test_context_verified_table_access(self):
        """verified_table shows a record when audit has verified access."""
        group = acm_factories.ManagedGroupFactory.create(name=settings.ANVIL_DCC_ADMINS_GROUP_NAME)
        acm_factories.GroupGroupMembershipFactory.create(
            parent_group=self.upload_workspace.workspace.authorization_domains.first(),
            child_group=group,
            role=acm_models.GroupGroupMembership.ADMIN,
        )
        # Check the table in the context.
        self.client.force_login(self.user)
        response = self.client.get(
            self.get_url(
                self.upload_workspace.workspace.billing_project.name,
                self.upload_workspace.workspace.name,
            )
        )
        self.assertIn("verified_table", response.context_data)
        table = response.context_data["verified_table"]
        self.assertIsInstance(
            table,
            upload_workspace_audit.UploadWorkspaceAuthDomainAuditTable,
        )
        self.assertEqual(len(table.rows), 1)
        self.assertEqual(table.rows[0].get_cell_value("workspace"), self.upload_workspace.workspace)
        self.assertEqual(table.rows[0].get_cell_value("managed_group"), group)
        self.assertEqual(table.rows[0].get_cell_value("role"), acm_models.GroupGroupMembership.ADMIN)
        self.assertEqual(
            table.rows[0].get_cell_value("note"),
            upload_workspace_audit.UploadWorkspaceAuthDomainAudit.DCC_ADMINS,
        )
        self.assertEqual(table.rows[0].get_cell_value("action"), "&mdash;")

    def test_context_verified_table_no_access(self):
        """verified_table shows a record when audit has verifiednotmember."""
        self.upload_workspace.upload_cycle.start_date = timezone.localdate() - timedelta(days=20)
        self.upload_workspace.upload_cycle.start_date = timezone.localdate() - timedelta(days=10)
        self.upload_workspace.upload_cycle.save()
        # Create and share a combined workspace.
        factories.CombinedConsortiumDataWorkspaceFactory(
            upload_cycle=self.upload_workspace.upload_cycle,
            date_completed=timezone.localdate() - timedelta(days=1),
        )
        group = acm_factories.ManagedGroupFactory.create(name="GREGOR_DCC_WRITERS")
        # Check the table in the context.
        self.client.force_login(self.user)
        response = self.client.get(
            self.get_url(
                self.upload_workspace.workspace.billing_project.name,
                self.upload_workspace.workspace.name,
            )
        )
        self.assertIn("verified_table", response.context_data)
        table = response.context_data["verified_table"]
        self.assertIsInstance(
            table,
            upload_workspace_audit.UploadWorkspaceAuthDomainAuditTable,
        )
        self.assertEqual(len(table.rows), 1)
        self.assertEqual(table.rows[0].get_cell_value("workspace"), self.upload_workspace.workspace)
        self.assertEqual(table.rows[0].get_cell_value("managed_group"), group)
        self.assertEqual(table.rows[0].get_cell_value("role"), None)
        self.assertEqual(
            table.rows[0].get_cell_value("note"),
            upload_workspace_audit.UploadWorkspaceAuthDomainAudit.DCC_AFTER_COMBINED,
        )
        self.assertEqual(table.rows[0].get_cell_value("action"), "&mdash;")

    def test_context_needs_action_table_add_member(self):
        """needs_action_table shows a record when audit finds that access needs to be granted."""
        group = acm_factories.ManagedGroupFactory.create(name="GREGOR_DCC_WRITERS")
        # Check the table in the context.
        self.client.force_login(self.user)
        response = self.client.get(
            self.get_url(
                self.upload_workspace.workspace.billing_project.name,
                self.upload_workspace.workspace.name,
            )
        )
        self.assertIn("needs_action_table", response.context_data)
        table = response.context_data["needs_action_table"]
        self.assertIsInstance(
            table,
            upload_workspace_audit.UploadWorkspaceAuthDomainAuditTable,
        )
        self.assertEqual(len(table.rows), 1)
        self.assertEqual(table.rows[0].get_cell_value("workspace"), self.upload_workspace.workspace)
        self.assertEqual(table.rows[0].get_cell_value("managed_group"), group)
        self.assertIsNone(table.rows[0].get_cell_value("role"))
        self.assertEqual(
            table.rows[0].get_cell_value("note"),
            upload_workspace_audit.UploadWorkspaceAuthDomainAudit.DCC_BEFORE_COMBINED,
        )
        self.assertNotEqual(table.rows[0].get_cell_value("action"), "&mdash;")

    def test_context_needs_action_table_add_admin(self):
        """needs_action_table shows a record when audit finds that access needs to be granted."""
        group = acm_factories.ManagedGroupFactory.create(name=settings.ANVIL_DCC_ADMINS_GROUP_NAME)
        # Check the table in the context.
        self.client.force_login(self.user)
        response = self.client.get(
            self.get_url(
                self.upload_workspace.workspace.billing_project.name,
                self.upload_workspace.workspace.name,
            )
        )
        self.assertIn("needs_action_table", response.context_data)
        table = response.context_data["needs_action_table"]
        self.assertIsInstance(
            table,
            upload_workspace_audit.UploadWorkspaceAuthDomainAuditTable,
        )
        self.assertEqual(len(table.rows), 1)
        self.assertEqual(table.rows[0].get_cell_value("workspace"), self.upload_workspace.workspace)
        self.assertEqual(table.rows[0].get_cell_value("managed_group"), group)
        self.assertIsNone(table.rows[0].get_cell_value("role"))
        self.assertEqual(
            table.rows[0].get_cell_value("note"),
            upload_workspace_audit.UploadWorkspaceAuthDomainAudit.DCC_ADMINS,
        )
        self.assertNotEqual(table.rows[0].get_cell_value("action"), "&mdash;")

    def test_context_needs_action_table_remove(self):
        """needs_action_table shows a record when audit finds that access needs to be removed."""
        self.upload_workspace.upload_cycle.start_date = timezone.localdate() - timedelta(days=20)
        self.upload_workspace.upload_cycle.start_date = timezone.localdate() - timedelta(days=10)
        self.upload_workspace.upload_cycle.save()
        # Create and share a combined workspace.
        factories.CombinedConsortiumDataWorkspaceFactory(
            upload_cycle=self.upload_workspace.upload_cycle,
            date_completed=timezone.localdate() - timedelta(days=1),
        )
        group = acm_factories.ManagedGroupFactory.create(name="GREGOR_DCC_WRITERS")
        acm_factories.GroupGroupMembershipFactory.create(
            parent_group=self.upload_workspace.workspace.authorization_domains.first(),
            child_group=group,
            role=acm_models.GroupGroupMembership.MEMBER,
        )
        # Check the table in the context.
        self.client.force_login(self.user)
        response = self.client.get(
            self.get_url(
                self.upload_workspace.workspace.billing_project.name,
                self.upload_workspace.workspace.name,
            )
        )
        self.assertIn("needs_action_table", response.context_data)
        table = response.context_data["needs_action_table"]
        self.assertIsInstance(
            table,
            upload_workspace_audit.UploadWorkspaceAuthDomainAuditTable,
        )
        self.assertEqual(len(table.rows), 1)
        self.assertEqual(table.rows[0].get_cell_value("workspace"), self.upload_workspace.workspace)
        self.assertEqual(table.rows[0].get_cell_value("managed_group"), group)
        self.assertEqual(table.rows[0].get_cell_value("role"), acm_models.GroupGroupMembership.MEMBER)
        self.assertEqual(
            table.rows[0].get_cell_value("note"),
            upload_workspace_audit.UploadWorkspaceAuthDomainAudit.DCC_AFTER_COMBINED,
        )
        self.assertNotEqual(table.rows[0].get_cell_value("action"), "&mdash;")

    def test_context_error_table_remove(self):
        """error table shows a record when audit finds that access needs to be removed."""
        group = acm_factories.ManagedGroupFactory.create()
        acm_factories.GroupGroupMembershipFactory.create(
            parent_group=self.upload_workspace.workspace.authorization_domains.first(),
            child_group=group,
            role=acm_models.GroupGroupMembership.MEMBER,
        )
        # Check the table in the context.
        self.client.force_login(self.user)
        response = self.client.get(
            self.get_url(
                self.upload_workspace.workspace.billing_project.name,
                self.upload_workspace.workspace.name,
            )
        )
        self.assertIn("errors_table", response.context_data)
        table = response.context_data["errors_table"]
        self.assertIsInstance(
            table,
            upload_workspace_audit.UploadWorkspaceAuthDomainAuditTable,
        )
        self.assertEqual(len(table.rows), 1)
        self.assertEqual(table.rows[0].get_cell_value("workspace"), self.upload_workspace.workspace)
        self.assertEqual(table.rows[0].get_cell_value("managed_group"), group)
        self.assertEqual(table.rows[0].get_cell_value("role"), acm_models.GroupGroupMembership.MEMBER)
        self.assertEqual(
            table.rows[0].get_cell_value("note"),
            upload_workspace_audit.UploadWorkspaceAuthDomainAudit.OTHER_GROUP,
        )
        self.assertNotEqual(table.rows[0].get_cell_value("action"), "&mdash;")

    def test_context_errors_table_change_to_member(self):
        """needs action table shows a record when audit finds that access needs to be removed."""
        group = acm_factories.ManagedGroupFactory.create(name="GREGOR_DCC_WRITERS")
        acm_factories.GroupGroupMembershipFactory.create(
            parent_group=self.upload_workspace.workspace.authorization_domains.first(),
            child_group=group,
            role=acm_models.GroupGroupMembership.ADMIN,
        )
        # Check the table in the context.
        self.client.force_login(self.user)
        response = self.client.get(
            self.get_url(
                self.upload_workspace.workspace.billing_project.name,
                self.upload_workspace.workspace.name,
            )
        )
        self.assertIn("errors_table", response.context_data)
        table = response.context_data["errors_table"]
        self.assertIsInstance(
            table,
            upload_workspace_audit.UploadWorkspaceAuthDomainAuditTable,
        )
        self.assertEqual(len(table.rows), 1)
        self.assertEqual(table.rows[0].get_cell_value("workspace"), self.upload_workspace.workspace)
        self.assertEqual(table.rows[0].get_cell_value("managed_group"), group)
        self.assertEqual(table.rows[0].get_cell_value("role"), acm_models.GroupGroupMembership.ADMIN)
        self.assertEqual(
            table.rows[0].get_cell_value("note"),
            upload_workspace_audit.UploadWorkspaceAuthDomainAudit.DCC_BEFORE_COMBINED,
        )
        self.assertNotEqual(table.rows[0].get_cell_value("action"), "&mdash;")

    def test_context_needs_action_table_change_to_admin(self):
        """error table shows a record when audit finds that access needs to be removed."""
        group = acm_factories.ManagedGroupFactory.create(name=settings.ANVIL_DCC_ADMINS_GROUP_NAME)
        acm_factories.GroupGroupMembershipFactory.create(
            parent_group=self.upload_workspace.workspace.authorization_domains.first(),
            child_group=group,
            role=acm_models.GroupGroupMembership.MEMBER,
        )
        # Check the table in the context.
        self.client.force_login(self.user)
        response = self.client.get(
            self.get_url(
                self.upload_workspace.workspace.billing_project.name,
                self.upload_workspace.workspace.name,
            )
        )
        self.assertIn("needs_action_table", response.context_data)
        table = response.context_data["needs_action_table"]
        self.assertIsInstance(
            table,
            upload_workspace_audit.UploadWorkspaceAuthDomainAuditTable,
        )
        self.assertEqual(len(table.rows), 1)
        self.assertEqual(table.rows[0].get_cell_value("workspace"), self.upload_workspace.workspace)
        self.assertEqual(table.rows[0].get_cell_value("managed_group"), group)
        self.assertEqual(table.rows[0].get_cell_value("role"), acm_models.GroupGroupMembership.MEMBER)
        self.assertEqual(
            table.rows[0].get_cell_value("note"),
            upload_workspace_audit.UploadWorkspaceAuthDomainAudit.DCC_ADMINS,
        )
        self.assertNotEqual(table.rows[0].get_cell_value("action"), "&mdash;")

    def test_title(self):
        self.client.force_login(self.user)
        response = self.client.get(
            self.get_url(
                self.upload_workspace.workspace.billing_project.name,
                self.upload_workspace.workspace.name,
            )
        )
        self.assertContains(response, str(self.upload_workspace))
        self.assertNotIn("all upload workspaces", response.content.decode().lower())


class UploadWorkspaceAuthDomainAuditByUploadCycleTest(AnVILAPIMockTestMixin, TestCase):
    """Tests for the UploadWorkspaceSharingAuditByUploadCycle view."""

    def setUp(self):
        """Set up test class."""
        super().setUp()
        self.factory = RequestFactory()
        # Create a user with both view and edit permission.
        self.user = User.objects.create_user(username="test", password="test")
        self.user.user_permissions.add(
            Permission.objects.get(codename=AnVILProjectManagerAccess.STAFF_VIEW_PERMISSION_CODENAME)
        )
        self.upload_cycle = factories.UploadCycleFactory.create(is_future=True)

    def get_url(self, *args):
        """Get the url for the view being tested."""
        return reverse(
            "gregor_anvil:audit:upload_workspaces:auth_domains:by_upload_cycle",
            args=args,
        )

    def get_view(self):
        """Return the view being tested."""
        return views.UploadWorkspaceAuthDomainAuditByUploadCycle.as_view()

    def test_view_redirect_not_logged_in(self):
        "View redirects to login view when user is not logged in."
        # Need a client for redirects.
        response = self.client.get(self.get_url(self.upload_cycle.cycle + 1))
        self.assertRedirects(
            response,
            resolve_url(settings.LOGIN_URL) + "?next=" + self.get_url(self.upload_cycle.cycle + 1),
        )

    def test_status_code_with_user_permission_view(self):
        """Returns successful response code if the user has view permission."""
        self.client.force_login(self.user)
        response = self.client.get(self.get_url(self.upload_cycle.cycle))
        self.assertEqual(response.status_code, 200)

    def test_access_without_user_permission(self):
        """Raises permission denied if user has no permissions."""
        user_no_perms = User.objects.create_user(username="test-none", password="test-none")
        request = self.factory.get(self.get_url(self.upload_cycle.cycle))
        request.user = user_no_perms
        with self.assertRaises(PermissionDenied):
            self.get_view()(request, cycle=self.upload_cycle.cycle)

    def test_invalid_upload_cycle(self):
        """Raises a 404 error with an invalid upload cycle."""
        request = self.factory.get(self.get_url(self.upload_cycle.cycle + 1))
        request.user = self.user
        with self.assertRaises(Http404):
            self.get_view()(request, cycle=self.upload_cycle.cycle + 1)

    def test_context_audit_results_no_upload_workspaces(self):
        """The audit_results exists in the context."""
        self.client.force_login(self.user)
        response = self.client.get(self.get_url(self.upload_cycle.cycle))
        self.assertIn("audit_results", response.context_data)
        audit_results = response.context_data["audit_results"]
        self.assertIsInstance(
            audit_results,
            upload_workspace_audit.UploadWorkspaceAuthDomainAudit,
        )
        self.assertTrue(audit_results.completed)
        self.assertEqual(audit_results.queryset.count(), 0)

    def test_context_audit_results_one_upload_workspace(self):
        """The audit_results exists in the context."""
        upload_workspace = factories.UploadWorkspaceFactory.create(upload_cycle=self.upload_cycle)
        self.client.force_login(self.user)
        response = self.client.get(self.get_url(self.upload_cycle.cycle))
        self.assertIn("audit_results", response.context_data)
        audit_results = response.context_data["audit_results"]
        self.assertIsInstance(
            audit_results,
            upload_workspace_audit.UploadWorkspaceAuthDomainAudit,
        )
        self.assertTrue(audit_results.completed)
        self.assertEqual(audit_results.queryset.count(), 1)
        self.assertIn(upload_workspace, audit_results.queryset)

    def test_context_audit_results_two_upload_workspaces(self):
        """The audit_results exists in the context."""
        upload_workspace_1 = factories.UploadWorkspaceFactory.create(upload_cycle=self.upload_cycle)
        upload_workspace_2 = factories.UploadWorkspaceFactory.create(upload_cycle=self.upload_cycle)
        self.client.force_login(self.user)
        response = self.client.get(self.get_url(self.upload_cycle.cycle))
        self.assertIn("audit_results", response.context_data)
        audit_results = response.context_data["audit_results"]
        self.assertIsInstance(
            audit_results,
            upload_workspace_audit.UploadWorkspaceAuthDomainAudit,
        )
        self.assertTrue(audit_results.completed)
        self.assertEqual(audit_results.queryset.count(), 2)
        self.assertIn(upload_workspace_1, audit_results.queryset)
        self.assertIn(upload_workspace_2, audit_results.queryset)

    def test_context_audit_results_ignores_other_upload_cycles(self):
        """The audit_results exists in the context."""
        upload_workspace = factories.UploadWorkspaceFactory.create(upload_cycle__cycle=self.upload_cycle.cycle + 1)
        self.client.force_login(self.user)
        response = self.client.get(self.get_url(self.upload_cycle.cycle))
        self.assertIn("audit_results", response.context_data)
        audit_results = response.context_data["audit_results"]
        self.assertIsInstance(
            audit_results,
            upload_workspace_audit.UploadWorkspaceAuthDomainAudit,
        )
        self.assertTrue(audit_results.completed)
        self.assertEqual(audit_results.queryset.count(), 0)
        self.assertNotIn(upload_workspace, audit_results.queryset)

    def test_context_verified_table_access(self):
        """verified_table shows a record when audit has verified access."""
        upload_workspace = factories.UploadWorkspaceFactory.create(upload_cycle=self.upload_cycle)
        group = acm_factories.ManagedGroupFactory.create(name=settings.ANVIL_DCC_ADMINS_GROUP_NAME)
        acm_factories.GroupGroupMembershipFactory.create(
            parent_group=upload_workspace.workspace.authorization_domains.first(),
            child_group=group,
            role=acm_models.GroupGroupMembership.ADMIN,
        )
        # Check the table in the context.
        self.client.force_login(self.user)
        response = self.client.get(self.get_url(upload_workspace.upload_cycle.cycle))
        self.assertIn("verified_table", response.context_data)
        table = response.context_data["verified_table"]
        self.assertIsInstance(
            table,
            upload_workspace_audit.UploadWorkspaceAuthDomainAuditTable,
        )
        self.assertEqual(len(table.rows), 1)
        self.assertEqual(table.rows[0].get_cell_value("workspace"), upload_workspace.workspace)
        self.assertEqual(table.rows[0].get_cell_value("managed_group"), group)
        self.assertEqual(table.rows[0].get_cell_value("role"), acm_models.GroupGroupMembership.ADMIN)
        self.assertEqual(
            table.rows[0].get_cell_value("note"),
            upload_workspace_audit.UploadWorkspaceAuthDomainAudit.DCC_ADMINS,
        )
        self.assertEqual(table.rows[0].get_cell_value("action"), "&mdash;")

    def test_context_verified_table_no_access(self):
        """verified_table shows a record when audit has verifiednotmember."""
        upload_workspace = factories.UploadWorkspaceFactory.create(
            upload_cycle__start_date=timezone.localdate() - timedelta(days=20),
            upload_cycle__end_date=timezone.localdate() - timedelta(days=10),
        )
        # Create and share a combined workspace.
        factories.CombinedConsortiumDataWorkspaceFactory(
            upload_cycle=upload_workspace.upload_cycle,
            date_completed=timezone.localdate() - timedelta(days=1),
        )
        group = acm_factories.ManagedGroupFactory.create(name="GREGOR_DCC_WRITERS")
        # Check the table in the context.
        self.client.force_login(self.user)
        response = self.client.get(self.get_url(upload_workspace.upload_cycle.cycle))
        self.assertIn("verified_table", response.context_data)
        table = response.context_data["verified_table"]
        self.assertIsInstance(
            table,
            upload_workspace_audit.UploadWorkspaceAuthDomainAuditTable,
        )
        self.assertEqual(len(table.rows), 1)
        self.assertEqual(table.rows[0].get_cell_value("workspace"), upload_workspace.workspace)
        self.assertEqual(table.rows[0].get_cell_value("managed_group"), group)
        self.assertEqual(table.rows[0].get_cell_value("role"), None)
        self.assertEqual(
            table.rows[0].get_cell_value("note"),
            upload_workspace_audit.UploadWorkspaceAuthDomainAudit.DCC_AFTER_COMBINED,
        )
        self.assertEqual(table.rows[0].get_cell_value("action"), "&mdash;")

    def test_context_needs_action_table_add_member(self):
        """needs_action_table shows a record when audit finds that access needs to be granted."""
        upload_workspace = factories.UploadWorkspaceFactory.create(upload_cycle=self.upload_cycle)
        group = acm_factories.ManagedGroupFactory.create(name="GREGOR_DCC_WRITERS")
        # Check the table in the context.
        self.client.force_login(self.user)
        response = self.client.get(self.get_url(upload_workspace.upload_cycle.cycle))
        self.assertIn("needs_action_table", response.context_data)
        table = response.context_data["needs_action_table"]
        self.assertIsInstance(
            table,
            upload_workspace_audit.UploadWorkspaceAuthDomainAuditTable,
        )
        self.assertEqual(len(table.rows), 1)
        self.assertEqual(table.rows[0].get_cell_value("workspace"), upload_workspace.workspace)
        self.assertEqual(table.rows[0].get_cell_value("managed_group"), group)
        self.assertIsNone(table.rows[0].get_cell_value("role"))
        self.assertEqual(
            table.rows[0].get_cell_value("note"),
            upload_workspace_audit.UploadWorkspaceAuthDomainAudit.DCC_BEFORE_COMBINED,
        )
        self.assertNotEqual(table.rows[0].get_cell_value("action"), "&mdash;")

    def test_context_needs_action_table_add_admin(self):
        """needs_action_table shows a record when audit finds that access needs to be granted."""
        upload_workspace = factories.UploadWorkspaceFactory.create(upload_cycle=self.upload_cycle)
        group = acm_factories.ManagedGroupFactory.create(name=settings.ANVIL_DCC_ADMINS_GROUP_NAME)
        # Check the table in the context.
        self.client.force_login(self.user)
        response = self.client.get(self.get_url(upload_workspace.upload_cycle.cycle))
        self.assertIn("needs_action_table", response.context_data)
        table = response.context_data["needs_action_table"]
        self.assertIsInstance(
            table,
            upload_workspace_audit.UploadWorkspaceAuthDomainAuditTable,
        )
        self.assertEqual(len(table.rows), 1)
        self.assertEqual(table.rows[0].get_cell_value("workspace"), upload_workspace.workspace)
        self.assertEqual(table.rows[0].get_cell_value("managed_group"), group)
        self.assertIsNone(table.rows[0].get_cell_value("role"))
        self.assertEqual(
            table.rows[0].get_cell_value("note"),
            upload_workspace_audit.UploadWorkspaceAuthDomainAudit.DCC_ADMINS,
        )
        self.assertNotEqual(table.rows[0].get_cell_value("action"), "&mdash;")

    def test_context_needs_action_table_remove(self):
        """needs_action_table shows a record when audit finds that access needs to be removed."""
        upload_workspace = factories.UploadWorkspaceFactory.create(
            upload_cycle__start_date=timezone.localdate() - timedelta(days=20),
            upload_cycle__end_date=timezone.localdate() - timedelta(days=10),
        )
        # Create and share a combined workspace.
        factories.CombinedConsortiumDataWorkspaceFactory(
            upload_cycle=upload_workspace.upload_cycle,
            date_completed=timezone.localdate() - timedelta(days=1),
        )
        group = acm_factories.ManagedGroupFactory.create(name="GREGOR_DCC_WRITERS")
        acm_factories.GroupGroupMembershipFactory.create(
            parent_group=upload_workspace.workspace.authorization_domains.first(),
            child_group=group,
            role=acm_models.GroupGroupMembership.MEMBER,
        )
        # Check the table in the context.
        self.client.force_login(self.user)
        response = self.client.get(self.get_url(upload_workspace.upload_cycle.cycle))
        self.assertIn("needs_action_table", response.context_data)
        table = response.context_data["needs_action_table"]
        self.assertIsInstance(
            table,
            upload_workspace_audit.UploadWorkspaceAuthDomainAuditTable,
        )
        self.assertEqual(len(table.rows), 1)
        self.assertEqual(table.rows[0].get_cell_value("workspace"), upload_workspace.workspace)
        self.assertEqual(table.rows[0].get_cell_value("managed_group"), group)
        self.assertEqual(table.rows[0].get_cell_value("role"), acm_models.GroupGroupMembership.MEMBER)
        self.assertEqual(
            table.rows[0].get_cell_value("note"),
            upload_workspace_audit.UploadWorkspaceAuthDomainAudit.DCC_AFTER_COMBINED,
        )
        self.assertNotEqual(table.rows[0].get_cell_value("action"), "&mdash;")

    def test_context_error_table_remove(self):
        """error table shows a record when audit finds that access needs to be removed."""
        upload_workspace = factories.UploadWorkspaceFactory.create(upload_cycle=self.upload_cycle)
        group = acm_factories.ManagedGroupFactory.create()
        acm_factories.GroupGroupMembershipFactory.create(
            parent_group=upload_workspace.workspace.authorization_domains.first(),
            child_group=group,
            role=acm_models.GroupGroupMembership.MEMBER,
        )
        # Check the table in the context.
        self.client.force_login(self.user)
        response = self.client.get(self.get_url(upload_workspace.upload_cycle.cycle))
        self.assertIn("errors_table", response.context_data)
        table = response.context_data["errors_table"]
        self.assertIsInstance(
            table,
            upload_workspace_audit.UploadWorkspaceAuthDomainAuditTable,
        )
        self.assertEqual(len(table.rows), 1)
        self.assertEqual(table.rows[0].get_cell_value("workspace"), upload_workspace.workspace)
        self.assertEqual(table.rows[0].get_cell_value("managed_group"), group)
        self.assertEqual(table.rows[0].get_cell_value("role"), acm_models.GroupGroupMembership.MEMBER)
        self.assertEqual(
            table.rows[0].get_cell_value("note"),
            upload_workspace_audit.UploadWorkspaceAuthDomainAudit.OTHER_GROUP,
        )
        self.assertNotEqual(table.rows[0].get_cell_value("action"), "&mdash;")

    def test_context_errors_table_change_to_member(self):
        """needs action table shows a record when audit finds that access needs to be removed."""
        upload_workspace = factories.UploadWorkspaceFactory.create(upload_cycle=self.upload_cycle)
        group = acm_factories.ManagedGroupFactory.create(name="GREGOR_DCC_WRITERS")
        acm_factories.GroupGroupMembershipFactory.create(
            parent_group=upload_workspace.workspace.authorization_domains.first(),
            child_group=group,
            role=acm_models.GroupGroupMembership.ADMIN,
        )
        # Check the table in the context.
        self.client.force_login(self.user)
        response = self.client.get(self.get_url(upload_workspace.upload_cycle.cycle))
        self.assertIn("errors_table", response.context_data)
        table = response.context_data["errors_table"]
        self.assertIsInstance(
            table,
            upload_workspace_audit.UploadWorkspaceAuthDomainAuditTable,
        )
        self.assertEqual(len(table.rows), 1)
        self.assertEqual(table.rows[0].get_cell_value("workspace"), upload_workspace.workspace)
        self.assertEqual(table.rows[0].get_cell_value("managed_group"), group)
        self.assertEqual(table.rows[0].get_cell_value("role"), acm_models.GroupGroupMembership.ADMIN)
        self.assertEqual(
            table.rows[0].get_cell_value("note"),
            upload_workspace_audit.UploadWorkspaceAuthDomainAudit.DCC_BEFORE_COMBINED,
        )
        self.assertNotEqual(table.rows[0].get_cell_value("action"), "&mdash;")

    def test_context_needs_action_table_change_to_admin(self):
        """error table shows a record when audit finds that access needs to be removed."""
        upload_workspace = factories.UploadWorkspaceFactory.create(upload_cycle=self.upload_cycle)
        group = acm_factories.ManagedGroupFactory.create(name=settings.ANVIL_DCC_ADMINS_GROUP_NAME)
        acm_factories.GroupGroupMembershipFactory.create(
            parent_group=upload_workspace.workspace.authorization_domains.first(),
            child_group=group,
            role=acm_models.GroupGroupMembership.MEMBER,
        )
        # Check the table in the context.
        self.client.force_login(self.user)
        response = self.client.get(self.get_url(upload_workspace.upload_cycle.cycle))
        self.assertIn("needs_action_table", response.context_data)
        table = response.context_data["needs_action_table"]
        self.assertIsInstance(
            table,
            upload_workspace_audit.UploadWorkspaceAuthDomainAuditTable,
        )
        self.assertEqual(len(table.rows), 1)
        self.assertEqual(table.rows[0].get_cell_value("workspace"), upload_workspace.workspace)
        self.assertEqual(table.rows[0].get_cell_value("managed_group"), group)
        self.assertEqual(table.rows[0].get_cell_value("role"), acm_models.GroupGroupMembership.MEMBER)
        self.assertEqual(
            table.rows[0].get_cell_value("note"),
            upload_workspace_audit.UploadWorkspaceAuthDomainAudit.DCC_ADMINS,
        )
        self.assertNotEqual(table.rows[0].get_cell_value("action"), "&mdash;")

    def test_title(self):
        self.client.force_login(self.user)
        response = self.client.get(self.get_url(self.upload_cycle.cycle))
        self.assertContains(response, str(self.upload_cycle))
        self.assertNotIn("all upload workspaces", response.content.decode().lower())


class UploadWorkspaceAuthDomainAuditResolveTest(AnVILAPIMockTestMixin, TestCase):
    """Tests for the UploadWorkspaceAuthDomainAuditResolve view."""

    def setUp(self):
        """Set up test class."""
        super().setUp()
        self.factory = RequestFactory()
        # Create a user with both view and edit permission.
        self.user = User.objects.create_user(username="test", password="test")
        self.user.user_permissions.add(
            Permission.objects.get(codename=AnVILProjectManagerAccess.STAFF_VIEW_PERMISSION_CODENAME)
        )
        self.user.user_permissions.add(
            Permission.objects.get(codename=AnVILProjectManagerAccess.STAFF_EDIT_PERMISSION_CODENAME)
        )

    def get_url(self, *args):
        """Get the url for the view being tested."""
        return reverse(
            "gregor_anvil:audit:upload_workspaces:auth_domains:resolve",
            args=args,
        )

    def get_view(self):
        """Return the view being tested."""
        return views.UploadWorkspaceAuthDomainAuditResolve.as_view()

    def test_view_redirect_not_logged_in(self):
        "View redirects to login view when user is not logged in."
        # Need a client for redirects.
        response = self.client.get(self.get_url("foo", "bar", "foobar"))
        self.assertRedirects(
            response,
            resolve_url(settings.LOGIN_URL) + "?next=" + self.get_url("foo", "bar", "foobar"),
        )

    def test_status_code_with_user_permission_staff_edit(self):
        """Returns successful response code if the user has staff edit permission."""
        upload_workspace = factories.UploadWorkspaceFactory.create()
        group = acm_factories.ManagedGroupFactory.create()
        self.client.force_login(self.user)
        response = self.client.get(
            self.get_url(upload_workspace.workspace.billing_project.name, upload_workspace.workspace.name, group.name)
        )
        self.assertEqual(response.status_code, 200)

    def test_status_code_with_user_permission_staff_view(self):
        """Returns 403 response code if the user has staff view permission."""
        user_view = User.objects.create_user(username="test-view", password="test-view")
        user_view.user_permissions.add(
            Permission.objects.get(codename=AnVILProjectManagerAccess.STAFF_VIEW_PERMISSION_CODENAME)
        )
        self.client.force_login(self.user)
        request = self.factory.get(self.get_url("foo", "bar", "foobar"))
        request.user = user_view
        with self.assertRaises(PermissionDenied):
            self.get_view()(request)

    def test_status_code_with_user_permission_view(self):
        """Returns forbidden response code if the user has view permission."""
        user = User.objects.create_user(username="test-none", password="test-none")
        user.user_permissions.add(Permission.objects.get(codename=AnVILProjectManagerAccess.VIEW_PERMISSION_CODENAME))
        request = self.factory.get(self.get_url("foo", "bar", "foobar"))
        request.user = user
        with self.assertRaises(PermissionDenied):
            self.get_view()(request)

    def test_access_without_user_permission(self):
        """Raises permission denied if user has no permissions."""
        user_no_perms = User.objects.create_user(username="test-none", password="test-none")
        request = self.factory.get(self.get_url("foo", "bar", "foobar"))
        request.user = user_no_perms
        with self.assertRaises(PermissionDenied):
            self.get_view()(request)

    def test_get_billing_project_does_not_exist(self):
        """Raises a 404 error with an invalid billing project."""
        upload_workspace = factories.UploadWorkspaceFactory.create()
        group = acm_factories.ManagedGroupFactory.create()
        self.client.force_login(self.user)
        response = self.client.get(self.get_url("foo", upload_workspace.workspace.name, group.name))
        self.assertEqual(response.status_code, 404)

    def test_get_workspace_name_does_not_exist(self):
        """Raises a 404 error with an invalid billing project."""
        upload_workspace = factories.UploadWorkspaceFactory.create()
        group = acm_factories.ManagedGroupFactory.create()
        self.client.force_login(self.user)
        response = self.client.get(self.get_url(upload_workspace.workspace.billing_project.name, "foo", group.name))
        self.assertEqual(response.status_code, 404)

    def test_get_group_does_not_exist(self):
        """get request raises a 404 error with an non-existent email."""
        upload_workspace = factories.UploadWorkspaceFactory.create()
        self.client.force_login(self.user)
        response = self.client.get(
            self.get_url(
                upload_workspace.workspace.billing_project.name,
                upload_workspace.workspace.name,
                "foo",
            )
        )
        self.assertEqual(response.status_code, 404)

    def test_get_context_audit_result(self):
        """The audit_results exists in the context."""
        upload_workspace = factories.UploadWorkspaceFactory.create()
        group = acm_factories.ManagedGroupFactory.create()
        self.client.force_login(self.user)
        response = self.client.get(
            self.get_url(upload_workspace.workspace.billing_project.name, upload_workspace.workspace.name, group.name)
        )
        self.assertIn("audit_result", response.context_data)
        self.assertIsInstance(
            response.context_data["audit_result"],
            workspace_auth_domain_audit_results.WorkspaceAuthDomainAuditResult,
        )

    def test_get_verified_member(self):
        """Get request with VerifiedMember result."""
        upload_workspace = factories.UploadWorkspaceFactory.create(upload_cycle__is_future=True)
        group = acm_factories.ManagedGroupFactory.create(name="GREGOR_DCC_WRITERS")
        acm_factories.GroupGroupMembershipFactory.create(
            parent_group=upload_workspace.workspace.authorization_domains.first(),
            child_group=group,
            role=acm_models.GroupGroupMembership.MEMBER,
        )
        self.client.force_login(self.user)
        response = self.client.get(
            self.get_url(upload_workspace.workspace.billing_project.name, upload_workspace.workspace.name, group.name)
        )
        self.assertIn("audit_result", response.context_data)
        audit_result = response.context_data["audit_result"]
        self.assertIsInstance(audit_result, workspace_auth_domain_audit_results.VerifiedMember)
        self.assertEqual(audit_result.workspace, upload_workspace.workspace)
        self.assertEqual(audit_result.managed_group, group)
        self.assertEqual(audit_result.note, upload_workspace_audit.UploadWorkspaceAuthDomainAudit.DCC_BEFORE_COMBINED)

    def test_get_verified_admin(self):
        """Get request with VerifiedAdmin result."""
        upload_workspace = factories.UploadWorkspaceFactory.create(upload_cycle__is_future=True)
        group = acm_factories.ManagedGroupFactory.create(name=settings.ANVIL_DCC_ADMINS_GROUP_NAME)
        acm_factories.GroupGroupMembershipFactory.create(
            parent_group=upload_workspace.workspace.authorization_domains.first(),
            child_group=group,
            role=acm_models.GroupGroupMembership.ADMIN,
        )
        self.client.force_login(self.user)
        response = self.client.get(
            self.get_url(upload_workspace.workspace.billing_project.name, upload_workspace.workspace.name, group.name)
        )
        self.assertIn("audit_result", response.context_data)
        audit_result = response.context_data["audit_result"]
        self.assertIsInstance(audit_result, workspace_auth_domain_audit_results.VerifiedAdmin)
        self.assertEqual(audit_result.workspace, upload_workspace.workspace)
        self.assertEqual(audit_result.managed_group, group)
        self.assertEqual(audit_result.note, upload_workspace_audit.UploadWorkspaceAuthDomainAudit.DCC_ADMINS)

    def test_get_verified_not_member(self):
        """Get request with VerifiedNotMember result."""
        upload_workspace = factories.UploadWorkspaceFactory.create()
        group = acm_factories.ManagedGroupFactory.create()
        self.client.force_login(self.user)
        response = self.client.get(
            self.get_url(upload_workspace.workspace.billing_project.name, upload_workspace.workspace.name, group.name)
        )
        self.assertIn("audit_result", response.context_data)
        audit_result = response.context_data["audit_result"]
        self.assertIsInstance(audit_result, workspace_auth_domain_audit_results.VerifiedNotMember)
        self.assertEqual(audit_result.workspace, upload_workspace.workspace)
        self.assertEqual(audit_result.managed_group, group)
        self.assertEqual(audit_result.note, upload_workspace_audit.UploadWorkspaceAuthDomainAudit.OTHER_GROUP)

    def test_get_add_member(self):
        """Get request with AddMember result."""
        upload_workspace = factories.UploadWorkspaceFactory.create(upload_cycle__is_future=True)
        group = acm_factories.ManagedGroupFactory.create(name="GREGOR_DCC_WRITERS")
        self.client.force_login(self.user)
        response = self.client.get(
            self.get_url(upload_workspace.workspace.billing_project.name, upload_workspace.workspace.name, group.name)
        )
        self.assertIn("audit_result", response.context_data)
        audit_result = response.context_data["audit_result"]
        self.assertIsInstance(audit_result, workspace_auth_domain_audit_results.AddMember)
        self.assertEqual(audit_result.workspace, upload_workspace.workspace)
        self.assertEqual(audit_result.managed_group, group)
        self.assertEqual(audit_result.note, upload_workspace_audit.UploadWorkspaceAuthDomainAudit.DCC_BEFORE_COMBINED)

    def test_get_add_admin(self):
        """Get request with AddAdmin result."""
        upload_workspace = factories.UploadWorkspaceFactory.create(upload_cycle__is_future=True)
        group = acm_factories.ManagedGroupFactory.create(name=settings.ANVIL_DCC_ADMINS_GROUP_NAME)
        self.client.force_login(self.user)
        response = self.client.get(
            self.get_url(upload_workspace.workspace.billing_project.name, upload_workspace.workspace.name, group.name)
        )
        self.assertIn("audit_result", response.context_data)
        audit_result = response.context_data["audit_result"]
        self.assertIsInstance(audit_result, workspace_auth_domain_audit_results.AddAdmin)
        self.assertEqual(audit_result.workspace, upload_workspace.workspace)
        self.assertEqual(audit_result.managed_group, group)
        self.assertEqual(audit_result.note, upload_workspace_audit.UploadWorkspaceAuthDomainAudit.DCC_ADMINS)

    def test_get_change_to_member(self):
        """Get request with ChangeToMember result."""
        upload_workspace = factories.UploadWorkspaceFactory.create(upload_cycle__is_future=True)
        group = acm_factories.ManagedGroupFactory.create(name="GREGOR_DCC_WRITERS")
        acm_factories.GroupGroupMembershipFactory.create(
            parent_group=upload_workspace.workspace.authorization_domains.first(),
            child_group=group,
            role=acm_models.GroupGroupMembership.ADMIN,
        )
        self.client.force_login(self.user)
        response = self.client.get(
            self.get_url(upload_workspace.workspace.billing_project.name, upload_workspace.workspace.name, group.name)
        )
        self.assertIn("audit_result", response.context_data)
        audit_result = response.context_data["audit_result"]
        self.assertIsInstance(audit_result, workspace_auth_domain_audit_results.ChangeToMember)
        self.assertEqual(audit_result.workspace, upload_workspace.workspace)
        self.assertEqual(audit_result.managed_group, group)
        self.assertEqual(audit_result.note, upload_workspace_audit.UploadWorkspaceAuthDomainAudit.DCC_BEFORE_COMBINED)

    def test_get_change_to_admin(self):
        """Get request with ChangeToAdmin result."""
        upload_workspace = factories.UploadWorkspaceFactory.create(upload_cycle__is_future=True)
        group = acm_factories.ManagedGroupFactory.create(name=settings.ANVIL_DCC_ADMINS_GROUP_NAME)
        acm_factories.GroupGroupMembershipFactory.create(
            parent_group=upload_workspace.workspace.authorization_domains.first(),
            child_group=group,
            role=acm_models.GroupGroupMembership.MEMBER,
        )
        self.client.force_login(self.user)
        response = self.client.get(
            self.get_url(upload_workspace.workspace.billing_project.name, upload_workspace.workspace.name, group.name)
        )
        self.assertIn("audit_result", response.context_data)
        audit_result = response.context_data["audit_result"]
        self.assertIsInstance(audit_result, workspace_auth_domain_audit_results.ChangeToAdmin)
        self.assertEqual(audit_result.workspace, upload_workspace.workspace)
        self.assertEqual(audit_result.managed_group, group)
        self.assertEqual(audit_result.note, upload_workspace_audit.UploadWorkspaceAuthDomainAudit.DCC_ADMINS)

    def test_get_remove(self):
        """Get request with ChangeToAdmin result."""
        upload_workspace = factories.UploadWorkspaceFactory.create(upload_cycle__is_future=True)
        group = acm_factories.ManagedGroupFactory.create()
        acm_factories.GroupGroupMembershipFactory.create(
            parent_group=upload_workspace.workspace.authorization_domains.first(),
            child_group=group,
        )
        self.client.force_login(self.user)
        response = self.client.get(
            self.get_url(upload_workspace.workspace.billing_project.name, upload_workspace.workspace.name, group.name)
        )
        self.assertIn("audit_result", response.context_data)
        audit_result = response.context_data["audit_result"]
        self.assertIsInstance(audit_result, workspace_auth_domain_audit_results.Remove)
        self.assertEqual(audit_result.workspace, upload_workspace.workspace)
        self.assertEqual(audit_result.managed_group, group)
        self.assertEqual(audit_result.note, upload_workspace_audit.UploadWorkspaceAuthDomainAudit.OTHER_GROUP)

    def test_post_billing_project_does_not_exist(self):
        """Raises a 404 error with an invalid billing project."""
        upload_workspace = factories.UploadWorkspaceFactory.create()
        group = acm_factories.ManagedGroupFactory.create()
        self.client.force_login(self.user)
        response = self.client.post(self.get_url("foo", upload_workspace.workspace.name, group.name))
        self.assertEqual(response.status_code, 404)

    def test_post_workspace_name_does_not_exist(self):
        """Raises a 404 error with an invalid billing project."""
        upload_workspace = factories.UploadWorkspaceFactory.create()
        group = acm_factories.ManagedGroupFactory.create()
        self.client.force_login(self.user)
        response = self.client.post(self.get_url(upload_workspace.workspace.billing_project.name, "foo", group.name))
        self.assertEqual(response.status_code, 404)

    def test_post_group_does_not_exist(self):
        """post request raises a 404 error with an non-existent email."""
        upload_workspace = factories.UploadWorkspaceFactory.create()
        self.client.force_login(self.user)
        response = self.client.post(
            self.get_url(
                upload_workspace.workspace.billing_project.name,
                upload_workspace.workspace.name,
                "foo",
            )
        )
        self.assertEqual(response.status_code, 404)

    def test_post_verified_member(self):
        """Get request with VerifiedMember result."""
        upload_workspace = factories.UploadWorkspaceFactory.create(upload_cycle__is_future=True)
        group = acm_factories.ManagedGroupFactory.create(name="GREGOR_DCC_WRITERS")
        date_created = timezone.now() - timedelta(weeks=3)
        with freeze_time(date_created):
            membership = acm_factories.GroupGroupMembershipFactory.create(
                parent_group=upload_workspace.workspace.authorization_domains.first(),
                child_group=group,
                role=acm_models.GroupGroupMembership.MEMBER,
            )
        self.client.force_login(self.user)
        response = self.client.post(
            self.get_url(upload_workspace.workspace.billing_project.name, upload_workspace.workspace.name, group.name)
        )
        self.assertRedirects(response, upload_workspace.get_absolute_url())
        self.assertEqual(acm_models.GroupGroupMembership.objects.count(), 1)
        membership.refresh_from_db()
        self.assertEqual(membership.created, date_created)
        self.assertEqual(membership.modified, date_created)

    def test_post_verified_admin(self):
        """Get request with VerifiedAdmin result."""
        upload_workspace = factories.UploadWorkspaceFactory.create(upload_cycle__is_future=True)
        group = acm_factories.ManagedGroupFactory.create(name=settings.ANVIL_DCC_ADMINS_GROUP_NAME)
        date_created = timezone.now() - timedelta(weeks=3)
        with freeze_time(date_created):
            membership = acm_factories.GroupGroupMembershipFactory.create(
                parent_group=upload_workspace.workspace.authorization_domains.first(),
                child_group=group,
                role=acm_models.GroupGroupMembership.ADMIN,
            )
        self.client.force_login(self.user)
        response = self.client.post(
            self.get_url(upload_workspace.workspace.billing_project.name, upload_workspace.workspace.name, group.name)
        )
        self.assertRedirects(response, upload_workspace.get_absolute_url())
        self.assertEqual(acm_models.GroupGroupMembership.objects.count(), 1)
        membership.refresh_from_db()
        self.assertEqual(membership.created, date_created)
        self.assertEqual(membership.modified, date_created)

    def test_post_verified_not_member(self):
        """Get request with VerifiedNotMember result."""
        upload_workspace = factories.UploadWorkspaceFactory.create()
        group = acm_factories.ManagedGroupFactory.create()
        self.client.force_login(self.user)
        response = self.client.post(
            self.get_url(upload_workspace.workspace.billing_project.name, upload_workspace.workspace.name, group.name)
        )
        self.assertRedirects(response, upload_workspace.get_absolute_url())
        self.assertEqual(acm_models.GroupGroupMembership.objects.count(), 0)

    def test_post_add_member(self):
        """Get request with AddMember result."""
        upload_workspace = factories.UploadWorkspaceFactory.create(
            upload_cycle__is_future=True, workspace__name="test-ws"
        )
        group = acm_factories.ManagedGroupFactory.create(name="GREGOR_DCC_WRITERS")
        # Add the mocked API response.
        # Note that the auth domain group is created automatically by the factory using the workspace name.
        self.anvil_response_mock.add(
            responses.PUT,
            self.api_client.sam_entry_point + f"/api/groups/v1/auth_test-ws/member/{group.name}@firecloud.org",
            status=204,
        )
        self.client.force_login(self.user)
        response = self.client.post(
            self.get_url(upload_workspace.workspace.billing_project.name, upload_workspace.workspace.name, group.name)
        )
        self.assertRedirects(response, upload_workspace.get_absolute_url())
        self.assertEqual(acm_models.GroupGroupMembership.objects.count(), 1)
        membership = acm_models.GroupGroupMembership.objects.get(
            parent_group=upload_workspace.workspace.authorization_domains.first(),
            child_group=group,
        )
        self.assertEqual(membership.role, acm_models.GroupGroupMembership.MEMBER)

    def test_post_add_admin(self):
        """Get request with AddAdmin result."""
        upload_workspace = factories.UploadWorkspaceFactory.create(
            upload_cycle__is_future=True, workspace__name="test-ws"
        )
        group = acm_factories.ManagedGroupFactory.create(name=settings.ANVIL_DCC_ADMINS_GROUP_NAME)
        self.client.force_login(self.user)
        # Add the mocked API response.
        # Note that the auth domain group is created automatically by the factory using the workspace name.
        self.anvil_response_mock.add(
            responses.PUT,
            self.api_client.sam_entry_point + f"/api/groups/v1/auth_test-ws/admin/{group.name}@firecloud.org",
            status=204,
        )
        response = self.client.post(
            self.get_url(upload_workspace.workspace.billing_project.name, upload_workspace.workspace.name, group.name)
        )
        self.assertRedirects(response, upload_workspace.get_absolute_url())
        self.assertEqual(acm_models.GroupGroupMembership.objects.count(), 1)
        membership = acm_models.GroupGroupMembership.objects.get(
            parent_group=upload_workspace.workspace.authorization_domains.first(),
            child_group=group,
        )
        self.assertEqual(membership.role, acm_models.GroupGroupMembership.ADMIN)

    def test_post_change_to_member(self):
        """Get request with ChangeToMember result."""
        upload_workspace = factories.UploadWorkspaceFactory.create(
            upload_cycle__is_future=True, workspace__name="test-ws"
        )
        group = acm_factories.ManagedGroupFactory.create(name="GREGOR_DCC_WRITERS")
        date_created = timezone.now() - timedelta(weeks=3)
        with freeze_time(date_created):
            membership = acm_factories.GroupGroupMembershipFactory.create(
                parent_group=upload_workspace.workspace.authorization_domains.first(),
                child_group=group,
                role=acm_models.GroupGroupMembership.ADMIN,
            )
        # Add the mocked API responses - one to create and one to delete.
        # Note that the auth domain group is created automatically by the factory using the workspace name.
        self.anvil_response_mock.add(
            responses.PUT,
            self.api_client.sam_entry_point + f"/api/groups/v1/auth_test-ws/member/{group.name}@firecloud.org",
            status=204,
        )
        self.anvil_response_mock.add(
            responses.DELETE,
            self.api_client.sam_entry_point + f"/api/groups/v1/auth_test-ws/admin/{group.name}@firecloud.org",
            status=204,
        )

        self.client.force_login(self.user)
        response = self.client.post(
            self.get_url(upload_workspace.workspace.billing_project.name, upload_workspace.workspace.name, group.name)
        )
        self.assertRedirects(response, upload_workspace.get_absolute_url())
        self.assertEqual(acm_models.GroupGroupMembership.objects.count(), 1)
        membership.refresh_from_db()
        self.assertGreater(membership.modified, membership.created)
        self.assertEqual(membership.role, acm_models.GroupGroupMembership.MEMBER)

    def test_post_change_to_admin(self):
        """Get request with ChangeToMember result."""
        upload_workspace = factories.UploadWorkspaceFactory.create(
            upload_cycle__is_future=True, workspace__name="test-ws"
        )
        group = acm_factories.ManagedGroupFactory.create(name=settings.ANVIL_DCC_ADMINS_GROUP_NAME)
        date_created = timezone.now() - timedelta(weeks=3)
        with freeze_time(date_created):
            membership = acm_factories.GroupGroupMembershipFactory.create(
                parent_group=upload_workspace.workspace.authorization_domains.first(),
                child_group=group,
                role=acm_models.GroupGroupMembership.MEMBER,
            )
        # Add the mocked API responses - one to create and one to delete.
        # Note that the auth domain group is created automatically by the factory using the workspace name.
        self.anvil_response_mock.add(
            responses.DELETE,
            self.api_client.sam_entry_point + f"/api/groups/v1/auth_test-ws/member/{group.name}@firecloud.org",
            status=204,
        )
        self.anvil_response_mock.add(
            responses.PUT,
            self.api_client.sam_entry_point + f"/api/groups/v1/auth_test-ws/admin/{group.name}@firecloud.org",
            status=204,
        )

        self.client.force_login(self.user)
        response = self.client.post(
            self.get_url(upload_workspace.workspace.billing_project.name, upload_workspace.workspace.name, group.name)
        )
        self.assertRedirects(response, upload_workspace.get_absolute_url())
        self.assertEqual(acm_models.GroupGroupMembership.objects.count(), 1)
        membership.refresh_from_db()
        self.assertGreater(membership.modified, membership.created)
        self.assertEqual(membership.role, acm_models.GroupGroupMembership.ADMIN)

    def test_post_remove_admin(self):
        """Post request with Remove result for an admin membership."""
        upload_workspace = factories.UploadWorkspaceFactory.create(
            upload_cycle__is_future=True, workspace__name="test-ws"
        )
        group = acm_factories.ManagedGroupFactory.create()
        acm_factories.GroupGroupMembershipFactory.create(
            parent_group=upload_workspace.workspace.authorization_domains.first(),
            child_group=group,
            role=acm_models.GroupGroupMembership.ADMIN,
        )
        self.anvil_response_mock.add(
            responses.DELETE,
            self.api_client.sam_entry_point + f"/api/groups/v1/auth_test-ws/admin/{group.name}@firecloud.org",
            status=204,
        )
        self.client.force_login(self.user)
        response = self.client.post(
            self.get_url(upload_workspace.workspace.billing_project.name, upload_workspace.workspace.name, group.name)
        )
        self.assertRedirects(response, upload_workspace.get_absolute_url())
        self.assertEqual(acm_models.GroupGroupMembership.objects.count(), 0)

    def test_post_remove_member(self):
        """Post request with Remove result for a member membership."""
        upload_workspace = factories.UploadWorkspaceFactory.create(
            upload_cycle__is_future=True, workspace__name="test-ws"
        )
        group = acm_factories.ManagedGroupFactory.create()
        acm_factories.GroupGroupMembershipFactory.create(
            parent_group=upload_workspace.workspace.authorization_domains.first(),
            child_group=group,
            role=acm_models.GroupGroupMembership.MEMBER,
        )
        self.anvil_response_mock.add(
            responses.DELETE,
            self.api_client.sam_entry_point + f"/api/groups/v1/auth_test-ws/member/{group.name}@firecloud.org",
            status=204,
        )
        self.client.force_login(self.user)
        response = self.client.post(
            self.get_url(upload_workspace.workspace.billing_project.name, upload_workspace.workspace.name, group.name)
        )
        self.assertRedirects(response, upload_workspace.get_absolute_url())
        self.assertEqual(acm_models.GroupGroupMembership.objects.count(), 0)

    def test_post_htmx_verified_member(self):
        """Get request with VerifiedMember result."""
        upload_workspace = factories.UploadWorkspaceFactory.create(upload_cycle__is_future=True)
        group = acm_factories.ManagedGroupFactory.create(name="GREGOR_DCC_WRITERS")
        date_created = timezone.now() - timedelta(weeks=3)
        with freeze_time(date_created):
            membership = acm_factories.GroupGroupMembershipFactory.create(
                parent_group=upload_workspace.workspace.authorization_domains.first(),
                child_group=group,
                role=acm_models.GroupGroupMembership.MEMBER,
            )
        self.client.force_login(self.user)
        header = {"HTTP_HX-Request": "true"}
        response = self.client.post(
            self.get_url(upload_workspace.workspace.billing_project.name, upload_workspace.workspace.name, group.name),
            **header,
        )
        self.assertEqual(response.content.decode(), views.UploadWorkspaceAuthDomainAuditResolve.htmx_success)
        self.assertEqual(acm_models.GroupGroupMembership.objects.count(), 1)
        membership.refresh_from_db()
        self.assertEqual(membership.created, date_created)
        self.assertEqual(membership.modified, date_created)

    def test_post_htmx_verified_admin(self):
        """Get request with VerifiedAdmin result."""
        upload_workspace = factories.UploadWorkspaceFactory.create(upload_cycle__is_future=True)
        group = acm_factories.ManagedGroupFactory.create(name=settings.ANVIL_DCC_ADMINS_GROUP_NAME)
        date_created = timezone.now() - timedelta(weeks=3)
        with freeze_time(date_created):
            membership = acm_factories.GroupGroupMembershipFactory.create(
                parent_group=upload_workspace.workspace.authorization_domains.first(),
                child_group=group,
                role=acm_models.GroupGroupMembership.ADMIN,
            )
        self.client.force_login(self.user)
        header = {"HTTP_HX-Request": "true"}
        response = self.client.post(
            self.get_url(upload_workspace.workspace.billing_project.name, upload_workspace.workspace.name, group.name),
            **header,
        )
        self.assertEqual(response.content.decode(), views.UploadWorkspaceAuthDomainAuditResolve.htmx_success)
        self.assertEqual(acm_models.GroupGroupMembership.objects.count(), 1)
        membership.refresh_from_db()
        self.assertEqual(membership.created, date_created)
        self.assertEqual(membership.modified, date_created)

    def test_post_htmx_verified_not_member(self):
        """Get request with VerifiedNotMember result."""
        upload_workspace = factories.UploadWorkspaceFactory.create()
        group = acm_factories.ManagedGroupFactory.create()
        self.client.force_login(self.user)
        header = {"HTTP_HX-Request": "true"}
        response = self.client.post(
            self.get_url(upload_workspace.workspace.billing_project.name, upload_workspace.workspace.name, group.name),
            **header,
        )
        self.assertEqual(response.content.decode(), views.UploadWorkspaceAuthDomainAuditResolve.htmx_success)
        self.assertEqual(acm_models.GroupGroupMembership.objects.count(), 0)

    def test_post_htmx_add_member(self):
        """Get request with AddMember result."""
        upload_workspace = factories.UploadWorkspaceFactory.create(
            upload_cycle__is_future=True, workspace__name="test-ws"
        )
        group = acm_factories.ManagedGroupFactory.create(name="GREGOR_DCC_WRITERS")
        # Add the mocked API response.
        # Note that the auth domain group is created automatically by the factory using the workspace name.
        self.anvil_response_mock.add(
            responses.PUT,
            self.api_client.sam_entry_point + f"/api/groups/v1/auth_test-ws/member/{group.name}@firecloud.org",
            status=204,
        )
        self.client.force_login(self.user)
        header = {"HTTP_HX-Request": "true"}
        response = self.client.post(
            self.get_url(upload_workspace.workspace.billing_project.name, upload_workspace.workspace.name, group.name),
            **header,
        )
        self.assertEqual(response.content.decode(), views.UploadWorkspaceAuthDomainAuditResolve.htmx_success)
        self.assertEqual(acm_models.GroupGroupMembership.objects.count(), 1)
        membership = acm_models.GroupGroupMembership.objects.get(
            parent_group=upload_workspace.workspace.authorization_domains.first(),
            child_group=group,
        )
        self.assertEqual(membership.role, acm_models.GroupGroupMembership.MEMBER)

    def test_post_htmx_add_admin(self):
        """Get request with AddAdmin result."""
        upload_workspace = factories.UploadWorkspaceFactory.create(
            upload_cycle__is_future=True, workspace__name="test-ws"
        )
        group = acm_factories.ManagedGroupFactory.create(name=settings.ANVIL_DCC_ADMINS_GROUP_NAME)
        self.client.force_login(self.user)
        # Add the mocked API response.
        # Note that the auth domain group is created automatically by the factory using the workspace name.
        self.anvil_response_mock.add(
            responses.PUT,
            self.api_client.sam_entry_point + f"/api/groups/v1/auth_test-ws/admin/{group.name}@firecloud.org",
            status=204,
        )
        header = {"HTTP_HX-Request": "true"}
        response = self.client.post(
            self.get_url(upload_workspace.workspace.billing_project.name, upload_workspace.workspace.name, group.name),
            **header,
        )
        self.assertEqual(response.content.decode(), views.UploadWorkspaceAuthDomainAuditResolve.htmx_success)
        self.assertEqual(acm_models.GroupGroupMembership.objects.count(), 1)
        membership = acm_models.GroupGroupMembership.objects.get(
            parent_group=upload_workspace.workspace.authorization_domains.first(),
            child_group=group,
        )
        self.assertEqual(membership.role, acm_models.GroupGroupMembership.ADMIN)

    def test_post_htmx_change_to_member(self):
        """Get request with ChangeToMember result."""
        upload_workspace = factories.UploadWorkspaceFactory.create(
            upload_cycle__is_future=True, workspace__name="test-ws"
        )
        group = acm_factories.ManagedGroupFactory.create(name="GREGOR_DCC_WRITERS")
        date_created = timezone.now() - timedelta(weeks=3)
        with freeze_time(date_created):
            membership = acm_factories.GroupGroupMembershipFactory.create(
                parent_group=upload_workspace.workspace.authorization_domains.first(),
                child_group=group,
                role=acm_models.GroupGroupMembership.ADMIN,
            )
        # Add the mocked API responses - one to create and one to delete.
        # Note that the auth domain group is created automatically by the factory using the workspace name.
        self.anvil_response_mock.add(
            responses.PUT,
            self.api_client.sam_entry_point + f"/api/groups/v1/auth_test-ws/member/{group.name}@firecloud.org",
            status=204,
        )
        self.anvil_response_mock.add(
            responses.DELETE,
            self.api_client.sam_entry_point + f"/api/groups/v1/auth_test-ws/admin/{group.name}@firecloud.org",
            status=204,
        )

        self.client.force_login(self.user)
        header = {"HTTP_HX-Request": "true"}
        response = self.client.post(
            self.get_url(upload_workspace.workspace.billing_project.name, upload_workspace.workspace.name, group.name),
            **header,
        )
        self.assertEqual(response.content.decode(), views.UploadWorkspaceAuthDomainAuditResolve.htmx_success)
        self.assertEqual(acm_models.GroupGroupMembership.objects.count(), 1)
        membership.refresh_from_db()
        self.assertGreater(membership.modified, membership.created)
        self.assertEqual(membership.role, acm_models.GroupGroupMembership.MEMBER)

    def test_post_htmx_change_to_admin(self):
        """Get request with ChangeToMember result."""
        upload_workspace = factories.UploadWorkspaceFactory.create(
            upload_cycle__is_future=True, workspace__name="test-ws"
        )
        group = acm_factories.ManagedGroupFactory.create(name=settings.ANVIL_DCC_ADMINS_GROUP_NAME)
        date_created = timezone.now() - timedelta(weeks=3)
        with freeze_time(date_created):
            membership = acm_factories.GroupGroupMembershipFactory.create(
                parent_group=upload_workspace.workspace.authorization_domains.first(),
                child_group=group,
                role=acm_models.GroupGroupMembership.MEMBER,
            )
        # Add the mocked API responses - one to create and one to delete.
        # Note that the auth domain group is created automatically by the factory using the workspace name.
        self.anvil_response_mock.add(
            responses.DELETE,
            self.api_client.sam_entry_point + f"/api/groups/v1/auth_test-ws/member/{group.name}@firecloud.org",
            status=204,
        )
        self.anvil_response_mock.add(
            responses.PUT,
            self.api_client.sam_entry_point + f"/api/groups/v1/auth_test-ws/admin/{group.name}@firecloud.org",
            status=204,
        )

        self.client.force_login(self.user)
        header = {"HTTP_HX-Request": "true"}
        response = self.client.post(
            self.get_url(upload_workspace.workspace.billing_project.name, upload_workspace.workspace.name, group.name),
            **header,
        )
        self.assertEqual(response.content.decode(), views.UploadWorkspaceAuthDomainAuditResolve.htmx_success)
        self.assertEqual(acm_models.GroupGroupMembership.objects.count(), 1)
        membership.refresh_from_db()
        self.assertGreater(membership.modified, membership.created)
        self.assertEqual(membership.role, acm_models.GroupGroupMembership.ADMIN)

    def test_post_htmx_remove_admin(self):
        """Post request with Remove result for an admin membership."""
        upload_workspace = factories.UploadWorkspaceFactory.create(
            upload_cycle__is_future=True, workspace__name="test-ws"
        )
        group = acm_factories.ManagedGroupFactory.create()
        acm_factories.GroupGroupMembershipFactory.create(
            parent_group=upload_workspace.workspace.authorization_domains.first(),
            child_group=group,
            role=acm_models.GroupGroupMembership.ADMIN,
        )
        self.anvil_response_mock.add(
            responses.DELETE,
            self.api_client.sam_entry_point + f"/api/groups/v1/auth_test-ws/admin/{group.name}@firecloud.org",
            status=204,
        )
        self.client.force_login(self.user)
        header = {"HTTP_HX-Request": "true"}
        response = self.client.post(
            self.get_url(upload_workspace.workspace.billing_project.name, upload_workspace.workspace.name, group.name),
            **header,
        )
        self.assertEqual(response.content.decode(), views.UploadWorkspaceAuthDomainAuditResolve.htmx_success)
        self.assertEqual(acm_models.GroupGroupMembership.objects.count(), 0)

    def test_post_htmx_remove_member(self):
        """Post request with Remove result for a member membership."""
        upload_workspace = factories.UploadWorkspaceFactory.create(
            upload_cycle__is_future=True, workspace__name="test-ws"
        )
        group = acm_factories.ManagedGroupFactory.create()
        acm_factories.GroupGroupMembershipFactory.create(
            parent_group=upload_workspace.workspace.authorization_domains.first(),
            child_group=group,
            role=acm_models.GroupGroupMembership.MEMBER,
        )
        self.anvil_response_mock.add(
            responses.DELETE,
            self.api_client.sam_entry_point + f"/api/groups/v1/auth_test-ws/member/{group.name}@firecloud.org",
            status=204,
        )
        self.client.force_login(self.user)
        header = {"HTTP_HX-Request": "true"}
        response = self.client.post(
            self.get_url(upload_workspace.workspace.billing_project.name, upload_workspace.workspace.name, group.name),
            **header,
        )
        self.assertEqual(response.content.decode(), views.UploadWorkspaceAuthDomainAuditResolve.htmx_success)
        self.assertEqual(acm_models.GroupGroupMembership.objects.count(), 0)

    def test_post_api_error_add_member(self):
        """Get request with AddMember result."""
        upload_workspace = factories.UploadWorkspaceFactory.create(
            upload_cycle__is_future=True, workspace__name="test-ws"
        )
        group = acm_factories.ManagedGroupFactory.create(name="GREGOR_DCC_WRITERS")
        # Add the mocked API response.
        # Note that the auth domain group is created automatically by the factory using the workspace name.
        self.anvil_response_mock.add(
            responses.PUT,
            self.api_client.sam_entry_point + f"/api/groups/v1/auth_test-ws/member/{group.name}@firecloud.org",
            status=500,
            json=ErrorResponseFactory().response,
        )
        self.client.force_login(self.user)
        response = self.client.post(
            self.get_url(upload_workspace.workspace.billing_project.name, upload_workspace.workspace.name, group.name)
        )
        self.assertEqual(response.status_code, 200)
        # No memberships were created.
        self.assertEqual(acm_models.GroupGroupMembership.objects.count(), 0)
        # Error message was added.
        messages = [m.message for m in get_messages(response.wsgi_request)]
        self.assertEqual(len(messages), 1)
        self.assertIn("AnVIL API Error", str(messages[0]))

    def test_post_api_error_add_admin(self):
        """Get request with AddAdmin result."""
        upload_workspace = factories.UploadWorkspaceFactory.create(
            upload_cycle__is_future=True, workspace__name="test-ws"
        )
        group = acm_factories.ManagedGroupFactory.create(name=settings.ANVIL_DCC_ADMINS_GROUP_NAME)
        self.client.force_login(self.user)
        # Add the mocked API response.
        # Note that the auth domain group is created automatically by the factory using the workspace name.
        self.anvil_response_mock.add(
            responses.PUT,
            self.api_client.sam_entry_point + f"/api/groups/v1/auth_test-ws/admin/{group.name}@firecloud.org",
            status=500,
            json=ErrorResponseFactory().response,
        )
        response = self.client.post(
            self.get_url(upload_workspace.workspace.billing_project.name, upload_workspace.workspace.name, group.name)
        )
        self.assertEqual(response.status_code, 200)
        # No memberships were created.
        self.assertEqual(acm_models.GroupGroupMembership.objects.count(), 0)
        # Error message was added.
        messages = [m.message for m in get_messages(response.wsgi_request)]
        self.assertEqual(len(messages), 1)
        self.assertIn("AnVIL API Error", str(messages[0]))

    def test_post_api_error_change_to_member_error_on_put_call(self):
        """Get request with ChangeToMember result."""
        upload_workspace = factories.UploadWorkspaceFactory.create(
            upload_cycle__is_future=True, workspace__name="test-ws"
        )
        group = acm_factories.ManagedGroupFactory.create(name="GREGOR_DCC_WRITERS")
        date_created = timezone.now() - timedelta(weeks=3)
        with freeze_time(date_created):
            membership = acm_factories.GroupGroupMembershipFactory.create(
                parent_group=upload_workspace.workspace.authorization_domains.first(),
                child_group=group,
                role=acm_models.GroupGroupMembership.ADMIN,
            )
        # Add the mocked API responses - one to create and one to delete.
        # Note that the auth domain group is created automatically by the factory using the workspace name.
        self.anvil_response_mock.add(
            responses.PUT,
            self.api_client.sam_entry_point + f"/api/groups/v1/auth_test-ws/member/{group.name}@firecloud.org",
            status=500,
            json=ErrorResponseFactory().response,
        )
        self.anvil_response_mock.add(
            responses.DELETE,
            self.api_client.sam_entry_point + f"/api/groups/v1/auth_test-ws/admin/{group.name}@firecloud.org",
            status=204,
        )
        self.client.force_login(self.user)
        response = self.client.post(
            self.get_url(upload_workspace.workspace.billing_project.name, upload_workspace.workspace.name, group.name)
        )
        self.assertEqual(response.status_code, 200)
        # The membership was not updated.
        self.assertEqual(acm_models.GroupGroupMembership.objects.count(), 1)
        membership.refresh_from_db()
        self.assertEqual(membership.created, date_created)
        self.assertEqual(membership.modified, date_created)
        self.assertEqual(membership.role, acm_models.GroupGroupMembership.ADMIN)
        # Error message was added.
        messages = [m.message for m in get_messages(response.wsgi_request)]
        self.assertEqual(len(messages), 1)
        self.assertIn("AnVIL API Error", str(messages[0]))

    def test_post_api_error_change_to_member_error_on_delete_call(self):
        """Get request with ChangeToMember result."""
        upload_workspace = factories.UploadWorkspaceFactory.create(
            upload_cycle__is_future=True, workspace__name="test-ws"
        )
        group = acm_factories.ManagedGroupFactory.create(name="GREGOR_DCC_WRITERS")
        date_created = timezone.now() - timedelta(weeks=3)
        with freeze_time(date_created):
            membership = acm_factories.GroupGroupMembershipFactory.create(
                parent_group=upload_workspace.workspace.authorization_domains.first(),
                child_group=group,
                role=acm_models.GroupGroupMembership.ADMIN,
            )
        # Add the mocked API responses - one to create and one to delete.
        # Note that the auth domain group is created automatically by the factory using the workspace name.
        self.anvil_response_mock.add(
            responses.DELETE,
            self.api_client.sam_entry_point + f"/api/groups/v1/auth_test-ws/admin/{group.name}@firecloud.org",
            status=500,
            json=ErrorResponseFactory().response,
        )
        self.client.force_login(self.user)
        response = self.client.post(
            self.get_url(upload_workspace.workspace.billing_project.name, upload_workspace.workspace.name, group.name)
        )
        self.assertEqual(response.status_code, 200)
        # The membership was not updated.
        self.assertEqual(acm_models.GroupGroupMembership.objects.count(), 1)
        membership.refresh_from_db()
        self.assertEqual(membership.created, date_created)
        self.assertEqual(membership.modified, date_created)
        self.assertEqual(membership.role, acm_models.GroupGroupMembership.ADMIN)
        # Error message was added.
        messages = [m.message for m in get_messages(response.wsgi_request)]
        self.assertEqual(len(messages), 1)
        self.assertIn("AnVIL API Error", str(messages[0]))

    def test_post_api_error_change_to_admin_error_on_delete_call(self):
        """Get request with ChangeToMember result."""
        upload_workspace = factories.UploadWorkspaceFactory.create(
            upload_cycle__is_future=True, workspace__name="test-ws"
        )
        group = acm_factories.ManagedGroupFactory.create(name=settings.ANVIL_DCC_ADMINS_GROUP_NAME)
        date_created = timezone.now() - timedelta(weeks=3)
        with freeze_time(date_created):
            membership = acm_factories.GroupGroupMembershipFactory.create(
                parent_group=upload_workspace.workspace.authorization_domains.first(),
                child_group=group,
                role=acm_models.GroupGroupMembership.MEMBER,
            )
        # Add the mocked API responses - one to create and one to delete.
        # Note that the auth domain group is created automatically by the factory using the workspace name.
        self.anvil_response_mock.add(
            responses.DELETE,
            self.api_client.sam_entry_point + f"/api/groups/v1/auth_test-ws/member/{group.name}@firecloud.org",
            status=500,
            json=ErrorResponseFactory().response,
        )
        self.client.force_login(self.user)
        response = self.client.post(
            self.get_url(upload_workspace.workspace.billing_project.name, upload_workspace.workspace.name, group.name)
        )
        self.assertEqual(response.status_code, 200)
        # The membership was not updated.
        self.assertEqual(acm_models.GroupGroupMembership.objects.count(), 1)
        membership.refresh_from_db()
        self.assertEqual(membership.created, date_created)
        self.assertEqual(membership.modified, date_created)
        self.assertEqual(membership.role, acm_models.GroupGroupMembership.MEMBER)
        # Error message was added.
        messages = [m.message for m in get_messages(response.wsgi_request)]
        self.assertEqual(len(messages), 1)
        self.assertIn("AnVIL API Error", str(messages[0]))

    def test_post_api_error_change_to_admin_error_on_put_call(self):
        """Get request with ChangeToMember result."""
        upload_workspace = factories.UploadWorkspaceFactory.create(
            upload_cycle__is_future=True, workspace__name="test-ws"
        )
        group = acm_factories.ManagedGroupFactory.create(name=settings.ANVIL_DCC_ADMINS_GROUP_NAME)
        date_created = timezone.now() - timedelta(weeks=3)
        with freeze_time(date_created):
            membership = acm_factories.GroupGroupMembershipFactory.create(
                parent_group=upload_workspace.workspace.authorization_domains.first(),
                child_group=group,
                role=acm_models.GroupGroupMembership.MEMBER,
            )
        # Add the mocked API responses - one to create and one to delete.
        # Note that the auth domain group is created automatically by the factory using the workspace name.
        self.anvil_response_mock.add(
            responses.DELETE,
            self.api_client.sam_entry_point + f"/api/groups/v1/auth_test-ws/member/{group.name}@firecloud.org",
            status=204,
        )
        self.anvil_response_mock.add(
            responses.PUT,
            self.api_client.sam_entry_point + f"/api/groups/v1/auth_test-ws/admin/{group.name}@firecloud.org",
            status=500,
            json=ErrorResponseFactory().response,
        )
        self.client.force_login(self.user)
        response = self.client.post(
            self.get_url(upload_workspace.workspace.billing_project.name, upload_workspace.workspace.name, group.name)
        )
        self.assertEqual(response.status_code, 200)
        # The membership was not updated.
        self.assertEqual(acm_models.GroupGroupMembership.objects.count(), 1)
        membership.refresh_from_db()
        self.assertEqual(membership.created, date_created)
        self.assertEqual(membership.modified, date_created)
        self.assertEqual(membership.role, acm_models.GroupGroupMembership.MEMBER)
        # Error message was added.
        messages = [m.message for m in get_messages(response.wsgi_request)]
        self.assertEqual(len(messages), 1)
        self.assertIn("AnVIL API Error", str(messages[0]))

    def test_post_api_error_remove_admin(self):
        """Post request with Remove result for an admin membership."""
        upload_workspace = factories.UploadWorkspaceFactory.create(
            upload_cycle__is_future=True, workspace__name="test-ws"
        )
        group = acm_factories.ManagedGroupFactory.create()
        date_created = timezone.now() - timedelta(weeks=3)
        with freeze_time(date_created):
            membership = acm_factories.GroupGroupMembershipFactory.create(
                parent_group=upload_workspace.workspace.authorization_domains.first(),
                child_group=group,
                role=acm_models.GroupGroupMembership.ADMIN,
            )
        self.anvil_response_mock.add(
            responses.DELETE,
            self.api_client.sam_entry_point + f"/api/groups/v1/auth_test-ws/admin/{group.name}@firecloud.org",
            status=500,
            json=ErrorResponseFactory().response,
        )
        self.client.force_login(self.user)
        response = self.client.post(
            self.get_url(upload_workspace.workspace.billing_project.name, upload_workspace.workspace.name, group.name)
        )
        self.assertEqual(response.status_code, 200)
        # The membership was not updated.
        self.assertEqual(acm_models.GroupGroupMembership.objects.count(), 1)
        membership.refresh_from_db()
        self.assertEqual(membership.created, date_created)
        self.assertEqual(membership.modified, date_created)
        self.assertEqual(membership.role, acm_models.GroupGroupMembership.ADMIN)
        # Error message was added.
        messages = [m.message for m in get_messages(response.wsgi_request)]
        self.assertEqual(len(messages), 1)
        self.assertIn("AnVIL API Error", str(messages[0]))

    def test_post_api_error_remove_member(self):
        """Post request with Remove result for a member membership."""
        upload_workspace = factories.UploadWorkspaceFactory.create(
            upload_cycle__is_future=True, workspace__name="test-ws"
        )
        group = acm_factories.ManagedGroupFactory.create()
        date_created = timezone.now() - timedelta(weeks=3)
        with freeze_time(date_created):
            membership = acm_factories.GroupGroupMembershipFactory.create(
                parent_group=upload_workspace.workspace.authorization_domains.first(),
                child_group=group,
                role=acm_models.GroupGroupMembership.MEMBER,
            )
        self.anvil_response_mock.add(
            responses.DELETE,
            self.api_client.sam_entry_point + f"/api/groups/v1/auth_test-ws/member/{group.name}@firecloud.org",
            status=500,
            json=ErrorResponseFactory().response,
        )
        self.client.force_login(self.user)
        response = self.client.post(
            self.get_url(upload_workspace.workspace.billing_project.name, upload_workspace.workspace.name, group.name)
        )
        self.assertEqual(response.status_code, 200)
        # The membership was not updated.
        self.assertEqual(acm_models.GroupGroupMembership.objects.count(), 1)
        membership.refresh_from_db()
        self.assertEqual(membership.created, date_created)
        self.assertEqual(membership.modified, date_created)
        self.assertEqual(membership.role, acm_models.GroupGroupMembership.MEMBER)
        # Error message was added.
        messages = [m.message for m in get_messages(response.wsgi_request)]
        self.assertEqual(len(messages), 1)
        self.assertIn("AnVIL API Error", str(messages[0]))

    def test_post_htmx_api_error_add_member(self):
        """Get request with AddMember result."""
        upload_workspace = factories.UploadWorkspaceFactory.create(
            upload_cycle__is_future=True, workspace__name="test-ws"
        )
        group = acm_factories.ManagedGroupFactory.create(name="GREGOR_DCC_WRITERS")
        # Add the mocked API response.
        # Note that the auth domain group is created automatically by the factory using the workspace name.
        self.anvil_response_mock.add(
            responses.PUT,
            self.api_client.sam_entry_point + f"/api/groups/v1/auth_test-ws/member/{group.name}@firecloud.org",
            status=500,
            json=ErrorResponseFactory().response,
        )
        self.client.force_login(self.user)
        header = {"HTTP_HX-Request": "true"}
        response = self.client.post(
            self.get_url(upload_workspace.workspace.billing_project.name, upload_workspace.workspace.name, group.name),
            **header,
        )
        self.assertEqual(response.content.decode(), views.UploadWorkspaceAuthDomainAuditResolve.htmx_error)
        # No memberships were created.
        self.assertEqual(acm_models.GroupGroupMembership.objects.count(), 0)
        # No messages
        messages = [m.message for m in get_messages(response.wsgi_request)]
        self.assertEqual(len(messages), 0)

    def test_post_htmx_api_error_add_admin(self):
        """Get request with AddAdmin result."""
        upload_workspace = factories.UploadWorkspaceFactory.create(
            upload_cycle__is_future=True, workspace__name="test-ws"
        )
        group = acm_factories.ManagedGroupFactory.create(name=settings.ANVIL_DCC_ADMINS_GROUP_NAME)
        self.client.force_login(self.user)
        # Add the mocked API response.
        # Note that the auth domain group is created automatically by the factory using the workspace name.
        self.anvil_response_mock.add(
            responses.PUT,
            self.api_client.sam_entry_point + f"/api/groups/v1/auth_test-ws/admin/{group.name}@firecloud.org",
            status=500,
            json=ErrorResponseFactory().response,
        )
        header = {"HTTP_HX-Request": "true"}
        response = self.client.post(
            self.get_url(upload_workspace.workspace.billing_project.name, upload_workspace.workspace.name, group.name),
            **header,
        )
        self.assertEqual(response.content.decode(), views.UploadWorkspaceAuthDomainAuditResolve.htmx_error)
        # No memberships were created.
        self.assertEqual(acm_models.GroupGroupMembership.objects.count(), 0)
        # No messages
        messages = [m.message for m in get_messages(response.wsgi_request)]
        self.assertEqual(len(messages), 0)

    def test_post_htmx_api_error_change_to_member_error_on_put_call(self):
        """Get request with ChangeToMember result."""
        upload_workspace = factories.UploadWorkspaceFactory.create(
            upload_cycle__is_future=True, workspace__name="test-ws"
        )
        group = acm_factories.ManagedGroupFactory.create(name="GREGOR_DCC_WRITERS")
        date_created = timezone.now() - timedelta(weeks=3)
        with freeze_time(date_created):
            membership = acm_factories.GroupGroupMembershipFactory.create(
                parent_group=upload_workspace.workspace.authorization_domains.first(),
                child_group=group,
                role=acm_models.GroupGroupMembership.ADMIN,
            )
        # Add the mocked API responses - one to create and one to delete.
        # Note that the auth domain group is created automatically by the factory using the workspace name.
        self.anvil_response_mock.add(
            responses.PUT,
            self.api_client.sam_entry_point + f"/api/groups/v1/auth_test-ws/member/{group.name}@firecloud.org",
            status=500,
            json=ErrorResponseFactory().response,
        )
        self.anvil_response_mock.add(
            responses.DELETE,
            self.api_client.sam_entry_point + f"/api/groups/v1/auth_test-ws/admin/{group.name}@firecloud.org",
            status=204,
        )
        self.client.force_login(self.user)
        header = {"HTTP_HX-Request": "true"}
        response = self.client.post(
            self.get_url(upload_workspace.workspace.billing_project.name, upload_workspace.workspace.name, group.name),
            **header,
        )
        self.assertEqual(response.content.decode(), views.UploadWorkspaceAuthDomainAuditResolve.htmx_error)
        # The membership was not updated.
        self.assertEqual(acm_models.GroupGroupMembership.objects.count(), 1)
        membership.refresh_from_db()
        self.assertEqual(membership.created, date_created)
        self.assertEqual(membership.modified, date_created)
        self.assertEqual(membership.role, acm_models.GroupGroupMembership.ADMIN)
        # No messages
        messages = [m.message for m in get_messages(response.wsgi_request)]
        self.assertEqual(len(messages), 0)

    def test_post_htmx_api_error_change_to_member_error_on_delete_call(self):
        """Get request with ChangeToMember result."""
        upload_workspace = factories.UploadWorkspaceFactory.create(
            upload_cycle__is_future=True, workspace__name="test-ws"
        )
        group = acm_factories.ManagedGroupFactory.create(name="GREGOR_DCC_WRITERS")
        date_created = timezone.now() - timedelta(weeks=3)
        with freeze_time(date_created):
            membership = acm_factories.GroupGroupMembershipFactory.create(
                parent_group=upload_workspace.workspace.authorization_domains.first(),
                child_group=group,
                role=acm_models.GroupGroupMembership.ADMIN,
            )
        # Add the mocked API responses - one to create and one to delete.
        # Note that the auth domain group is created automatically by the factory using the workspace name.
        self.anvil_response_mock.add(
            responses.DELETE,
            self.api_client.sam_entry_point + f"/api/groups/v1/auth_test-ws/admin/{group.name}@firecloud.org",
            status=500,
            json=ErrorResponseFactory().response,
        )
        self.client.force_login(self.user)
        header = {"HTTP_HX-Request": "true"}
        response = self.client.post(
            self.get_url(upload_workspace.workspace.billing_project.name, upload_workspace.workspace.name, group.name),
            **header,
        )
        self.assertEqual(response.content.decode(), views.UploadWorkspaceAuthDomainAuditResolve.htmx_error)
        # The membership was not updated.
        self.assertEqual(acm_models.GroupGroupMembership.objects.count(), 1)
        membership.refresh_from_db()
        self.assertEqual(membership.created, date_created)
        self.assertEqual(membership.modified, date_created)
        self.assertEqual(membership.role, acm_models.GroupGroupMembership.ADMIN)
        # No messages
        messages = [m.message for m in get_messages(response.wsgi_request)]
        self.assertEqual(len(messages), 0)

    def test_post_htmx_api_error_change_to_admin_error_on_delete_call(self):
        """Get request with ChangeToMember result."""
        upload_workspace = factories.UploadWorkspaceFactory.create(
            upload_cycle__is_future=True, workspace__name="test-ws"
        )
        group = acm_factories.ManagedGroupFactory.create(name=settings.ANVIL_DCC_ADMINS_GROUP_NAME)
        date_created = timezone.now() - timedelta(weeks=3)
        with freeze_time(date_created):
            membership = acm_factories.GroupGroupMembershipFactory.create(
                parent_group=upload_workspace.workspace.authorization_domains.first(),
                child_group=group,
                role=acm_models.GroupGroupMembership.MEMBER,
            )
        # Add the mocked API responses - one to create and one to delete.
        # Note that the auth domain group is created automatically by the factory using the workspace name.
        self.anvil_response_mock.add(
            responses.DELETE,
            self.api_client.sam_entry_point + f"/api/groups/v1/auth_test-ws/member/{group.name}@firecloud.org",
            status=500,
            json=ErrorResponseFactory().response,
        )
        self.client.force_login(self.user)
        header = {"HTTP_HX-Request": "true"}
        response = self.client.post(
            self.get_url(upload_workspace.workspace.billing_project.name, upload_workspace.workspace.name, group.name),
            **header,
        )
        self.assertEqual(response.content.decode(), views.UploadWorkspaceAuthDomainAuditResolve.htmx_error)
        # The membership was not updated.
        self.assertEqual(acm_models.GroupGroupMembership.objects.count(), 1)
        membership.refresh_from_db()
        self.assertEqual(membership.created, date_created)
        self.assertEqual(membership.modified, date_created)
        self.assertEqual(membership.role, acm_models.GroupGroupMembership.MEMBER)
        # No messages
        messages = [m.message for m in get_messages(response.wsgi_request)]
        self.assertEqual(len(messages), 0)

    def test_post_htmx_api_error_change_to_admin_error_on_put_call(self):
        """Get request with ChangeToMember result."""
        upload_workspace = factories.UploadWorkspaceFactory.create(
            upload_cycle__is_future=True, workspace__name="test-ws"
        )
        group = acm_factories.ManagedGroupFactory.create(name=settings.ANVIL_DCC_ADMINS_GROUP_NAME)
        date_created = timezone.now() - timedelta(weeks=3)
        with freeze_time(date_created):
            membership = acm_factories.GroupGroupMembershipFactory.create(
                parent_group=upload_workspace.workspace.authorization_domains.first(),
                child_group=group,
                role=acm_models.GroupGroupMembership.MEMBER,
            )
        # Add the mocked API responses - one to create and one to delete.
        # Note that the auth domain group is created automatically by the factory using the workspace name.
        self.anvil_response_mock.add(
            responses.DELETE,
            self.api_client.sam_entry_point + f"/api/groups/v1/auth_test-ws/member/{group.name}@firecloud.org",
            status=204,
        )
        self.anvil_response_mock.add(
            responses.PUT,
            self.api_client.sam_entry_point + f"/api/groups/v1/auth_test-ws/admin/{group.name}@firecloud.org",
            status=500,
            json=ErrorResponseFactory().response,
        )
        self.client.force_login(self.user)
        header = {"HTTP_HX-Request": "true"}
        response = self.client.post(
            self.get_url(upload_workspace.workspace.billing_project.name, upload_workspace.workspace.name, group.name),
            **header,
        )
        self.assertEqual(response.content.decode(), views.UploadWorkspaceAuthDomainAuditResolve.htmx_error)
        # The membership was not updated.
        self.assertEqual(acm_models.GroupGroupMembership.objects.count(), 1)
        membership.refresh_from_db()
        self.assertEqual(membership.created, date_created)
        self.assertEqual(membership.modified, date_created)
        self.assertEqual(membership.role, acm_models.GroupGroupMembership.MEMBER)
        # No messages
        messages = [m.message for m in get_messages(response.wsgi_request)]
        self.assertEqual(len(messages), 0)

    def test_post_htmx_api_error_remove_admin(self):
        """Post request with Remove result for an admin membership."""
        upload_workspace = factories.UploadWorkspaceFactory.create(
            upload_cycle__is_future=True, workspace__name="test-ws"
        )
        group = acm_factories.ManagedGroupFactory.create()
        date_created = timezone.now() - timedelta(weeks=3)
        with freeze_time(date_created):
            membership = acm_factories.GroupGroupMembershipFactory.create(
                parent_group=upload_workspace.workspace.authorization_domains.first(),
                child_group=group,
                role=acm_models.GroupGroupMembership.ADMIN,
            )
        self.anvil_response_mock.add(
            responses.DELETE,
            self.api_client.sam_entry_point + f"/api/groups/v1/auth_test-ws/admin/{group.name}@firecloud.org",
            status=500,
            json=ErrorResponseFactory().response,
        )
        self.client.force_login(self.user)
        header = {"HTTP_HX-Request": "true"}
        response = self.client.post(
            self.get_url(upload_workspace.workspace.billing_project.name, upload_workspace.workspace.name, group.name),
            **header,
        )
        self.assertEqual(response.content.decode(), views.UploadWorkspaceAuthDomainAuditResolve.htmx_error)
        # The membership was not updated.
        self.assertEqual(acm_models.GroupGroupMembership.objects.count(), 1)
        membership.refresh_from_db()
        self.assertEqual(membership.created, date_created)
        self.assertEqual(membership.modified, date_created)
        self.assertEqual(membership.role, acm_models.GroupGroupMembership.ADMIN)
        # No messages
        messages = [m.message for m in get_messages(response.wsgi_request)]
        self.assertEqual(len(messages), 0)

    def test_post_htmx_api_error_remove_member(self):
        """Post request with Remove result for a member membership."""
        upload_workspace = factories.UploadWorkspaceFactory.create(
            upload_cycle__is_future=True, workspace__name="test-ws"
        )
        group = acm_factories.ManagedGroupFactory.create()
        date_created = timezone.now() - timedelta(weeks=3)
        with freeze_time(date_created):
            membership = acm_factories.GroupGroupMembershipFactory.create(
                parent_group=upload_workspace.workspace.authorization_domains.first(),
                child_group=group,
                role=acm_models.GroupGroupMembership.MEMBER,
            )
        self.anvil_response_mock.add(
            responses.DELETE,
            self.api_client.sam_entry_point + f"/api/groups/v1/auth_test-ws/member/{group.name}@firecloud.org",
            status=500,
            json=ErrorResponseFactory().response,
        )
        self.client.force_login(self.user)
        header = {"HTTP_HX-Request": "true"}
        response = self.client.post(
            self.get_url(upload_workspace.workspace.billing_project.name, upload_workspace.workspace.name, group.name),
            **header,
        )
        self.assertEqual(response.content.decode(), views.UploadWorkspaceAuthDomainAuditResolve.htmx_error)
        # The membership was not updated.
        self.assertEqual(acm_models.GroupGroupMembership.objects.count(), 1)
        membership.refresh_from_db()
        self.assertEqual(membership.created, date_created)
        self.assertEqual(membership.modified, date_created)
        self.assertEqual(membership.role, acm_models.GroupGroupMembership.MEMBER)
        # No messages
        messages = [m.message for m in get_messages(response.wsgi_request)]
        self.assertEqual(len(messages), 0)


class CombinedConsortiumDataWorkspaceSharingAuditTest(AnVILAPIMockTestMixin, TestCase):
    """Tests for the CombinedConsortiumDataWorkspaceSharingAudit view."""

    def setUp(self):
        """Set up test class."""
        super().setUp()
        self.factory = RequestFactory()
        # Create a user with both view and edit permission.
        self.user = User.objects.create_user(username="test", password="test")
        self.user.user_permissions.add(
            Permission.objects.get(codename=AnVILProjectManagerAccess.STAFF_VIEW_PERMISSION_CODENAME)
        )

    def get_url(self, *args):
        """Get the url for the view being tested."""
        return reverse(
            "gregor_anvil:audit:combined_workspaces:sharing:all",
            args=args,
        )

    def get_view(self):
        """Return the view being tested."""
        return views.CombinedConsortiumDataWorkspaceSharingAudit.as_view()

    def test_view_redirect_not_logged_in(self):
        "View redirects to login view when user is not logged in."
        # Need a client for redirects.
        response = self.client.get(self.get_url())
        self.assertRedirects(
            response,
            resolve_url(settings.LOGIN_URL) + "?next=" + self.get_url(),
        )

    def test_status_code_with_user_permission_view(self):
        """Returns successful response code if the user has view permission."""
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

    def test_context_audit_results_no_workspaces(self):
        """The audit_results exists in the context."""
        self.client.force_login(self.user)
        response = self.client.get(self.get_url())
        self.assertIn("audit_results", response.context_data)
        audit_results = response.context_data["audit_results"]
        self.assertIsInstance(
            audit_results,
            combined_workspace_audit.CombinedConsortiumDataWorkspaceSharingAudit,
        )
        self.assertTrue(audit_results.completed)
        self.assertEqual(audit_results.queryset.count(), 0)

    def test_context_audit_results_one_workspace(self):
        """The audit_results exists in the context."""
        workspace = factories.CombinedConsortiumDataWorkspaceFactory.create()
        self.client.force_login(self.user)
        response = self.client.get(self.get_url())
        self.assertIn("audit_results", response.context_data)
        audit_results = response.context_data["audit_results"]
        self.assertIsInstance(
            audit_results,
            combined_workspace_audit.CombinedConsortiumDataWorkspaceSharingAudit,
        )
        self.assertTrue(audit_results.completed)
        self.assertEqual(audit_results.queryset.count(), 1)
        self.assertIn(workspace, audit_results.queryset)

    def test_context_audit_results_two_workspaces(self):
        """The audit_results exists in the context."""
        workspace_1 = factories.CombinedConsortiumDataWorkspaceFactory.create()
        workspace_2 = factories.CombinedConsortiumDataWorkspaceFactory.create()
        self.client.force_login(self.user)
        response = self.client.get(self.get_url())
        self.assertIn("audit_results", response.context_data)
        audit_results = response.context_data["audit_results"]
        self.assertIsInstance(
            audit_results,
            combined_workspace_audit.CombinedConsortiumDataWorkspaceSharingAudit,
        )
        self.assertTrue(audit_results.completed)
        self.assertEqual(audit_results.queryset.count(), 2)
        self.assertIn(workspace_1, audit_results.queryset)
        self.assertIn(workspace_2, audit_results.queryset)

    def test_context_verified_table_access(self):
        """verified_table shows a record when audit has verified access."""
        workspace = factories.CombinedConsortiumDataWorkspaceFactory.create(
            date_completed=timezone.now() - timedelta(days=1)
        )
        group = workspace.workspace.authorization_domains.first()
        acm_factories.WorkspaceGroupSharingFactory.create(
            workspace=workspace.workspace,
            group=group,
            access=acm_models.WorkspaceGroupSharing.READER,
        )
        # Check the table in the context.
        self.client.force_login(self.user)
        response = self.client.get(self.get_url())
        self.assertIn("verified_table", response.context_data)
        table = response.context_data["verified_table"]
        self.assertIsInstance(
            table,
            combined_workspace_audit.CombinedConsortiumDataWorkspaceSharingAuditTable,
        )
        self.assertEqual(len(table.rows), 1)
        self.assertEqual(table.rows[0].get_cell_value("workspace"), workspace.workspace)
        self.assertEqual(table.rows[0].get_cell_value("managed_group"), group)
        self.assertEqual(table.rows[0].get_cell_value("access"), "READER")
        self.assertEqual(
            table.rows[0].get_cell_value("note"),
            combined_workspace_audit.CombinedConsortiumDataWorkspaceSharingAudit.AUTH_DOMAIN_AFTER_COMPLETE,
        )
        self.assertEqual(table.rows[0].get_cell_value("action"), "&mdash;")

    def test_context_verified_table_no_access(self):
        """verified_table shows a record when audit has verified access."""
        workspace = factories.CombinedConsortiumDataWorkspaceFactory.create()
        group = workspace.workspace.authorization_domains.first()
        # Check the table in the context.
        self.client.force_login(self.user)
        response = self.client.get(self.get_url())
        self.assertIn("verified_table", response.context_data)
        table = response.context_data["verified_table"]
        self.assertIsInstance(
            table,
            combined_workspace_audit.CombinedConsortiumDataWorkspaceSharingAuditTable,
        )
        self.assertEqual(len(table.rows), 1)
        self.assertEqual(table.rows[0].get_cell_value("workspace"), workspace.workspace)
        self.assertEqual(table.rows[0].get_cell_value("managed_group"), group)
        self.assertIsNone(table.rows[0].get_cell_value("access"))
        self.assertEqual(
            table.rows[0].get_cell_value("note"),
            combined_workspace_audit.CombinedConsortiumDataWorkspaceSharingAudit.AUTH_DOMAIN_BEFORE_COMPLETE,
        )
        self.assertEqual(table.rows[0].get_cell_value("action"), "&mdash;")

    def test_context_needs_action_table_share_as_reader(self):
        """needs_action_table shows a record when audit finds that access needs to be granted."""
        workspace = factories.CombinedConsortiumDataWorkspaceFactory.create(
            date_completed=timezone.now() - timedelta(days=1)
        )
        group = workspace.workspace.authorization_domains.first()
        # Check the table in the context.
        self.client.force_login(self.user)
        response = self.client.get(self.get_url())
        self.assertIn("needs_action_table", response.context_data)
        table = response.context_data["needs_action_table"]
        self.assertIsInstance(
            table,
            combined_workspace_audit.CombinedConsortiumDataWorkspaceSharingAuditTable,
        )
        self.assertEqual(len(table.rows), 1)
        self.assertEqual(table.rows[0].get_cell_value("workspace"), workspace.workspace)
        self.assertEqual(table.rows[0].get_cell_value("managed_group"), group)
        self.assertIsNone(table.rows[0].get_cell_value("access"))
        self.assertEqual(
            table.rows[0].get_cell_value("note"),
            combined_workspace_audit.CombinedConsortiumDataWorkspaceSharingAudit.AUTH_DOMAIN_AFTER_COMPLETE,
        )
        self.assertNotEqual(table.rows[0].get_cell_value("action"), "&mdash;")

    def test_context_needs_action_table_share_as_writer_with_compute(self):
        """needs_action_table shows a record when audit finds that access needs to be granted."""
        group = acm_factories.ManagedGroupFactory.create(name="GREGOR_DCC_WRITERS")
        workspace = factories.CombinedConsortiumDataWorkspaceFactory.create()
        # Check the table in the context.
        self.client.force_login(self.user)
        response = self.client.get(self.get_url())
        self.assertIn("needs_action_table", response.context_data)
        table = response.context_data["needs_action_table"]
        self.assertIsInstance(
            table,
            combined_workspace_audit.CombinedConsortiumDataWorkspaceSharingAuditTable,
        )
        self.assertEqual(len(table.rows), 1)
        self.assertEqual(table.rows[0].get_cell_value("workspace"), workspace.workspace)
        self.assertEqual(table.rows[0].get_cell_value("managed_group"), group)
        self.assertIsNone(table.rows[0].get_cell_value("access"))
        self.assertEqual(
            table.rows[0].get_cell_value("note"),
            combined_workspace_audit.CombinedConsortiumDataWorkspaceSharingAudit.DCC_WRITERS_BEFORE_COMPLETE,
        )
        self.assertNotEqual(table.rows[0].get_cell_value("action"), "&mdash;")

    def test_context_needs_action_table_share_as_owner(self):
        """needs_action_table shows a record when audit finds that access needs to be granted."""
        workspace = factories.CombinedConsortiumDataWorkspaceFactory.create()
        group = acm_factories.ManagedGroupFactory.create(name=settings.ANVIL_DCC_ADMINS_GROUP_NAME)
        # Check the table in the context.
        self.client.force_login(self.user)
        response = self.client.get(self.get_url())
        self.assertIn("needs_action_table", response.context_data)
        table = response.context_data["needs_action_table"]
        self.assertIsInstance(
            table,
            combined_workspace_audit.CombinedConsortiumDataWorkspaceSharingAuditTable,
        )
        self.assertEqual(len(table.rows), 1)
        self.assertEqual(table.rows[0].get_cell_value("workspace"), workspace.workspace)
        self.assertEqual(table.rows[0].get_cell_value("managed_group"), group)
        self.assertIsNone(table.rows[0].get_cell_value("access"))
        self.assertEqual(
            table.rows[0].get_cell_value("note"),
            combined_workspace_audit.CombinedConsortiumDataWorkspaceSharingAudit.DCC_ADMIN_AS_OWNER,
        )
        self.assertNotEqual(table.rows[0].get_cell_value("action"), "&mdash;")

    def test_context_needs_action_table_stop_sharing(self):
        """needs_action_table shows a record when audit finds that access needs to be granted."""
        # Change upload workspace end dates so it's in the past.
        group = acm_factories.ManagedGroupFactory.create(name="GREGOR_DCC_MEMBERS")
        workspace = factories.CombinedConsortiumDataWorkspaceFactory.create(
            date_completed=timezone.localdate() - timedelta(days=1),
        )
        # Create a sharing record.
        acm_factories.WorkspaceGroupSharingFactory.create(
            workspace=workspace.workspace,
            group=group,
            access=acm_models.WorkspaceGroupSharing.READER,
        )
        # Share with the auth domain to prevent that audit result.
        acm_factories.WorkspaceGroupSharingFactory.create(
            workspace=workspace.workspace,
            group=workspace.workspace.authorization_domains.first(),
            access=acm_models.WorkspaceGroupSharing.READER,
        )
        # Check the table in the context.
        self.client.force_login(self.user)
        response = self.client.get(self.get_url())
        self.assertIn("needs_action_table", response.context_data)
        table = response.context_data["needs_action_table"]
        self.assertIsInstance(
            table,
            combined_workspace_audit.CombinedConsortiumDataWorkspaceSharingAuditTable,
        )
        self.assertEqual(len(table.rows), 1)
        self.assertEqual(table.rows[0].get_cell_value("workspace"), workspace.workspace)
        self.assertEqual(table.rows[0].get_cell_value("managed_group"), group)
        self.assertEqual(table.rows[0].get_cell_value("access"), "READER")
        self.assertEqual(
            table.rows[0].get_cell_value("note"),
            combined_workspace_audit.CombinedConsortiumDataWorkspaceSharingAudit.DCC_MEMBERS_AFTER_COMPLETE,
        )
        self.assertNotEqual(table.rows[0].get_cell_value("action"), "&mdash;")

    def test_context_error_table_stop_sharing(self):
        """error_table shows a record when an audit error is detected."""
        workspace = factories.CombinedConsortiumDataWorkspaceFactory.create()
        group = acm_factories.ManagedGroupFactory.create()
        # Create a sharing record.
        acm_factories.WorkspaceGroupSharingFactory.create(
            workspace=workspace.workspace,
            group=group,
            access=acm_models.WorkspaceGroupSharing.READER,
        )
        # Check the table in the context.
        self.client.force_login(self.user)
        response = self.client.get(self.get_url())
        self.assertIn("errors_table", response.context_data)
        table = response.context_data["errors_table"]
        self.assertIsInstance(
            table,
            combined_workspace_audit.CombinedConsortiumDataWorkspaceSharingAuditTable,
        )
        self.assertEqual(len(table.rows), 1)
        self.assertEqual(table.rows[0].get_cell_value("workspace"), workspace.workspace)
        self.assertEqual(table.rows[0].get_cell_value("managed_group"), group)
        self.assertEqual(table.rows[0].get_cell_value("access"), "READER")
        self.assertEqual(
            table.rows[0].get_cell_value("note"),
            combined_workspace_audit.CombinedConsortiumDataWorkspaceSharingAudit.OTHER_GROUP,
        )
        self.assertNotEqual(table.rows[0].get_cell_value("action"), "&mdash;")

    def test_title(self):
        self.client.force_login(self.user)
        response = self.client.get(self.get_url())
        # self.assertContains(response, str(self.workspace))
        self.assertIn("all combined workspaces", response.content.decode().lower())


class CombinedConsortiumDataWorkspaceSharingAuditByWorkspaceTest(AnVILAPIMockTestMixin, TestCase):
    """Tests for the CombinedConsortiumDataWorkspaceSharingAuditByWorkspace view."""

    def setUp(self):
        """Set up test class."""
        super().setUp()
        self.factory = RequestFactory()
        # Create a user with both view and edit permission.
        self.user = User.objects.create_user(username="test", password="test")
        self.user.user_permissions.add(
            Permission.objects.get(codename=AnVILProjectManagerAccess.STAFF_VIEW_PERMISSION_CODENAME)
        )
        self.workspace = factories.CombinedConsortiumDataWorkspaceFactory.create()

    def get_url(self, *args):
        """Get the url for the view being tested."""
        return reverse(
            "gregor_anvil:audit:combined_workspaces:sharing:by_workspace",
            args=args,
        )

    def get_view(self):
        """Return the view being tested."""
        return views.CombinedConsortiumDataWorkspaceSharingAuditByWorkspace.as_view()

    def test_view_redirect_not_logged_in(self):
        "View redirects to login view when user is not logged in."
        # Need a client for redirects.
        response = self.client.get(self.get_url("foo", "bar"))
        self.assertRedirects(
            response,
            resolve_url(settings.LOGIN_URL) + "?next=" + self.get_url("foo", "bar"),
        )

    def test_status_code_with_user_permission_view(self):
        """Returns successful response code if the user has view permission."""
        self.client.force_login(self.user)
        response = self.client.get(
            self.get_url(self.workspace.workspace.billing_project.name, self.workspace.workspace.name)
        )
        self.assertEqual(response.status_code, 200)

    def test_access_without_user_permission(self):
        """Raises permission denied if user has no permissions."""
        user_no_perms = User.objects.create_user(username="test-none", password="test-none")
        request = self.factory.get(self.get_url("foo", "bar"))
        request.user = user_no_perms
        with self.assertRaises(PermissionDenied):
            self.get_view()(request)

    def test_invalid_billing_project_name(self):
        """Raises a 404 error with an invalid object billing project."""
        request = self.factory.get(self.get_url("foo", self.workspace.workspace.name))
        request.user = self.user
        with self.assertRaises(Http404):
            self.get_view()(
                request,
                billing_project_slug="foo",
                workspace_slug=self.workspace.workspace.name,
            )

    def test_invalid_workspace_name(self):
        """Raises a 404 error with an invalid workspace name."""
        request = self.factory.get(self.get_url(self.workspace.workspace.billing_project.name, "foo"))
        request.user = self.user
        with self.assertRaises(Http404):
            self.get_view()(
                request,
                billing_project_slug=self.workspace.workspace.billing_project.name,
                workspace_slug="foo",
            )

    def test_context_audit_results(self):
        """The audit_results exists in the context."""
        self.client.force_login(self.user)
        response = self.client.get(
            self.get_url(
                self.workspace.workspace.billing_project.name,
                self.workspace.workspace.name,
            )
        )
        self.assertIn("audit_results", response.context_data)
        audit_results = response.context_data["audit_results"]
        self.assertIsInstance(
            audit_results,
            combined_workspace_audit.CombinedConsortiumDataWorkspaceSharingAudit,
        )
        self.assertTrue(audit_results.completed)
        self.assertEqual(audit_results.queryset.count(), 1)
        self.assertIn(self.workspace, audit_results.queryset)

    def test_context_audit_results_does_not_include_other_workspaces(self):
        """The audit_results does not include other workspaces."""
        other_workspace = factories.CombinedConsortiumDataWorkspaceFactory.create()
        self.client.force_login(self.user)
        response = self.client.get(
            self.get_url(
                self.workspace.workspace.billing_project.name,
                self.workspace.workspace.name,
            )
        )
        audit_results = response.context_data["audit_results"]
        self.assertEqual(audit_results.queryset.count(), 1)
        self.assertNotIn(other_workspace, audit_results.queryset)

    def test_context_verified_table_access(self):
        """verified_table shows a record when audit has verified access."""
        self.workspace.date_completed = timezone.now() - timedelta(days=1)
        self.workspace.save()
        group = self.workspace.workspace.authorization_domains.first()
        acm_factories.WorkspaceGroupSharingFactory.create(
            workspace=self.workspace.workspace,
            group=group,
            access=acm_models.WorkspaceGroupSharing.READER,
        )
        # Check the table in the context.
        self.client.force_login(self.user)
        response = self.client.get(
            self.get_url(self.workspace.workspace.billing_project.name, self.workspace.workspace.name)
        )
        self.assertIn("verified_table", response.context_data)
        table = response.context_data["verified_table"]
        self.assertIsInstance(
            table,
            combined_workspace_audit.CombinedConsortiumDataWorkspaceSharingAuditTable,
        )
        self.assertEqual(len(table.rows), 1)
        self.assertEqual(table.rows[0].get_cell_value("workspace"), self.workspace.workspace)
        self.assertEqual(table.rows[0].get_cell_value("managed_group"), group)
        self.assertEqual(table.rows[0].get_cell_value("access"), "READER")
        self.assertEqual(
            table.rows[0].get_cell_value("note"),
            combined_workspace_audit.CombinedConsortiumDataWorkspaceSharingAudit.AUTH_DOMAIN_AFTER_COMPLETE,
        )
        self.assertEqual(table.rows[0].get_cell_value("action"), "&mdash;")

    def test_context_verified_table_no_access(self):
        """verified_table shows a record when audit has verified no access."""
        group = self.workspace.workspace.authorization_domains.first()
        # Check the table in the context.
        self.client.force_login(self.user)
        response = self.client.get(
            self.get_url(self.workspace.workspace.billing_project.name, self.workspace.workspace.name)
        )
        self.assertIn("verified_table", response.context_data)
        table = response.context_data["verified_table"]
        self.assertIsInstance(
            table,
            combined_workspace_audit.CombinedConsortiumDataWorkspaceSharingAuditTable,
        )
        self.assertEqual(len(table.rows), 1)
        self.assertEqual(table.rows[0].get_cell_value("workspace"), self.workspace.workspace)
        self.assertEqual(table.rows[0].get_cell_value("managed_group"), group)
        self.assertIsNone(table.rows[0].get_cell_value("access"))
        self.assertEqual(
            table.rows[0].get_cell_value("note"),
            combined_workspace_audit.CombinedConsortiumDataWorkspaceSharingAudit.AUTH_DOMAIN_BEFORE_COMPLETE,
        )
        self.assertEqual(table.rows[0].get_cell_value("action"), "&mdash;")

    def test_context_needs_action_table_share_as_reader(self):
        """needs_action_table shows a record when audit finds that access needs to be granted."""
        self.workspace.date_completed = timezone.now() - timedelta(days=1)
        self.workspace.save()
        group = self.workspace.workspace.authorization_domains.first()
        # Check the table in the context.
        self.client.force_login(self.user)
        response = self.client.get(
            self.get_url(self.workspace.workspace.billing_project.name, self.workspace.workspace.name)
        )
        self.assertIn("needs_action_table", response.context_data)
        table = response.context_data["needs_action_table"]
        self.assertIsInstance(
            table,
            combined_workspace_audit.CombinedConsortiumDataWorkspaceSharingAuditTable,
        )
        self.assertEqual(len(table.rows), 1)
        self.assertEqual(table.rows[0].get_cell_value("workspace"), self.workspace.workspace)
        self.assertEqual(table.rows[0].get_cell_value("managed_group"), group)
        self.assertIsNone(table.rows[0].get_cell_value("access"))
        self.assertEqual(
            table.rows[0].get_cell_value("note"),
            combined_workspace_audit.CombinedConsortiumDataWorkspaceSharingAudit.AUTH_DOMAIN_AFTER_COMPLETE,
        )
        self.assertNotEqual(table.rows[0].get_cell_value("action"), "&mdash;")

    def test_context_needs_action_table_share_as_writer_with_compute(self):
        """needs_action_table shows a record when audit finds that access needs to be granted."""
        group = acm_factories.ManagedGroupFactory.create(name="GREGOR_DCC_WRITERS")
        # Check the table in the context.
        self.client.force_login(self.user)
        response = self.client.get(
            self.get_url(self.workspace.workspace.billing_project.name, self.workspace.workspace.name)
        )
        self.assertIn("needs_action_table", response.context_data)
        table = response.context_data["needs_action_table"]
        self.assertIsInstance(
            table,
            combined_workspace_audit.CombinedConsortiumDataWorkspaceSharingAuditTable,
        )
        self.assertEqual(len(table.rows), 1)
        self.assertEqual(table.rows[0].get_cell_value("workspace"), self.workspace.workspace)
        self.assertEqual(table.rows[0].get_cell_value("managed_group"), group)
        self.assertIsNone(table.rows[0].get_cell_value("access"))
        self.assertEqual(
            table.rows[0].get_cell_value("note"),
            combined_workspace_audit.CombinedConsortiumDataWorkspaceSharingAudit.DCC_WRITERS_BEFORE_COMPLETE,
        )
        self.assertNotEqual(table.rows[0].get_cell_value("action"), "&mdash;")

    def test_context_needs_action_table_share_as_owner(self):
        """needs_action_table shows a record when audit finds that access needs to be granted."""
        group = acm_factories.ManagedGroupFactory.create(name=settings.ANVIL_DCC_ADMINS_GROUP_NAME)
        # Check the table in the context.
        self.client.force_login(self.user)
        response = self.client.get(
            self.get_url(self.workspace.workspace.billing_project.name, self.workspace.workspace.name)
        )
        self.assertIn("needs_action_table", response.context_data)
        table = response.context_data["needs_action_table"]
        self.assertIsInstance(
            table,
            combined_workspace_audit.CombinedConsortiumDataWorkspaceSharingAuditTable,
        )
        self.assertEqual(len(table.rows), 1)
        self.assertEqual(table.rows[0].get_cell_value("workspace"), self.workspace.workspace)
        self.assertEqual(table.rows[0].get_cell_value("managed_group"), group)
        self.assertIsNone(table.rows[0].get_cell_value("access"))
        self.assertEqual(
            table.rows[0].get_cell_value("note"),
            combined_workspace_audit.CombinedConsortiumDataWorkspaceSharingAudit.DCC_ADMIN_AS_OWNER,
        )
        self.assertNotEqual(table.rows[0].get_cell_value("action"), "&mdash;")

    def test_context_needs_action_table_stop_sharing(self):
        """needs_action_table shows a record when audit finds that access needs to be granted."""
        # Change upload workspace end dates so it's in the past.
        group = acm_factories.ManagedGroupFactory.create(name="GREGOR_DCC_MEMBERS")
        self.workspace.date_completed = timezone.localdate() - timedelta(days=1)
        self.workspace.save()
        # Create a sharing record.
        acm_factories.WorkspaceGroupSharingFactory.create(
            workspace=self.workspace.workspace,
            group=group,
            access=acm_models.WorkspaceGroupSharing.READER,
        )
        # Share with the auth domain to prevent that audit result.
        acm_factories.WorkspaceGroupSharingFactory.create(
            workspace=self.workspace.workspace,
            group=self.workspace.workspace.authorization_domains.first(),
            access=acm_models.WorkspaceGroupSharing.READER,
        )
        # Check the table in the context.
        self.client.force_login(self.user)
        response = self.client.get(
            self.get_url(self.workspace.workspace.billing_project.name, self.workspace.workspace.name)
        )
        self.assertIn("needs_action_table", response.context_data)
        table = response.context_data["needs_action_table"]
        self.assertIsInstance(
            table,
            combined_workspace_audit.CombinedConsortiumDataWorkspaceSharingAuditTable,
        )
        self.assertEqual(len(table.rows), 1)
        self.assertEqual(table.rows[0].get_cell_value("workspace"), self.workspace.workspace)
        self.assertEqual(table.rows[0].get_cell_value("managed_group"), group)
        self.assertEqual(table.rows[0].get_cell_value("access"), "READER")
        self.assertEqual(
            table.rows[0].get_cell_value("note"),
            combined_workspace_audit.CombinedConsortiumDataWorkspaceSharingAudit.DCC_MEMBERS_AFTER_COMPLETE,
        )
        self.assertNotEqual(table.rows[0].get_cell_value("action"), "&mdash;")

    def test_context_error_table_stop_sharing(self):
        """error_table shows a record when an audit error is detected."""
        group = acm_factories.ManagedGroupFactory.create()
        # Create a sharing record.
        acm_factories.WorkspaceGroupSharingFactory.create(
            workspace=self.workspace.workspace,
            group=group,
            access=acm_models.WorkspaceGroupSharing.READER,
        )
        # Check the table in the context.
        self.client.force_login(self.user)
        response = self.client.get(
            self.get_url(self.workspace.workspace.billing_project.name, self.workspace.workspace.name)
        )
        self.assertIn("errors_table", response.context_data)
        table = response.context_data["errors_table"]
        self.assertIsInstance(
            table,
            combined_workspace_audit.CombinedConsortiumDataWorkspaceSharingAuditTable,
        )
        self.assertEqual(len(table.rows), 1)
        self.assertEqual(table.rows[0].get_cell_value("workspace"), self.workspace.workspace)
        self.assertEqual(table.rows[0].get_cell_value("managed_group"), group)
        self.assertEqual(table.rows[0].get_cell_value("access"), "READER")
        self.assertEqual(
            table.rows[0].get_cell_value("note"),
            combined_workspace_audit.CombinedConsortiumDataWorkspaceSharingAudit.OTHER_GROUP,
        )
        self.assertNotEqual(table.rows[0].get_cell_value("action"), "&mdash;")

    def test_title(self):
        self.client.force_login(self.user)
        response = self.client.get(
            self.get_url(self.workspace.workspace.billing_project.name, self.workspace.workspace.name)
        )
        # self.assertContains(response, str(self.workspace))
        self.assertIn(str(self.workspace), response.content.decode().lower())
