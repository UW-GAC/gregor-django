from django.db import models


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
