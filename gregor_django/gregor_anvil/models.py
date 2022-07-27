from anvil_consortium_manager.models import BaseWorkspaceData
from django.core.validators import MinValueValidator
from django.db import models
from django.urls import reverse


class ConsentGroup(models.Model):
    """A model to track consent groups."""

    code = models.CharField(max_length=20, unique=True)
    """The short consent code for this ConsentGroup (e.g., GRU)."""

    consent = models.CharField(max_length=255, unique=True)
    """The consent description for this group (e.g., General Research Use)."""

    data_use_limitations = models.TextField()
    """The full data use limitations for this ConsentGroup."""

    def __str__(self):
        """String method.
        Returns:
            A string showing the short consent code of the object.
        """
        return self.code

    def get_absolute_url(self):
        """Return the absolute url for this object."""
        return reverse("gregor_anvil:consent_groups:detail", args=[self.pk])


class ResearchCenter(models.Model):
    """A model to track Research Centers."""

    short_name = models.CharField(max_length=15, unique=True)
    """The short name of the Research Center."""

    full_name = models.CharField(max_length=255)
    """The full name of the Research Center."""

    def __str__(self):
        """String method.

        Returns:
            A string showing the short name of the object.
        """
        return self.short_name

    def get_absolute_url(self):
        """Return the absolute url for this object."""
        return reverse("gregor_anvil:research_centers:detail", args=[self.pk])


class UploadWorkspace(BaseWorkspaceData):
    """A model to track additional data about an upload workspace."""

    research_center = models.ForeignKey(ResearchCenter, on_delete=models.PROTECT)
    """The ResearchCenter providing data for this Workspace."""

    consent_group = models.ForeignKey(ConsentGroup, on_delete=models.PROTECT)
    """The ConsentGroup associated with this workspace."""

    # PositiveIntegerField allows 0 and we want this to be 1 or higher.
    # We'll need to add a separate constraint.
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

    def __str__(self):
        """String method.
        Returns:
            A string showing the workspace name of the object.
        """
        return "{} - {} - v{}".format(
            self.research_center, self.consent_group, self.version
        )
