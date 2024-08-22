from datetime import date, timedelta

from anvil_consortium_manager.tests.factories import ManagedGroupFactory, WorkspaceFactory
from django.core.exceptions import NON_FIELD_ERRORS, ValidationError
from django.db.utils import IntegrityError
from django.test import TestCase
from django.utils import timezone
from faker import Faker

from .. import models
from . import factories

fake = Faker()


class ConsentGroupTest(TestCase):
    """Tests for the ConsentGroup model."""

    def test_model_saving(self):
        """Creation using the model constructor and .save() works."""
        instance = models.ConsentGroup(code="TEST", consent="test consent", data_use_limitations="test limitations")
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
        instance = models.ConsentGroup(code="FOO", data_use_limitations="test limitations")
        with self.assertRaises(ValidationError):
            instance.full_clean()


class ResearchCenterTest(TestCase):
    """Tests for the ResearchCenter model."""

    def test_model_saving(self):
        """Creation using the model constructor and .save() works."""
        instance = models.ResearchCenter(
            full_name="Test name",
            short_name="TEST",
        )
        instance.full_clean()
        instance.save()
        self.assertIsInstance(instance, models.ResearchCenter)

    def test_model_saving_with_groups(self):
        """Creation using the model constructor and .save() works."""
        member_group = ManagedGroupFactory.create()
        uploader_group = ManagedGroupFactory.create()
        instance = models.ResearchCenter(
            full_name="Test name",
            short_name="TEST",
            member_group=member_group,
            uploader_group=uploader_group,
        )
        instance.full_clean()
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

    def test_member_group_uploader_group_must_be_different(self):
        """The same group cannot be used as the members group and uploaders group."""
        group = ManagedGroupFactory.create()
        instance = models.ResearchCenter(
            full_name="Test name",
            short_name="TEST",
            member_group=group,
            uploader_group=group,
        )
        with self.assertRaises(ValidationError) as e:
            instance.full_clean()
        self.assertEqual(len(e.exception.error_dict), 1)
        self.assertIn(NON_FIELD_ERRORS, e.exception.error_dict)
        self.assertEqual(len(e.exception.error_dict[NON_FIELD_ERRORS]), 1)
        self.assertIn("must be different", str(e.exception.error_dict[NON_FIELD_ERRORS][0]))

    def test_member_group_non_member_group_must_be_different(self):
        """The same group cannot be used as the members group and non-members group."""
        group = ManagedGroupFactory.create()
        instance = models.ResearchCenter(
            full_name="Test name",
            short_name="TEST",
            member_group=group,
            non_member_group=group,
        )
        with self.assertRaises(ValidationError) as e:
            instance.full_clean()
        self.assertEqual(len(e.exception.error_dict), 1)
        self.assertIn(NON_FIELD_ERRORS, e.exception.error_dict)
        self.assertEqual(len(e.exception.error_dict[NON_FIELD_ERRORS]), 1)
        self.assertIn("must be different", str(e.exception.error_dict[NON_FIELD_ERRORS][0]))

    def test_non_member_group_uploader_group_must_be_different(self):
        """The same group cannot be used as the members group and uploaders group."""
        group = ManagedGroupFactory.create()
        instance = models.ResearchCenter(
            full_name="Test name",
            short_name="TEST",
            non_member_group=group,
            uploader_group=group,
        )
        with self.assertRaises(ValidationError) as e:
            instance.full_clean()
        self.assertEqual(len(e.exception.error_dict), 1)
        self.assertIn(NON_FIELD_ERRORS, e.exception.error_dict)
        self.assertEqual(len(e.exception.error_dict[NON_FIELD_ERRORS]), 1)
        self.assertIn("must be different", str(e.exception.error_dict[NON_FIELD_ERRORS][0]))

    def test_error_two_rcs_same_member_group(self):
        """Cannot have the same member group for two RCs."""
        member_group = ManagedGroupFactory.create()
        factories.ResearchCenterFactory.create(member_group=member_group)
        instance = factories.ResearchCenterFactory.build(
            full_name="Test name",
            short_name="TEST",
            member_group=member_group,
        )
        with self.assertRaises(ValidationError) as e:
            instance.full_clean()
        self.assertEqual(len(e.exception.error_dict), 1)
        self.assertIn("member_group", e.exception.error_dict)
        self.assertEqual(len(e.exception.error_dict["member_group"]), 1)
        self.assertIn("already exists", str(e.exception.error_dict["member_group"][0]))

    def test_error_two_rcs_same_uploader_group(self):
        """Cannot have the same uploader group for two RCs."""
        uploader_group = ManagedGroupFactory.create()
        factories.ResearchCenterFactory.create(uploader_group=uploader_group)
        instance = factories.ResearchCenterFactory.build(
            full_name="Test name",
            short_name="TEST",
            uploader_group=uploader_group,
        )
        with self.assertRaises(ValidationError) as e:
            instance.full_clean()
        self.assertEqual(len(e.exception.error_dict), 1)
        self.assertIn("uploader_group", e.exception.error_dict)
        self.assertEqual(len(e.exception.error_dict["uploader_group"]), 1)
        self.assertIn("already exists", str(e.exception.error_dict["uploader_group"][0]))


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
        self.assertIsNone(instance.date_ready_for_compute)

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

    def test_model_order(self):
        """Models are ordered by cycle."""
        instance_1 = factories.UploadCycleFactory.create(cycle=2)
        instance_2 = factories.UploadCycleFactory.create(cycle=1)
        qs = models.UploadCycle.objects.all()
        self.assertEqual(qs[0], instance_2)
        self.assertEqual(qs[1], instance_1)

    def test_get_absolute_url(self):
        """The get_absolute_url() method works."""
        instance = factories.UploadCycleFactory()
        self.assertIsInstance(instance.get_absolute_url(), str)

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
        instance_2 = factories.UploadCycleFactory.build(start_date=same_date, end_date=same_date)
        with self.assertRaises(ValidationError) as e:
            instance_2.full_clean()
        self.assertEqual(len(e.exception.message_dict), 1)
        self.assertIn(NON_FIELD_ERRORS, e.exception.message_dict)
        self.assertEqual(len(e.exception.error_dict[NON_FIELD_ERRORS]), 1)
        self.assertIn("end_date", e.exception.message_dict[NON_FIELD_ERRORS][0])
        self.assertIn("after start_date", e.exception.message_dict[NON_FIELD_ERRORS][0])

    def test_start_date_after_date_ready_for_compute(self):
        today = date.today()
        instance = factories.UploadCycleFactory.build(
            start_date=today + timedelta(days=1),
            end_date=today + timedelta(days=10),
            date_ready_for_compute=today,
        )
        with self.assertRaises(ValidationError) as e:
            instance.full_clean()
        self.assertEqual(len(e.exception.message_dict), 1)
        self.assertIn(NON_FIELD_ERRORS, e.exception.message_dict)
        self.assertEqual(len(e.exception.error_dict[NON_FIELD_ERRORS]), 1)
        self.assertIn("date_ready_for_compute", e.exception.message_dict[NON_FIELD_ERRORS][0])
        self.assertIn("after start_date", e.exception.message_dict[NON_FIELD_ERRORS][0])

    def test_date_ready_for_compute_after_end_date(self):
        today = date.today()
        instance = factories.UploadCycleFactory.build(
            start_date=today,
            end_date=today + timedelta(days=10),
            date_ready_for_compute=today + timedelta(days=11),
        )
        with self.assertRaises(ValidationError) as e:
            instance.full_clean()
        self.assertEqual(len(e.exception.message_dict), 1)
        self.assertIn(NON_FIELD_ERRORS, e.exception.message_dict)
        self.assertEqual(len(e.exception.error_dict[NON_FIELD_ERRORS]), 1)
        self.assertIn("date_ready_for_compute", e.exception.message_dict[NON_FIELD_ERRORS][0])
        self.assertIn("before end_date", e.exception.message_dict[NON_FIELD_ERRORS][0])

    def test_get_partner_upload_workspaces_no_date_completed(self):
        """PartnerUploadWorkspace with no date_completed is not included."""
        upload_cycle = factories.UploadCycleFactory.create()
        factories.PartnerUploadWorkspaceFactory.create(date_completed=None)
        included_workspaces = upload_cycle.get_partner_upload_workspaces()
        self.assertEqual(included_workspaces.count(), 0)

    def test_get_partner_uplod_workspaces_with_date_completed(self):
        """PartnerUploadWorkspace with date_completed before UploadCycle end_date is included."""
        upload_cycle = factories.UploadCycleFactory.create()
        workspace = factories.PartnerUploadWorkspaceFactory.create(
            date_completed=upload_cycle.end_date - timedelta(days=4)
        )
        included_workspaces = upload_cycle.get_partner_upload_workspaces()
        self.assertEqual(included_workspaces.count(), 1)
        self.assertIn(workspace, included_workspaces)

    def test_get_partner_upload_workspaces_with_date_completed_after_end_date(self):
        """PartnerUploadWorkspace with date_completed after UploadCycle end_date is not included."""
        upload_cycle = factories.UploadCycleFactory.create()
        factories.PartnerUploadWorkspaceFactory.create(date_completed=upload_cycle.end_date + timedelta(days=4))
        included_workspaces = upload_cycle.get_partner_upload_workspaces()
        self.assertEqual(included_workspaces.count(), 0)

    def test_get_partner_upload_workspaces_with_date_completed_equal_to_end_date(self):
        """PartnerUploadWorkspace with date_completed equal to UploadCycle end_date is included."""
        upload_cycle = factories.UploadCycleFactory.create()
        workspace = factories.PartnerUploadWorkspaceFactory.create(date_completed=upload_cycle.end_date)
        included_workspaces = upload_cycle.get_partner_upload_workspaces()
        self.assertEqual(included_workspaces.count(), 1)
        self.assertIn(workspace, included_workspaces)

    def test_get_partner_upload_workspaces_higher_versions_with_date_completed(self):
        """Only the highest version is included when two PartnerUploadWorkspaces have date_completed."""
        upload_cycle = factories.UploadCycleFactory.create()
        workspace_1 = factories.PartnerUploadWorkspaceFactory.create(
            version=1, date_completed=upload_cycle.end_date - timedelta(days=4)
        )
        workspace_2 = factories.PartnerUploadWorkspaceFactory.create(
            partner_group=workspace_1.partner_group,
            consent_group=workspace_1.consent_group,
            version=2,
            date_completed=upload_cycle.end_date - timedelta(days=3),
        )
        included_workspaces = upload_cycle.get_partner_upload_workspaces()
        self.assertEqual(included_workspaces.count(), 1)
        self.assertNotIn(workspace_1, included_workspaces)
        self.assertIn(workspace_2, included_workspaces)

    def test_get_partner_upload_workspaces_higher_version_no_date_completed(self):
        """PartnerUploadWorkspaces with higher versions and no date_completed are not included."""
        upload_cycle = factories.UploadCycleFactory.create()
        workspace_1 = factories.PartnerUploadWorkspaceFactory.create(
            version=1, date_completed=upload_cycle.end_date - timedelta(days=4)
        )
        workspace_2 = factories.PartnerUploadWorkspaceFactory.create(
            partner_group=workspace_1.partner_group,
            consent_group=workspace_1.consent_group,
            version=2,
            date_completed=None,
        )
        included_workspaces = upload_cycle.get_partner_upload_workspaces()
        self.assertEqual(included_workspaces.count(), 1)
        self.assertIn(workspace_1, included_workspaces)
        self.assertNotIn(workspace_2, included_workspaces)

    def test_get_partner_upload_workspaces_different_partner_groups(self):
        """PartnerUploadWorkspaces with different PartnerGroups are both included."""
        upload_cycle = factories.UploadCycleFactory.create()
        workspace_1 = factories.PartnerUploadWorkspaceFactory.create(
            version=1, date_completed=upload_cycle.end_date - timedelta(days=4)
        )
        workspace_2 = factories.PartnerUploadWorkspaceFactory.create(
            consent_group=workspace_1.consent_group,
            version=2,
            date_completed=upload_cycle.end_date - timedelta(days=3),
        )
        included_workspaces = upload_cycle.get_partner_upload_workspaces()
        self.assertEqual(included_workspaces.count(), 2)
        self.assertIn(workspace_1, included_workspaces)
        self.assertIn(workspace_2, included_workspaces)

    def test_get_partner_upload_workspaces_different_consent_groups(self):
        """PartnerUploadWorkspaces with different ConsentGroups are both included."""

    def test_get_partner_upload_workspaces_full_test(self):
        upload_cycle = factories.UploadCycleFactory.create()
        workspace_1 = factories.PartnerUploadWorkspaceFactory.create(
            version=1, date_completed=upload_cycle.end_date - timedelta(days=4)
        )
        workspace_2 = factories.PartnerUploadWorkspaceFactory.create(
            partner_group=workspace_1.partner_group,
            consent_group=workspace_1.consent_group,
            version=2,
            date_completed=upload_cycle.end_date - timedelta(days=3),
        )
        workspace_3 = factories.PartnerUploadWorkspaceFactory.create(
            version=1, date_completed=upload_cycle.end_date - timedelta(days=2)
        )
        workspace_4 = factories.PartnerUploadWorkspaceFactory.create(
            partner_group=workspace_3.partner_group,
            consent_group=workspace_3.consent_group,
            version=2,
            date_completed=None,
        )
        included_workspaces = upload_cycle.get_partner_upload_workspaces()
        self.assertEqual(included_workspaces.count(), 2)
        self.assertNotIn(workspace_1, included_workspaces)
        self.assertIn(workspace_2, included_workspaces)
        self.assertIn(workspace_3, included_workspaces)
        self.assertNotIn(workspace_4, included_workspaces)

    def test_date_ready_for_compute(self):
        """UploadCycle is ready for compute if all PartnerUploadWorkspaces have date_completed."""
        upload_cycle = factories.UploadCycleFactory.create()
        self.assertIsNone(upload_cycle.date_ready_for_compute)
        date = timezone.localdate()
        upload_cycle.date_ready_for_compute = date
        upload_cycle.save()
        self.assertEqual(upload_cycle.date_ready_for_compute, date)

    def test_is_current_is_past_is_future(self):
        # Previous cycle.
        instance = factories.UploadCycleFactory.create(
            start_date=timezone.localdate() - timedelta(days=40),
            end_date=timezone.localdate() - timedelta(days=10),
        )
        self.assertTrue(instance.is_past)
        self.assertFalse(instance.is_current)
        self.assertFalse(instance.is_future)
        # Current cycle, end date today.
        instance = factories.UploadCycleFactory.create(
            start_date=timezone.localdate() - timedelta(days=10),
            end_date=timezone.localdate(),
        )
        self.assertFalse(instance.is_past)
        self.assertTrue(instance.is_current)
        self.assertFalse(instance.is_future)
        # Current cycle.
        instance = factories.UploadCycleFactory.create(
            start_date=timezone.localdate() - timedelta(days=10),
            end_date=timezone.localdate() + timedelta(days=10),
        )
        self.assertFalse(instance.is_past)
        self.assertTrue(instance.is_current)
        self.assertFalse(instance.is_future)
        # Current cycle, start date today.
        instance = factories.UploadCycleFactory.create(
            start_date=timezone.localdate(),
            end_date=timezone.localdate() + timedelta(days=10),
        )
        self.assertFalse(instance.is_past)
        self.assertTrue(instance.is_current)
        self.assertFalse(instance.is_future)
        # Future cycle.
        instance = factories.UploadCycleFactory.create(
            start_date=timezone.localdate() + timedelta(days=10),
            end_date=timezone.localdate() + timedelta(days=40),
        )
        self.assertFalse(instance.is_past)
        self.assertFalse(instance.is_current)
        self.assertTrue(instance.is_future)


