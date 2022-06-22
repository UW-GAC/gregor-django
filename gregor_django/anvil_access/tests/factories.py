from factory import Faker, fuzzy, SubFactory
from factory.django import DjangoModelFactory

from .. import models


class ConsentGroupFactory(DjangoModelFactory):
    """A factory for the ConsentGroup model."""

    code = models.ConsentGroup.GRU
    data_use_limitations = Faker("paragraph")

    class Meta:
        model = models.ConsentGroup
        django_get_or_create = ["code"]
