from django.db import models

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