class UploadWorkspaceTest(TestCase):
    """Tests for the UploadWorkspace model."""

    def test_model_saving(self):
        """Creation using the model constructor and .save() works."""
        research_center = factories.ResearchCenterFactory.create()
        consent_group = factories.ConsentGroupFactory.create()
        upload_cycle = factories.UploadCycleFactory.create()
        workspace = WorkspaceFactory.create()
        instance = models.UploadWorkspace(
            research_center=research_center,
            consent_group=consent_group,
            workspace=workspace,
            upload_cycle=upload_cycle,
        )
        instance.save()
        self.assertIsInstance(instance, models.UploadWorkspace)
        self.assertIsNone(instance.date_qc_completed)

    def test_str_method(self):
        """The custom __str__ method returns the correct string."""
        instance = factories.UploadWorkspaceFactory.create()
        instance.save()
        self.assertIsInstance(instance.__str__(), str)
        self.assertEqual(instance.__str__(), instance.workspace.name)

    def test_unique_constraint(self):
        """Cannot save two instances with the same ResearchCenter, ConsentGroup, and version."""
        instance_1 = factories.UploadWorkspaceFactory.create()
        workspace = WorkspaceFactory.create()
        instance_2 = factories.UploadWorkspaceFactory.build(
            research_center=instance_1.research_center,
            consent_group=instance_1.consent_group,
            workspace=workspace,
            upload_cycle=instance_1.upload_cycle,
        )
        with self.assertRaises(ValidationError):
            instance_2.full_clean()
        with self.assertRaises(IntegrityError):
            instance_2.save()

    def test_same_research_center(self):
        """Can save multiple UploadWorkspace models with the same ResearchCenter."""
        instance_1 = factories.UploadWorkspaceFactory.create()
        upload_cycle = factories.UploadCycleFactory.create()
        consent_group = factories.ConsentGroupFactory.create()
        workspace = WorkspaceFactory.create()
        instance_2 = factories.UploadWorkspaceFactory.build(
            research_center=instance_1.research_center,
            consent_group=consent_group,
            workspace=workspace,
            upload_cycle=upload_cycle,
        )
        instance_2.full_clean()
        instance_2.save()
        self.assertEqual(models.UploadWorkspace.objects.count(), 2)

    def test_same_consent_group(self):
        """Can save multiple UploadWorkspace models with the same ConsentGroup."""
        instance_1 = factories.UploadWorkspaceFactory.create()
        research_center = factories.ResearchCenterFactory.create()
        upload_cycle = factories.UploadCycleFactory.create()
        workspace = WorkspaceFactory.create()
        instance_2 = factories.UploadWorkspaceFactory.build(
            research_center=research_center,
            consent_group=instance_1.consent_group,
            workspace=workspace,
            upload_cycle=upload_cycle,
        )
        instance_2.full_clean()
        instance_2.save()
        self.assertEqual(models.UploadWorkspace.objects.count(), 2)

    def test_same_upload_cycle(self):
        """Can save multiple UploadWorkspace models with the same upload_cycle."""
        instance_1 = factories.UploadWorkspaceFactory.create()
        research_center = factories.ResearchCenterFactory.create()
        consent_group = factories.ConsentGroupFactory.create()
        workspace = WorkspaceFactory.create()
        instance_2 = factories.UploadWorkspaceFactory.build(
            research_center=research_center,
            consent_group=consent_group,
            workspace=workspace,
            upload_cycle=instance_1.upload_cycle,
        )
        instance_2.full_clean()
        instance_2.save()
        self.assertEqual(models.UploadWorkspace.objects.count(), 2)

    def test_duplicated_workspace(self):
        """One workspace cannot be associated with two UploadWorkspace models."""
        instance_1 = factories.UploadWorkspaceFactory.create()
        research_center = factories.ResearchCenterFactory.create()
        upload_cycle = factories.UploadCycleFactory.create()
        consent_group = factories.ConsentGroupFactory.create()
        instance_2 = factories.UploadWorkspaceFactory.build(
            research_center=research_center,
            consent_group=consent_group,
            workspace=instance_1.workspace,
            upload_cycle=upload_cycle,
        )
        with self.assertRaises(ValidationError):
            instance_2.full_clean()
        with self.assertRaises(IntegrityError):
            instance_2.save()


