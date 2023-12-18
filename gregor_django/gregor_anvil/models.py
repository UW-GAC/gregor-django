from anvil_consortium_manager.models import BaseWorkspaceData
from django.core.exceptions import ValidationError
from django.core.validators import MinValueValidator
from django.db import models
from django.urls import reverse
from django_extensions.db.models import TimeStampedModel
from simple_history.models import HistoricalRecords


class ConsentGroup(TimeStampedModel, models.Model):
    """A model to track consent groups."""

    code = models.CharField(max_length=20, unique=True)
    """The short consent code for this ConsentGroup (e.g., GRU)."""

    consent = models.CharField(max_length=255, unique=True)
    """The consent description for this group (e.g., General Research Use)."""

    data_use_limitations = models.TextField()
    """The full data use limitations for this ConsentGroup."""

    history = HistoricalRecords()

    def __str__(self):
        """String method.
        Returns:
            A string showing the short consent code of the object.
        """
        return self.code

    def get_absolute_url(self):
        """Return the absolute url for this object."""
        return reverse("gregor_anvil:consent_groups:detail", args=[self.pk])


class ResearchCenter(TimeStampedModel, models.Model):
    """A model to track Research Centers."""

    short_name = models.CharField(max_length=15, unique=True)
    """The short name of the Research Center."""

    full_name = models.CharField(max_length=255, unique=True)
    """The full name of the Research Center."""

    history = HistoricalRecords()

    def __str__(self):
        """String method.

        Returns:
            A string showing the short name of the object.
        """
        return self.short_name

    def get_absolute_url(self):
        """Return the absolute url for this object."""
        return reverse("gregor_anvil:research_centers:detail", args=[self.pk])


class PartnerGroup(TimeStampedModel, models.Model):
    """A model to track Partner Groups"""

    short_name = models.CharField(max_length=15, unique=True)
    """The short name of the Partner Group"""

    full_name = models.CharField(max_length=255, unique=True)
    """The full name of the Partner Group"""

    history = HistoricalRecords()

    def __str__(self):
        """String method.

        Returns:
        A string showing the short_name of the object.
        """
        return self.short_name

    def get_absolute_url(self):
        """Return the absolute url for this object."""
        return reverse("gregor_anvil:partner_groups:detail", args=[self.pk])


class UploadCycle(TimeStampedModel, models.Model):
    """A model tracking the upload cycles that exist in the app."""

    cycle = models.PositiveIntegerField(
        validators=[MinValueValidator(1)],
        help_text="The upload cycle represented by this model.",
        unique=True,
    )
    start_date = models.DateField(help_text="The start date of this upload cycle.")
    end_date = models.DateField(help_text="The end date of this upload cycle.")
    note = models.TextField(blank=True, help_text="Additional notes.")
    # Django simple history.
    history = HistoricalRecords()

    class Meta:
        ordering = [
            "cycle",
        ]

    def __str__(self):
        return "U{cycle:02d}".format(cycle=self.cycle)

    def clean(self):
        """Custom cleaning methods."""
        # End date must be after start date.
        if self.start_date and self.end_date and self.start_date >= self.end_date:
            raise ValidationError("end_date must be after start_date!")

    def get_absolute_url(self):
        """Return the absolute url for this object."""
        return reverse("gregor_anvil:upload_cycles:detail", args=[self.cycle])

    def get_partner_upload_workspaces(self):
        """Return a queryset of PartnerUploadWorkspace objects that are included in this upload cycle.

        For a given PartnerGroup and ConsentGroup, the workspace with the highest version that also has a date_completed
        that is before the end_date of this upload cycle is included.
        """
        qs = PartnerUploadWorkspace.objects.filter(
            date_completed__lte=self.end_date
        ).order_by("-version")
        # This is not ideal, but we can't use .distinct on fields.
        pks_to_keep = []
        for partner_group in PartnerGroup.objects.all():
            for consent_group in ConsentGroup.objects.all():
                instance = qs.filter(
                    partner_group=partner_group, consent_group=consent_group
                ).first()
                if instance:
                    pks_to_keep.append(instance.pk)
        return qs.filter(pk__in=pks_to_keep)


