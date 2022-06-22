from django.core.exceptions import ValidationError
from django.db.utils import IntegrityError
from django.test import TestCase

from .. import models
from . import factories


class ConsentGroupTest(TestCase):
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
