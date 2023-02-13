"""Test forms for the gregor_anvil app."""

from anvil_consortium_manager.tests.factories import WorkspaceFactory
from django.test import TestCase

from .. import forms
from . import factories


class UploadWorkspaceFormTest(TestCase):
    """Tests for the UploadWorkspace class."""

    form_class = forms.UploadWorkspaceForm

    def setUp(self):
        """Create a workspace for use in the form."""
        self.workspace = WorkspaceFactory()

    def test_valid(self):
        """Form is valid with necessary input."""
        research_center = factories.ResearchCenterFactory()
        consent_group = factories.ConsentGroupFactory()
        form_data = {
            "research_center": research_center,
            "consent_group": consent_group,
            "version": 1,
            "workspace": self.workspace,
        }
        form = self.form_class(data=form_data)
        self.assertTrue(form.is_valid())

    def test_invalid_missing_research_center(self):
        """Form is invalid when missing research_center."""
        consent_group = factories.ConsentGroupFactory()
        form_data = {
            "consent_group": consent_group,
            "version": 1,
            "workspace": self.workspace,
        }
        form = self.form_class(data=form_data)
        self.assertFalse(form.is_valid())
        self.assertEqual(len(form.errors), 1)
        self.assertIn("research_center", form.errors)
        self.assertEqual(len(form.errors["research_center"]), 1)
        self.assertIn("required", form.errors["research_center"][0])

    def test_invalid_missing_consent_group(self):
        """Form is invalid when missing consent_group."""
        research_center = factories.ResearchCenterFactory()
        form_data = {
            "research_center": research_center,
            "version": 1,
            "workspace": self.workspace,
        }
        form = self.form_class(data=form_data)
        self.assertFalse(form.is_valid())
        self.assertEqual(len(form.errors), 1)
        self.assertIn("consent_group", form.errors)
        self.assertEqual(len(form.errors["consent_group"]), 1)
        self.assertIn("required", form.errors["consent_group"][0])

    def test_invalid_missing_version(self):
        """Form is invalid when missing research_center."""
        research_center = factories.ResearchCenterFactory()
        consent_group = factories.ConsentGroupFactory()
        form_data = {
            "research_center": research_center,
            "consent_group": consent_group,
            "workspace": self.workspace,
        }
        form = self.form_class(data=form_data)
        self.assertFalse(form.is_valid())
        self.assertEqual(len(form.errors), 1)
        self.assertIn("version", form.errors)
        self.assertEqual(len(form.errors["version"]), 1)
        self.assertIn("required", form.errors["version"][0])

    def test_invalid_missing_workspace(self):
        """Form is invalid when missing research_center."""
        research_center = factories.ResearchCenterFactory()
        consent_group = factories.ConsentGroupFactory()
        form_data = {
            "research_center": research_center,
            "consent_group": consent_group,
            "version": 1,
        }
        form = self.form_class(data=form_data)
        self.assertFalse(form.is_valid())
        self.assertEqual(len(form.errors), 1)
        self.assertIn("workspace", form.errors)
        self.assertEqual(len(form.errors["workspace"]), 1)
        self.assertIn("required", form.errors["workspace"][0])

    def test_invalid_duplicate_object(self):
        """Form is invalid with a duplicated object."""
        upload_workspace = factories.UploadWorkspaceFactory.create()
        form_data = {
            "research_center": upload_workspace.research_center,
            "consent_group": upload_workspace.consent_group,
            "version": upload_workspace.version,
            "workspace": self.workspace,
        }
        form = self.form_class(data=form_data)
        self.assertFalse(form.is_valid())
        non_field_errors = form.non_field_errors()
        self.assertEqual(len(non_field_errors), 1)
        self.assertIn("already exists", non_field_errors[0])


class ExampleWorkspaceFormTest(TestCase):

    form_class = forms.ExampleWorkspaceForm

    def setUp(self):
        """Create a workspace for use in the form."""
        self.workspace = WorkspaceFactory.create()

    def test_valid(self):
        """Form is valid with necessary input."""
        form_data = {
            "workspace": self.workspace,
        }
        form = self.form_class(data=form_data)
        self.assertTrue(form.is_valid())

    def test_invalid_missing_workspace(self):
        """Form is invalid when missing workspace."""
        form_data = {}
        form = self.form_class(data=form_data)
        self.assertFalse(form.is_valid())
        self.assertEqual(len(form.errors), 1)
        self.assertIn("workspace", form.errors)
        self.assertEqual(len(form.errors["workspace"]), 1)
        self.assertIn("required", form.errors["workspace"][0])


