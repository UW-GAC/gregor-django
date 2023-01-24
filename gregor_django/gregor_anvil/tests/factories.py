from anvil_consortium_manager.tests.factories import WorkspaceFactory
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