class PartnerGroupTest(TestCase):
    """Tests for the ResearchCenter model."""

    def test_model_saving(self):
        """Creation using the model constructor and .save() works."""
        instance = models.PartnerGroup(
            full_name="Test name",
            short_name="TEST",
        )
        instance.full_clean()
        instance.save()
        self.assertIsInstance(instance, models.PartnerGroup)

    def test_model_saving_with_groups(self):
        """Creation using the model constructor and .save() works."""
        member_group = ManagedGroupFactory.create()
        uploader_group = ManagedGroupFactory.create()
        instance = models.PartnerGroup(
            full_name="Test name",
            short_name="TEST",
            member_group=member_group,
            uploader_group=uploader_group,
        )
        instance.full_clean()
        instance.save()
        self.assertIsInstance(instance, models.PartnerGroup)

    def test_str_method(self):
        """The custom __str__ method returns the correct string."""
        instance = factories.PartnerGroupFactory.create(short_name="Test")
        instance.save()
        self.assertIsInstance(instance.__str__(), str)
        self.assertEqual(instance.__str__(), "Test")

    def test_get_absolute_url(self):
        """The get_absolute_url() method works."""
        instance = factories.PartnerGroupFactory()
        self.assertIsInstance(instance.get_absolute_url(), str)

    def test_unique_short_name(self):
        """Saving a model with a duplicate short name fails."""
        factories.PartnerGroupFactory.create(short_name="FOO")
        instance2 = models.PartnerGroup(short_name="FOO", full_name="full name")
        with self.assertRaises(ValidationError):
            instance2.full_clean()
        with self.assertRaises(IntegrityError):
            instance2.save()

    def test_member_group_uploader_group_must_be_different(self):
        """The same group cannot be used as the members group and uploaders group."""
        group = ManagedGroupFactory.create()
        instance = models.PartnerGroup(
            full_name="Test name",
            short_name="TEST",
            member_group=group,
            uploader_group=group,
        )
        with self.assertRaises(ValidationError) as e:
            instance.full_clean()
        self.assertEqual(len(e.exception.error_dict), 1)
        self.assertIn(NON_FIELD_ERRORS, e.exception.error_dict)
        self.assertEqual(len(e.exception.error_dict[NON_FIELD_ERRORS]), 1)
        self.assertIn("must be different", str(e.exception.error_dict[NON_FIELD_ERRORS][0]))

    def test_error_two_groups_same_member_group(self):
        """Cannot have the same member group for two RCs."""
        member_group = ManagedGroupFactory.create()
        factories.PartnerGroupFactory.create(member_group=member_group)
        instance = factories.PartnerGroupFactory.build(
            full_name="Test name",
            short_name="TEST",
            member_group=member_group,
        )
        with self.assertRaises(ValidationError) as e:
            instance.full_clean()
        self.assertEqual(len(e.exception.error_dict), 1)
        self.assertIn("member_group", e.exception.error_dict)
        self.assertEqual(len(e.exception.error_dict["member_group"]), 1)
        self.assertIn("already exists", str(e.exception.error_dict["member_group"][0]))

    def test_error_two_groups_same_uploader_group(self):
        """Cannot have the same uploader group for two RCs."""
        uploader_group = ManagedGroupFactory.create()
        factories.PartnerGroupFactory.create(uploader_group=uploader_group)
        instance = factories.PartnerGroupFactory.build(
            full_name="Test name",
            short_name="TEST",
            uploader_group=uploader_group,
        )
        with self.assertRaises(ValidationError) as e:
            instance.full_clean()
        self.assertEqual(len(e.exception.error_dict), 1)
        self.assertIn("uploader_group", e.exception.error_dict)
        self.assertEqual(len(e.exception.error_dict["uploader_group"]), 1)
        self.assertIn("already exists", str(e.exception.error_dict["uploader_group"][0]))


