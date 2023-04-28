import json

import responses
from anvil_consortium_manager import models as acm_models
from anvil_consortium_manager.tests import factories as acm_factories
from anvil_consortium_manager.tests.utils import AnVILAPIMockTestMixin
from django.conf import settings
from django.contrib.auth import get_user_model
from django.contrib.auth.models import Permission
from django.core.exceptions import PermissionDenied
from django.http.response import Http404
from django.shortcuts import resolve_url
from django.test import RequestFactory, TestCase
from django.urls import reverse

from gregor_django.users.tests.factories import UserFactory

from .. import models, tables, views
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
        self.assertNotIn(
            reverse("anvil_consortium_manager:index"), response.rendered_content
        )

    def test_acm_link_with_view_permission(self):
        """ACM link shows up if you have view permission."""
        user = User.objects.create_user(username="test-none", password="test-none")
        user.user_permissions.add(
            Permission.objects.get(
                codename=acm_models.AnVILProjectManagerAccess.VIEW_PERMISSION_CODENAME
            )
        )
        self.client.force_login(user)
        response = self.client.get(self.get_url())
        self.assertIn("AnVIL Consortium Manager", response.rendered_content)
        self.assertIn(
            reverse("anvil_consortium_manager:index"), response.rendered_content
        )

    def test_acm_link_with_view_and_edit_permission(self):
        """ACM link shows up if you have view and edit permission."""
        user = User.objects.create_user(username="test-none", password="test-none")
        user.user_permissions.add(
            Permission.objects.get(
                codename=acm_models.AnVILProjectManagerAccess.VIEW_PERMISSION_CODENAME
            )
        )
        user.user_permissions.add(
            Permission.objects.get(
                codename=acm_models.AnVILProjectManagerAccess.EDIT_PERMISSION_CODENAME
            )
        )
        self.client.force_login(user)
        response = self.client.get(self.get_url())
        self.assertIn("AnVIL Consortium Manager", response.rendered_content)
        self.assertIn(
            reverse("anvil_consortium_manager:index"), response.rendered_content
        )

    def test_acm_link_with_edit_but_not_view_permission(self):
        """ACM link does not show up if you only have edit permission.

        This is something that shouldn't happen but could if admin only gave EDIT but not VIEW permission."""
        user = User.objects.create_user(username="test-none", password="test-none")
        user.user_permissions.add(
            Permission.objects.get(
                codename=acm_models.AnVILProjectManagerAccess.EDIT_PERMISSION_CODENAME
            )
        )
        self.client.force_login(user)
        response = self.client.get(self.get_url())
        self.assertNotIn("AnVIL Consortium Manager", response.rendered_content)
        self.assertNotIn(
            reverse("anvil_consortium_manager:index"), response.rendered_content
        )


