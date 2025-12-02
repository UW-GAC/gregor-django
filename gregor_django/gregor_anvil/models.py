from datetime import date

from anvil_consortium_manager.models import BaseWorkspaceData, ManagedGroup
from django.core.exceptions import ValidationError
from django.core.validators import MinValueValidator
from django.db import models
from django.urls import reverse
from django.utils import timezone
from django_extensions.db.models import TimeStampedModel
from simple_history.models import HistoricalRecords


def validate_not_future_date(value: date):
    if value > timezone.now().date():
        raise ValidationError("Date cannot be in the future.")


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

    drupal_node_id = models.IntegerField(blank=True, null=True)
    """Reference node ID for entity in drupal"""

    member_group = models.OneToOneField(
        ManagedGroup,
        on_delete=models.PROTECT,
        help_text="The AnVIL group containing members from this Research Center.",
        related_name="research_center_of_members",
        blank=True,
        null=True,
    )

    non_member_group = models.OneToOneField(
        ManagedGroup,
        on_delete=models.PROTECT,
        help_text="The AnVIL group containing non-members from this Research Center.",
        related_name="research_center_of_non_members",
        blank=True,
        null=True,
    )

    uploader_group = models.OneToOneField(
        ManagedGroup,
        on_delete=models.PROTECT,
        help_text="The group that has write/upload access to workspaces associated with this Research Center.",
        related_name="research_center_of_uploaders",
        blank=True,
        null=True,
    )

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

    def clean(self):
        """Custom cleaning methods."""
        # Members group and uploaders group must be different.
        if self.member_group and self.uploader_group and self.member_group == self.uploader_group:
            raise ValidationError("member_group and uploader_group must be different!")
        if self.non_member_group and self.uploader_group and self.non_member_group == self.uploader_group:
            raise ValidationError("non_member_group and uploader_group must be different!")
        if self.member_group and self.non_member_group and self.member_group == self.non_member_group:
            raise ValidationError("member_group and non_member_group must be different!")


class PartnerGroup(TimeStampedModel, models.Model):
    """A model to track Partner Groups"""

    class StatusTypes(models.TextChoices):
        ACTIVE = "Active", "Active"
        INACTIVE = "Inactive", "Inactive"

    short_name = models.CharField(max_length=15, unique=True)
    """The short name of the Partner Group"""

    full_name = models.CharField(max_length=255, unique=True)
    """The full name of the Partner Group"""

    drupal_node_id = models.IntegerField(blank=True, null=True)
    """Reference node ID for entity in drupal"""

    status = models.CharField(max_length=20, choices=StatusTypes.choices, default=StatusTypes.ACTIVE)

    member_group = models.OneToOneField(
        ManagedGroup,
        on_delete=models.PROTECT,
        help_text="The AnVIL group containing members from this Partner Group.",
        related_name="partner_group_of_members",
        null=True,
        blank=True,
    )

    uploader_group = models.OneToOneField(
        ManagedGroup,
        on_delete=models.PROTECT,
        help_text="The group that has write/upload access to workspaces associated with this Partner Group.",
        related_name="partner_group_of_uploaders",
        null=True,
        blank=True,
    )

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

    def clean(self):
        """Custom cleaning methods."""
        # Members group and uploaders group must be different.
        if self.member_group and self.uploader_group and self.member_group == self.uploader_group:
            raise ValidationError("member_group and uploader_group must be different!")