class PartnerUploadWorkspaceTest(TestCase):
    """Tests for the PartnerUploadWorkspace model."""

    def test_model_saving(self):
        """Creation using the model constructor and .save() works."""
        partner_group = factories.PartnerGroupFactory.create()
        consent_group = factories.ConsentGroupFactory.create()
        workspace = WorkspaceFactory.create()
        instance = models.PartnerUploadWorkspace(
            partner_group=partner_group,
            consent_group=consent_group,
            workspace=workspace,
            version=1,
        )
        instance.save()
        self.assertIsInstance(instance, models.PartnerUploadWorkspace)

    def test_str_method(self):
        """The custom __str__ method returns the correct string."""
        instance = factories.PartnerUploadWorkspaceFactory.create()
        instance.save()
        self.assertIsInstance(instance.__str__(), str)
        self.assertEqual(instance.__str__(), instance.workspace.__str__())

    def test_date_completed(self):
        instance = factories.PartnerUploadWorkspaceFactory.create(date_completed=date.today())
        instance.save()
        self.assertIsNotNone(instance.date_completed)

    def test_unique_constraint(self):
        """Cannot save two instances with the same ResearchCenter, ConsentGroup, and version."""
        instance_1 = factories.PartnerUploadWorkspaceFactory.create()
        workspace = WorkspaceFactory.create()
        instance_2 = factories.PartnerUploadWorkspaceFactory.build(
            partner_group=instance_1.partner_group,
            consent_group=instance_1.consent_group,
            workspace=workspace,
            version=instance_1.version,
        )
        with self.assertRaises(ValidationError) as e:
            instance_2.full_clean()
        self.assertEqual(len(e.exception.error_dict), 1)
        self.assertIn(NON_FIELD_ERRORS, e.exception.error_dict)
        self.assertEqual(len(e.exception.error_dict[NON_FIELD_ERRORS]), 1)
        with self.assertRaises(IntegrityError):
            instance_2.save()

    def test_different_partner_group(self):
        """Can save two instances with different PartnerGroups and the same version/consent_group."""
        instance_1 = factories.PartnerUploadWorkspaceFactory.create()
        partner_group = factories.PartnerGroupFactory.create()
        workspace = WorkspaceFactory.create()
        instance_2 = factories.PartnerUploadWorkspaceFactory.build(
            partner_group=partner_group,
            consent_group=instance_1.consent_group,
            workspace=workspace,
            version=instance_1.version,
        )
        instance_2.full_clean()
        instance_2.save()
        self.assertEqual(models.PartnerUploadWorkspace.objects.count(), 2)

    def test_different_consent_group(self):
        """Can save two instances with different ConsentGroups and the same version and partner group."""
        instance_1 = factories.PartnerUploadWorkspaceFactory.create()
        consent_group = factories.ConsentGroupFactory.create()
        workspace = WorkspaceFactory.create()
        instance_2 = factories.PartnerUploadWorkspaceFactory.build(
            partner_group=instance_1.partner_group,
            consent_group=consent_group,
            workspace=workspace,
            version=instance_1.version,
        )
        instance_2.full_clean()
        instance_2.save()
        self.assertEqual(models.PartnerUploadWorkspace.objects.count(), 2)

    def test_different_upload_cycle(self):
        """Can save two instances models with different versions and the same partner group and consent group."""
        instance_1 = factories.PartnerUploadWorkspaceFactory.create()
        workspace = WorkspaceFactory.create()
        instance_2 = factories.PartnerUploadWorkspaceFactory.build(
            partner_group=instance_1.partner_group,
            consent_group=instance_1.consent_group,
            workspace=workspace,
            version=instance_1.version + 1,
        )
        instance_2.full_clean()
        instance_2.save()
        self.assertEqual(models.PartnerUploadWorkspace.objects.count(), 2)

    def test_duplicated_workspace(self):
        """One workspace cannot be associated with two PartnerUploadWorkspace models."""
        instance_1 = factories.PartnerUploadWorkspaceFactory.create()
        partner_group = factories.PartnerGroupFactory.create()
        consent_group = factories.ConsentGroupFactory.create()
        instance_2 = factories.PartnerUploadWorkspaceFactory.build(
            partner_group=partner_group,
            consent_group=consent_group,
            workspace=instance_1.workspace,
            version=instance_1.version + 1,
        )
        with self.assertRaises(ValidationError) as e:
            instance_2.full_clean()
        self.assertEqual(len(e.exception.error_dict), 1)
        self.assertIn("workspace", e.exception.error_dict)
        self.assertEqual(len(e.exception.error_dict["workspace"]), 1)
        with self.assertRaises(IntegrityError):
            instance_2.save()