class ConsentGroupDetailTest(TestCase):
    """Tests for the ConsentGroupDetail view."""

    def setUp(self):
        """Set up test class."""
        self.factory = RequestFactory()
        self.model_factory = factories.ConsentGroupFactory
        # Create a user with both view and edit permission.
        self.user = User.objects.create_user(username="test", password="test")
        self.user.user_permissions.add(
            Permission.objects.get(
                codename=acm_models.AnVILProjectManagerAccess.VIEW_PERMISSION_CODENAME
            )
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
        self.assertRedirects(
            response, resolve_url(settings.LOGIN_URL) + "?next=" + self.get_url(1)
        )

    def test_status_code_with_user_permission(self):
        """Returns successful response code."""
        obj = self.model_factory.create()
        self.client.force_login(self.user)
        response = self.client.get(self.get_url(obj.pk))
        self.assertEqual(response.status_code, 200)

    def test_access_without_user_permission(self):
        """Raises permission denied if user has no permissions."""
        user_no_perms = User.objects.create_user(
            username="test-none", password="test-none"
        )
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
            Permission.objects.get(
                codename=acm_models.AnVILProjectManagerAccess.VIEW_PERMISSION_CODENAME
            )
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
        self.assertRedirects(
            response, resolve_url(settings.LOGIN_URL) + "?next=" + self.get_url()
        )

    def test_status_code_with_user_permission(self):
        """Returns successful response code."""
        self.client.force_login(self.user)
        response = self.client.get(self.get_url())
        self.assertEqual(response.status_code, 200)

    def test_access_without_user_permission(self):
        """Raises permission denied if user has no permissions."""
        user_no_perms = User.objects.create_user(
            username="test-none", password="test-none"
        )
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
            Permission.objects.get(
                codename=acm_models.AnVILProjectManagerAccess.VIEW_PERMISSION_CODENAME
            )
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
        self.assertRedirects(
            response, resolve_url(settings.LOGIN_URL) + "?next=" + self.get_url(1)
        )

    def test_status_code_with_user_permission(self):
        """Returns successful response code."""
        obj = self.model_factory.create()
        self.client.force_login(self.user)
        response = self.client.get(self.get_url(obj.pk))
        self.assertEqual(response.status_code, 200)

    def test_access_without_user_permission(self):
        """Raises permission denied if user has no permissions."""
        user_no_perms = User.objects.create_user(
            username="test-none", password="test-none"
        )
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
        self.assertIn("site_user_table", response.context_data)
        table = response.context_data["site_user_table"]
        self.assertEqual(len(table.rows), 1)

        self.assertIn(site_user, table.data)
        self.assertNotIn(non_site_user, table.data)


class ResearchCenterListTest(TestCase):
    """Tests for the ResearchCenterList view."""

    def setUp(self):
        """Set up test class."""
        self.factory = RequestFactory()
        self.model_factory = factories.ResearchCenterFactory
        # Create a user with both view and edit permission.
        self.user = User.objects.create_user(username="test", password="test")
        self.user.user_permissions.add(
            Permission.objects.get(
                codename=acm_models.AnVILProjectManagerAccess.VIEW_PERMISSION_CODENAME
            )
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
        self.assertRedirects(
            response, resolve_url(settings.LOGIN_URL) + "?next=" + self.get_url()
        )

    def test_status_code_with_user_permission(self):
        """Returns successful response code."""
        self.client.force_login(self.user)
        response = self.client.get(self.get_url())
        self.assertEqual(response.status_code, 200)

    def test_access_without_user_permission(self):
        """Raises permission denied if user has no permissions."""
        user_no_perms = User.objects.create_user(
            username="test-none", password="test-none"
        )
        request = self.factory.get(self.get_url())
        request.user = user_no_perms
        with self.assertRaises(PermissionDenied):
            self.get_view()(request)

    def test_view_has_correct_table_class(self):
        """View has the correct table class in the context."""
        self.client.force_login(self.user)
        response = self.client.get(self.get_url())
        self.assertIn("table", response.context_data)
        self.assertIsInstance(
            response.context_data["table"], tables.ResearchCenterTable
        )

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
            Permission.objects.get(
                codename=acm_models.AnVILProjectManagerAccess.VIEW_PERMISSION_CODENAME
            )
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
        self.assertRedirects(
            response, resolve_url(settings.LOGIN_URL) + "?next=" + self.get_url(1)
        )

    def test_status_code_with_user_permission(self):
        """Returns successful response code."""
        obj = self.model_factory.create()
        self.client.force_login(self.user)
        response = self.client.get(self.get_url(obj.pk))
        self.assertEqual(response.status_code, 200)

    def test_access_without_user_permission(self):
        """Raises permission denied if user has no permissions."""
        user_no_perms = User.objects.create_user(
            username="test-none", password="test-none"
        )
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
        self.assertIn("partner_group_user_table", response.context_data)
        table = response.context_data["partner_group_user_table"]
        self.assertEqual(len(table.rows), 1)

        self.assertIn(pg_user, table.data)
        self.assertNotIn(non_pg_user, table.data)


class PartnerGroupListTest(TestCase):
    """Tests for the ResearchCenterList view."""

    def setUp(self):
        """Set up test class."""
        self.factory = RequestFactory()
        self.model_factory = factories.PartnerGroupFactory
        # Create a user with both view and edit permission.
        self.user = User.objects.create_user(username="test", password="test")
        self.user.user_permissions.add(
            Permission.objects.get(
                codename=acm_models.AnVILProjectManagerAccess.VIEW_PERMISSION_CODENAME
            )
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
        self.assertRedirects(
            response, resolve_url(settings.LOGIN_URL) + "?next=" + self.get_url()
        )

    def test_status_code_with_user_permission(self):
        """Returns successful response code."""
        self.client.force_login(self.user)
        response = self.client.get(self.get_url())
        self.assertEqual(response.status_code, 200)

    def test_access_without_user_permission(self):
        """Raises permission denied if user has no permissions."""
        user_no_perms = User.objects.create_user(
            username="test-none", password="test-none"
        )
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


class UploadWorkspaceDetailTest(TestCase):
    """Tests of the anvil_consortium_manager WorkspaceDetail view using the UploadWorkspace adapter."""

    def setUp(self):
        """Set up test class."""
        self.factory = RequestFactory()
        # Create a user with both view and edit permission.
        self.user = User.objects.create_user(username="test", password="test")
        self.user.user_permissions.add(
            Permission.objects.get(
                codename=acm_models.AnVILProjectManagerAccess.VIEW_PERMISSION_CODENAME
            )
        )
        self.object = factories.UploadWorkspaceFactory.create()

    def get_url(self, *args):
        """Get the url for the view being tested."""
        return reverse("anvil_consortium_manager:workspaces:detail", args=args)

    def test_status_code(self):
        """Response has a status code of 200."""
        self.client.force_login(self.user)
        response = self.client.get(
            self.get_url(
                self.object.workspace.billing_project.name, self.object.workspace.name
            )
        )
        self.assertEqual(response.status_code, 200)


class UploadWorkspaceListTest(TestCase):
    """Tests of the anvil_consortium_manager WorkspaceList view using this app's adapter."""

    def setUp(self):
        """Set up test class."""
        self.factory = RequestFactory()
        # Create a user with both view and edit permission.
        self.user = User.objects.create_user(username="test", password="test")
        self.user.user_permissions.add(
            Permission.objects.get(
                codename=acm_models.AnVILProjectManagerAccess.VIEW_PERMISSION_CODENAME
            )
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
        self.assertIsInstance(
            response.context_data["table"], tables.UploadWorkspaceTable
        )


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
            Permission.objects.get(
                codename=acm_models.AnVILProjectManagerAccess.VIEW_PERMISSION_CODENAME
            )
        )
        self.user.user_permissions.add(
            Permission.objects.get(
                codename=acm_models.AnVILProjectManagerAccess.EDIT_PERMISSION_CODENAME
            )
        )
        self.workspace_type = "upload"

    def get_url(self, *args):
        """Get the url for the view being tested."""
        return reverse("anvil_consortium_manager:workspaces:new", args=args)

    def test_creates_upload_workspace(self):
        """Posting valid data to the form creates a workspace data object when using a custom adapter."""
        research_center = factories.ResearchCenterFactory.create()
        consent_group = factories.ConsentGroupFactory.create()
        billing_project = acm_factories.BillingProjectFactory.create(
            name="test-billing-project"
        )
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
                "workspacedata-0-version": 5,
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
        self.assertEqual(new_workspace_data.version, 5)


class UploadWorkspaceAutocompleteByTypeTest(TestCase):
    def setUp(self):
        """Set up test class."""
        self.factory = RequestFactory()
        # Create a user with the correct permissions.
        self.user = User.objects.create_user(username="test", password="test")
        self.user.user_permissions.add(
            Permission.objects.get(
                codename=acm_models.AnVILProjectManagerAccess.VIEW_PERMISSION_CODENAME
            )
        )

    def get_url(self, *args):
        """Get the url for the view being tested."""
        return reverse(
            "anvil_consortium_manager:workspaces:autocomplete_by_type", args=args
        )

    def test_returns_all_objects(self):
        """Queryset returns all objects when there is no query."""
        workspaces = factories.UploadWorkspaceFactory.create_batch(10)
        self.client.force_login(self.user)
        response = self.client.get(self.get_url("upload"))
        returned_ids = [
            int(x["id"])
            for x in json.loads(response.content.decode("utf-8"))["results"]
        ]
        self.assertEqual(len(returned_ids), 10)
        self.assertEqual(sorted(returned_ids), sorted([x.pk for x in workspaces]))

    def test_returns_correct_object_match(self):
        """Queryset returns the correct objects when query matches the name."""
        factories.UploadWorkspaceFactory.create(workspace__name="other")
        workspace = factories.UploadWorkspaceFactory.create(
            workspace__name="test-workspace"
        )
        self.client.force_login(self.user)
        response = self.client.get(self.get_url("upload"), {"q": "test-workspace"})
        returned_ids = [
            int(x["id"])
            for x in json.loads(response.content.decode("utf-8"))["results"]
        ]
        self.assertEqual(len(returned_ids), 1)
        self.assertEqual(returned_ids[0], workspace.pk)

    def test_returns_correct_object_starting_with_query(self):
        """Queryset returns the correct objects when query matches the beginning of the name."""
        factories.UploadWorkspaceFactory.create(workspace__name="other")
        workspace = factories.UploadWorkspaceFactory.create(
            workspace__name="test-workspace"
        )
        self.client.force_login(self.user)
        response = self.client.get(self.get_url("upload"), {"q": "test"})
        returned_ids = [
            int(x["id"])
            for x in json.loads(response.content.decode("utf-8"))["results"]
        ]
        self.assertEqual(len(returned_ids), 1)
        self.assertEqual(returned_ids[0], workspace.pk)

    def test_returns_correct_object_containing_query(self):
        """Queryset returns the correct objects when the name contains the query."""
        factories.UploadWorkspaceFactory.create(workspace__name="other")
        workspace = factories.UploadWorkspaceFactory.create(
            workspace__name="test-workspace"
        )
        self.client.force_login(self.user)
        response = self.client.get(self.get_url("upload"), {"q": "work"})
        returned_ids = [
            int(x["id"])
            for x in json.loads(response.content.decode("utf-8"))["results"]
        ]
        self.assertEqual(len(returned_ids), 1)
        self.assertEqual(returned_ids[0], workspace.pk)

    def test_returns_correct_object_case_insensitive(self):
        """Queryset returns the correct objects when query matches the beginning of the name."""
        factories.UploadWorkspaceFactory.create(workspace__name="other")
        workspace = factories.UploadWorkspaceFactory.create(
            workspace__name="test-workspace"
        )
        self.client.force_login(self.user)
        response = self.client.get(self.get_url("upload"), {"q": "TEST-WORKSPACE"})
        returned_ids = [
            int(x["id"])
            for x in json.loads(response.content.decode("utf-8"))["results"]
        ]
        self.assertEqual(len(returned_ids), 1)
        self.assertEqual(returned_ids[0], workspace.pk)

    def test_forwarded_consent_group(self):
        """Queryset is filtered to consent groups matching the forwarded value if specified."""
        consent_group = factories.ConsentGroupFactory.create()
        workspace = factories.UploadWorkspaceFactory.create(
            workspace__name="test_1", consent_group=consent_group
        )
        other_consent_group = factories.ConsentGroupFactory.create()
        other_workspace = factories.UploadWorkspaceFactory.create(
            workspace__name="test_2", consent_group=other_consent_group
        )
        self.client.force_login(self.user)
        response = self.client.get(
            self.get_url("upload"),
            {"q": "test", "forward": json.dumps({"consent_group": consent_group.pk})},
        )
        returned_ids = [
            int(x["id"])
            for x in json.loads(response.content.decode("utf-8"))["results"]
        ]
        self.assertEqual(len(returned_ids), 1)
        self.assertIn(workspace.pk, returned_ids)
        self.assertNotIn(other_workspace.pk, returned_ids)


class ExampleWorkspaceListTest(TestCase):
    """Tests of the anvil_consortium_manager WorkspaceList view using the ExampleWorkspace adapter."""

    def setUp(self):
        """Set up test class."""
        self.factory = RequestFactory()
        # Create a user with both view and edit permission.
        self.user = User.objects.create_user(username="test", password="test")
        self.user.user_permissions.add(
            Permission.objects.get(
                codename=acm_models.AnVILProjectManagerAccess.VIEW_PERMISSION_CODENAME
            )
        )
        self.workspace_type = "example"

    def get_url(self, *args):
        """Get the url for the view being tested."""
        return reverse("anvil_consortium_manager:workspaces:list", args=args)

    def test_view_has_correct_table_class(self):
        """The view has the correct table class in the context."""
        self.client.force_login(self.user)
        response = self.client.get(self.get_url(self.workspace_type))
        self.assertIn("table", response.context_data)
        self.assertIsInstance(
            response.context_data["table"], tables.DefaultWorkspaceTable
        )


class ExampleWorkspaceCreateTest(AnVILAPIMockTestMixin, TestCase):
    """Tests of the WorkspaceCreate view from ACM with extra ExampleWorkspace model."""

    api_success_code = 201

    def setUp(self):
        """Set up test class."""
        # The superclass uses the responses package to mock API responses.
        super().setUp()
        # Create a user with both view and edit permissions.
        self.user = User.objects.create_user(username="test", password="test")
        self.user.user_permissions.add(
            Permission.objects.get(
                codename=acm_models.AnVILProjectManagerAccess.VIEW_PERMISSION_CODENAME
            )
        )
        self.user.user_permissions.add(
            Permission.objects.get(
                codename=acm_models.AnVILProjectManagerAccess.EDIT_PERMISSION_CODENAME
            )
        )
        self.workspace_type = "example"

    def get_url(self, *args):
        """Get the url for the view being tested."""
        return reverse("anvil_consortium_manager:workspaces:new", args=args)

    def test_creates_upload_workspace(self):
        """Posting valid data to the form creates a workspace data object when using a custom adapter."""
        billing_project = acm_factories.BillingProjectFactory.create(
            name="test-billing-project"
        )
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
            },
        )
        self.assertEqual(response.status_code, 302)
        # The workspace is created.
        new_workspace = acm_models.Workspace.objects.latest("pk")
        # Workspace data is added.
        self.assertEqual(models.ExampleWorkspace.objects.count(), 1)
        new_workspace_data = models.ExampleWorkspace.objects.latest("pk")
        self.assertEqual(new_workspace_data.workspace, new_workspace)


class TemplateWorkspaceDetailTest(TestCase):
    """Tests of the anvil_consortium_manager WorkspaceDetail view using the TemplateWorkspace adapter."""

    def setUp(self):
        """Set up test class."""
        self.factory = RequestFactory()
        # Create a user with both view and edit permission.
        self.user = User.objects.create_user(username="test", password="test")
        self.user.user_permissions.add(
            Permission.objects.get(
                codename=acm_models.AnVILProjectManagerAccess.VIEW_PERMISSION_CODENAME
            )
        )
        self.object = factories.TemplateWorkspaceFactory.create()

    def get_url(self, *args):
        """Get the url for the view being tested."""
        return reverse("anvil_consortium_manager:workspaces:detail", args=args)

    def test_status_code(self):
        """Response has a status code of 200."""
        self.client.force_login(self.user)
        response = self.client.get(
            self.get_url(
                self.object.workspace.billing_project.name, self.object.workspace.name
            )
        )
        self.assertEqual(response.status_code, 200)


class TemplateWorkspaceListTest(TestCase):
    """Tests of the anvil_consortium_manager WorkspaceList view using the TemplateWorkspace adapter."""

    def setUp(self):
        """Set up test class."""
        self.factory = RequestFactory()
        # Create a user with both view and edit permission.
        self.user = User.objects.create_user(username="test", password="test")
        self.user.user_permissions.add(
            Permission.objects.get(
                codename=acm_models.AnVILProjectManagerAccess.VIEW_PERMISSION_CODENAME
            )
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
        self.assertIsInstance(
            response.context_data["table"], tables.TemplateWorkspaceTable
        )


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
            Permission.objects.get(
                codename=acm_models.AnVILProjectManagerAccess.VIEW_PERMISSION_CODENAME
            )
        )
        self.user.user_permissions.add(
            Permission.objects.get(
                codename=acm_models.AnVILProjectManagerAccess.EDIT_PERMISSION_CODENAME
            )
        )
        self.workspace_type = "template"

    def get_url(self, *args):
        """Get the url for the view being tested."""
        return reverse("anvil_consortium_manager:workspaces:new", args=args)

    def test_creates_upload_workspace(self):
        """Posting valid data to the form creates a workspace data object when using a custom adapter."""
        billing_project = acm_factories.BillingProjectFactory.create(
            name="test-billing-project"
        )
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
            Permission.objects.get(
                codename=acm_models.AnVILProjectManagerAccess.VIEW_PERMISSION_CODENAME
            )
        )
        self.object = factories.CombinedConsortiumDataWorkspaceFactory.create()

    def get_url(self, *args):
        """Get the url for the view being tested."""
        return reverse("anvil_consortium_manager:workspaces:detail", args=args)

    def test_status_code(self):
        """Response has a status code of 200."""
        upload_workspace = factories.UploadWorkspaceFactory.create()
        self.object.upload_workspaces.add(upload_workspace)
        self.client.force_login(self.user)
        response = self.client.get(
            self.get_url(
                self.object.workspace.billing_project.name, self.object.workspace.name
            )
        )
        self.assertEqual(response.status_code, 200)


