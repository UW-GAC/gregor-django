from django.core.exceptions import ValidationError
from django.db.utils import IntegrityError
from django.test import TestCase

from anvil_consortium_manager.tests import factories as acm_factories
from .. import models
from . import factories


class ConsentGroupTest(TestCase):
    """Tests for the ConsentGroup model."""

    def test_model_saving(self):
        """Creation using the model constructor and .save() works."""
        instance = models.ConsentGroup(code=models.ConsentGroup.GRU, data_use_limitations="test limitations")
        instance.save()
        self.assertIsInstance(instance, models.ConsentGroup)

    def test_str_method(self):
        """The custom __str__ method returns the correct string."""
        instance = factories.ConsentGroupFactory.create(code=models.ConsentGroup.GRU)
        instance.save()
        self.assertIsInstance(instance.__str__(), str)
        self.assertEqual(instance.__str__(), models.ConsentGroup.GRU)

    # def test_get_absolute_url(self):
    #     """The get_absolute_url() method works."""
    #     instance = factories.ConsentGroupFactory()
    #     self.assertIsInstance(instance.get_absolute_url(), str)

    def test_unique_code(self):
        """Saving a model with a duplicate code fails."""
        instance1 = models.ConsentGroup(code=models.ConsentGroup.GRU, data_use_limitations="test limitations 1")
        instance1.save()
        instance2 = models.ConsentGroup(code=models.ConsentGroup.GRU, data_use_limitations="test limitations 2")
        with self.assertRaises(ValidationError):
            instance2.full_clean()
        with self.assertRaises(IntegrityError):
            instance2.save()

    def test_invalid_code(self):
        """Cleaning a model with an invalid code fails."""
        instance = models.ConsentGroup(code="FOO", data_use_limitations="test limitations")
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

    # def test_get_absolute_url(self):
    #     """The get_absolute_url() method works."""
    #     instance = factories.ConsentGroupFactory()
    #     self.assertIsInstance(instance.get_absolute_url(), str)

    def test_unique_short_name(self):
        """Saving a model with a duplicate short name fails."""
        instance1 = factories.ResearchCenterFactory.create(short_name="FOO")
        instance2 = models.ResearchCenter(short_name="FOO", full_name="full name")
        with self.assertRaises(ValidationError):
            instance2.full_clean()
        with self.assertRaises(IntegrityError):
            instance2.save()


class WorkspaceDataTest(TestCase):
    """Tests for the WorkspaceData model."""

    def test_model_saving(self):
        """Creation using the model constructor and .save() works."""
        research_center = factories.ResearchCenterFactory.create()
        consent_group = factories.ConsentGroupFactory.create()
        workspace = acm_factories.WorkspaceFactory.create()
        instance = models.WorkspaceData(research_center=research_center, consent_group=consent_group, workspace=workspace, version=1)
        instance.save()
        self.assertIsInstance(instance, models.WorkspaceData)

    def test_str_method(self):
        """The custom __str__ method returns the correct string."""
        instance = factories.WorkspaceDataFactory.create()
        instance.save()
        self.assertIsInstance(instance.__str__(), str)
        self.assertEqual(instance.__str__(), instance.workspace.__str__())

    def test_unique_constraint(self):
        """Cannot save two instances with the same ResearchCenter, ConsentGroup, and version."""
        research_center = factories.ResearchCenterFactory.create()
        consent_group = factories.ConsentGroupFactory.create()
        workspace_1 = acm_factories.WorkspaceFactory.create(name="ws-1")
        workspace_2 = acm_factories.WorkspaceFactory.create(name="ws-2")
        instance_1 = models.WorkspaceData(research_center=research_center, consent_group=consent_group, workspace=workspace_1, version=1)
        instance_1.save()
        instance_2 = models.WorkspaceData(research_center=research_center, consent_group=consent_group, workspace=workspace_2, version=1)
        with self.assertRaises(ValidationError):
            instance_2.full_clean()
        with self.assertRaises(IntegrityError):
            instance_2.save()

    def test_same_research_center(self):
        """Can save multiple WorkspaceData models with the same ResearchCenter."""
        research_center = factories.ResearchCenterFactory()
        consent_group_1 = factories.ConsentGroupFactory(code=models.ConsentGroup.GRU)
        consent_group_2 = factories.ConsentGroupFactory(code=models.ConsentGroup.HMB)
        workspace_1 = acm_factories.WorkspaceFactory.create()
        workspace_2 = acm_factories.WorkspaceFactory.create()
        instance_1 = models.WorkspaceData(research_center=research_center, consent_group=consent_group_1, workspace=workspace_1, version=1)
        instance_1.save()
        instance_2 = models.WorkspaceData(research_center=research_center, consent_group=consent_group_2, workspace=workspace_2, version=1)
        instance_2.full_clean()
        instance_2.save()
        self.assertEqual(models.WorkspaceData.objects.count(), 2)

    def test_same_consent_group(self):
        """Can save multiple WorkspaceData models with the same ConsentGroup."""
        consent_group = factories.ConsentGroupFactory(code=models.ConsentGroup.GRU)
        research_center_1 = factories.ResearchCenterFactory()
        research_center_2 = factories.ResearchCenterFactory()
        workspace_1 = acm_factories.WorkspaceFactory.create()
        workspace_2 = acm_factories.WorkspaceFactory.create()
        instance_1 = models.WorkspaceData(research_center=research_center_1, consent_group=consent_group, workspace=workspace_1, version=1)
        instance_1.save()
        instance_2 = models.WorkspaceData(research_center=research_center_2, consent_group=consent_group, workspace=workspace_2, version=1)
        instance_2.full_clean()
        instance_2.save()
        self.assertEqual(models.WorkspaceData.objects.count(), 2)

    def test_same_version(self):
        """Can save multiple WorkspaceData models with the same version."""
        consent_group = factories.ConsentGroupFactory(code=models.ConsentGroup.GRU)
        research_center = factories.ResearchCenterFactory()
        workspace_1 = acm_factories.WorkspaceFactory.create()
        workspace_2 = acm_factories.WorkspaceFactory.create()
        instance_1 = models.WorkspaceData(research_center=research_center, consent_group=consent_group, workspace=workspace_1, version=1)
        instance_1.save()
        instance_2 = models.WorkspaceData(research_center=research_center, consent_group=consent_group, workspace=workspace_2, version=2)
        instance_2.full_clean()
        instance_2.save()
        self.assertEqual(models.WorkspaceData.objects.count(), 2)

    def test_duplicated_workspace(self):
        """One workspace cannot be associated with two WorkspaceData models."""
        workspace = acm_factories.WorkspaceFactory.create()
        consent_group_1 = factories.ConsentGroupFactory(code=models.ConsentGroup.GRU)
        consent_group_2 = factories.ConsentGroupFactory(code=models.ConsentGroup.HMB)
        research_center_1 = factories.ResearchCenterFactory.create()
        research_center_2 = factories.ResearchCenterFactory.create()
        instance_1 = models.WorkspaceData(research_center=research_center_1, consent_group=consent_group_1, workspace=workspace, version=1)
        instance_1.save()
        instance_2 = models.WorkspaceData(research_center=research_center_2, consent_group=consent_group_2, workspace=workspace, version=1)
        with self.assertRaises(ValidationError):
            instance_2.full_clean()
        with self.assertRaises(IntegrityError):
            instance_2.save()