class ResourceWorkspaceTest(TestCase):
    """Tests for the ResourceWorkspace model."""

    def test_model_saving(self):
        """Creation using the model constructor and .save() works."""
        workspace = WorkspaceFactory.create()
        instance = models.ResourceWorkspace(workspace=workspace)
        instance.save()
        self.assertIsInstance(instance, models.ResourceWorkspace)

    def test_str_method(self):
        workspace = WorkspaceFactory.create(billing_project__name="test-bp", name="test-ws")
        instance = factories.ResourceWorkspaceFactory.create(workspace=workspace)
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
        workspace = WorkspaceFactory.create(billing_project__name="test-bp", name="test-ws")
        instance = factories.TemplateWorkspaceFactory.create(workspace=workspace)
        self.assertIsInstance(str(instance), str)
        self.assertEqual(str(instance), "test-bp/test-ws")


class CombinedConsortiumDataWorkspaceTest(TestCase):
    """Tests for the CombinedConsortiumDataWorkspace model."""

    def test_model_saving(self):
        """Creation using the model constructor and .save() works."""
        workspace = WorkspaceFactory.create()
        upload_cycle = factories.UploadCycleFactory.create()
        instance = models.CombinedConsortiumDataWorkspace(workspace=workspace, upload_cycle=upload_cycle)
        instance.save()
        self.assertIsInstance(instance, models.CombinedConsortiumDataWorkspace)

    def test_str_method(self):
        """The custom __str__ method returns the correct string."""
        instance = factories.CombinedConsortiumDataWorkspaceFactory.create()
        instance.save()
        self.assertIsInstance(instance.__str__(), str)
        self.assertEqual(instance.__str__(), instance.workspace.__str__())


