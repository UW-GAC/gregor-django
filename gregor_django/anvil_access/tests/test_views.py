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

from .. import forms, models, views
from . import factories

# from .utils import AnVILAPIMockTestMixin

User = get_user_model()


class OverriddenURLsTest(TestCase):
    """Tests to check that specific URLs provided by anvil_consortium_manager are overriden with a 404 page."""

    def setUp(self):
        """Set up test class."""
        # Create a user with both view and edit permission.
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

    def test_workspace_create(self):
        """status code is 404 when accessing the workspace create url."""
        url = reverse("anvil:workspaces:new")
        self.client.force_login(self.user)
        response = self.client.get(url)
        self.assertEqual(response.status_code, 404)

    def test_workspace_delete(self):
        """status code is 404 when accessing the workspace delete url."""
        workspace = acm_factories.WorkspaceFactory.create()
        url = reverse("anvil:workspaces:delete", args=[workspace.pk])
        self.client.force_login(self.user)
        response = self.client.get(url)
        self.assertEqual(response.status_code, 404)


class ResearchCenterDetailTest(TestCase):
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
        return reverse("anvil_access:research_centers:detail", args=args)

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
        request = self.factory.get(self.get_url(obj.pk))
        request.user = self.user
        response = self.get_view()(request, pk=obj.pk)
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


class ResearchCenterListTest(TestCase):
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
        return reverse("anvil_access:research_centers:list")

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
        request = self.factory.get(self.get_url())
        request.user = self.user
        response = self.get_view()(request)
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


class ConsentGroupDetailTest(TestCase):
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
        return reverse("anvil_access:consent_groups:detail", args=args)

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
        request = self.factory.get(self.get_url(obj.pk))
        request.user = self.user
        response = self.get_view()(request, pk=obj.pk)
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
        return reverse("anvil_access:research_centers:list")

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
        request = self.factory.get(self.get_url())
        request.user = self.user
        response = self.get_view()(request)
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


class WorkspaceListTest(TestCase):
    def setUp(self):
        """Set up test class."""
        self.factory = RequestFactory()
        self.model_factory = factories.WorkspaceDataFactory
        # Create a user with both view and edit permission.
        self.user = User.objects.create_user(username="test", password="test")
        self.user.user_permissions.add(
            Permission.objects.get(
                codename=acm_models.AnVILProjectManagerAccess.VIEW_PERMISSION_CODENAME
            )
        )

    def get_url(self):
        """Get the url for the view being tested."""
        return reverse("anvil_access:workspaces:list")

    def get_view(self):
        """Return the view being tested."""
        return views.WorkspaceList.as_view()

    def test_view_redirect_not_logged_in(self):
        "View redirects to login view when user is not logged in."
        # Need a client for redirects.
        response = self.client.get(self.get_url())
        self.assertRedirects(
            response, resolve_url(settings.LOGIN_URL) + "?next=" + self.get_url()
        )

    def test_status_code_with_user_permission(self):
        """Returns successful response code."""
        request = self.factory.get(self.get_url())
        request.user = self.user
        response = self.get_view()(request)
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