class UploadCycle(TimeStampedModel, models.Model):
    """A model tracking the upload cycles that exist in the app."""

    cycle = models.PositiveIntegerField(
        validators=[MinValueValidator(1)],
        help_text="The upload cycle represented by this model.",
        unique=True,
    )
    start_date = models.DateField(help_text="The start date of this upload cycle.")
    end_date = models.DateField(help_text="The end date of this upload cycle.")
    date_ready_for_compute = models.DateField(
        help_text="Date that this workspace was ready for RC uploaders to run compute.",
        blank=True,
        null=True,
        default=None,
        validators=[validate_not_future_date],
    )
    note = models.TextField(blank=True, help_text="Additional notes.")

    # Django simple history.
    history = HistoricalRecords()

    class Meta:
        ordering = [
            "cycle",
        ]

    def __str__(self):
        return "U{cycle:02d}".format(cycle=self.cycle)

    def get_absolute_url(self):
        """Return the absolute url for this object."""
        return reverse("gregor_anvil:upload_cycles:detail", args=[self.cycle])

    def clean(self):
        """Custom cleaning methods."""
        # End date must be after start date.
        if self.start_date and self.end_date and self.start_date >= self.end_date:
            raise ValidationError("end_date must be after start_date!")
        # date_ready_for_compute must be after start_date
        if self.start_date and self.date_ready_for_compute and self.start_date > self.date_ready_for_compute:
            raise ValidationError("date_ready_for_compute must be after start_date!")
        # date_ready_for_compute must be before end_date
        if self.end_date and self.date_ready_for_compute and self.end_date < self.date_ready_for_compute:
            raise ValidationError("date_ready_for_compute must be before end_date!")

    def get_partner_upload_workspaces(self):
        """Return a queryset of PartnerUploadWorkspace objects that are included in this upload cycle.

        For a given PartnerGroup and ConsentGroup, the workspace with the highest version that also has a date_completed
        that is before the end_date of this upload cycle is included.
        """
        qs = PartnerUploadWorkspace.objects.filter(date_completed__lte=self.end_date).order_by("-version")
        # This is not ideal, but we can't use .distinct on fields.
        pks_to_keep = []
        for partner_group in PartnerGroup.objects.all():
            for consent_group in ConsentGroup.objects.all():
                instance = qs.filter(partner_group=partner_group, consent_group=consent_group).first()
                if instance:
                    pks_to_keep.append(instance.pk)
        return qs.filter(pk__in=pks_to_keep)

    @property
    def is_current(self):
        """Return a boolean indicating whether this upload cycle is the current one."""
        return self.start_date <= timezone.localdate() and self.end_date >= timezone.localdate()

    @property
    def is_past(self):
        """Return a boolean indicating whether this upload cycle is a past cycle."""
        return self.end_date < timezone.localdate()

    @property
    def is_future(self):
        """Return a boolean indicating whether this upload cycle is a future cycle."""
        return self.start_date > timezone.localdate()


class UploadWorkspace(TimeStampedModel, BaseWorkspaceData):
    """A model to track additional data about an upload workspace."""

    research_center = models.ForeignKey(ResearchCenter, on_delete=models.PROTECT)
    """The ResearchCenter providing data for this Workspace."""

    consent_group = models.ForeignKey(ConsentGroup, on_delete=models.PROTECT)
    """The ConsentGroup associated with this workspace."""

    # Replaces previous version field following 0011-0013 migrations.
    upload_cycle = models.ForeignKey(UploadCycle, on_delete=models.PROTECT)
    """The UploadCycle associated with this workspace."""

    date_qc_completed = models.DateField(
        help_text="Date that QC was completed for this workspace. If null, QC is not complete.",
        blank=True,
        null=True,
        default=None,
        validators=[validate_not_future_date],
    )

    class Meta:
        constraints = [
            # Model uniqueness.
            models.UniqueConstraint(
                name="unique_workspace_data_2",
                fields=["research_center", "consent_group", "upload_cycle"],
            ),
        ]

    def __str__(self):
        return self.workspace.name

    def clean(self):
        """Custom cleaning methods."""
        # Check that date_qc_completed is after the upload cycle end date.
        if self.date_qc_completed and self.upload_cycle.end_date > self.date_qc_completed:
            raise ValidationError("date_qc_completed must after end_date of associated upload_cycle.")


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
        validators=[validate_not_future_date],
    )

    class Meta:
        constraints = [
            # Model uniqueness.
            models.UniqueConstraint(
                name="unique_partner_upload_workspace_data",
                fields=["partner_group", "consent_group", "version"],
            ),
        ]


