from datetime import date, timedelta

from anvil_consortium_manager.tests.factories import WorkspaceFactory
from django.core.exceptions import NON_FIELD_ERRORS, ValidationError
from django.db.utils import DataError, IntegrityError
from django.test import TestCase

from .. import models
from . import factories


class ConsentGroupTest(TestCase):
    """Tests for the ConsentGroup model."""

    def test_model_saving(self):
        """Creation using the model constructor and .save() works."""
        instance = models.ConsentGroup(
            code="TEST", consent="test consent", data_use_limitations="test limitations"
        )
        instance.save()
        self.assertIsInstance(instance, models.ConsentGroup)

    def test_str_method(self):
        """The custom __str__ method returns the correct string."""
        instance = factories.ConsentGroupFactory.create(code="test")
        instance.save()
        self.assertIsInstance(instance.__str__(), str)
        self.assertEqual(instance.__str__(), "test")

    def test_get_absolute_url(self):
        """The get_absolute_url() method works."""
        instance = factories.ConsentGroupFactory()
        self.assertIsInstance(instance.get_absolute_url(), str)

    def test_unique_code(self):
        """Saving a model with a duplicate code fails."""
        instance_1 = models.ConsentGroup(
            code="TEST",
            consent="test consent 1",
            data_use_limitations="test limitations 1",
        )
        instance_1.save()
        instance_2 = models.ConsentGroup(
            code="TEST",
            consent="test consent 2",
            data_use_limitations="test limitations 1",
        )
        with self.assertRaises(ValidationError):
            instance_2.full_clean()
        with self.assertRaises(IntegrityError):
            instance_2.save()

    def test_unique_consent(self):
        """Saving a model with a duplicate consent fails."""
        instance_1 = models.ConsentGroup(
            code="TEST1",
            consent="test consent 1",
            data_use_limitations="test limitations",
        )
        instance_1.save()
        instance_2 = models.ConsentGroup(
            code="TEST2",
            consent="test consent 1",
            data_use_limitations="test limitations",
        )
        with self.assertRaises(ValidationError):
            instance_2.full_clean()
        with self.assertRaises(IntegrityError):
            instance_2.save()

    def test_invalid_code(self):
        """Cleaning a model with an invalid code fails."""
        instance = models.ConsentGroup(
            code="FOO", data_use_limitations="test limitations"
        )
        with self.assertRaises(ValidationError):
            instance.full_clean()


class ResearchCenterTest(TestCase):
    """Tests for the ResearchCenter model."""

    def test_model_saving(self):
        """Creation using the model constructor and .save() works."""
        instance = models.ResearchCenter(full_name="Test name", short_name="TEST")
        instance.save()
        self.assertIsInstance(instance, models.ResearchCenter)

    def test_str_method(self):
        """The custom __str__ method returns the correct string."""
        instance = factories.ResearchCenterFactory.create(short_name="Test")
        instance.save()
        self.assertIsInstance(instance.__str__(), str)
        self.assertEqual(instance.__str__(), "Test")

    def test_get_absolute_url(self):
        """The get_absolute_url() method works."""
        instance = factories.ResearchCenterFactory()
        self.assertIsInstance(instance.get_absolute_url(), str)

    def test_unique_short_name(self):
        """Saving a model with a duplicate short name fails."""
        factories.ResearchCenterFactory.create(short_name="FOO")
        instance2 = models.ResearchCenter(short_name="FOO", full_name="full name")
        with self.assertRaises(ValidationError):
            instance2.full_clean()
        with self.assertRaises(IntegrityError):
            instance2.save()


