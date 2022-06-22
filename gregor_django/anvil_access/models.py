from anvil_consortium_manager import models as acm_models
from django.db import models
from django.template.defaultfilters import truncatechars  # or truncatewords


# Create your models here.
class ConsentGroup(models.Model):
    """A model to track consent groups."""

    GRU = "GRU"
    HMB = "HMB"

    CODE_CHOICES = [
        (GRU, "General Research Use"),
        (HMB, "Health/Medical/Biomedical"),
    ]

    code = models.CharField(max_length=20, choices=CODE_CHOICES, unique=True)
    """The short consent code for this ConsentGroup."""

    data_use_limitations = models.TextField()
    """The full data use limitations for this ConsentGroup."""

    def __str__(self):
        """String method.

        Returns:
            A string showing the short consent code of the object.
        """
        return self.code

    @property
    def short_data_use_limitations(self):
        """Return a truncated version of the data_use_limitations.

        Returns:
            str: The truncated data_use_limitations
        """
        return truncatechars(self.data_use_limitations, 100)


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


class WorkspaceData(models.Model):
    """A model to track additional data about a Workspace."""

    research_center = models.ForeignKey(ResearchCenter, on_delete=models.PROTECT)
    """The ResearchCenter providing data for this Workspace."""

    consent_group = models.ForeignKey(ConsentGroup, on_delete=models.PROTECT)
    """The ConsentGroup associated with this Workspace."""

    version = models.IntegerField()
    """The version associated with this Workspace."""

    workspace = models.OneToOneField(acm_models.Workspace, on_delete=models.CASCADE)
    """The AnVIL workspace."""

    class Meta:
        constraints = [
            models.UniqueConstraint(
                name="unique_workspace_data",
                fields=["research_center", "consent_group", "version"],
            )
        ]

    def __str__(self):
        """String method.

        Returns:
            A string showing the workspace name of the object.
        """
        return self.workspace.__str__()
