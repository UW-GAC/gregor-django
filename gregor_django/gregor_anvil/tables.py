import django_tables2 as tables
from anvil_consortium_manager.adapters.workspace import workspace_adapter_registry
from anvil_consortium_manager.models import Account, Workspace
from django.utils.html import format_html

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


class PartnerGroupTable(tables.Table):
    """A table for PartnerGroups."""

    full_name = tables.Column(linkify=True)

    class Meta:
        model = models.PartnerGroup
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


class WorkspaceSharedWithConsortiumTable(tables.Table):
    """Table including a column to indicate if a workspace is shared with PRIMED_ALL."""

    is_shared = tables.columns.Column(
        accessor="pk",
        verbose_name="Shared with GREGoR?",
        orderable=False,
    )

    def render_is_shared(self, record):
        is_shared = record.workspacegroupsharing_set.filter(
            group__name="GREGOR_ALL"
        ).exists()
        if is_shared:
            icon = "check-circle-fill"
            color = "green"
            value = format_html(
                """<i class="bi bi-{}" style="color: {};"></i>""".format(icon, color)
            )
        else:
            value = ""
        return value


class DefaultWorkspaceTable(WorkspaceSharedWithConsortiumTable, tables.Table):
    """Class to use for default workspace tables in GREGoR."""

    name = tables.Column(linkify=True, verbose_name="Workspace")
    billing_project = tables.Column(linkify=True)
    number_groups = tables.Column(
        verbose_name="Number of groups shared with",
        empty_values=(),
        orderable=False,
        accessor="workspacegroupsharing_set__count",
    )

    class Meta:
        model = Workspace
        fields = (
            "name",
            "billing_project",
            "number_groups",
            "is_shared",
        )
        order_by = ("name",)


class UploadWorkspaceTable(WorkspaceSharedWithConsortiumTable, tables.Table):
    """A table for Workspaces that includes fields from UploadWorkspace."""

    name = tables.columns.Column(linkify=True)

    class Meta:
        model = Workspace
        fields = (
            "name",
            "uploadworkspace__research_center",
            "uploadworkspace__consent_group",
            "uploadworkspace__version",
            "is_shared",
        )


class TemplateWorkspaceTable(WorkspaceSharedWithConsortiumTable, tables.Table):
    """A table for Workspaces that includes fields from TemplateWorkspace."""

    name = tables.columns.Column(linkify=True)

    class Meta:
        model = Workspace
        fields = (
            "name",
            "templateworkspace__intended_use",
            "is_shared",
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


class ReleaseWorkspaceTable(tables.Table):
    """A table for Workspaces that includes fields from ReleaseWorkspace."""

    name = tables.columns.Column(linkify=True)
    number_workspaces = tables.columns.Column(
        accessor="pk",
        verbose_name="Number of workspaces",
        orderable=False,
    )

    class Meta:
        model = Workspace
        fields = (
            "name",
            "releaseworkspace__consent_group",
            "releaseworkspace__dbgap_version",
            "releaseworkspace__dbgap_participant_set",
            "number_workspaces",
            "releaseworkspace__date_released",
        )

    def render_number_workspaces(self, record):
        return record.releaseworkspace.upload_workspaces.count()