class ResourceWorkspace(TimeStampedModel, BaseWorkspaceData):
    """A model to track resource workspaces."""

    brief_description = models.TextField()


class TemplateWorkspace(TimeStampedModel, BaseWorkspaceData):
    """A model to track template workspaces."""

    intended_use = models.TextField()


class CombinedConsortiumDataWorkspace(TimeStampedModel, BaseWorkspaceData):
    """A model to track a workspace that has data combined from multiple upload workspaces."""

    upload_cycle = models.ForeignKey(UploadCycle, on_delete=models.PROTECT)
    date_completed = models.DateField(
        help_text="Date that data preparation in this workspace was completed.",
        blank=True,
        null=True,
        default=None,
        validators=[validate_not_future_date],
    )

    def clean(self):
        """Custom cleaning methods."""
        # Check that date_qc_completed is after the upload cycle end date.
        if self.date_completed and self.upload_cycle.end_date > self.date_completed:
            raise ValidationError("date_completed must after end_date of associated upload_cycle.")


class ReleaseWorkspace(TimeStampedModel, BaseWorkspaceData):
    """A model to track a workspace for preparing data releases for the scientific community."""

    phs = 3047
    """dbGaP-assigned phs for the GREGoR study."""

    consent_group = models.ForeignKey(
        ConsentGroup,
        help_text="Consent group for the data in this workspace.",
        on_delete=models.PROTECT,
    )
    upload_cycle = models.ForeignKey(UploadCycle, on_delete=models.PROTECT)
    full_data_use_limitations = models.TextField(help_text="The full data use limitations for this workspace.")
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
    # Contributing workspaces.
    contributing_upload_workspaces = models.ManyToManyField(
        UploadWorkspace,
        help_text=(
            "UploadWorkspaces with data tables contributing to this release. "
            "(Note that this does not include workspaces containing files contributing to this release.)"
        ),
        related_name="release_workspaces",
    )
    contributing_dcc_processed_data_workspaces = models.ManyToManyField(
        "DCCProcessedDataWorkspace",
        help_text="DCCProcessedDataWorkspaces with data tables contributing to this release.",
        related_name="release_workspaces",
        blank=True,
    )
    contributing_partner_upload_workspaces = models.ManyToManyField(
        PartnerUploadWorkspace,
        help_text="PartnerUploadWorkspaces with data tables contributing to this release.",
        related_name="release_workspaces",
        blank=True,
    )

    date_released = models.DateField(
        null=True,
        blank=True,
        help_text="Date that this workspace was released to the scientific community.",
        validators=[validate_not_future_date],
    )

    class Meta:
        constraints = [
            # Model uniqueness.
            models.UniqueConstraint(
                name="unique_release_workspace_2",
                fields=["consent_group", "upload_cycle"],
            ),
        ]
        verbose_name = "release prep workspace"

    def get_dbgap_accession(self):
        return "phs{phs:06d}.v{v}.p{p}".format(phs=self.phs, v=self.dbgap_version, p=self.dbgap_participant_set)


class DCCProcessingWorkspace(TimeStampedModel, BaseWorkspaceData):
    upload_cycle = models.ForeignKey(
        UploadCycle,
        on_delete=models.PROTECT,
        help_text="Upload cycle associated with this workspace.",
    )
    purpose = models.TextField(help_text="The type of processing that is done in this workspace.")


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


class ExchangeWorkspace(TimeStampedModel, BaseWorkspaceData):
    """A workspace to be used to exchange data with a ResearchCenter."""

    research_center = models.OneToOneField(
        ResearchCenter,
        on_delete=models.PROTECT,
        help_text="The ResearchCenter associated with this workspace.",
    )
