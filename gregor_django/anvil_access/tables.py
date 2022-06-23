import django_tables2 as tables

from . import models


class ResearchCenterTable(tables.Table):
    """A table for `ResearchCenters`."""

    short_name = tables.columns.Column(linkify=True)

    class Meta:
        model = models.ResearchCenter
        fields = ("short_name", "full_name")


class ConsentGroupTable(tables.Table):
    """A table for `ConsentGroups`."""

    code = tables.columns.Column(linkify=True)
    short_data_use_limitations = tables.columns.Column(
        "short_data_use_limitations", orderable=False
    )

    class Meta:
        model = models.ConsentGroup
        fields = ("code",)
