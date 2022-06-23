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
        fields = (
            "code",
            "consent",
        )


class WorkspaceDataTable(tables.Table):
    """A table for `WorkspaceData` objects."""

    workspace = tables.columns.Column(
        linkify=("anvil_access:workspaces:detail", [tables.utils.A("pk")])
    )
    research_center = tables.Column(linkify=True)
    consent_group = tables.Column(linkify=True)

    class Meta:
        model = models.WorkspaceData
        fields = (
            "workspace",
            "research_center",
            "consent_group",
            "version",
        )
