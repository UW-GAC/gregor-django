from anvil_consortium_manager.tests import factories as acm_factories
from factory import Faker, SubFactory
from factory.django import DjangoModelFactory

from .. import models


class ConsentGroupFactory(DjangoModelFactory):
    """A factory for the ConsentGroup model."""

    code = Faker("word")
    consent = Faker("catch_phrase")
    data_use_limitations = Faker("paragraph", nb_sentences=10)

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
    version = Faker("random_int", min=1, max=10)
    workspace = SubFactory(acm_factories.WorkspaceFactory)

    class Meta:
        model = models.WorkspaceData
        django_get_or_create = ["research_center", "consent_group"]
