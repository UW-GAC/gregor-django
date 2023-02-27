import django_tables2 as tables
from anvil_consortium_manager.adapters.workspace import workspace_adapter_registry
from anvil_consortium_manager.models import Account, Workspace

from . import models


class AccountTable(tables.Table):
    """A custom table for `Accounts`."""

    email = tables.Column(linkify=True)
    user__name = tables.Column(linkify=lambda record: record.user.get_absolute_url())
    is_service_account = tables.BooleanColumn(verbose_name="Service account?")
    number_groups = tables.Column(
        verbose_name="Number of groups",
        empty_values=(),
        orderable=False,
        accessor="groupaccountmembership_set__count",
    )

    class Meta:
        model = Account
        fields = ("email", "user__name", "user__research_centers", "is_service_account")


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


class WorkspaceReportTable(tables.Table):
    """Table to store aggregated workspace counts."""

    workspace_type = tables.columns.Column(orderable=False)
    n_total = tables.columns.Column(verbose_name="Total number", orderable=False)
    n_shared = tables.columns.Column(
        verbose_name="Number shared with consortium", orderable=False
    )

    class Meta:
        model = Workspace
        fields = ("workspace_type",)

    def render_workspace_type(self, value):
        adapter_names = workspace_adapter_registry.get_registered_names()
        return adapter_names[value] + "s"
