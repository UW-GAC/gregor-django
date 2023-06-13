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


class UploadCycle(TimeStampedModel):
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

    def __str__(self):
        return "U{cycle:02d}".format(cycle=self.cycle)

    def clean(self):
        """Custom cleaning methods."""
        # End date must be after start date.
        if self.start_date >= self.end_date:
            raise ValidationError("end_date must be after start_date!")

    def get_absolute_url(self):
        """Return the absolute url for this object."""
        return reverse("gregor_anvil:upload_cycles:detail", args=[self.cycle])


class UploadWorkspace(TimeStampedModel, BaseWorkspaceData):
    """A model to track additional data about an upload workspace."""

    research_center = models.ForeignKey(ResearchCenter, on_delete=models.PROTECT)
    """The ResearchCenter providing data for this Workspace."""

    consent_group = models.ForeignKey(ConsentGroup, on_delete=models.PROTECT)
    """The ConsentGroup associated with this workspace."""

    # PositiveIntegerField allows 0 and we want this to be 1 or higher.
    # We'll need to add a separate constraint in addition to this validator.
    version = models.PositiveIntegerField(validators=[MinValueValidator(1)])
    """The version associated with this Workspace."""

    class Meta:
        constraints = [
            # Model uniqueness.
            models.UniqueConstraint(
                name="unique_workspace_data",
                fields=["research_center", "consent_group", "version"],
            ),
            # Version must be positive and *not* zero.
            models.CheckConstraint(
                name="positive_version",
                check=models.Q(version__gt=0),
            ),
        ]


class ExampleWorkspace(TimeStampedModel, BaseWorkspaceData):
    """A model to track example workspaces."""


class TemplateWorkspace(TimeStampedModel, BaseWorkspaceData):
    """A model to track template workspaces."""

    intended_use = models.TextField()


class CombinedConsortiumDataWorkspace(TimeStampedModel, BaseWorkspaceData):
    """A model to track a workspace that has data combined from multiple upload workspaces."""

    upload_workspaces = models.ManyToManyField(
        UploadWorkspace, help_text="Upload workspaces"
    )


class ReleaseWorkspace(TimeStampedModel, BaseWorkspaceData):
    """A model to track a workspace for release to the scientific community."""

    phs = 3047
    """dbGaP-assigned phs for the GREGoR study."""

    consent_group = models.ForeignKey(
        ConsentGroup,
        help_text="Consent group for the data in this workspace.",
        on_delete=models.PROTECT,
    )
    upload_workspaces = models.ManyToManyField(
        UploadWorkspace,
        help_text="Upload workspaces contributing data to this workspace.",
    )
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
                name="unique_release_workspace",
                fields=["consent_group", "dbgap_version"],
            ),
        ]

    def get_dbgap_accession(self):
        return "phs{phs:06d}.v{v}.p{p}".format(
            phs=self.phs, v=self.dbgap_version, p=self.dbgap_participant_set
        )
