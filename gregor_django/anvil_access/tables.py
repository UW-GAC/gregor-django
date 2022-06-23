import django_tables2 as tables

from . import models


class ResearchCenterTable(tables.Table):
    """A table for ResearchCenters."""

    short_name = tables.columns.Column(linkify=True)

    class Meta:
        model = models.ResearchCenter
        fields = ("short_name", "full_name")