class ReleaseWorkspaceDetailTest(TestCase):
    """Tests of the anvil_consortium_manager WorkspaceDetail view using the ReleaseWorkspaceAdapter."""

    def setUp(self):
        """Set up test class."""
        self.factory = RequestFactory()
        # Create a user with both view and edit permission.
        self.user = User.objects.create_user(username="test", password="test")
        self.user.user_permissions.add(
            Permission.objects.get(
                codename=acm_models.AnVILProjectManagerAccess.VIEW_PERMISSION_CODENAME
            )
        )
        self.object = factories.ReleaseWorkspaceFactory.create()

    def get_url(self, *args):
        """Get the url for the view being tested."""
        return reverse("anvil_consortium_manager:workspaces:detail", args=args)

    def test_status_code(self):
        """Response has a status code of 200."""
        upload_workspace = factories.UploadWorkspaceFactory.create()
        self.object.upload_workspaces.add(upload_workspace)
        self.client.force_login(self.user)
        response = self.client.get(
            self.get_url(
                self.object.workspace.billing_project.name, self.object.workspace.name
            )
        )
        self.assertEqual(response.status_code, 200)


class WorkspaceReportTest(TestCase):
    def setUp(self):
        """Set up test class."""
        self.factory = RequestFactory()
        # self.model_factory = factories.ResearchCenterFactory
        # Create a user with both view and edit permission.
        self.user = User.objects.create_user(username="test", password="test")
        self.user.user_permissions.add(
            Permission.objects.get(
                codename=acm_models.AnVILProjectManagerAccess.VIEW_PERMISSION_CODENAME
            )
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
        self.assertRedirects(
            response, resolve_url(settings.LOGIN_URL) + "?next=" + self.get_url()
        )

    def test_access_without_user_permission(self):
        """Raises permission denied if user has no permissions."""
        user_no_perms = User.objects.create_user(
            username="test-none", password="test-none"
        )
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
        acm_factories.WorkspaceGroupSharingFactory.create(
            workspace=upload_workspace.workspace, group=group
        )
        self.client.force_login(self.user)
        response = self.client.get(self.get_url())
        # workspace table
        self.assertIn("workspace_count_table", response.context_data)
        table = response.context_data["workspace_count_table"]
        self.assertEqual(len(table.data), 1)
        self.assertIn(
            {"workspace_type": "upload", "n_total": 1, "n_shared": 0}, table.data
        )

    def test_workspace_count_table_one_workspace_type_some_shared(self):
        """Workspace table includes correct values for one workspace type where only some workspaces are shared."""  # noqa: E501
        upload_workspace_1 = factories.UploadWorkspaceFactory.create()
        # Workspaces that won't be shared.
        factories.UploadWorkspaceFactory.create_batch(2)
        group = acm_factories.ManagedGroupFactory.create(name="GREGOR_ALL")
        acm_factories.WorkspaceGroupSharingFactory.create(
            workspace=upload_workspace_1.workspace, group=group
        )
        self.client.force_login(self.user)
        response = self.client.get(self.get_url())
        # workspace table
        self.assertIn("workspace_count_table", response.context_data)
        table = response.context_data["workspace_count_table"]
        self.assertEqual(len(table.data), 1)
        self.assertIn(
            {"workspace_type": "upload", "n_total": 3, "n_shared": 1}, table.data
        )

    def test_workspace_count_table_two_workspace_types_some_shared(self):
        """Workspace table includes correct values for one workspace type where only some workspaces are shared."""  # noqa: E501
        upload_workspace_1 = factories.UploadWorkspaceFactory.create()
        factories.UploadWorkspaceFactory.create_batch(2)
        example_workspace_1 = factories.ExampleWorkspaceFactory.create()
        example_workspace_2 = factories.ExampleWorkspaceFactory.create()
        factories.ExampleWorkspaceFactory.create_batch(3)
        group = acm_factories.ManagedGroupFactory.create(name="GREGOR_ALL")
        acm_factories.WorkspaceGroupSharingFactory.create(
            workspace=upload_workspace_1.workspace, group=group
        )
        acm_factories.WorkspaceGroupSharingFactory.create(
            workspace=example_workspace_1.workspace, group=group
        )
        acm_factories.WorkspaceGroupSharingFactory.create(
            workspace=example_workspace_2.workspace, group=group
        )
        self.client.force_login(self.user)
        response = self.client.get(self.get_url())
        # workspace table
        self.assertIn("workspace_count_table", response.context_data)
        table = response.context_data["workspace_count_table"]
        self.assertEqual(len(table.data), 2)
        self.assertIn(
            {"workspace_type": "upload", "n_total": 3, "n_shared": 1}, table.data
        )
        self.assertIn(
            {"workspace_type": "example", "n_total": 5, "n_shared": 2}, table.data
        )

    def test_workspace_count_table_one_workspace_shared_twice(self):
        """Workspace table includes correct values for one workspace  that has been shared twice."""  # noqa: E501
        upload_workspace_1 = factories.UploadWorkspaceFactory.create()
        # Create the sharing record with GREGOR_ALL.
        acm_factories.WorkspaceGroupSharingFactory.create(
            workspace=upload_workspace_1.workspace, group__name="GREGOR_ALL"
        )
        # Create a sharing record with another group.
        acm_factories.WorkspaceGroupSharingFactory.create(
            workspace=upload_workspace_1.workspace
        )
        self.client.force_login(self.user)
        response = self.client.get(self.get_url())
        # workspace table
        self.assertIn("workspace_count_table", response.context_data)
        table = response.context_data["workspace_count_table"]
        self.assertEqual(len(table.data), 1)
        self.assertIn(
            {"workspace_type": "upload", "n_total": 1, "n_shared": 1}, table.data
        )

    def test_has_no_workspace_when_shared_with_different_group_in_context(self):
        upload_workspace = factories.UploadWorkspaceFactory.create()
        group = acm_factories.ManagedGroupFactory.create(name="ANOTHER_GROUP")
        acm_factories.WorkspaceGroupSharingFactory.create(
            workspace=upload_workspace.workspace, group=group
        )
        self.client.force_login(self.user)
        response = self.client.get(self.get_url())
        table = response.context_data["workspace_count_table"]
        self.assertEqual(len(table.data), 1)
        self.assertIn(
            {"workspace_type": "upload", "n_total": 1, "n_shared": 0}, table.data
        )

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
        another_user = User.objects.create_user(
            username="another_user", password="another_user"
        )
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
        another_user = User.objects.create_user(
            username="another_user", password="another_user"
        )
        acm_factories.AccountFactory.create(user=another_user, verified=False)
        self.client.force_login(self.user)
        response = self.client.get(self.get_url())
        self.assertTrue("verified_linked_accounts" in response.context_data)
        self.assertEqual(response.context_data["verified_linked_accounts"], 1)
