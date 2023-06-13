from datetime import timedelta

from anvil_consortium_manager.tests.factories import WorkspaceFactory
from factory import Faker, LazyAttribute, Sequence, SubFactory
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


class UploadCycleFactory(DjangoModelFactory):
    """A factory for the UploadCycle model."""

    cycle = Sequence(lambda x: x)
    start_date = Faker("date_object")
    end_date = LazyAttribute(lambda o: o.start_date + timedelta(days=o.duration))

    class Params:
        duration = 90

    class Meta:
        model = models.UploadCycle


class PartnerGroupFactory(DjangoModelFactory):
    """A factory for the PartnerGroup model."""

    short_name = Faker("word")
    full_name = Faker("company")

    class Meta:
        model = models.PartnerGroup
        django_get_or_create = ["short_name"]


class UploadWorkspaceFactory(DjangoModelFactory):
    """A factory for the UploadWorkspace model."""

    research_center = SubFactory(ResearchCenterFactory)
    consent_group = SubFactory(ConsentGroupFactory)
    version = Faker("random_int", min=1, max=10)
    workspace = SubFactory(WorkspaceFactory, workspace_type="upload")

    class Meta:
        model = models.UploadWorkspace
        django_get_or_create = ["research_center", "consent_group"]


class ExampleWorkspaceFactory(DjangoModelFactory):
    """A factory for the ExampleWorkspace model."""

    workspace = SubFactory(
        WorkspaceFactory,
        workspace_type="example",
    )

    class Meta:
        model = models.ExampleWorkspace


class TemplateWorkspaceFactory(DjangoModelFactory):
    """A factory for the TemplateWorkspace model."""

    workspace = SubFactory(
        WorkspaceFactory,
        workspace_type="template",
    )
    intended_use = Faker("paragraph")

    class Meta:
        model = models.TemplateWorkspace


class CombinedConsortiumDataWorkspaceFactory(DjangoModelFactory):
    """A factory for the CombinedConsortiumDataWorkspace model."""

    class Meta:
        model = models.CombinedConsortiumDataWorkspace

    workspace = SubFactory(
        WorkspaceFactory,
        workspace_type="combined_consortium",
    )


class ReleaseWorkspaceFactory(DjangoModelFactory):
    """A factory for the ReleaseWorkspace model."""

    class Meta:
        model = models.ReleaseWorkspace

    full_data_use_limitations = Faker("paragraph")
    consent_group = SubFactory(ConsentGroupFactory)
    dbgap_version = Faker("random_int", min=1, max=10)
    dbgap_participant_set = Faker("random_int", min=1, max=10)

    workspace = SubFactory(
        WorkspaceFactory,
        workspace_type="release",
    )