class UploadWorkspace(TimeStampedModel, BaseWorkspaceData):
    """A model to track additional data about an upload workspace."""

    research_center = models.ForeignKey(ResearchCenter, on_delete=models.PROTECT)
    """The ResearchCenter providing data for this Workspace."""

    consent_group = models.ForeignKey(ConsentGroup, on_delete=models.PROTECT)
    """The ConsentGroup associated with this workspace."""

    # Replaces previous version field following 0011-0013 migrations.
    upload_cycle = models.ForeignKey(UploadCycle, on_delete=models.PROTECT)
    """The UploadCycle associated with this workspace."""

    class Meta:
        constraints = [
            # Model uniqueness.
            models.UniqueConstraint(
                name="unique_workspace_data_2",
                fields=["research_center", "consent_group", "upload_cycle"],
            ),
        ]


class PartnerUploadWorkspace(TimeStampedModel, BaseWorkspaceData):
    """A model to track additional data about a partner workspace."""

    partner_group = models.ForeignKey(PartnerGroup, on_delete=models.PROTECT)
    """The PartnerGroup providing data for this Workspace."""

    consent_group = models.ForeignKey(ConsentGroup, on_delete=models.PROTECT)
    """The ConsentGroup associated with this workspace."""

    version = models.IntegerField(
        validators=[MinValueValidator(1)],
        help_text="The version of this workspace for this PartnerGroup and ConsentGroup.",
    )
    date_completed = models.DateField(
        help_text="The date when uploads to this workspace and data validation were completed.",
        null=True,
        blank=True,
    )

    class Meta:
        constraints = [
            # Model uniqueness.
            models.UniqueConstraint(
                name="unique_partner_upload_workspace_data",
                fields=["partner_group", "consent_group", "version"],
            ),
        ]


class ExampleWorkspace(TimeStampedModel, BaseWorkspaceData):
    """A model to track example workspaces."""


class TemplateWorkspace(TimeStampedModel, BaseWorkspaceData):
    """A model to track template workspaces."""

    intended_use = models.TextField()


class CombinedConsortiumDataWorkspace(TimeStampedModel, BaseWorkspaceData):
    """A model to track a workspace that has data combined from multiple upload workspaces."""

    upload_cycle = models.ForeignKey(UploadCycle, on_delete=models.PROTECT)


class ReleaseWorkspace(TimeStampedModel, BaseWorkspaceData):
    """A model to track a workspace for release to the scientific community."""

    phs = 3047
    """dbGaP-assigned phs for the GREGoR study."""

    consent_group = models.ForeignKey(
        ConsentGroup,
        help_text="Consent group for the data in this workspace.",
        on_delete=models.PROTECT,
    )
    upload_cycle = models.ForeignKey(UploadCycle, on_delete=models.PROTECT)
    full_data_use_limitations = models.TextField(
        help_text="The full data use limitations for this workspace."
    )
    dbgap_version = models.IntegerField(
        verbose_name=" dbGaP version",
        validators=[MinValueValidator(1)],
        help_text="Version of the release (should be the same as dbGaP version).",
    )
    dbgap_participant_set = models.IntegerField(
        verbose_name=" dbGaP participant set",
        validators=[MinValueValidator(1)],
        help_text="dbGaP participant set of the workspace",
    )
    date_released = models.DateField(
        null=True,
        blank=True,
        help_text="Date that this workspace was released to the scientific community.",
    )

    class Meta:
        constraints = [
            # Model uniqueness.
            models.UniqueConstraint(
                name="unique_release_workspace_2",
                fields=["consent_group", "upload_cycle"],
            ),
        ]

    def get_dbgap_accession(self):
        return "phs{phs:06d}.v{v}.p{p}".format(
            phs=self.phs, v=self.dbgap_version, p=self.dbgap_participant_set
        )


class DCCProcessingWorkspace(TimeStampedModel, BaseWorkspaceData):

    upload_cycle = models.ForeignKey(
        UploadCycle,
        on_delete=models.PROTECT,
        help_text="Upload cycle associated with this workspace.",
    )
    purpose = models.TextField(
        help_text="The type of processing that is done in this workspace."
    )


class DCCProcessedDataWorkspace(TimeStampedModel, BaseWorkspaceData):
    """A workspace to store DCC processed data, split by consent (e.g., re-aligned CRAMs and gVCFs)."""

    upload_cycle = models.ForeignKey(
        UploadCycle,
        on_delete=models.PROTECT,
        help_text="Upload cycle associated with this workspace.",
    )
    consent_group = models.ForeignKey(
        ConsentGroup,
        help_text="Consent group associated with this data.",
        on_delete=models.PROTECT,
    )

    class Meta:
        constraints = [
            # Model uniqueness.
            models.UniqueConstraint(
                name="unique_dcc_processed_data_workspace",
                fields=["upload_cycle", "consent_group"],
            ),
        ]