class ReleaseWorkspaceTest(TestCase):
    """Tests for the ReleaseWorkspace model."""

    def test_model_saving(self):
        """Creation using the model constructor and .save() works."""
        workspace = WorkspaceFactory.create()
        upload_cycle = factories.UploadCycleFactory.create()
        consent_group = factories.ConsentGroupFactory.create()
        instance = models.ReleaseWorkspace(
            workspace=workspace,
            upload_cycle=upload_cycle,
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

    def test_unique_constraint(self):
        """Cannot save two instances with the same ConsentGroup and upload_cycle."""
        instance_1 = factories.ReleaseWorkspaceFactory.create()
        workspace_2 = WorkspaceFactory.create(name="ws-2")
        instance_2 = factories.ReleaseWorkspaceFactory.build(
            workspace=workspace_2,
            consent_group=instance_1.consent_group,
            upload_cycle=instance_1.upload_cycle,
        )
        with self.assertRaises(ValidationError):
            instance_2.full_clean()
        with self.assertRaises(IntegrityError):
            instance_2.save()

    def test_same_consent_group(self):
        """Can save multiple ReleaseWorkspace models with the same ConsentGroup and different upload_cycle."""
        instance_1 = factories.ReleaseWorkspaceFactory.create()
        workspace_2 = WorkspaceFactory.create(name="ws-2")
        upload_cycle = factories.UploadCycleFactory.create()
        instance_2 = factories.ReleaseWorkspaceFactory.build(
            workspace=workspace_2,
            consent_group=instance_1.consent_group,
            upload_cycle=upload_cycle,
        )
        instance_2.full_clean()
        instance_2.save()
        self.assertEqual(models.ReleaseWorkspace.objects.count(), 2)

    def test_same_dbgap_version(self):
        """Can save multiple ReleaseWorkspace models with the same upload_cycle and different ConsentGroup."""
        instance_1 = factories.ReleaseWorkspaceFactory.create()
        workspace_2 = WorkspaceFactory.create(name="ws-2")
        consent_group_2 = factories.ConsentGroupFactory()
        instance_2 = factories.ReleaseWorkspaceFactory.build(
            workspace=workspace_2,
            consent_group=consent_group_2,
            upload_cycle=instance_1.upload_cycle,
        )
        instance_2.full_clean()
        instance_2.save()
        self.assertEqual(models.ReleaseWorkspace.objects.count(), 2)

    def test_positive_dbgap_version_not_negative(self):
        """Version cannot be negative."""
        consent_group = factories.ConsentGroupFactory.create()
        workspace = WorkspaceFactory.create(name="ws")
        upload_cycle = factories.UploadCycleFactory.create()
        instance = factories.ReleaseWorkspaceFactory.build(
            consent_group=consent_group,
            workspace=workspace,
            upload_cycle=upload_cycle,
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
        upload_cycle = factories.UploadCycleFactory.create()
        instance = factories.ReleaseWorkspaceFactory.build(
            consent_group=consent_group,
            workspace=workspace,
            upload_cycle=upload_cycle,
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
        upload_cycle = factories.UploadCycleFactory.create()
        instance = factories.ReleaseWorkspaceFactory.build(
            consent_group=consent_group,
            workspace=workspace,
            upload_cycle=upload_cycle,
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
        upload_cycle = factories.UploadCycleFactory.create()
        instance = factories.ReleaseWorkspaceFactory.build(
            consent_group=consent_group,
            workspace=workspace,
            upload_cycle=upload_cycle,
            dbgap_participant_set=0,
        )
        with self.assertRaises(ValidationError) as e:
            instance.full_clean()
        self.assertEqual(len(e.exception.error_dict), 1)
        self.assertIn("dbgap_participant_set", e.exception.error_dict)
        self.assertEqual(len(e.exception.error_dict["dbgap_participant_set"]), 1)

    def test_get_dbgap_accession(self):
        """get_dbgap_accession works as expected."""
        instance = factories.ReleaseWorkspaceFactory.create(dbgap_version=1, dbgap_participant_set=2)
        self.assertEqual(instance.get_dbgap_accession(), "phs003047.v1.p2")


class DCCProcessingWorkspaceTest(TestCase):
    """Tests for the DCCProcessingWorkspace model."""

    def test_model_saving(self):
        """Creation using the model constructor and .save() works."""
        workspace = WorkspaceFactory.create()
        upload_cycle = factories.UploadCycleFactory.create()
        instance = models.DCCProcessingWorkspace(
            upload_cycle=upload_cycle,
            purpose="foo",
            workspace=workspace,
        )
        instance.save()
        self.assertIsInstance(instance, models.DCCProcessingWorkspace)

    def test_str_method(self):
        """The custom __str__ method returns the correct string."""
        instance = factories.DCCProcessingWorkspaceFactory.create()
        instance.save()
        self.assertIsInstance(instance.__str__(), str)
        self.assertEqual(instance.__str__(), instance.workspace.__str__())

    def test_two_workspaces_same_upload_cycle(self):
        """Can have two workspaces with the same upload cycle."""
        dcc_processing_workspace = factories.DCCProcessingWorkspaceFactory.create()
        workspace = WorkspaceFactory.create()
        instance = factories.DCCProcessingWorkspaceFactory.build(
            upload_cycle=dcc_processing_workspace.upload_cycle,
            workspace=workspace,
        )
        instance.full_clean()
        instance.save()
        self.assertEqual(models.DCCProcessingWorkspace.objects.count(), 2)


class DCCProcessedDataWorkspaceTest(TestCase):
    """Tests for the DCCProcessedDataWorkspace model."""

    def test_model_saving(self):
        """Creation using the model constructor and .save() works."""
        upload_cycle = factories.UploadCycleFactory.create()
        consent_group = factories.ConsentGroupFactory.create()
        workspace = WorkspaceFactory.create()
        instance = models.DCCProcessedDataWorkspace(
            consent_group=consent_group,
            upload_cycle=upload_cycle,
            workspace=workspace,
        )
        instance.save()
        self.assertIsInstance(instance, models.DCCProcessedDataWorkspace)

    def test_str_method(self):
        """The custom __str__ method returns the correct string."""
        instance = factories.DCCProcessedDataWorkspaceFactory.create()
        instance.save()
        self.assertIsInstance(instance.__str__(), str)
        self.assertEqual(instance.__str__(), instance.workspace.__str__())

    def test_unique(self):
        """Cannot have two workspaces with the same upload cycle and consent group."""
        dcc_processed_data_workspace = factories.DCCProcessedDataWorkspaceFactory.create()
        workspace = WorkspaceFactory.create()
        instance = factories.DCCProcessedDataWorkspaceFactory.build(
            upload_cycle=dcc_processed_data_workspace.upload_cycle,
            consent_group=dcc_processed_data_workspace.consent_group,
            workspace=workspace,
        )
        with self.assertRaises(ValidationError) as e:
            instance.full_clean()
        self.assertEqual(len(e.exception.error_dict), 1)
        self.assertIn(NON_FIELD_ERRORS, e.exception.error_dict)
        self.assertEqual(len(e.exception.error_dict[NON_FIELD_ERRORS]), 1)
        with self.assertRaises(IntegrityError):
            instance.save()


class ExchangeWorkspaceTest(TestCase):
    """Tests for the ExchangeWorkspace model."""

    def test_model_saving(self):
        """Creation using the model constructor and .save() works."""
        research_center = factories.ResearchCenterFactory.create()
        workspace = WorkspaceFactory.create()
        instance = models.ExchangeWorkspace(
            research_center=research_center,
            workspace=workspace,
        )
        instance.save()
        self.assertIsInstance(instance, models.ExchangeWorkspace)

    def test_str_method(self):
        """The custom __str__ method returns the correct string."""
        instance = factories.ExchangeWorkspaceFactory.create()
        instance.save()
        self.assertIsInstance(instance.__str__(), str)
        self.assertEqual(instance.__str__(), instance.workspace.__str__())

    def test_unique_constraint(self):
        """Cannot save two instances with the same ResearchCenter."""
        instance_1 = factories.ExchangeWorkspaceFactory.create()
        workspace = WorkspaceFactory.create()
        instance_2 = factories.ExchangeWorkspaceFactory.build(
            research_center=instance_1.research_center,
            workspace=workspace,
        )
        with self.assertRaises(ValidationError):
            instance_2.full_clean()
        with self.assertRaises(IntegrityError):
            instance_2.save()

    def test_duplicated_workspace(self):
        """One workspace cannot be associated with two UploadWorkspace models."""
        instance_1 = factories.ExchangeWorkspaceFactory.create()
        research_center = factories.ResearchCenterFactory.create()
        instance_2 = factories.ExchangeWorkspaceFactory.build(
            research_center=research_center,
            workspace=instance_1.workspace,
        )
        with self.assertRaises(ValidationError):
            instance_2.full_clean()
        with self.assertRaises(IntegrityError):
            instance_2.save()