class UploadCycleTest(TestCase):
    """Tests for the UploadCycle model."""

    def test_model_saving(self):
        """Creation using the model constructor and .save() works."""
        instance = models.UploadCycle(
            cycle=1,
            start_date=date.today(),
            end_date=date.today() + timedelta(days=1),
        )
        instance.full_clean()
        instance.save()
        self.assertIsInstance(instance, models.UploadCycle)

    def test_model_saving_with_note(self):
        """Creation using the model constructor and .save() works."""
        instance = models.UploadCycle(
            cycle=1,
            start_date=date.today(),
            end_date=date.today() + timedelta(days=1),
            note="foo",
        )
        instance.full_clean()
        instance.save()
        self.assertIsInstance(instance, models.UploadCycle)

    def test_str_method(self):
        """The custom __str__ method returns the correct string."""
        instance = factories.UploadCycleFactory.create(cycle=1)
        instance.save()
        self.assertIsInstance(instance.__str__(), str)
        self.assertEqual(instance.__str__(), "U01")

    # def test_get_absolute_url(self):
    #     """The get_absolute_url() method works."""
    #     instance = factories.ConsentGroupFactory()
    #     self.assertIsInstance(instance.get_absolute_url(), str)

    def test_cycle_unique(self):
        """Saving a model with a duplicate cycle fails."""
        factories.UploadCycleFactory.create(cycle=2)
        instance_2 = factories.UploadCycleFactory.build(cycle=2)
        with self.assertRaises(ValidationError):
            instance_2.full_clean()
        with self.assertRaises(IntegrityError):
            instance_2.save()

    def test_positive_cycle_not_negative(self):
        """cycle cannot be negative."""
        instance = factories.UploadCycleFactory.build(cycle=-1)
        with self.assertRaises(ValidationError) as e:
            instance.full_clean()
        self.assertEqual(len(e.exception.error_dict), 1)
        self.assertIn("cycle", e.exception.error_dict)
        self.assertEqual(len(e.exception.error_dict["cycle"]), 1)

    def test_positive_cycle_not_zero(self):
        """cycle cannot be 0."""
        instance = factories.UploadCycleFactory.build(cycle=0)
        with self.assertRaises(ValidationError) as e:
            instance.full_clean()
        self.assertEqual(len(e.exception.error_dict), 1)
        self.assertIn("cycle", e.exception.error_dict)
        self.assertEqual(len(e.exception.error_dict["cycle"]), 1)

    def test_note(self):
        instance = factories.UploadCycleFactory.create(cycle=0, note="my test note")
        self.assertEqual(instance.note, "my test note")

    def test_start_date_greater_than_end_date(self):
        instance_2 = factories.UploadCycleFactory.build(
            start_date=date.today(), end_date=date.today() - timedelta(days=10)
        )
        with self.assertRaises(ValidationError) as e:
            instance_2.full_clean()
        self.assertEqual(len(e.exception.error_dict), 1)
        self.assertIn(NON_FIELD_ERRORS, e.exception.message_dict)
        self.assertEqual(len(e.exception.message_dict[NON_FIELD_ERRORS]), 1)
        self.assertIn("after start_date", e.exception.message_dict[NON_FIELD_ERRORS][0])

    def test_start_date_equal_to_end_date(self):
        same_date = date.today()
        instance_2 = factories.UploadCycleFactory.build(
            start_date=same_date, end_date=same_date
        )
        with self.assertRaises(ValidationError) as e:
            instance_2.full_clean()
        self.assertEqual(len(e.exception.message_dict), 1)
        self.assertIn(NON_FIELD_ERRORS, e.exception.message_dict)
        self.assertEqual(len(e.exception.error_dict[NON_FIELD_ERRORS]), 1)
        self.assertIn("after start_date", e.exception.message_dict[NON_FIELD_ERRORS][0])


