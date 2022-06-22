from factory import Faker, fuzzy, SubFactory
from factory.django import DjangoModelFactory

from anvil_consortium_manager.tests import factories as acm_factories
from .. import models


class ConsentGroupFactory(DjangoModelFactory):
    """A factory for the ConsentGroup model."""

    code = models.ConsentGroup.GRU
    data_use_limitations = Faker("paragraph")

    class Meta:
        model = models.ConsentGroup
        django_get_or_create = ["code"]


class ResearchCenterFactory(DjangoModelFactory):
    """A factory for the ResearchCenter model."""

    short_name = Faker("word")
    full_name = Faker("company")

    class Meta:
        model = models.ResearchCenter
        django_get_or_create = ["short_name"]


class WorkspaceDataFactory(DjangoModelFactory):
    """A factory for the WorkspaceData model."""

    research_center = SubFactory(ResearchCenterFactory)
    consent_group = SubFactory(ConsentGroupFactory)
    workspace = SubFactory(acm_factories.WorkspaceFactory)

    class Meta:
        model = models.WorkspaceData
        django_get_or_create = ["research_center", "consent_group"]
