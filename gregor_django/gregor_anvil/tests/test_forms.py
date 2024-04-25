"""Test forms for the gregor_anvil app."""

from datetime import date, timedelta

from anvil_consortium_manager.tests.factories import WorkspaceFactory
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


class PartnerUploadWorkspaceFormTest(TestCase):
    """Tests for the PartnerUploadWorkspace class."""

    form_class = forms.PartnerUploadWorkspaceForm

    def setUp(self):
        """Create a workspace for use in the form."""
        self.workspace = WorkspaceFactory()
        self.partner_group = factories.PartnerGroupFactory()
        self.consent_group = factories.ConsentGroupFactory()

    def test_valid(self):
        """Form is valid with necessary input."""
        form_data = {
            "partner_group": self.partner_group,
            "consent_group": self.consent_group,
            "version": 1,
            "workspace": self.workspace,
        }
        form = self.form_class(data=form_data)
        self.assertTrue(form.is_valid())

    def test_invalid_missing_partner_group(self):
        """Form is invalid when missing partner_group."""
        form_data = {
            # "partner_group": self.partner_group,
            "consent_group": self.consent_group,
            "version": 1,
            "workspace": self.workspace,
        }
        form = self.form_class(data=form_data)
        self.assertFalse(form.is_valid())
        self.assertEqual(len(form.errors), 1)
        self.assertIn("partner_group", form.errors)
        self.assertEqual(len(form.errors["partner_group"]), 1)
        self.assertIn("required", form.errors["partner_group"][0])

    def test_invalid_missing_consent_group(self):
        """Form is invalid when missing consent_group."""
        form_data = {
            "partner_group": self.partner_group,
            # "consent_group": self.consent_group,
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
        form_data = {
            "partner_group": self.partner_group,
            "consent_group": self.consent_group,
            # "version": 1,
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
        form_data = {
            "partner_group": self.partner_group,
            "consent_group": self.consent_group,
            "version": 1,
            # "workspace": self.workspace,
        }
        form = self.form_class(data=form_data)
        self.assertFalse(form.is_valid())
        self.assertEqual(len(form.errors), 1)
        self.assertIn("workspace", form.errors)
        self.assertEqual(len(form.errors["workspace"]), 1)
        self.assertIn("required", form.errors["workspace"][0])

    def test_invalid_duplicate_object(self):
        """Form is invalid with a duplicated object."""
        instance = factories.PartnerUploadWorkspaceFactory.create()
        form_data = {
            "partner_group": instance.partner_group,
            "consent_group": instance.consent_group,
            "version": instance.version,
            "workspace": self.workspace,
        }
        form = self.form_class(data=form_data)
        self.assertFalse(form.is_valid())
        non_field_errors = form.non_field_errors()
        self.assertEqual(len(non_field_errors), 1)
        self.assertIn("already exists", non_field_errors[0])


class ResourceWorkspaceFormTest(TestCase):

    form_class = forms.ResourceWorkspaceForm

    def setUp(self):
        """Create a workspace for use in the form."""
        self.workspace = WorkspaceFactory.create()

    def test_valid(self):
        """Form is valid with necessary input."""
        form_data = {
            "workspace": self.workspace,
            "brief_description": "Test use",
        }
        form = self.form_class(data=form_data)
        self.assertTrue(form.is_valid())

    def test_invalid_missing_workspace(self):
        """Form is invalid when missing workspace."""
        form_data = {
            "brief_description": "Test use",
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
        self.assertIn("brief_description", form.errors)
        self.assertEqual(len(form.errors["brief_description"]), 1)
        self.assertIn("required", form.errors["brief_description"][0])


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

    def test_invalid_blank_upload_cycle(self):
        """Form is invalid when missing upload_workspace."""
        form_data = {
            "workspace": self.workspace,
        }
        form = self.form_class(data=form_data)
        self.assertFalse(form.is_valid())
        self.assertEqual(len(form.errors), 1)
        self.assertIn("upload_cycle", form.errors)
        self.assertEqual(len(form.errors["upload_cycle"]), 1)
        self.assertIn("required", form.errors["upload_cycle"][0])


class ReleaseWorkspaceFormTest(TestCase):
    """Tests for the ReleaseWorkspace class."""

    form_class = forms.ReleaseWorkspaceForm

    def setUp(self):
        """Create a workspace for use in the form."""
        self.workspace = WorkspaceFactory()
        self.upload_cycle = factories.UploadCycleFactory.create()
        self.consent_group = factories.ConsentGroupFactory.create()

    def test_valid(self):
        """Form is valid with necessary input."""
        form_data = {
            "workspace": self.workspace,
            "upload_cycle": self.upload_cycle,
            "full_data_use_limitations": "foo bar",
            "consent_group": self.consent_group,
            "dbgap_version": 1,
            "dbgap_participant_set": 1,
        }
        form = self.form_class(data=form_data)
        self.assertTrue(form.is_valid())

    def test_invalid_missing_workspace(self):
        """Form is invalid when missing research_center."""
        form_data = {
            # "workspace": self.workspace,
            "upload_cycle": self.upload_cycle,
            "full_data_use_limitations": "foo bar",
            "consent_group": self.consent_group,
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
        form_data = {
            "workspace": self.workspace,
            # "upload_cycle": self.upload_cycle,
            "full_data_use_limitations": "foo bar",
            "consent_group": self.consent_group,
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

    def test_invalid_missing_consent_group(self):
        """Form is invalid when missing consent_group."""
        form_data = {
            "workspace": self.workspace,
            "upload_cycle": self.upload_cycle,
            "full_data_use_limitations": "foo bar",
            # "consent_group": self.consent_group,
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
        form_data = {
            "workspace": self.workspace,
            "upload_cycle": self.upload_cycle,
            "full_data_use_limitations": "foo bar",
            "consent_group": self.consent_group,
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
        form_data = {
            "workspace": self.workspace,
            "upload_cycle": self.upload_cycle,
            "full_data_use_limitations": "foo bar",
            "consent_group": self.consent_group,
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
        form_data = {
            "workspace": self.workspace,
            "upload_cycle": release_workspace.upload_cycle,
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


class DCCProcessingWorkspaceFormTest(TestCase):
    """Tests for the DCCProcessingWorkspace class."""

    form_class = forms.DCCProcessingWorkspaceForm

    def setUp(self):
        """Create a workspace for use in the form."""
        self.workspace = WorkspaceFactory()
        self.upload_cycle = factories.UploadCycleFactory.create()

    def test_valid(self):
        """Form is valid with necessary input."""
        upload_workspace = factories.UploadWorkspaceFactory.create()
        form_data = {
            "workspace": self.workspace,
            "upload_workspaces": [upload_workspace],
            "upload_cycle": upload_workspace.upload_cycle,
            "purpose": "foo",
        }
        form = self.form_class(data=form_data)
        self.assertTrue(form.is_valid())

    def test_invalid_missing_workspace(self):
        """Form is invalid when missing workspace."""
        form_data = {
            # "workspace": self.workspace,
            "upload_cycle": self.upload_cycle,
            "purpose": "foo",
        }
        form = self.form_class(data=form_data)
        self.assertFalse(form.is_valid())
        self.assertEqual(len(form.errors), 1)
        self.assertIn("workspace", form.errors)
        self.assertEqual(len(form.errors["workspace"]), 1)
        self.assertIn("required", form.errors["workspace"][0])

    def test_invalid_missing_upload_cycle(self):
        """Form is invalid when missing upload_cycle."""
        form_data = {
            "workspace": self.workspace,
            # "upload_cycle": self.upload_cycle,
            "purpose": "foo",
        }
        form = self.form_class(data=form_data)
        self.assertFalse(form.is_valid())
        self.assertEqual(len(form.errors), 1)
        self.assertIn("upload_cycle", form.errors)
        self.assertEqual(len(form.errors["upload_cycle"]), 1)
        self.assertIn("required", form.errors["upload_cycle"][0])

    def test_invalid_missing_purpose(self):
        """Form is invalid when missing purpose."""
        form_data = {
            "workspace": self.workspace,
            "upload_cycle": self.upload_cycle,
            # "purpose": "foo",
        }
        form = self.form_class(data=form_data)
        self.assertFalse(form.is_valid())
        self.assertEqual(len(form.errors), 1)
        self.assertIn("purpose", form.errors)
        self.assertEqual(len(form.errors["purpose"]), 1)
        self.assertIn("required", form.errors["purpose"][0])

    def test_invalid_blank_purpose(self):
        """Form is invalid when purpose is blank."""
        form_data = {
            "workspace": self.workspace,
            "upload_cycle": self.upload_cycle,
            "purpose": "",
        }
        form = self.form_class(data=form_data)
        self.assertFalse(form.is_valid())
        self.assertEqual(len(form.errors), 1)
        self.assertIn("purpose", form.errors)
        self.assertEqual(len(form.errors["purpose"]), 1)
        self.assertIn("required", form.errors["purpose"][0])


class DCCProcessedDataWorkspaceFormTest(TestCase):
    """Tests for the DCCProcessedDataWorkspaceForm class."""

    form_class = forms.DCCProcessedDataWorkspaceForm

    def setUp(self):
        """Create a workspace for use in the form."""
        self.workspace = WorkspaceFactory()
        self.upload_cycle = factories.UploadCycleFactory.create()
        self.consent_group = factories.ConsentGroupFactory()

    def test_valid(self):
        """Form is valid with necessary input."""
        form_data = {
            "upload_cycle": self.upload_cycle,
            "consent_group": self.consent_group,
            "workspace": self.workspace,
        }
        form = self.form_class(data=form_data)
        self.assertTrue(form.is_valid())

    def test_invalid_missing_upload_cycle(self):
        """Form is invalid when missing research_center."""
        form_data = {
            # "upload_cycle": self.upload_cycle,
            "consent_group": self.consent_group,
            "workspace": self.workspace,
        }
        form = self.form_class(data=form_data)
        self.assertFalse(form.is_valid())
        self.assertEqual(len(form.errors), 1)
        self.assertIn("upload_cycle", form.errors)
        self.assertEqual(len(form.errors["upload_cycle"]), 1)
        self.assertIn("required", form.errors["upload_cycle"][0])

    def test_invalid_missing_consent_group(self):
        """Form is invalid when missing consent_group."""
        form_data = {
            "upload_cycle": self.upload_cycle,
            # "consent_group": self.consent_group,
            "workspace": self.workspace,
        }
        form = self.form_class(data=form_data)
        self.assertFalse(form.is_valid())
        self.assertEqual(len(form.errors), 1)
        self.assertIn("consent_group", form.errors)
        self.assertEqual(len(form.errors["consent_group"]), 1)
        self.assertIn("required", form.errors["consent_group"][0])


class ExchangeWorkspaceFormTest(TestCase):
    """Tests for the ExchangeWorkspace class."""

    form_class = forms.ExchangeWorkspaceForm

    def setUp(self):
        """Create a workspace for use in the form."""
        self.workspace = WorkspaceFactory()

    def test_valid(self):
        """Form is valid with necessary input."""
        research_center = factories.ResearchCenterFactory()
        form_data = {
            "research_center": research_center,
            "workspace": self.workspace,
        }
        form = self.form_class(data=form_data)
        self.assertTrue(form.is_valid())

    def test_invalid_missing_research_center(self):
        """Form is invalid when missing research_center."""
        form_data = {
            "workspace": self.workspace,
        }
        form = self.form_class(data=form_data)
        self.assertFalse(form.is_valid())
        self.assertEqual(len(form.errors), 1)
        self.assertIn("research_center", form.errors)
        self.assertEqual(len(form.errors["research_center"]), 1)
        self.assertIn("required", form.errors["research_center"][0])

    def test_invalid_missing_workspace(self):
        """Form is invalid when missing research_center."""
        research_center = factories.ResearchCenterFactory()
        form_data = {
            "research_center": research_center,
        }
        form = self.form_class(data=form_data)
        self.assertFalse(form.is_valid())
        self.assertEqual(len(form.errors), 1)
        self.assertIn("workspace", form.errors)
        self.assertEqual(len(form.errors["workspace"]), 1)
        self.assertIn("required", form.errors["workspace"][0])

    def test_invalid_duplicate_object(self):
        """Form is invalid with a duplicated object."""
        exchange_workspace = factories.ExchangeWorkspaceFactory.create()
        form_data = {
            "research_center": exchange_workspace.research_center,
            "workspace": self.workspace,
        }
        form = self.form_class(data=form_data)
        self.assertFalse(form.is_valid())
        self.assertIn("research_center", form.errors)
        self.assertEqual(len(form.errors["research_center"]), 1)
        self.assertIn("already exists", form.errors["research_center"][0])