class UploadWorkspaceTest(TestCase):
    """Tests for the UploadWorkspace model."""

    def test_model_saving(self):
        """Creation using the model constructor and .save() works."""
        research_center = factories.ResearchCenterFactory.create()
        consent_group = factories.ConsentGroupFactory.create()
        workspace = WorkspaceFactory.create()
        instance = models.UploadWorkspace(
            research_center=research_center,
            consent_group=consent_group,
            workspace=workspace,
            version=1,
        )
        instance.save()
        self.assertIsInstance(instance, models.UploadWorkspace)

    def test_str_method(self):
        """The custom __str__ method returns the correct string."""
        instance = factories.UploadWorkspaceFactory.create()
        instance.save()
        self.assertIsInstance(instance.__str__(), str)
        self.assertEqual(instance.__str__(), instance.workspace.__str__())

    def test_unique_constraint(self):
        """Cannot save two instances with the same ResearchCenter, ConsentGroup, and version."""
        research_center = factories.ResearchCenterFactory.create()
        consent_group = factories.ConsentGroupFactory.create()
        workspace_1 = WorkspaceFactory.create(name="ws-1")
        workspace_2 = WorkspaceFactory.create(name="ws-2")
        instance_1 = models.UploadWorkspace(
            research_center=research_center,
            consent_group=consent_group,
            workspace=workspace_1,
            version=1,
        )
        instance_1.save()
        instance_2 = models.UploadWorkspace(
            research_center=research_center,
            consent_group=consent_group,
            workspace=workspace_2,
            version=1,
        )
        with self.assertRaises(ValidationError):
            instance_2.full_clean()
        with self.assertRaises(IntegrityError):
            instance_2.save()

    def test_same_research_center(self):
        """Can save multiple UploadWorkspace models with the same ResearchCenter."""
        research_center = factories.ResearchCenterFactory()
        consent_group_1 = factories.ConsentGroupFactory()
        consent_group_2 = factories.ConsentGroupFactory()
        workspace_1 = WorkspaceFactory.create()
        workspace_2 = WorkspaceFactory.create()
        instance_1 = models.UploadWorkspace(
            research_center=research_center,
            consent_group=consent_group_1,
            workspace=workspace_1,
            version=1,
        )
        instance_1.save()
        instance_2 = models.UploadWorkspace(
            research_center=research_center,
            consent_group=consent_group_2,
            workspace=workspace_2,
            version=1,
        )
        instance_2.full_clean()
        instance_2.save()
        self.assertEqual(models.UploadWorkspace.objects.count(), 2)

    def test_same_consent_group(self):
        """Can save multiple UploadWorkspace models with the same ConsentGroup."""
        consent_group = factories.ConsentGroupFactory()
        research_center_1 = factories.ResearchCenterFactory()
        research_center_2 = factories.ResearchCenterFactory()
        workspace_1 = WorkspaceFactory.create()
        workspace_2 = WorkspaceFactory.create()
        instance_1 = models.UploadWorkspace(
            research_center=research_center_1,
            consent_group=consent_group,
            workspace=workspace_1,
            version=1,
        )
        instance_1.save()
        instance_2 = models.UploadWorkspace(
            research_center=research_center_2,
            consent_group=consent_group,
            workspace=workspace_2,
            version=1,
        )
        instance_2.full_clean()
        instance_2.save()
        self.assertEqual(models.UploadWorkspace.objects.count(), 2)

    def test_same_version(self):
        """Can save multiple UploadWorkspace models with the same version."""
        consent_group = factories.ConsentGroupFactory()
        research_center = factories.ResearchCenterFactory()
        workspace_1 = WorkspaceFactory.create()
        workspace_2 = WorkspaceFactory.create()
        instance_1 = models.UploadWorkspace(
            research_center=research_center,
            consent_group=consent_group,
            workspace=workspace_1,
            version=1,
        )
        instance_1.save()
        instance_2 = models.UploadWorkspace(
            research_center=research_center,
            consent_group=consent_group,
            workspace=workspace_2,
            version=2,
        )
        instance_2.full_clean()
        instance_2.save()
        self.assertEqual(models.UploadWorkspace.objects.count(), 2)

    def test_duplicated_workspace(self):
        """One workspace cannot be associated with two UploadWorkspace models."""
        workspace = WorkspaceFactory.create()
        consent_group_1 = factories.ConsentGroupFactory()
        consent_group_2 = factories.ConsentGroupFactory()
        research_center_1 = factories.ResearchCenterFactory.create()
        research_center_2 = factories.ResearchCenterFactory.create()
        instance_1 = models.UploadWorkspace(
            research_center=research_center_1,
            consent_group=consent_group_1,
            workspace=workspace,
            version=1,
        )
        instance_1.save()
        instance_2 = models.UploadWorkspace(
            research_center=research_center_2,
            consent_group=consent_group_2,
            workspace=workspace,
            version=1,
        )
        with self.assertRaises(ValidationError):
            instance_2.full_clean()
        with self.assertRaises(IntegrityError):
            instance_2.save()

    def test_constraint_positive_version_not_negative(self):
        """Version cannot be negative."""
        research_center = factories.ResearchCenterFactory.create()
        consent_group = factories.ConsentGroupFactory.create()
        workspace = WorkspaceFactory.create(name="ws")
        instance = models.UploadWorkspace(
            research_center=research_center,
            consent_group=consent_group,
            workspace=workspace,
            version=-1,
        )
        # No validation error with CheckConstraints.
        with self.assertRaises(ValidationError):
            instance.full_clean()
        # mysql raises DataError, sqlite IntegrityError
        # allow either
        with self.assertRaises((DataError, IntegrityError)):
            instance.save()

    def test_constraint_positive_version_not_zero(self):
        """Version cannot be 0."""
        research_center = factories.ResearchCenterFactory.create()
        consent_group = factories.ConsentGroupFactory.create()
        workspace = WorkspaceFactory.create(name="ws")
        instance = models.UploadWorkspace(
            research_center=research_center,
            consent_group=consent_group,
            workspace=workspace,
            version=-0,
        )
        # No validation error with CheckConstraints.
        with self.assertRaises(ValidationError):
            instance.full_clean()
        with self.assertRaises(IntegrityError):
            instance.save()


