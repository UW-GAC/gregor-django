import django_tables2 as tables

from . import models


class ResearchCenterTable(tables.Table):
    """A table for ResearchCenters."""

    class Meta:
        model = models.ResearchCenter
        fields = ("short_name", "full_name")
