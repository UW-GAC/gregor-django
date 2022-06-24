"""Test forms for the anvil_access app."""

from django.test import TestCase

from .. import forms
from . import factories


class WorkspaceDataImportFormTest(TestCase):
    """Tests for the `WorkspaceDataImportForm` class."""

    form_class = forms.WorkspaceDataImportForm

    def setUp(self):
        """Setup method to create data for tests."""
        self.research_center = factories.ResearchCenterFactory.create()
        self.consent_group = factories.ConsentGroupFactory.create()
        self.workspace_name = "bp/ws"

    def test_valid(self):
        """Form is valid with necessary input."""
        form_data = {
            "workspace": self.workspace_name,
            "research_center": self.research_center,
            "consent_group": self.consent_group,
            "version": 1,
        }
        workspace_choices = [
            (self.workspace_name, self.workspace_name),
        ]
        form = self.form_class(workspace_choices=workspace_choices, data=form_data)
        self.assertTrue(form.is_valid())

    def test_invalid_not_in_choices(self):
        """Form is not valid when the selected workspace isn't one of the available choices."""
        form_data = {
            "workspace": "foo",
            "research_center": self.research_center,
            "consent_group": self.consent_group,
            "version": 1,
        }
        workspace_choices = [
            (self.workspace_name, self.workspace_name),
        ]
        form = self.form_class(workspace_choices=workspace_choices, data=form_data)
        self.assertFalse(form.is_valid())
        self.assertIn("workspace", form.errors)
        self.assertEqual(len(form.errors), 1)

    def test_invalid_workspace_empty_string(self):
        """Form is not valid when an empty string is passed for workspace."""
        form_data = {
            "workspace": "",
            "research_center": self.research_center,
            "consent_group": self.consent_group,
            "version": 1,
        }
        workspace_choices = [
            (self.workspace_name, self.workspace_name),
        ]
        form = self.form_class(workspace_choices=workspace_choices, data=form_data)
        self.assertFalse(form.is_valid())
        self.assertIn("workspace", form.errors)
        self.assertEqual(len(form.errors), 1)

    def test_invalid_workspace_missing(self):
        """Form is invalid when missing workspace."""
        form_data = {
            "research_center": self.research_center,
            "consent_group": self.consent_group,
            "version": 1,
        }
        workspace_choices = [
            (self.workspace_name, self.workspace_name),
        ]
        form = self.form_class(workspace_choices=workspace_choices, data=form_data)
        self.assertFalse(form.is_valid())
        self.assertIn("workspace", form.errors)
        self.assertEqual(len(form.errors), 1)

    def test_invalid_research_center_missing(self):
        """Form is not valid when research_center is missing."""
        form_data = {
            "workspace": self.workspace_name,
            "consent_group": self.consent_group,
            "version": 1,
        }
        workspace_choices = [
            (self.workspace_name, self.workspace_name),
        ]
        form = self.form_class(workspace_choices=workspace_choices, data=form_data)
        self.assertFalse(form.is_valid())
        self.assertIn("research_center", form.errors)
        self.assertEqual(len(form.errors), 1)

    def test_invalid_consent_group_missing(self):
        """Form is not valid when research_center is missing."""
        form_data = {
            "workspace": self.workspace_name,
            "research_center": self.research_center,
            "version": 1,
        }
        workspace_choices = [
            (self.workspace_name, self.workspace_name),
        ]
        form = self.form_class(workspace_choices=workspace_choices, data=form_data)
        self.assertFalse(form.is_valid())
        self.assertIn("consent_group", form.errors)
        self.assertEqual(len(form.errors), 1)

    def test_invalid_version_missing(self):
        """Form is not valid when version is missing."""
        form_data = {
            "workspace": self.workspace_name,
            "research_center": self.research_center,
            "consent_group": self.consent_group,
        }
        workspace_choices = [
            (self.workspace_name, self.workspace_name),
        ]
        form = self.form_class(workspace_choices=workspace_choices, data=form_data)
        self.assertFalse(form.is_valid())
        self.assertIn("version", form.errors)
        self.assertEqual(len(form.errors), 1)

    def test_invalid_version_is_zero(self):
        """Form is not valid when version is zero."""
        form_data = {
            "workspace": self.workspace_name,
            "research_center": self.research_center,
            "consent_group": self.consent_group,
            "version": 0,
        }
        workspace_choices = [
            (self.workspace_name, self.workspace_name),
        ]
        form = self.form_class(workspace_choices=workspace_choices, data=form_data)
        self.assertFalse(form.is_valid())
        self.assertIn("version", form.errors)
        self.assertEqual(len(form.errors), 1)

    def test_invalid_version_is_negative(self):
        """Form is not valid when version is negative."""
        form_data = {
            "workspace": self.workspace_name,
            "research_center": self.research_center,
            "consent_group": self.consent_group,
            "version": -1,
        }
        workspace_choices = [
            (self.workspace_name, self.workspace_name),
        ]
        form = self.form_class(workspace_choices=workspace_choices, data=form_data)
        self.assertFalse(form.is_valid())
        self.assertIn("version", form.errors)
        self.assertEqual(len(form.errors), 1)

    def test_invalid_unique_constraint(self):
        """Form is not valid when the unique constraint is violated."""
        workspace_data = factories.WorkspaceDataFactory.create()
        workspace_name = "bp-2/ws-1"
        form_data = {
            "workspace": workspace_name,
            "research_center": workspace_data.research_center,
            "consent_group": workspace_data.consent_group,
            "version": workspace_data.version,
        }
        workspace_choices = [
            (workspace_name, workspace_name),
        ]
        form = self.form_class(workspace_choices=workspace_choices, data=form_data)
        self.assertFalse(form.is_valid())
        self.assertEqual(len(form.non_field_errors()), 1)

    def test_invalid_when_workspace_already_attached_to_workspacedata(self):
        """Form is not valid when the unique constraint is violated."""
        workspace_data = factories.WorkspaceDataFactory.create()
        workspace_name = workspace_data.workspace.get_full_name()
        form_data = {
            "workspace": workspace_name,
            "research_center": workspace_data.research_center,
            "consent_group": workspace_data.consent_group,
            "version": workspace_data.version,
        }
        workspace_choices = [
            (workspace_name, workspace_name),
        ]
        form = self.form_class(workspace_choices=workspace_choices, data=form_data)
        self.assertFalse(form.is_valid())
        self.assertEqual(len(form.non_field_errors()), 1)