class ExampleWorkspaceTest(TestCase):
    """Tests for the ExampleWorkspace model."""

    def test_model_saving(self):
        """Creation using the model constructor and .save() works."""
        workspace = WorkspaceFactory.create()
        instance = models.ExampleWorkspace(workspace=workspace)
        instance.save()
        self.assertIsInstance(instance, models.ExampleWorkspace)

    def test_str_method(self):
        workspace = WorkspaceFactory.create(
            billing_project__name="test-bp", name="test-ws"
        )
        instance = factories.ExampleWorkspaceFactory.create(workspace=workspace)
        self.assertIsInstance(str(instance), str)
        self.assertEqual(str(instance), "test-bp/test-ws")


class TemplateWorkspaceTest(TestCase):
    """Tests for the TemplateWorkspace model."""

    def test_model_saving(self):
        """Creation using the model constructor and .save() works."""
        workspace = WorkspaceFactory.create()
        instance = models.TemplateWorkspace(workspace=workspace, intended_use="foo")
        instance.save()
        self.assertIsInstance(instance, models.TemplateWorkspace)

    def test_str_method(self):
        workspace = WorkspaceFactory.create(
            billing_project__name="test-bp", name="test-ws"
        )
        instance = factories.TemplateWorkspaceFactory.create(workspace=workspace)
        self.assertIsInstance(str(instance), str)
        self.assertEqual(str(instance), "test-bp/test-ws")


class CombinedConsortiumDataWorkspaceTest(TestCase):
    """Tests for the CombinedConsortiumDataWorkspace model."""

    def test_model_saving(self):
        """Creation using the model constructor and .save() works."""
        workspace = WorkspaceFactory.create()
        instance = models.CombinedConsortiumDataWorkspace(workspace=workspace)
        instance.save()
        self.assertIsInstance(instance, models.CombinedConsortiumDataWorkspace)

    def test_str_method(self):
        """The custom __str__ method returns the correct string."""
        instance = factories.CombinedConsortiumDataWorkspaceFactory.create()
        instance.save()
        self.assertIsInstance(instance.__str__(), str)
        self.assertEqual(instance.__str__(), instance.workspace.__str__())

    def test_one_upload_workspace(self):
        """Can link one upload workspace."""
        upload_workspace = factories.UploadWorkspaceFactory.create()
        instance = factories.CombinedConsortiumDataWorkspaceFactory.create()
        instance.save()
        instance.upload_workspaces.add(upload_workspace)
        self.assertEqual(instance.upload_workspaces.count(), 1)
        self.assertIn(upload_workspace, instance.upload_workspaces.all())

    def test_two_upload_workspaces(self):
        """Can link two upload workspaces."""
        upload_workspace_1 = factories.UploadWorkspaceFactory.create()
        upload_workspace_2 = factories.UploadWorkspaceFactory.create()
        instance = factories.CombinedConsortiumDataWorkspaceFactory.create()
        instance.save()
        instance.upload_workspaces.add(upload_workspace_1, upload_workspace_2)
        self.assertEqual(instance.upload_workspaces.count(), 2)
        self.assertIn(upload_workspace_1, instance.upload_workspaces.all())
        self.assertIn(upload_workspace_2, instance.upload_workspaces.all())


