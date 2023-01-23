import django_tables2 as tables
from anvil_consortium_manager.models import Workspace

from . import models


class ResearchCenterTable(tables.Table):
    """A table for ResearchCenters."""

    full_name = tables.Column(linkify=True)

    class Meta:
        model = models.ResearchCenter
        fields = ("full_name", "short_name")


class ConsentGroupTable(tables.Table):
    """A table for `ConsentGroups`."""

    code = tables.columns.Column(linkify=True)

    class Meta:
        model = models.ConsentGroup
        fields = (
            "code",
            "consent",
        )


class UploadWorkspaceTable(tables.Table):
    """A table for Workspaces that includes fields from UploadWorkspace."""

    name = tables.columns.Column(linkify=True)

    class Meta:
        model = Workspace
        fields = (
            "name",
            "uploadworkspace__research_center",
            "uploadworkspace__consent_group",
            "uploadworkspace__version",
        )


class TemplateWorkspaceTable(tables.Table):
    """A table for Workspaces that includes fields from TemplateWorkspace."""

    name = tables.columns.Column(linkify=True)

    class Meta:
        model = Workspace
        fields = (
            "name",
            "templateworkspace__intended_use",
        )
