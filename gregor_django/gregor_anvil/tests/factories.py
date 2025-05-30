from datetime import timedelta

from anvil_consortium_manager.tests.factories import ManagedGroupFactory, WorkspaceFactory
from django.utils import timezone
from factory import Faker, LazyAttribute, Sequence, SubFactory, Trait, post_generation
from factory.django import DjangoModelFactory

from .. import models


class ConsentGroupFactory(DjangoModelFactory):
    """A factory for the ConsentGroup model."""

    code = Sequence(lambda x: "C{}".format(x))
    consent = Faker("catch_phrase")
    data_use_limitations = Faker("paragraph", nb_sentences=10)

    class Meta:
        model = models.ConsentGroup
        django_get_or_create = ["code"]


class ResearchCenterFactory(DjangoModelFactory):
    """A factory for the ResearchCenter model."""

    short_name = Sequence(lambda x: "RC{}".format(x))
    full_name = Faker("company")

    class Meta:
        model = models.ResearchCenter
        django_get_or_create = ["short_name"]


class UploadCycleFactory(DjangoModelFactory):
    """A factory for the UploadCycle model."""

    cycle = Sequence(lambda x: x + 1)
    start_date = Faker("date_object")
    end_date = LazyAttribute(lambda o: o.start_date + timedelta(days=o.duration))

    class Params:
        duration = 90
        is_past = Trait(
            start_date=timezone.localdate() - timedelta(days=100),
            end_date=timezone.localdate() - timedelta(days=10),
            date_ready_for_compute=timezone.localdate() - timedelta(days=90),
        )
        is_current = Trait(
            start_date=timezone.localdate() - timedelta(days=45),
            end_date=timezone.localdate() + timedelta(days=45),
        )
        is_future = Trait(
            start_date=timezone.localdate() + timedelta(days=10),
            end_date=timezone.localdate() + timedelta(days=100),
        )

    class Meta:
        model = models.UploadCycle
        django_get_or_create = ["cycle"]


class PartnerGroupFactory(DjangoModelFactory):
    """A factory for the PartnerGroup model."""

    short_name = Sequence(lambda x: "PG{}".format(x))
    full_name = Faker("company")

    class Meta:
        model = models.PartnerGroup
        django_get_or_create = ["short_name"]


class UploadWorkspaceFactory(DjangoModelFactory):
    """A factory for the UploadWorkspace model."""

    research_center = SubFactory(ResearchCenterFactory)
    consent_group = SubFactory(ConsentGroupFactory)
    upload_cycle = SubFactory(UploadCycleFactory)
    workspace = SubFactory(WorkspaceFactory, workspace_type="upload")

    class Meta:
        model = models.UploadWorkspace
        skip_postgeneration_save = True

    @post_generation
    def authorization_domains(self, create, extracted, **kwargs):
        # Add an authorization domain.
        if not create:
            # Simple build, do nothing.
            return

        # Create an authorization domain.
        auth_domain = ManagedGroupFactory.create(name="auth_{}".format(self.workspace.name))
        self.workspace.authorization_domains.add(auth_domain)


class PartnerUploadWorkspaceFactory(DjangoModelFactory):
    """A factory for the UploadWorkspace model."""

    partner_group = SubFactory(PartnerGroupFactory)
    consent_group = SubFactory(ConsentGroupFactory)
    version = Faker("random_int", min=1)
    workspace = SubFactory(WorkspaceFactory, workspace_type="partner_upload")

    class Meta:
        model = models.PartnerUploadWorkspace


class ResourceWorkspaceFactory(DjangoModelFactory):
    """A factory for the ResourceWorkspace model."""

    workspace = SubFactory(
        WorkspaceFactory,
        workspace_type="resource",
    )
    brief_description = Faker("sentence")

    class Meta:
        model = models.ResourceWorkspace


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
        skip_postgeneration_save = True

    upload_cycle = SubFactory(UploadCycleFactory)
    workspace = SubFactory(
        WorkspaceFactory,
        workspace_type="combined_consortium",
    )

    @post_generation
    def authorization_domains(self, create, extracted, **kwargs):
        # Add an authorization domain.
        if not create:
            # Simple build, do nothing.
            return

        # Create an authorization domain.
        auth_domain = ManagedGroupFactory.create(name="auth_{}".format(self.workspace.name))
        self.workspace.authorization_domains.add(auth_domain)


class ReleaseWorkspaceFactory(DjangoModelFactory):
    """A factory for the ReleaseWorkspace model."""

    class Meta:
        model = models.ReleaseWorkspace

    full_data_use_limitations = Faker("paragraph")
    consent_group = SubFactory(ConsentGroupFactory)
    dbgap_version = Faker("random_int", min=1, max=10)
    dbgap_participant_set = Faker("random_int", min=1, max=10)
    upload_cycle = SubFactory(UploadCycleFactory)

    workspace = SubFactory(
        WorkspaceFactory,
        workspace_type="release",
    )


class DCCProcessingWorkspaceFactory(DjangoModelFactory):
    """A factory for the class DCCProcessingWorkspace model."""

    class Meta:
        model = models.DCCProcessingWorkspace

    upload_cycle = SubFactory(UploadCycleFactory)
    purpose = Faker("paragraph")
    workspace = SubFactory(
        WorkspaceFactory,
        workspace_type="dcc_processing",
    )


class DCCProcessedDataWorkspaceFactory(DjangoModelFactory):
    """A factory for the class DCCProcessedDataWorkspace model."""

    class Meta:
        model = models.DCCProcessedDataWorkspace
        skip_postgeneration_save = True

    consent_group = SubFactory(ConsentGroupFactory)
    upload_cycle = SubFactory(UploadCycleFactory)
    workspace = SubFactory(
        WorkspaceFactory,
        workspace_type="dcc_processed_data",
    )

    @post_generation
    def authorization_domains(self, create, extracted, **kwargs):
        # Add an authorization domain.
        if not create:
            # Simple build, do nothing.
            return

        # Create an authorization domain.
        auth_domain = ManagedGroupFactory.create(name="auth_{}".format(self.workspace.name))
        self.workspace.authorization_domains.add(auth_domain)


class ExchangeWorkspaceFactory(DjangoModelFactory):
    """A factory for the ExchangeWorkspace model."""

    research_center = SubFactory(ResearchCenterFactory)
    workspace = SubFactory(WorkspaceFactory, workspace_type="exchange")

    class Meta:
        model = models.ExchangeWorkspace
