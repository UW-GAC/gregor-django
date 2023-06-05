"""Test forms for the gregor_anvil app."""

from datetime import date, timedelta

from anvil_consortium_manager.tests.factories import WorkspaceFactory
from django.core.exceptions import NON_FIELD_ERRORS
from django.test import TestCase

from .. import forms
from . import factories


class UploadCycleForm(TestCase):
    """Tests for the UploadCycleForm class."""

    form_class = forms.UploadCycleForm

    def test_valid(self):
        """Form is valid with necessary input."""
        form_data = {
            "cycle": 1,
            "start_date": date.today(),
            "end_date": date.today() + timedelta(days=1),
        }
        form = self.form_class(data=form_data)
        self.assertTrue(form.is_valid())

    def test_invalid_missing_cycle(self):
        """Form is invalid when missing cycle."""
        form_data = {
            # "cycle": 1,
            "start_date": date.today(),
            "end_date": date.today() + timedelta(days=1),
        }
        form = self.form_class(data=form_data)
        self.assertFalse(form.is_valid())
        self.assertEqual(len(form.errors), 1)
        self.assertIn("cycle", form.errors)
        self.assertEqual(len(form.errors["cycle"]), 1)
        self.assertIn("required", form.errors["cycle"][0])

    def test_invalid_missing_start_date(self):
        """Form is invalid when missing start_date."""
        form_data = {
            "cycle": 1,
            # "start_date": date.today(),
            "end_date": date.today() + timedelta(days=1),
        }
        form = self.form_class(data=form_data)
        self.assertFalse(form.is_valid())
        self.assertEqual(len(form.errors), 1)
        self.assertIn("start_date", form.errors)
        self.assertEqual(len(form.errors["start_date"]), 1)
        self.assertIn("required", form.errors["start_date"][0])

    def test_invalid_missing_end_date(self):
        """Form is invalid when missing cycle."""
        form_data = {
            "cycle": 1,
            "start_date": date.today(),
            # "end_date": date.today() + timedelta(days=1),
        }
        form = self.form_class(data=form_data)
        self.assertFalse(form.is_valid())
        self.assertEqual(len(form.errors), 1)
        self.assertIn("end_date", form.errors)
        self.assertEqual(len(form.errors["end_date"]), 1)
        self.assertIn("required", form.errors["end_date"][0])

    def test_valid_note(self):
        """Form is valid with a note."""
        form_data = {
            "cycle": 1,
            "start_date": date.today(),
            "end_date": date.today() + timedelta(days=1),
            "note": "my test note",
        }
        form = self.form_class(data=form_data)
        self.assertTrue(form.is_valid())


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
        upload_cycle = factories.UploadCycleFactory()
        form_data = {
            "research_center": research_center,
            "consent_group": consent_group,
            "upload_cycle": upload_cycle,
            "workspace": self.workspace,
        }
        form = self.form_class(data=form_data)
        self.assertTrue(form.is_valid())

    def test_invalid_missing_research_center(self):
        """Form is invalid when missing research_center."""
        consent_group = factories.ConsentGroupFactory()
        upload_cycle = factories.UploadCycleFactory()
        form_data = {
            "consent_group": consent_group,
            "upload_cycle": upload_cycle,
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
        upload_cycle = factories.UploadCycleFactory()
        form_data = {
            "research_center": research_center,
            "upload_cycle": upload_cycle,
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
        self.assertIn("upload_cycle", form.errors)
        self.assertEqual(len(form.errors["upload_cycle"]), 1)
        self.assertIn("required", form.errors["upload_cycle"][0])

    def test_invalid_missing_workspace(self):
        """Form is invalid when missing research_center."""
        research_center = factories.ResearchCenterFactory()
        consent_group = factories.ConsentGroupFactory()
        upload_cycle = factories.UploadCycleFactory()
        form_data = {
            "research_center": research_center,
            "consent_group": consent_group,
            "upload_cycle": upload_cycle,
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
            "upload_cycle": upload_workspace.upload_cycle,
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


class CombinedConsortiumDataWorkspaceFormTest(TestCase):
    """Tests for the CombinedConsortiumDataWorkspaceForm class."""

    form_class = forms.CombinedConsortiumDataWorkspaceForm

    def setUp(self):
        """Create a workspace for use in the form."""
        self.workspace = WorkspaceFactory.create()

    def test_valid_one_upload_workspace(self):
        """Form is valid with necessary input."""
        upload_cycle = factories.UploadCycleFactory.create()
        upload_workspace = factories.UploadWorkspaceFactory.create(
            upload_cycle=upload_cycle
        )
        form_data = {
            "workspace": self.workspace,
            "upload_cycle": upload_cycle,
            "upload_workspaces": [upload_workspace],
        }
        form = self.form_class(data=form_data)
        self.assertTrue(form.is_valid())

    def test_valid_two_upload_workspaces(self):
        """Form is valid with necessary input."""
        upload_cycle = factories.UploadCycleFactory.create()
        upload_workspace_1 = factories.UploadWorkspaceFactory.create(
            upload_cycle=upload_cycle
        )
        upload_workspace_2 = factories.UploadWorkspaceFactory.create(
            upload_cycle=upload_cycle
        )
        form_data = {
            "workspace": self.workspace,
            "upload_cycle": upload_cycle,
            "upload_workspaces": [upload_workspace_1, upload_workspace_2],
        }
        form = self.form_class(data=form_data)
        self.assertTrue(form.is_valid())

    def test_invalid_missing_workspace(self):
        """Form is invalid when missing workspace."""
        upload_cycle = factories.UploadCycleFactory.create()
        upload_workspace = factories.UploadWorkspaceFactory.create(
            upload_cycle=upload_cycle
        )
        form_data = {
            "upload_cycle": upload_cycle,
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
        upload_cycle = factories.UploadCycleFactory.create()
        form_data = {
            "upload_cycle": upload_cycle,
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
        upload_cycle = factories.UploadCycleFactory.create()
        form_data = {
            "workspace": self.workspace,
            "upload_cycle": upload_cycle,
            "upload_workspaces": [],
        }
        form = self.form_class(data=form_data)
        self.assertFalse(form.is_valid())
        self.assertEqual(len(form.errors), 1)
        self.assertIn("upload_workspaces", form.errors)
        self.assertEqual(len(form.errors["upload_workspaces"]), 1)
        self.assertIn("required", form.errors["upload_workspaces"][0])

    def test_invalid_blank_upload_cycle(self):
        """Form is invalid when missing upload_workspace."""
        upload_workspace = factories.UploadWorkspaceFactory.create()
        form_data = {
            "workspace": self.workspace,
            "upload_workspaces": [upload_workspace],
        }
        form = self.form_class(data=form_data)
        self.assertFalse(form.is_valid())
        self.assertEqual(len(form.errors), 1)
        self.assertIn("upload_cycle", form.errors)
        self.assertEqual(len(form.errors["upload_cycle"]), 1)
        self.assertIn("required", form.errors["upload_cycle"][0])

    def test_clean_upload_workspace_from_previous_cycle(self):
        """Form is invalid with a workspace from a previous upload cycle."""
        upload_workspace = factories.UploadWorkspaceFactory.create(
            upload_cycle__cycle=1
        )
        upload_cycle = factories.UploadCycleFactory.create(cycle=2)
        form_data = {
            "workspace": self.workspace,
            "upload_cycle": upload_cycle,
            "upload_workspaces": [upload_workspace],
        }
        form = self.form_class(data=form_data)
        self.assertFalse(form.is_valid())
        self.assertEqual(len(form.errors), 1)
        self.assertIn(NON_FIELD_ERRORS, form.errors)
        self.assertEqual(len(form.errors[NON_FIELD_ERRORS]), 1)
        self.assertIn(
            form.ERROR_UPLOAD_CYCLE_DOES_NOT_MATCH,
            form.errors[NON_FIELD_ERRORS][0],
        )

    def test_clean_upload_cycle(self):
        """Form is invalid when a workspace from a later cycle is selected."""
        upload_cycle = factories.UploadCycleFactory.create(cycle=1)
        upload_workspace = factories.UploadWorkspaceFactory.create(
            upload_cycle__cycle=2
        )
        form_data = {
            "workspace": self.workspace,
            "upload_cycle": upload_cycle,
            "upload_workspaces": [upload_workspace],
        }
        form = self.form_class(data=form_data)
        self.assertFalse(form.is_valid())
        self.assertEqual(len(form.errors), 1)
        self.assertIn(NON_FIELD_ERRORS, form.errors)
        self.assertEqual(len(form.errors[NON_FIELD_ERRORS]), 1)
        self.assertIn(
            form.ERROR_UPLOAD_CYCLE_DOES_NOT_MATCH,
            form.errors[NON_FIELD_ERRORS][0],
        )


class ReleaseWorkspaceFormTest(TestCase):
    """Tests for the ReleaseWorkspace class."""

    form_class = forms.ReleaseWorkspaceForm

    def setUp(self):
        """Create a workspace for use in the form."""
        self.workspace = WorkspaceFactory()

    def test_valid(self):
        """Form is valid with necessary input."""
        upload_workspace = factories.UploadWorkspaceFactory.create()
        form_data = {
            "workspace": self.workspace,
            "upload_cycle": upload_workspace.upload_cycle,
            "upload_workspaces": [upload_workspace],
            "full_data_use_limitations": "foo bar",
            "consent_group": upload_workspace.consent_group,
            "dbgap_version": 1,
            "dbgap_participant_set": 1,
        }
        form = self.form_class(data=form_data)
        self.assertTrue(form.is_valid())

    def test_invalid_missing_workspace(self):
        """Form is invalid when missing research_center."""
        upload_workspace = factories.UploadWorkspaceFactory.create()
        form_data = {
            # "workspace": self.workspace,
            "upload_cycle": upload_workspace.upload_cycle,
            "upload_workspaces": [upload_workspace],
            "full_data_use_limitations": "foo bar",
            "consent_group": upload_workspace.consent_group,
            "dbgap_version": 1,
            "dbgap_participant_set": 1,
        }
        form = self.form_class(data=form_data)
        self.assertFalse(form.is_valid())
        self.assertEqual(len(form.errors), 1)
        self.assertIn("workspace", form.errors)
        self.assertEqual(len(form.errors["workspace"]), 1)
        self.assertIn("required", form.errors["workspace"][0])

    def test_invalid_missing_upload_cycle(self):
        """Form is invalid when missing consent_group."""
        upload_workspace = factories.UploadWorkspaceFactory.create()
        form_data = {
            "workspace": self.workspace,
            # "upload_cycle": upload_workspace.upload_cycle,
            "upload_workspaces": [upload_workspace],
            "full_data_use_limitations": "foo bar",
            "consent_group": upload_workspace.consent_group,
            "dbgap_version": 1,
            "dbgap_participant_set": 1,
        }
        form = self.form_class(data=form_data)
        form = self.form_class(data=form_data)
        self.assertFalse(form.is_valid())
        self.assertEqual(len(form.errors), 1)
        self.assertIn("upload_cycle", form.errors)
        self.assertEqual(len(form.errors["upload_cycle"]), 1)
        self.assertIn("required", form.errors["upload_cycle"][0])

    def test_invalid_missing_upload_workspaces(self):
        """Form is invalid when missing research_center."""
        upload_workspace = factories.UploadWorkspaceFactory.create()
        form_data = {
            "workspace": self.workspace,
            "upload_cycle": upload_workspace.upload_cycle,
            # "upload_workspaces": [upload_workspace],
            "full_data_use_limitations": "foo bar",
            "consent_group": upload_workspace.consent_group,
            "dbgap_version": 1,
            "dbgap_participant_set": 1,
        }
        form = self.form_class(data=form_data)
        form = self.form_class(data=form_data)
        self.assertFalse(form.is_valid())
        self.assertEqual(len(form.errors), 1)
        self.assertIn("upload_workspaces", form.errors)
        self.assertEqual(len(form.errors["upload_workspaces"]), 1)
        self.assertIn("required", form.errors["upload_workspaces"][0])

    def test_invalid_missing_consent_group(self):
        """Form is invalid when missing consent_group."""
        upload_workspace = factories.UploadWorkspaceFactory.create()
        form_data = {
            "workspace": self.workspace,
            "upload_cycle": upload_workspace.upload_cycle,
            "upload_workspaces": [upload_workspace],
            "full_data_use_limitations": "foo bar",
            # "consent_group": upload_workspace.consent_group,
            "dbgap_version": 1,
            "dbgap_participant_set": 1,
        }
        form = self.form_class(data=form_data)
        form = self.form_class(data=form_data)
        self.assertFalse(form.is_valid())
        self.assertEqual(len(form.errors), 1)
        self.assertIn("consent_group", form.errors)
        self.assertEqual(len(form.errors["consent_group"]), 1)
        self.assertIn("required", form.errors["consent_group"][0])

    def test_invalid_missing_version(self):
        """Form is invalid when missing research_center."""
        upload_workspace = factories.UploadWorkspaceFactory.create()
        form_data = {
            "workspace": self.workspace,
            "upload_cycle": upload_workspace.upload_cycle,
            "upload_workspaces": [upload_workspace],
            "full_data_use_limitations": "foo bar",
            "consent_group": upload_workspace.consent_group,
            # "dbgap_version": 1,
            "dbgap_participant_set": 1,
        }
        form = self.form_class(data=form_data)
        self.assertFalse(form.is_valid())
        self.assertEqual(len(form.errors), 1)
        self.assertIn("dbgap_version", form.errors)
        self.assertEqual(len(form.errors["dbgap_version"]), 1)
        self.assertIn("required", form.errors["dbgap_version"][0])

    def test_invalid_missing_dbgap_participant_set(self):
        """Form is invalid when missing research_center."""
        upload_workspace = factories.UploadWorkspaceFactory.create()
        form_data = {
            "workspace": self.workspace,
            "upload_cycle": upload_workspace.upload_cycle,
            "upload_workspaces": [upload_workspace],
            "full_data_use_limitations": "foo bar",
            "consent_group": upload_workspace.consent_group,
            "dbgap_version": 1,
            # "dbgap_participant_set": 1,
        }
        form = self.form_class(data=form_data)
        self.assertFalse(form.is_valid())
        self.assertEqual(len(form.errors), 1)
        self.assertIn("dbgap_participant_set", form.errors)
        self.assertEqual(len(form.errors["dbgap_participant_set"]), 1)
        self.assertIn("required", form.errors["dbgap_participant_set"][0])

    def test_invalid_duplicate_object(self):
        """Form is invalid with a duplicated object."""
        release_workspace = factories.ReleaseWorkspaceFactory.create()
        upload_workspace = factories.UploadWorkspaceFactory.create(
            consent_group=release_workspace.consent_group,
            upload_cycle=release_workspace.upload_cycle,
        )
        form_data = {
            "workspace": self.workspace,
            "upload_cycle": release_workspace.upload_cycle,
            "upload_workspaces": [upload_workspace],
            "full_data_use_limitations": "foo bar",
            "consent_group": release_workspace.consent_group,
            "dbgap_version": 1,
            "dbgap_participant_set": 1,
        }
        form = self.form_class(data=form_data)
        self.assertFalse(form.is_valid())
        self.assertEqual(len(form.errors), 1)
        non_field_errors = form.non_field_errors()
        self.assertEqual(len(non_field_errors), 1)
        self.assertIn("already exists", non_field_errors[0])

    def test_valid_two_upload_workspaces(self):
        upload_workspace_1 = factories.UploadWorkspaceFactory.create()
        upload_workspace_2 = factories.UploadWorkspaceFactory.create(
            consent_group=upload_workspace_1.consent_group,
            upload_cycle=upload_workspace_1.upload_cycle,
        )
        form_data = {
            "workspace": self.workspace,
            "upload_cycle": upload_workspace_1.upload_cycle,
            "upload_workspaces": [upload_workspace_1, upload_workspace_2],
            "full_data_use_limitations": "foo bar",
            "consent_group": upload_workspace_1.consent_group,
            "dbgap_version": 1,
            "dbgap_participant_set": 1,
        }
        form = self.form_class(data=form_data)
        self.assertTrue(form.is_valid())

    def test_invalid_upload_workspaces_have_different_consent_group(self):
        upload_workspace_1 = factories.UploadWorkspaceFactory.create()
        upload_workspace_2 = factories.UploadWorkspaceFactory.create(
            upload_cycle=upload_workspace_1.upload_cycle
        )
        form_data = {
            "workspace": self.workspace,
            "upload_cycle": upload_workspace_1.upload_cycle,
            "upload_workspaces": [upload_workspace_1, upload_workspace_2],
            "full_data_use_limitations": "foo bar",
            "consent_group": upload_workspace_1.consent_group,
            "dbgap_version": 1,
            "dbgap_participant_set": 1,
        }
        form = self.form_class(data=form_data)
        self.assertFalse(form.is_valid())
        self.assertEqual(len(form.errors), 1)
        self.assertIn("upload_workspaces", form.errors)
        self.assertEqual(len(form.errors["upload_workspaces"]), 1)
        self.assertIn(
            self.form_class.ERROR_UPLOAD_WORKSPACE_CONSENT,
            form.errors["upload_workspaces"][0],
        )

    def test_invalid_upload_workspaces_have_different_upload_cycles(self):
        upload_workspace_1 = factories.UploadWorkspaceFactory.create()
        upload_workspace_2 = factories.UploadWorkspaceFactory.create(
            consent_group=upload_workspace_1.consent_group
        )
        form_data = {
            "workspace": self.workspace,
            "upload_cycle": upload_workspace_1.upload_cycle,
            "upload_workspaces": [upload_workspace_1, upload_workspace_2],
            "full_data_use_limitations": "foo bar",
            "consent_group": upload_workspace_1.consent_group,
            "dbgap_version": 1,
            "dbgap_participant_set": 1,
        }
        form = self.form_class(data=form_data)
        self.assertFalse(form.is_valid())
        self.assertEqual(len(form.errors), 1)
        self.assertIn("upload_workspaces", form.errors)
        self.assertEqual(len(form.errors["upload_workspaces"]), 1)
        self.assertIn(
            self.form_class.ERROR_UPLOAD_CYCLE,
            form.errors["upload_workspaces"][0],
        )

    def test_invalid_upload_workspace_consent_does_not_match_consent_group(self):
        consent_group = factories.ConsentGroupFactory()
        upload_workspace = factories.UploadWorkspaceFactory.create()
        form_data = {
            "workspace": self.workspace,
            "upload_cycle": upload_workspace.upload_cycle,
            "upload_workspaces": [upload_workspace],
            "full_data_use_limitations": "foo bar",
            "consent_group": consent_group,
            "dbgap_version": 1,
            "dbgap_participant_set": 1,
        }
        form = self.form_class(data=form_data)
        self.assertFalse(form.is_valid())
        self.assertEqual(len(form.errors), 1)
        non_field_errors = form.non_field_errors()
        self.assertEqual(len(non_field_errors), 1)
        self.assertIn(self.form_class.ERROR_CONSENT_DOES_NOT_MATCH, non_field_errors[0])

    def test_clean(self):
        """Form is invalid when upload_workspace upload cycle does not match upload_cycle."""
        upload_workspace = factories.UploadWorkspaceFactory.create()
        upload_cycle = factories.UploadCycleFactory.create()
        form_data = {
            "workspace": self.workspace,
            "upload_cycle": upload_cycle,
            "upload_workspaces": [upload_workspace],
            "full_data_use_limitations": "foo bar",
            "consent_group": upload_workspace.consent_group,
            "dbgap_version": 1,
            "dbgap_participant_set": 1,
        }
        form = self.form_class(data=form_data)
        self.assertFalse(form.is_valid())
        self.assertEqual(len(form.errors), 1)
        self.assertIn(NON_FIELD_ERRORS, form.errors)
        self.assertEqual(len(form.errors[NON_FIELD_ERRORS]), 1)
        self.assertIn(
            self.form_class.ERROR_UPLOAD_CYCLE,
            form.errors[NON_FIELD_ERRORS][0],
        )


class DCCProcessingWorkspaceFormTest(TestCase):
    """Tests for the DCCProcessingWorkspace class."""

    form_class = forms.DCCProcessingWorkspaceForm

    def setUp(self):
        """Create a workspace for use in the form."""
        self.workspace = WorkspaceFactory()

    def test_valid(self):
        """Form is valid with necessary input."""
        upload_workspace = factories.UploadWorkspaceFactory.create()
        form_data = {
            "workspace": self.workspace,
            "upload_workspaces": [upload_workspace],
            "upload_cycle": upload_workspace.upload_cycle,
        }
        form = self.form_class(data=form_data)
        self.assertTrue(form.is_valid())

    def test_invalid_missing_workspace(self):
        """Form is invalid when missing workspace."""
        upload_workspace = factories.UploadWorkspaceFactory.create()
        form_data = {
            # "workspace": self.workspace,
            "upload_workspaces": [upload_workspace],
            "upload_cycle": upload_workspace.upload_cycle,
        }
        form = self.form_class(data=form_data)
        self.assertFalse(form.is_valid())
        self.assertEqual(len(form.errors), 1)
        self.assertIn("workspace", form.errors)
        self.assertEqual(len(form.errors["workspace"]), 1)
        self.assertIn("required", form.errors["workspace"][0])

    def test_invalid_missing_upload_workspaces(self):
        """Form is invalid when missing upload_workspaces."""
        upload_cycle = factories.UploadCycleFactory.create()
        form_data = {
            "workspace": self.workspace,
            # "upload_workspaces": [upload_workspace],
            "upload_cycle": upload_cycle,
        }
        form = self.form_class(data=form_data)
        self.assertFalse(form.is_valid())
        self.assertEqual(len(form.errors), 1)
        self.assertIn("upload_workspaces", form.errors)
        self.assertEqual(len(form.errors["upload_workspaces"]), 1)
        self.assertIn("required", form.errors["upload_workspaces"][0])

    def test_valid_two_upload_workspaces(self):
        upload_workspace_1 = factories.UploadWorkspaceFactory.create()
        upload_workspace_2 = factories.UploadWorkspaceFactory.create(
            upload_cycle=upload_workspace_1.upload_cycle
        )
        form_data = {
            "workspace": self.workspace,
            "upload_workspaces": [upload_workspace_1, upload_workspace_2],
            "upload_cycle": upload_workspace_1.upload_cycle,
        }
        form = self.form_class(data=form_data)
        self.assertTrue(form.is_valid())

    def test_clean(self):
        """Form is invalid when upload_workspace upload cycle does not match upload_cycle."""
        upload_workspace = factories.UploadWorkspaceFactory.create()
        upload_cycle = factories.UploadCycleFactory.create()
        form_data = {
            "workspace": self.workspace,
            "upload_cycle": upload_cycle,
            "upload_workspaces": [upload_workspace],
        }
        form = self.form_class(data=form_data)
        self.assertFalse(form.is_valid())
        self.assertEqual(len(form.errors), 1)
        self.assertIn(NON_FIELD_ERRORS, form.errors)
        self.assertEqual(len(form.errors[NON_FIELD_ERRORS]), 1)
        self.assertIn(
            self.form_class.ERROR_UPLOAD_CYCLE,
            form.errors[NON_FIELD_ERRORS][0],
        )


class DCCProcessedDataWorkspaceFormTest(TestCase):
    """Tests for the DCCProcessedDataWorkspaceForm class."""

    form_class = forms.DCCProcessedDataWorkspaceForm

    def setUp(self):
        """Create a workspace for use in the form."""
        self.workspace = WorkspaceFactory()

    def test_valid(self):
        """Form is valid with necessary input."""
        dcc_processing_workspace = factories.DCCProcessingWorkspaceFactory()
        consent_group = factories.ConsentGroupFactory()
        form_data = {
            "dcc_processing_workspace": dcc_processing_workspace,
            "consent_group": consent_group,
            "workspace": self.workspace,
        }
        form = self.form_class(data=form_data)
        self.assertTrue(form.is_valid())

    def test_invalid_missing_dcc_processing_workspace(self):
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
        self.assertIn("dcc_processing_workspace", form.errors)
        self.assertEqual(len(form.errors["dcc_processing_workspace"]), 1)
        self.assertIn("required", form.errors["dcc_processing_workspace"][0])

    def test_invalid_missing_consent_group(self):
        """Form is invalid when missing consent_group."""
        dcc_processing_workspace = factories.DCCProcessingWorkspaceFactory()
        form_data = {
            "dcc_processing_workspace": dcc_processing_workspace,
            "version": 1,
            "workspace": self.workspace,
        }
        form = self.form_class(data=form_data)
        self.assertFalse(form.is_valid())
        self.assertEqual(len(form.errors), 1)
        self.assertIn("consent_group", form.errors)
        self.assertEqual(len(form.errors["consent_group"]), 1)
        self.assertIn("required", form.errors["consent_group"][0])