class TemplateWorkspaceFormTest(TestCase):

    form_class = forms.TemplateWorkspaceForm

    def setUp(self):
        """Create a workspace for use in the form."""
        self.workspace = WorkspaceFactory.create()

    def test_valid(self):
        """Form is valid with necessary input."""
        form_data = {
            "workspace": self.workspace,
            "intended_use": "foo",
        }
        form = self.form_class(data=form_data)
        self.assertTrue(form.is_valid())

    def test_invalid_missing_workspace(self):
        """Form is invalid when missing workspace."""
        form_data = {
            "intended_use": "foo",
        }
        form = self.form_class(data=form_data)
        self.assertFalse(form.is_valid())
        self.assertEqual(len(form.errors), 1)
        self.assertIn("workspace", form.errors)
        self.assertEqual(len(form.errors["workspace"]), 1)
        self.assertIn("required", form.errors["workspace"][0])

    def test_invalid_missing_intended_use(self):
        """Form is invalid when missing intended_use."""
        form_data = {
            "workspace": self.workspace,
        }
        form = self.form_class(data=form_data)
        self.assertFalse(form.is_valid())
        self.assertEqual(len(form.errors), 1)
        self.assertIn("intended_use", form.errors)
        self.assertEqual(len(form.errors["intended_use"]), 1)
        self.assertIn("required", form.errors["intended_use"][0])


class CombinedConsortiumDataWorkspaceForm(TestCase):
    """Tests for the CombinedConsortiumDataWorkspaceForm class."""

    form_class = forms.CombinedConsortiumDataWorkspaceForm

    def setUp(self):
        """Create a workspace for use in the form."""
        self.workspace = WorkspaceFactory.create()

    def test_valid_one_upload_workspace(self):
        """Form is valid with necessary input."""
        upload_workspace = factories.UploadWorkspaceFactory.create()
        form_data = {
            "workspace": self.workspace,
            "upload_workspaces": [upload_workspace],
        }
        form = self.form_class(data=form_data)
        self.assertTrue(form.is_valid())

    def test_valid_two_upload_workspaces(self):
        """Form is valid with necessary input."""
        upload_workspace_1 = factories.UploadWorkspaceFactory.create(version=1)
        upload_workspace_2 = factories.UploadWorkspaceFactory.create(version=1)
        form_data = {
            "workspace": self.workspace,
            "upload_workspaces": [upload_workspace_1, upload_workspace_2],
        }
        form = self.form_class(data=form_data)
        self.assertTrue(form.is_valid())

    def test_invalid_missing_workspace(self):
        """Form is invalid when missing workspace."""
        upload_workspace = factories.UploadWorkspaceFactory.create()
        form_data = {
            "upload_workspaces": [upload_workspace],
        }
        form = self.form_class(data=form_data)
        self.assertFalse(form.is_valid())
        self.assertEqual(len(form.errors), 1)
        self.assertIn("workspace", form.errors)
        self.assertEqual(len(form.errors["workspace"]), 1)
        self.assertIn("required", form.errors["workspace"][0])

    def test_invalid_missing_upload_workspace(self):
        """Form is invalid when missing upload_workspace."""
        form_data = {
            "workspace": self.workspace,
        }
        form = self.form_class(data=form_data)
        self.assertFalse(form.is_valid())
        self.assertEqual(len(form.errors), 1)
        self.assertIn("upload_workspaces", form.errors)
        self.assertEqual(len(form.errors["upload_workspaces"]), 1)
        self.assertIn("required", form.errors["upload_workspaces"][0])

    def test_invalid_blank_upload_workspace(self):
        """Form is invalid when missing upload_workspace."""
        form_data = {
            "workspace": self.workspace,
            "upload_workspaces": [],
        }
        form = self.form_class(data=form_data)
        self.assertFalse(form.is_valid())
        self.assertEqual(len(form.errors), 1)
        self.assertIn("upload_workspaces", form.errors)
        self.assertEqual(len(form.errors["upload_workspaces"]), 1)
        self.assertIn("required", form.errors["upload_workspaces"][0])

    def test_invalid_different_upload_workspace_versions(self):
        """Form is invalid when upload workspaces have different versions."""
        upload_workspace_1 = factories.UploadWorkspaceFactory.create(version=1)
        upload_workspace_2 = factories.UploadWorkspaceFactory.create(version=2)
        form_data = {
            "workspace": self.workspace,
            "upload_workspaces": [upload_workspace_1, upload_workspace_2],
        }
        form = self.form_class(data=form_data)
        self.assertFalse(form.is_valid())
        self.assertEqual(len(form.errors), 1)
        self.assertIn("upload_workspaces", form.errors)
        self.assertEqual(len(form.errors["upload_workspaces"]), 1)
        self.assertIn(
            form.ERROR_UPLOAD_VERSION_DOES_NOT_MATCH,
            form.errors["upload_workspaces"][0],
        )
