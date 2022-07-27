"""Test forms for the gregor_anvil app."""

from anvil_consortium_manager.tests import factories as acm_factories
from django.test import TestCase

from .. import forms
from . import factories


class UploadWorkspaceFormTest(TestCase):
    """Tests for the UploadWorkspace class."""

    form_class = forms.UploadWorkspaceForm

    def setUp(self):
        """Create a workspace for use in the form."""
        self.workspace = acm_factories.WorkspaceFactory()

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
