from anvil_consortium_manager.tests.factories import WorkspaceFactory
from django.core.exceptions import ValidationError
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
        instance = factories.UploadWorkspaceFactory.create(
            research_center__short_name="TestRC", consent_group__code="GRU", version=1
        )
        instance.save()
        self.assertIsInstance(instance.__str__(), str)
        self.assertEqual(instance.__str__(), "TestRC - GRU - v1")

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