class ReleaseWorkspaceTest(TestCase):
    """Tests for the ReleaseWorkspace model."""

    def test_model_saving(self):
        """Creation using the model constructor and .save() works."""
        workspace = WorkspaceFactory.create()
        consent_group = factories.ConsentGroupFactory.create()
        instance = models.ReleaseWorkspace(
            workspace=workspace,
            full_data_use_limitations="foo",
            consent_group=consent_group,
            dbgap_version=1,
            dbgap_participant_set=1,
        )
        instance.save()
        self.assertIsInstance(instance, models.ReleaseWorkspace)

    def test_str_method(self):
        """The custom __str__ method returns the correct string."""
        instance = factories.ReleaseWorkspaceFactory.create()
        instance.save()
        self.assertIsInstance(instance.__str__(), str)
        self.assertEqual(instance.__str__(), instance.workspace.__str__())

    def test_one_upload_workspace(self):
        """Can link one upload workspace."""
        instance = factories.ReleaseWorkspaceFactory.create()
        instance.save()
        upload_workspace = factories.UploadWorkspaceFactory.create(
            consent_group=instance.consent_group
        )
        instance.upload_workspaces.add(upload_workspace)
        self.assertEqual(instance.upload_workspaces.count(), 1)
        self.assertIn(upload_workspace, instance.upload_workspaces.all())

    def test_two_upload_workspaces(self):
        """Can link two upload workspaces."""
        instance = factories.ReleaseWorkspaceFactory.create()
        instance.save()
        upload_workspace_1 = factories.UploadWorkspaceFactory.create(
            consent_group=instance.consent_group
        )
        upload_workspace_2 = factories.UploadWorkspaceFactory.create(
            consent_group=instance.consent_group
        )
        instance.upload_workspaces.add(upload_workspace_1, upload_workspace_2)
        self.assertEqual(instance.upload_workspaces.count(), 2)
        self.assertIn(upload_workspace_1, instance.upload_workspaces.all())
        self.assertIn(upload_workspace_2, instance.upload_workspaces.all())

    def test_unique_constraint(self):
        """Cannot save two instances with the same ConsentGroup and dbgap_version."""
        consent_group = factories.ConsentGroupFactory.create()
        workspace_1 = WorkspaceFactory.create(name="ws-1")
        factories.ReleaseWorkspaceFactory.create(
            workspace=workspace_1,
            consent_group=consent_group,
            dbgap_version=1,
        )
        workspace_2 = WorkspaceFactory.create(name="ws-2")
        instance_2 = factories.ReleaseWorkspaceFactory.build(
            workspace=workspace_2,
            consent_group=consent_group,
            dbgap_version=1,
        )
        with self.assertRaises(ValidationError):
            instance_2.full_clean()
        with self.assertRaises(IntegrityError):
            instance_2.save()

    def test_same_consent_group(self):
        """Can save multiple ReleaseWorkspace models with the same ConsentGroup and different dbgap_version."""
        consent_group = factories.ConsentGroupFactory.create()
        workspace_1 = WorkspaceFactory.create(name="ws-1")
        factories.ReleaseWorkspaceFactory.create(
            workspace=workspace_1,
            consent_group=consent_group,
            dbgap_version=1,
        )
        workspace_2 = WorkspaceFactory.create(name="ws-2")
        instance_2 = factories.ReleaseWorkspaceFactory.build(
            workspace=workspace_2,
            consent_group=consent_group,
            dbgap_version=2,
        )
        instance_2.full_clean()
        instance_2.save()
        self.assertEqual(models.ReleaseWorkspace.objects.count(), 2)

    def test_same_dbgap_version(self):
        """Can save multiple ReleaseWorkspace models with the same dbgap_version and different ConsentGroup."""
        consent_group_1 = factories.ConsentGroupFactory()
        consent_group_2 = factories.ConsentGroupFactory()
        factories.ReleaseWorkspaceFactory.create(
            consent_group=consent_group_1,
            dbgap_version=1,
        )
        workspace_2 = WorkspaceFactory.create(name="ws-2")
        instance_2 = factories.ReleaseWorkspaceFactory.build(
            workspace=workspace_2,
            consent_group=consent_group_2,
            dbgap_version=1,
        )
        instance_2.full_clean()
        instance_2.save()
        self.assertEqual(models.ReleaseWorkspace.objects.count(), 2)

    def test_positive_dbgap_version_not_negative(self):
        """Version cannot be negative."""
        consent_group = factories.ConsentGroupFactory.create()
        workspace = WorkspaceFactory.create(name="ws")
        instance = factories.ReleaseWorkspaceFactory.build(
            consent_group=consent_group,
            workspace=workspace,
            dbgap_version=-1,
        )
        with self.assertRaises(ValidationError) as e:
            instance.full_clean()
        self.assertEqual(len(e.exception.error_dict), 1)
        self.assertIn("dbgap_version", e.exception.error_dict)
        self.assertEqual(len(e.exception.error_dict["dbgap_version"]), 1)

    def test_positive_dbgap_version_not_zero(self):
        """Version cannot be 0."""
        consent_group = factories.ConsentGroupFactory.create()
        workspace = WorkspaceFactory.create(name="ws")
        instance = factories.ReleaseWorkspaceFactory.build(
            consent_group=consent_group,
            workspace=workspace,
            dbgap_version=0,
        )
        with self.assertRaises(ValidationError) as e:
            instance.full_clean()
        self.assertEqual(len(e.exception.error_dict), 1)
        self.assertIn("dbgap_version", e.exception.error_dict)
        self.assertEqual(len(e.exception.error_dict["dbgap_version"]), 1)

    def test_positive_dbgap_participant_set_not_negative(self):
        """dbgap_participant_set cannot be negative."""
        consent_group = factories.ConsentGroupFactory.create()
        workspace = WorkspaceFactory.create(name="ws")
        instance = factories.ReleaseWorkspaceFactory.build(
            consent_group=consent_group,
            workspace=workspace,
            dbgap_participant_set=-1,
        )
        with self.assertRaises(ValidationError) as e:
            instance.full_clean()
        self.assertEqual(len(e.exception.error_dict), 1)
        self.assertIn("dbgap_participant_set", e.exception.error_dict)
        self.assertEqual(len(e.exception.error_dict["dbgap_participant_set"]), 1)

    def test_positive_dbgap_participant_set_not_zero(self):
        """dbgap_participant_set cannot be 0."""
        consent_group = factories.ConsentGroupFactory.create()
        workspace = WorkspaceFactory.create(name="ws")
        instance = factories.ReleaseWorkspaceFactory.build(
            consent_group=consent_group,
            workspace=workspace,
            dbgap_participant_set=0,
        )
        with self.assertRaises(ValidationError) as e:
            instance.full_clean()
        self.assertEqual(len(e.exception.error_dict), 1)
        self.assertIn("dbgap_participant_set", e.exception.error_dict)
        self.assertEqual(len(e.exception.error_dict["dbgap_participant_set"]), 1)

    def test_get_dbgap_accession(self):
        """get_dbgap_accession works as expected."""
        instance = factories.ReleaseWorkspaceFactory.create(
            dbgap_version=1, dbgap_participant_set=2
        )
        self.assertEqual(instance.get_dbgap_accession(), "phs003047.v1.p2")
