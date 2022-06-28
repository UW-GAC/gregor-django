import anvil_consortium_manager.tables as acm_tables
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


class WorkspaceTable(acm_tables.WorkspaceTable):
    """A table extending the `WorkspaceTable` to add `WorkspaceData` information."""

    # Add columns from WorkspaceData.
    research_center = tables.columns.Column(
        accessor="workspacedata__research_center", linkify=True
    )
    consent_group = tables.columns.Column(
        accessor="workspacedata__consent_group", linkify=True
    )
    version = tables.columns.Column(accessor="workspacedata__version")

    class Meta:
        # Do not include billing_project, since it is already in the name.
        # Do not include the number of authorization domains.
        exclude = ("billing_project", "n_authorization_domains")
        # Reorder columns.
        sequence = ("name", "research_center", "consent_group", "version")
