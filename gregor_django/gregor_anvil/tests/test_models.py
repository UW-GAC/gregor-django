from django.core.exceptions import ValidationError
from django.db.utils import IntegrityError
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