class WorkspaceDataImportTest(AnVILAPIMockTestMixin, TestCase):
    """Tests for the `WorkspaceDataImport` view."""

    api_success_code = 200

    def setUp(self):
        """Set up test class."""
        # The superclass uses the responses package to mock API responses.
        super().setUp()
        self.factory = RequestFactory()
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

    def get_url(self, *args):
        """Get the url for the view being tested."""
        return reverse("anvil_access:workspaces:import", args=args)

    def get_api_url(self, billing_project_name, workspace_name):
        return (
            self.entry_point
            + "/api/workspaces/"
            + billing_project_name
            + "/"
            + workspace_name
        )

    def get_api_json_response(
        self, billing_project, workspace, authorization_domains=[], access="OWNER"
    ):
        """Return a pared down version of the json response from the AnVIL API with only fields we need."""
        json_data = {
            "accessLevel": access,
            "owners": [],
            "workspace": {
                "authorizationDomain": [
                    {"membersGroupName": x} for x in authorization_domains
                ],
                "name": workspace,
                "namespace": billing_project,
            },
        }
        return json_data

    def get_view(self):
        """Return the view being tested."""
        return views.WorkspaceDataImport.as_view()

    def test_view_redirect_not_logged_in(self):
        "View redirects to login view when user is not logged in."
        # Need a client for redirects.
        response = self.client.get(self.get_url())
        self.assertRedirects(
            response, resolve_url(settings.LOGIN_URL) + "?next=" + self.get_url()
        )

    def test_status_code_with_user_permission(self):
        """Returns successful response code."""
        workspace_list_url = self.entry_point + "/api/workspaces"
        responses.add(
            responses.GET,
            workspace_list_url,
            match=[
                responses.matchers.query_param_matcher(
                    {"fields": "workspace.namespace,workspace.name,accessLevel"}
                )
            ],
            status=200,
            json=[],
        )
        self.client.force_login(self.user)
        response = self.client.get(self.get_url())
        self.assertEqual(response.status_code, 200)

    def test_access_with_view_permission(self):
        """Raises permission denied if user has only view permission."""
        user_with_view_perm = User.objects.create_user(
            username="test-other", password="test-other"
        )
        user_with_view_perm.user_permissions.add(
            Permission.objects.get(
                codename=acm_models.AnVILProjectManagerAccess.VIEW_PERMISSION_CODENAME
            )
        )
        request = self.factory.get(self.get_url())
        request.user = user_with_view_perm
        with self.assertRaises(PermissionDenied):
            self.get_view()(request)

    def test_access_without_user_permission(self):
        """Raises permission denied if user has no permissions."""
        user_no_perms = User.objects.create_user(
            username="test-none", password="test-none"
        )
        request = self.factory.get(self.get_url())
        request.user = user_no_perms
        with self.assertRaises(PermissionDenied):
            self.get_view()(request)

    def test_has_form_in_context(self):
        """Response includes a form."""
        billing_project_name = "test-billing-project"
        workspace_name = "test-workspace"
        workspace_list_url = self.entry_point + "/api/workspaces"
        responses.add(
            responses.GET,
            workspace_list_url,
            match=[
                responses.matchers.query_param_matcher(
                    {"fields": "workspace.namespace,workspace.name,accessLevel"}
                )
            ],
            status=200,
            json=[self.get_api_json_response(billing_project_name, workspace_name)],
        )
        request = self.factory.get(self.get_url())
        request.user = self.user
        response = self.get_view()(request)
        self.assertTrue("form" in response.context_data)
        self.assertIsInstance(
            response.context_data["form"], forms.WorkspaceDataImportForm
        )

    def test_form_choices_no_available_workspaces(self):
        """Choices are populated correctly with one available workspace."""
        workspace_list_url = self.entry_point + "/api/workspaces"
        responses.add(
            responses.GET,
            workspace_list_url,
            match=[
                responses.matchers.query_param_matcher(
                    {"fields": "workspace.namespace,workspace.name,accessLevel"}
                )
            ],
            status=200,
            json=[],
        )
        self.client.force_login(self.user)
        response = self.client.get(self.get_url())
        # Choices are populated correctly.
        workspace_choices = response.context_data["form"].fields["workspace"].choices
        self.assertEqual(len(workspace_choices), 1)
        # The first choice is the empty string.
        self.assertEqual("", workspace_choices[0][0])
        # A message is shown.
        self.assertIn("messages", response.context)
        messages = list(response.context["messages"])
        self.assertEqual(len(messages), 1)
        self.assertEqual(
            views.WorkspaceDataImport.message_no_available_workspaces, str(messages[0])
        )

    def test_form_choices_one_available_workspace(self):
        """Choices are populated correctly with one available workspace."""
        workspace_list_url = self.entry_point + "/api/workspaces"
        responses.add(
            responses.GET,
            workspace_list_url,
            match=[
                responses.matchers.query_param_matcher(
                    {"fields": "workspace.namespace,workspace.name,accessLevel"}
                )
            ],
            status=200,
            json=[self.get_api_json_response("bp-1", "ws-1")],
        )
        request = self.factory.get(self.get_url())
        request.user = self.user
        response = self.get_view()(request)
        # Choices are populated correctly.
        workspace_choices = response.context_data["form"].fields["workspace"].choices
        self.assertEqual(len(workspace_choices), 2)
        # The first choice is the empty string.
        self.assertEqual("", workspace_choices[0][0])
        # Second choice is the workspace.
        self.assertTrue(("bp-1/ws-1", "bp-1/ws-1") in workspace_choices)

    def test_form_choices_two_available_workspaces(self):
        """Choices are populated correctly with two available workspaces."""
        workspace_list_url = self.entry_point + "/api/workspaces"
        responses.add(
            responses.GET,
            workspace_list_url,
            match=[
                responses.matchers.query_param_matcher(
                    {"fields": "workspace.namespace,workspace.name,accessLevel"}
                )
            ],
            status=200,
            json=[
                self.get_api_json_response("bp-1", "ws-1"),
                self.get_api_json_response("bp-2", "ws-2"),
            ],
        )
        request = self.factory.get(self.get_url())
        request.user = self.user
        response = self.get_view()(request)
        # Choices are populated correctly.
        workspace_choices = response.context_data["form"].fields["workspace"].choices
        self.assertEqual(len(workspace_choices), 3)
        # The first choice is the empty string.
        self.assertEqual("", workspace_choices[0][0])
        # The next choices are the workspaces.
        self.assertTrue(("bp-1/ws-1", "bp-1/ws-1") in workspace_choices)
        self.assertTrue(("bp-2/ws-2", "bp-2/ws-2") in workspace_choices)

    def test_form_does_not_show_already_imported_workspaces(self):
        """The form does not show workspaces that have already been imported in the choices."""
        acm_factories.WorkspaceFactory.create(
            billing_project__name="bp", name="ws-imported"
        )
        workspace_list_url = self.entry_point + "/api/workspaces"
        responses.add(
            responses.GET,
            workspace_list_url,
            match=[
                responses.matchers.query_param_matcher(
                    {"fields": "workspace.namespace,workspace.name,accessLevel"}
                )
            ],
            status=200,
            json=[
                self.get_api_json_response("bp", "ws-imported", access="OWNER"),
            ],
        )
        self.client.force_login(self.user)
        response = self.client.get(self.get_url())
        self.assertTrue("form" in response.context_data)
        form_choices = response.context_data["form"].fields["workspace"].choices
        # Choices are populated.
        self.assertEqual(len(form_choices), 1)
        self.assertFalse(("bp/ws-imported", "bp/ws-imported") in form_choices)
        # A message is shown.
        self.assertIn("messages", response.context)
        messages = list(response.context["messages"])
        self.assertEqual(len(messages), 1)
        self.assertEqual(
            views.WorkspaceDataImport.message_no_available_workspaces, str(messages[0])
        )

    def test_form_does_not_show_workspaces_not_owner(self):
        """The form does not show workspaces where we aren't owners in the choices."""
        workspace_list_url = self.entry_point + "/api/workspaces"
        responses.add(
            responses.GET,
            workspace_list_url,
            match=[
                responses.matchers.query_param_matcher(
                    {"fields": "workspace.namespace,workspace.name,accessLevel"}
                )
            ],
            status=200,
            json=[
                self.get_api_json_response("bp", "ws-owner", access="OWNER"),
                self.get_api_json_response("bp", "ws-reader", access="READER"),
            ],
        )
        request = self.factory.get(self.get_url())
        request.user = self.user
        response = self.get_view()(request)
        self.assertTrue("form" in response.context_data)
        form_choices = response.context_data["form"].fields["workspace"].choices
        # Choices are populated.
        self.assertEqual(len(form_choices), 2)
        self.assertTrue(("bp/ws-owner", "bp/ws-owner") in form_choices)
        self.assertFalse(("bp/ws-reader", "bp/ws-reader") in form_choices)

    def test_can_import_workspace_and_billing_project_as_user(self):
        """Can import a workspace from AnVIL when the billing project does not exist in Django and we are users."""
        research_center = factories.ResearchCenterFactory.create()
        consent_group = factories.ConsentGroupFactory.create()
        version = 1
        billing_project_name = "billing-project"
        workspace_name = "workspace"
        # Available workspaces API call.
        workspace_list_url = self.entry_point + "/api/workspaces"
        responses.add(
            responses.GET,
            workspace_list_url,
            match=[
                responses.matchers.query_param_matcher(
                    {"fields": "workspace.namespace,workspace.name,accessLevel"}
                )
            ],
            status=200,
            json=[self.get_api_json_response(billing_project_name, workspace_name)],
        )
        # Billing project API call.
        billing_project_url = (
            self.entry_point + "/api/billing/v2/" + billing_project_name
        )
        responses.add(responses.GET, billing_project_url, status=200)
        url = self.get_api_url(billing_project_name, workspace_name)
        responses.add(
            responses.GET,
            url,
            status=self.api_success_code,
            json=self.get_api_json_response(billing_project_name, workspace_name),
        )
        self.client.force_login(self.user)
        response = self.client.post(
            self.get_url(),
            {
                "workspace": billing_project_name + "/" + workspace_name,
                "research_center": research_center.pk,
                "consent_group": consent_group.pk,
                "version": version,
            },
        )
        self.assertEqual(response.status_code, 302)
        # Created a billing project.
        self.assertEqual(acm_models.BillingProject.objects.count(), 1)
        new_billing_project = acm_models.BillingProject.objects.latest("pk")
        self.assertEqual(new_billing_project.name, billing_project_name)
        self.assertEqual(new_billing_project.has_app_as_user, True)
        # Created a workspace.
        self.assertEqual(acm_models.Workspace.objects.count(), 1)
        new_workspace = acm_models.Workspace.objects.latest("pk")
        self.assertEqual(new_workspace.name, workspace_name)
        responses.assert_call_count(billing_project_url, 1)
        responses.assert_call_count(url, 1)
        # Created a WorkspaceData instance.
        self.assertEqual(models.WorkspaceData.objects.count(), 1)
        self.assertEqual(new_workspace.workspacedata.research_center, research_center)
        self.assertEqual(new_workspace.workspacedata.consent_group, consent_group)
        self.assertEqual(new_workspace.workspacedata.version, version)

    def test_success_message(self):
        """Can import a workspace from AnVIL when the billing project does not exist in Django and we are users."""
        research_center = factories.ResearchCenterFactory.create()
        consent_group = factories.ConsentGroupFactory.create()
        billing_project_name = "billing-project"
        workspace_name = "workspace"
        # Available workspaces API call.
        workspace_list_url = self.entry_point + "/api/workspaces"
        responses.add(
            responses.GET,
            workspace_list_url,
            match=[
                responses.matchers.query_param_matcher(
                    {"fields": "workspace.namespace,workspace.name,accessLevel"}
                )
            ],
            status=200,
            json=[self.get_api_json_response(billing_project_name, workspace_name)],
        )
        # Billing project API call.
        billing_project_url = (
            self.entry_point + "/api/billing/v2/" + billing_project_name
        )
        responses.add(responses.GET, billing_project_url, status=200)
        url = self.get_api_url(billing_project_name, workspace_name)
        responses.add(
            responses.GET,
            url,
            status=self.api_success_code,
            json=self.get_api_json_response(billing_project_name, workspace_name),
        )
        self.client.force_login(self.user)
        response = self.client.post(
            self.get_url(),
            {
                "workspace": billing_project_name + "/" + workspace_name,
                "research_center": research_center.pk,
                "consent_group": consent_group.pk,
                "version": 1,
            },
            follow=True,
        )
        self.assertIn("messages", response.context)
        messages = list(response.context["messages"])
        self.assertEqual(len(messages), 1)
        self.assertEqual(views.WorkspaceDataImport.success_msg, str(messages[0]))

    def test_can_import_workspace_and_billing_project_as_not_user(self):
        """Can import a workspace from AnVIL when the billing project does not exist in Django and we are not users."""
        research_center = factories.ResearchCenterFactory.create()
        consent_group = factories.ConsentGroupFactory.create()
        billing_project_name = "billing-project"
        workspace_name = "workspace"
        # Available workspaces API call.
        workspace_list_url = self.entry_point + "/api/workspaces"
        responses.add(
            responses.GET,
            workspace_list_url,
            match=[
                responses.matchers.query_param_matcher(
                    {"fields": "workspace.namespace,workspace.name,accessLevel"}
                )
            ],
            status=200,
            json=[self.get_api_json_response(billing_project_name, workspace_name)],
        )
        # Billing project API call.
        billing_project_url = (
            self.entry_point + "/api/billing/v2/" + billing_project_name
        )
        responses.add(
            responses.GET, billing_project_url, status=404, json={"message": "other"}
        )
        url = self.get_api_url(billing_project_name, workspace_name)
        responses.add(
            responses.GET,
            url,
            status=self.api_success_code,
            json=self.get_api_json_response(billing_project_name, workspace_name),
        )
        self.client.force_login(self.user)
        response = self.client.post(
            self.get_url(),
            {
                "workspace": billing_project_name + "/" + workspace_name,
                "research_center": research_center.pk,
                "consent_group": consent_group.pk,
                "version": 1,
            },
        )
        self.assertEqual(response.status_code, 302)
        # Created a billing project.
        self.assertEqual(acm_models.BillingProject.objects.count(), 1)
        new_billing_project = acm_models.BillingProject.objects.latest("pk")
        self.assertEqual(new_billing_project.name, billing_project_name)
        self.assertEqual(new_billing_project.has_app_as_user, False)
        # Created a workspace.
        self.assertEqual(acm_models.Workspace.objects.count(), 1)
        new_workspace = acm_models.Workspace.objects.latest("pk")
        self.assertEqual(new_workspace.name, workspace_name)
        responses.assert_call_count(billing_project_url, 1)
        responses.assert_call_count(url, 1)
        # Created a WorkspaceData instance.
        self.assertEqual(models.WorkspaceData.objects.count(), 1)
        self.assertEqual(new_workspace.workspacedata.research_center, research_center)
        self.assertEqual(new_workspace.workspacedata.consent_group, consent_group)
        self.assertEqual(new_workspace.workspacedata.version, 1)

    def test_can_import_workspace_with_existing_billing_project(self):
        """Can import a workspace from AnVIL when the billing project exists in Django."""
        research_center = factories.ResearchCenterFactory.create()
        consent_group = factories.ConsentGroupFactory.create()
        billing_project = acm_factories.BillingProjectFactory.create(
            name="billing-project"
        )
        workspace_name = "workspace"
        # Available workspaces API call.
        workspace_list_url = self.entry_point + "/api/workspaces"
        responses.add(
            responses.GET,
            workspace_list_url,
            match=[
                responses.matchers.query_param_matcher(
                    {"fields": "workspace.namespace,workspace.name,accessLevel"}
                )
            ],
            status=200,
            json=[self.get_api_json_response(billing_project.name, workspace_name)],
        )
        url = self.get_api_url(billing_project.name, workspace_name)
        responses.add(
            responses.GET,
            url,
            status=self.api_success_code,
            json=self.get_api_json_response(billing_project.name, workspace_name),
        )
        self.client.force_login(self.user)
        response = self.client.post(
            self.get_url(),
            {
                "workspace": billing_project.name + "/" + workspace_name,
                "research_center": research_center.pk,
                "consent_group": consent_group.pk,
                "version": 1,
            },
        )
        self.assertEqual(response.status_code, 302)
        # Created a workspace.
        self.assertEqual(acm_models.Workspace.objects.count(), 1)
        new_workspace = acm_models.Workspace.objects.latest("pk")
        self.assertEqual(new_workspace.name, workspace_name)
        responses.assert_call_count(url, 1)
        # History is added for the workspace.
        self.assertEqual(new_workspace.history.count(), 1)
        self.assertEqual(new_workspace.history.latest().history_type, "+")
        # BillingProject is *not* updated.
        self.assertEqual(billing_project.history.count(), 1)
        self.assertEqual(billing_project.history.latest().history_type, "+")
        # Created a WorkspaceData instance.
        self.assertEqual(models.WorkspaceData.objects.count(), 1)
        self.assertEqual(new_workspace.workspacedata.research_center, research_center)
        self.assertEqual(new_workspace.workspacedata.consent_group, consent_group)
        self.assertEqual(new_workspace.workspacedata.version, 1)

    def test_can_import_workspace_with_auth_domain_in_app(self):
        """Can import a workspace with an auth domain that is already in the app."""
        research_center = factories.ResearchCenterFactory.create()
        consent_group = factories.ConsentGroupFactory.create()
        billing_project = acm_factories.BillingProjectFactory.create(
            name="billing-project"
        )
        workspace_name = "workspace"
        auth_domain = acm_factories.ManagedGroupFactory.create(name="auth-domain")
        # Available workspaces API call.
        workspace_json = self.get_api_json_response(
            billing_project.name,
            workspace_name,
            authorization_domains=[auth_domain.name],
        )
        workspace_list_url = self.entry_point + "/api/workspaces"
        responses.add(
            responses.GET,
            workspace_list_url,
            match=[
                responses.matchers.query_param_matcher(
                    {"fields": "workspace.namespace,workspace.name,accessLevel"}
                )
            ],
            status=200,
            # Assume that this is the only workspace we can see on AnVIL.
            json=[workspace_json],
        )
        url = self.get_api_url(billing_project.name, workspace_name)
        responses.add(
            responses.GET,
            url,
            status=self.api_success_code,
            json=workspace_json,
        )
        self.client.force_login(self.user)
        response = self.client.post(
            self.get_url(),
            {
                "workspace": billing_project.name + "/" + workspace_name,
                "research_center": research_center.pk,
                "consent_group": consent_group.pk,
                "version": 1,
            },
        )
        self.assertEqual(response.status_code, 302)
        # Created a workspace.
        self.assertEqual(acm_models.Workspace.objects.count(), 1)
        new_workspace = acm_models.Workspace.objects.latest("pk")
        self.assertEqual(new_workspace.name, workspace_name)
        responses.assert_call_count(url, 1)
        # History is added for the workspace.
        self.assertEqual(new_workspace.history.count(), 1)
        self.assertEqual(new_workspace.history.latest().history_type, "+")
        # History is added for the authorization domain.
        self.assertEqual(acm_models.WorkspaceAuthorizationDomain.history.count(), 1)
        self.assertEqual(
            acm_models.WorkspaceAuthorizationDomain.history.latest().history_type, "+"
        )
        # Created a WorkspaceData instance.
        self.assertEqual(models.WorkspaceData.objects.count(), 1)
        self.assertEqual(new_workspace.workspacedata.research_center, research_center)
        self.assertEqual(new_workspace.workspacedata.consent_group, consent_group)
        self.assertEqual(new_workspace.workspacedata.version, 1)

    def test_can_import_workspace_with_auth_domain_not_in_app(self):
        """Can import a workspace with an auth domain that is not already in the app."""
        research_center = factories.ResearchCenterFactory.create()
        consent_group = factories.ConsentGroupFactory.create()
        billing_project = acm_factories.BillingProjectFactory.create(
            name="billing-project"
        )
        workspace_name = "workspace"
        auth_domain_name = "auth-group"
        # Available workspaces API call.
        workspace_list_url = self.entry_point + "/api/workspaces"
        responses.add(
            responses.GET,
            workspace_list_url,
            match=[
                responses.matchers.query_param_matcher(
                    {"fields": "workspace.namespace,workspace.name,accessLevel"}
                )
            ],
            status=200,
            json=[
                self.get_api_json_response(
                    billing_project.name,
                    workspace_name,
                    authorization_domains=[auth_domain_name],
                )
            ],
        )
        url = self.get_api_url(billing_project.name, workspace_name)
        responses.add(
            responses.GET,
            url,
            status=self.api_success_code,
            json=self.get_api_json_response(
                billing_project.name,
                workspace_name,
                authorization_domains=[auth_domain_name],
            ),
        )
        # Add Response for the auth domain group.
        group_url = self.entry_point + "/api/groups"
        responses.add(
            responses.GET,
            group_url,
            status=200,
            # Assume we are not members since we didn't create the group ourselves.
            json=[
                {
                    "groupEmail": auth_domain_name + "@firecloud.org",
                    "groupName": auth_domain_name,
                    "role": "Member",
                }
            ],
        )
        self.client.force_login(self.user)
        response = self.client.post(
            self.get_url(),
            {
                "workspace": billing_project.name + "/" + workspace_name,
                "research_center": research_center.pk,
                "consent_group": consent_group.pk,
                "version": 1,
            },
        )
        self.assertEqual(response.status_code, 302)
        # Created a workspace.
        self.assertEqual(acm_models.Workspace.objects.count(), 1)
        new_workspace = acm_models.Workspace.objects.latest("pk")
        self.assertEqual(new_workspace.name, workspace_name)
        responses.assert_call_count(url, 1)
        # History is added for the workspace.
        self.assertEqual(new_workspace.history.count(), 1)
        self.assertEqual(new_workspace.history.latest().history_type, "+")
        # An authorization domain group was created.
        self.assertEqual(acm_models.ManagedGroup.objects.count(), 1)
        group = acm_models.ManagedGroup.objects.latest()
        self.assertEqual(group.name, auth_domain_name)
        # The workspace authorization domain relationship was created.
        auth_domain = acm_models.WorkspaceAuthorizationDomain.objects.latest("pk")
        self.assertEqual(auth_domain.workspace, new_workspace)
        self.assertEqual(auth_domain.group, group)
        self.assertEqual(auth_domain.history.count(), 1)
        self.assertEqual(auth_domain.history.latest().history_type, "+")
        # Created a WorkspaceData instance.
        self.assertEqual(models.WorkspaceData.objects.count(), 1)
        self.assertEqual(new_workspace.workspacedata.research_center, research_center)
        self.assertEqual(new_workspace.workspacedata.consent_group, consent_group)
        self.assertEqual(new_workspace.workspacedata.version, 1)

    def test_redirects_to_new_object_detail(self):
        """After successfully creating an object, view redirects to the object's detail page."""
        # This needs to use the client because the RequestFactory doesn't handle redirects.
        research_center = factories.ResearchCenterFactory.create()
        consent_group = factories.ConsentGroupFactory.create()
        billing_project = acm_factories.BillingProjectFactory.create(
            name="billing-project"
        )
        workspace_name = "workspace"
        # Available workspaces API call.
        workspace_list_url = self.entry_point + "/api/workspaces"
        responses.add(
            responses.GET,
            workspace_list_url,
            match=[
                responses.matchers.query_param_matcher(
                    {"fields": "workspace.namespace,workspace.name,accessLevel"}
                )
            ],
            status=200,
            json=[self.get_api_json_response(billing_project.name, workspace_name)],
        )
        url = self.get_api_url(billing_project.name, workspace_name)
        responses.add(
            responses.GET,
            url,
            status=self.api_success_code,
            json=self.get_api_json_response(billing_project.name, workspace_name),
        )
        self.client.force_login(self.user)
        response = self.client.post(
            self.get_url(),
            {
                "workspace": billing_project.name + "/" + workspace_name,
                "research_center": research_center.pk,
                "consent_group": consent_group.pk,
                "version": 1,
            },
        )
        new_object = acm_models.Workspace.objects.latest("pk")
        self.assertRedirects(response, new_object.workspacedata.get_absolute_url())
        responses.assert_call_count(url, 1)

    def test_workspace_already_imported_without_workspace_data(self):
        """Does not import a workspace that already exists in Django even if WorkspaceData does not exist."""
        research_center = factories.ResearchCenterFactory.create()
        consent_group = factories.ConsentGroupFactory.create()
        workspace = acm_factories.WorkspaceFactory.create()
        # Available workspaces API call.
        workspace_list_url = self.entry_point + "/api/workspaces"
        responses.add(
            responses.GET,
            workspace_list_url,
            match=[
                responses.matchers.query_param_matcher(
                    {"fields": "workspace.namespace,workspace.name,accessLevel"}
                )
            ],
            status=200,
            json=[
                self.get_api_json_response(
                    workspace.billing_project.name, workspace.name
                )
            ],
        )
        # Messages need the client.
        self.client.force_login(self.user)
        response = self.client.post(
            self.get_url(),
            {
                "workspace": workspace.billing_project.name + "/" + workspace.name,
                "research_center": research_center.pk,
                "consent_group": consent_group.pk,
                "version": 1,
            },
        )
        self.assertEqual(response.status_code, 200)
        form = response.context_data["form"]
        self.assertFalse(form.is_valid())
        self.assertIn("workspace", form.errors.keys())
        self.assertIn("valid", form.errors["workspace"][0])
        # Did not create any new BillingProjects.
        self.assertEqual(acm_models.BillingProject.objects.count(), 1)
        # Did not create eany new Workspaces.
        self.assertEqual(acm_models.Workspace.objects.count(), 1)
        # Did not create any new WorkspaceDatas.
        self.assertEqual(models.WorkspaceData.objects.count(), 0)

    def test_workspace_already_imported_with_workspace_data(self):
        """Does not import WorkspaceData that already exists in Django."""
        workspace_data = factories.WorkspaceDataFactory.create()
        # Available workspaces API call.
        workspace_list_url = self.entry_point + "/api/workspaces"
        responses.add(
            responses.GET,
            workspace_list_url,
            match=[
                responses.matchers.query_param_matcher(
                    {"fields": "workspace.namespace,workspace.name,accessLevel"}
                )
            ],
            status=200,
            json=[
                self.get_api_json_response(
                    workspace_data.workspace.billing_project.name,
                    workspace_data.workspace.name,
                )
            ],
        )
        # Messages need the client.
        self.client.force_login(self.user)
        response = self.client.post(
            self.get_url(),
            {
                "workspace": workspace_data.workspace.billing_project.name
                + "/"
                + workspace_data.workspace.name,
                "research_center": workspace_data.research_center.pk,
                "consent_group": workspace_data.consent_group.pk,
                "version": workspace_data.version,
            },
        )
        self.assertEqual(response.status_code, 200)
        form = response.context_data["form"]
        self.assertFalse(form.is_valid())
        self.assertIn("workspace", form.errors.keys())
        self.assertIn("valid", form.errors["workspace"][0])
        self.assertEqual(len(form.non_field_errors()), 1)
        self.assertIn("already exists", form.non_field_errors()[0])
        # Did not create any new BillingProjects.
        self.assertEqual(acm_models.BillingProject.objects.count(), 1)
        # Did not create eany new Workspaces.
        self.assertEqual(acm_models.Workspace.objects.count(), 1)
        # Did not create eany new WorkspaceDatas.
        self.assertEqual(models.WorkspaceData.objects.count(), 1)

    def test_invalid_workspace_name(self):
        """Does not create an object if workspace name is invalid."""
        research_center = factories.ResearchCenterFactory.create()
        consent_group = factories.ConsentGroupFactory.create()
        # Available workspaces API call.
        workspace_list_url = self.entry_point + "/api/workspaces"
        responses.add(
            responses.GET,
            workspace_list_url,
            match=[
                responses.matchers.query_param_matcher(
                    {"fields": "workspace.namespace,workspace.name,accessLevel"}
                )
            ],
            status=200,
            json=[self.get_api_json_response("foo", "bar")],
        )
        # No API call.
        request = self.factory.post(
            self.get_url(),
            {
                "workspace": "billing-project/workspace name",
                "research_center": research_center.pk,
                "consent_group": consent_group.pk,
                "version": 1,
            },
        )
        request.user = self.user
        response = self.get_view()(request)
        self.assertEqual(response.status_code, 200)
        self.assertIn("form", response.context_data)
        form = response.context_data["form"]
        self.assertFalse(form.is_valid())
        self.assertIn("workspace", form.errors.keys())
        self.assertIn("valid", form.errors["workspace"][0])
        # Did not create any objects.
        self.assertEqual(acm_models.BillingProject.objects.count(), 0)
        self.assertEqual(acm_models.Workspace.objects.count(), 0)
        self.assertEqual(models.WorkspaceData.objects.count(), 0)

    def test_post_blank_data(self):
        """Posting blank data does not create an object."""
        # Available workspaces API call.
        workspace_list_url = self.entry_point + "/api/workspaces"
        responses.add(
            responses.GET,
            workspace_list_url,
            match=[
                responses.matchers.query_param_matcher(
                    {"fields": "workspace.namespace,workspace.name,accessLevel"}
                )
            ],
            status=200,
            json=[self.get_api_json_response("foo", "bar")],
        )
        request = self.factory.post(self.get_url(), {})
        request.user = self.user
        response = self.get_view()(request)
        self.assertEqual(response.status_code, 200)
        form = response.context_data["form"]
        self.assertFalse(form.is_valid())
        self.assertIn("workspace", form.errors.keys())
        self.assertIn("required", form.errors["workspace"][0])
        self.assertIn("research_center", form.errors.keys())
        self.assertIn("required", form.errors["research_center"][0])
        self.assertIn("consent_group", form.errors.keys())
        self.assertIn("required", form.errors["consent_group"][0])
        self.assertIn("version", form.errors.keys())
        self.assertIn("required", form.errors["version"][0])
        self.assertEqual(models.WorkspaceData.objects.count(), 0)
        self.assertEqual(len(responses.calls), 1)  # just the workspace list.

    def test_other_anvil_api_error(self):
        research_center = factories.ResearchCenterFactory.create()
        consent_group = factories.ConsentGroupFactory.create()
        billing_project_name = "billing-project"
        workspace_name = "workspace"
        # Available workspaces API call.
        workspace_list_url = self.entry_point + "/api/workspaces"
        responses.add(
            responses.GET,
            workspace_list_url,
            match=[
                responses.matchers.query_param_matcher(
                    {"fields": "workspace.namespace,workspace.name,accessLevel"}
                )
            ],
            status=200,
            json=[self.get_api_json_response(billing_project_name, workspace_name)],
        )
        # Available workspaces API call.
        workspace_list_url = self.entry_point + "/api/workspaces"
        responses.add(
            responses.GET,
            workspace_list_url,
            match=[
                responses.matchers.query_param_matcher(
                    {"fields": "workspace.namespace,workspace.name,accessLevel"}
                )
            ],
            status=200,
            json=[self.get_api_json_response(billing_project_name, workspace_name)],
        )
        url = self.get_api_url(billing_project_name, workspace_name)
        responses.add(
            responses.GET,
            self.get_api_url(billing_project_name, workspace_name),
            status=500,
            json={"message": "an error"},
        )
        self.client.force_login(self.user)
        response = self.client.post(
            self.get_url(),
            {
                "workspace": billing_project_name + "/" + workspace_name,
                "research_center": research_center.pk,
                "consent_group": consent_group.pk,
                "version": 1,
            },
        )
        self.assertEqual(response.status_code, 200)
        form = response.context_data["form"]
        # The form is valid but there was a different error. Is this really what we want?
        self.assertTrue(form.is_valid())
        # Check messages.
        self.assertIn("messages", response.context)
        messages = list(response.context["messages"])
        self.assertEqual(len(messages), 1)
        self.assertEqual("AnVIL API Error: an error", str(messages[0]))
        # Did not create any objects.
        self.assertEqual(models.WorkspaceData.objects.count(), 0)
        responses.assert_call_count(url, 1)

    def test_anvil_api_error_workspace_list_get(self):
        # Available workspaces API call.
        responses.add(
            responses.GET,
            self.entry_point + "/api/workspaces",
            match=[
                responses.matchers.query_param_matcher(
                    {"fields": "workspace.namespace,workspace.name,accessLevel"}
                )
            ],
            status=500,
            json={"message": "an error"},
        )
        self.client.force_login(self.user)
        response = self.client.get(self.get_url())
        self.assertEqual(response.status_code, 200)
        self.assertIn("form", response.context_data)
        # Check messages.
        self.assertIn("messages", response.context)
        messages = list(response.context["messages"])
        self.assertEqual(len(messages), 1)
        self.assertEqual(
            views.WorkspaceDataImport.message_error_fetching_workspaces,
            str(messages[0]),
        )
        # Did not create any objects.
        self.assertEqual(models.WorkspaceData.objects.count(), 0)

    def test_anvil_api_error_workspace_list_post(self):
        research_center = factories.ResearchCenterFactory.create()
        consent_group = factories.ConsentGroupFactory.create()
        # Available workspaces API call.
        responses.add(
            responses.GET,
            self.entry_point + "/api/workspaces",
            match=[
                responses.matchers.query_param_matcher(
                    {"fields": "workspace.namespace,workspace.name,accessLevel"}
                )
            ],
            status=500,
            json={"message": "an error"},
        )
        self.client.force_login(self.user)
        response = self.client.post(
            self.get_url(),
            {
                "workspace": "billing-project/workspace",
                "research_center": research_center.pk,
                "consent_group": consent_group.pk,
                "version": 1,
            },
        )
        self.assertEqual(response.status_code, 200)
        form = response.context_data["form"]
        # The form is not valid because workspaces couldn't be fetched.
        self.assertFalse(form.is_valid())
        # Check messages.
        self.assertIn("messages", response.context)
        messages = list(response.context["messages"])
        self.assertEqual(len(messages), 1)
        self.assertEqual(
            views.WorkspaceDataImport.message_error_fetching_workspaces,
            str(messages[0]),
        )
        # Did not create any objects.
        self.assertEqual(models.WorkspaceData.objects.count(), 0)
