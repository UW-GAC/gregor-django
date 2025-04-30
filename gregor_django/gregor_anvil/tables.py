import django_tables2 as tables
from anvil_consortium_manager.adapters.workspace import workspace_adapter_registry
from anvil_consortium_manager.models import Account, ManagedGroup, Workspace
from django.utils.html import format_html

from . import models


class BooleanIconColumn(tables.BooleanColumn):
    """A column that renders a boolean value as an icon.

    This column renders a boolean value as a bootstrap icon. By default, the icon is a green checkmark for True,
    and nothing for False, but this can be customized by keyword arguments.

    Args:
        show_false_icon (bool): Whether to show an icon for False values.
        true_color (str): The color of the icon for True values. (Default: green)
        false_color (str): The color of the icon for False values. (Default: red)
        true_icon (str): The icon to use for True values. (Default: check-circle-fill)
        false_icon (str): The icon to use for False values. (Default: x-circle-fill)
    """

    def __init__(
        self,
        show_false_icon=False,
        true_color="green",
        false_color="red",
        true_icon="check-circle-fill",
        false_icon="x-circle-fill",
        **kwargs,
    ):
        super().__init__(**kwargs)
        self.show_false_icon = show_false_icon
        self.true_color = true_color
        self.false_color = false_color
        self.true_icon = true_icon
        self.false_icon = false_icon

    def render(self, value, record, bound_column):
        value = self._get_bool_value(record, value, bound_column)
        if value:
            rendered_value = format_html(
                f"""<i class="bi bi-{self.true_icon} bi-align-center px-2" style="color: {self.true_color};"></i>"""
            )
        else:
            if self.show_false_icon:
                rendered_value = format_html(
                    f"""<i class="bi bi-{self.false_icon} bi-align-center px-2" style="color: {self.false_color};"></i>"""  # noqa: E501
                )
            else:
                rendered_value = ""
        return rendered_value


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
        fields = (
            "email",
            "user__name",
            "user__research_centers",
            "is_service_account",
            "status",
        )


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
        fields = ("full_name", "short_name", "status")

    def render_status(self, value):
        status_classes = {
            models.PartnerGroup.StatusTypes.ACTIVE: "bg-success",
            models.PartnerGroup.StatusTypes.INACTIVE: "bg-danger",
        }

        css_class = status_classes.get(value, "bg-warning")

        return format_html('<span class="badge {}">{}</span>', css_class, value)


class ConsentGroupTable(tables.Table):
    """A table for `ConsentGroups`."""

    code = tables.columns.Column(linkify=True)

    class Meta:
        model = models.ConsentGroup
        fields = (
            "code",
            "consent",
        )


class UploadCycleTable(tables.Table):
    """A table for `UploadCycle` objects."""

    cycle = tables.columns.Column(linkify=True)

    class Meta:
        model = models.UploadCycle
        fields = (
            "cycle",
            "start_date",
            "end_date",
            "date_ready_for_compute",
        )

    def render_cycle(self, record):
        return str(record)


class WorkspaceConsortiumAccessTable(tables.Table):
    """Table including a column to indicate if a workspace is shared with PRIMED_ALL."""

    consortium_access = tables.columns.Column(
        accessor="pk",
        verbose_name="Consortium access?",
        orderable=False,
    )

    def render_consortium_access(self, record):
        try:
            group = ManagedGroup.objects.get(name="GREGOR_ALL")
        except ManagedGroup.DoesNotExist:
            has_consortium_access = False
        else:
            has_consortium_access = record.is_in_authorization_domain(group) and record.is_shared(group)

        if has_consortium_access:
            icon = "check-circle-fill"
            color = "green"
            value = format_html("""<i class="bi bi-{}" style="color: {};"></i>""".format(icon, color))
        else:
            value = ""
        return value


class DefaultWorkspaceTable(WorkspaceConsortiumAccessTable, tables.Table):
    """Class to use for default workspace tables in GREGoR for view users."""

    name = tables.Column(linkify=True, verbose_name="Workspace")
    billing_project = tables.Column()

    class Meta:
        model = Workspace
        fields = (
            "name",
            "billing_project",
            "consortium_access",
        )
        order_by = ("name",)


class DefaultWorkspaceStaffTable(DefaultWorkspaceTable):
    """Class to use for default workspace tables in GREGoR for staff users."""

    billing_project = tables.Column(linkify=True)
    number_groups = tables.Column(
        verbose_name="Number of groups shared with",
        empty_values=(),
        orderable=False,
        accessor="workspacegroupsharing_set__count",
    )

    class Meta(DefaultWorkspaceTable.Meta):
        fields = (
            "name",
            "billing_project",
            "number_groups",
            "consortium_access",
        )


class UploadWorkspaceTable(WorkspaceConsortiumAccessTable, tables.Table):
    """A table for Workspaces that includes fields from UploadWorkspace."""

    name = tables.columns.Column(linkify=True)
    uploadworkspace__upload_cycle = tables.columns.Column(linkify=True)

    class Meta:
        model = Workspace
        fields = (
            "name",
            "uploadworkspace__upload_cycle",
            "uploadworkspace__research_center",
            "uploadworkspace__consent_group",
            "uploadworkspace__date_qc_completed",
            "consortium_access",
        )


class PartnerUploadWorkspaceTable(WorkspaceConsortiumAccessTable, tables.Table):
    """A table for Workspaces that includes fields from PartnerUploadWorkspace."""

    name = tables.columns.Column(linkify=True)
    partneruploadworkspace__partner_group = tables.columns.Column()

    class Meta:
        model = Workspace
        fields = (
            "name",
            "partneruploadworkspace__partner_group",
            "partneruploadworkspace__consent_group",
            "partneruploadworkspace__version",
            "partneruploadworkspace__date_completed",
            "consortium_access",
        )


class PartnerUploadWorkspaceStaffTable(PartnerUploadWorkspaceTable):
    """A table for Workspaces that includes fields from PartnerUploadWorkspace."""

    partneruploadworkspace__partner_group = tables.columns.Column(linkify=True)


class TemplateWorkspaceTable(WorkspaceConsortiumAccessTable, tables.Table):
    """A table for Workspaces that includes fields from TemplateWorkspace."""

    name = tables.columns.Column(linkify=True)

    class Meta:
        model = Workspace
        fields = (
            "name",
            "templateworkspace__intended_use",
            "consortium_access",
        )


class WorkspaceReportTable(tables.Table):
    """Table to store aggregated workspace counts."""

    workspace_type = tables.columns.Column(orderable=False)
    n_total = tables.columns.Column(verbose_name="Total number", orderable=False)
    n_shared = tables.columns.Column(verbose_name="Number shared with consortium", orderable=False)

    class Meta:
        model = Workspace
        fields = ("workspace_type",)

    def render_workspace_type(self, value):
        adapter_names = workspace_adapter_registry.get_registered_names()
        return adapter_names[value] + "s"


class CombinedConsortiumDataWorkspaceTable(WorkspaceConsortiumAccessTable, tables.Table):
    """A table for Workspaces that includes fields from CombinedConsortiumDataWorkspace."""

    name = tables.columns.Column(linkify=True)
    combinedconsortiumdataworkspace__upload_cycle = tables.columns.Column(linkify=True)

    class Meta:
        model = Workspace
        fields = (
            "name",
            "combinedconsortiumdataworkspace__upload_cycle",
            "combinedconsortiumdataworkspace__date_completed",
        )


class ReleaseWorkspaceTable(tables.Table):
    """A table for Workspaces that includes fields from ReleaseWorkspace."""

    name = tables.columns.Column(linkify=True)
    releaseworkspace__upload_cycle = tables.columns.Column(linkify=True)

    class Meta:
        model = Workspace
        fields = (
            "name",
            "releaseworkspace__upload_cycle",
            "releaseworkspace__consent_group",
            "releaseworkspace__dbgap_version",
            "releaseworkspace__dbgap_participant_set",
            "releaseworkspace__date_released",
        )


class DCCProcessingWorkspaceTable(tables.Table):
    """A table for Workspaces that includes fields from DCCProcessingWorkspace."""

    name = tables.columns.Column(linkify=True)
    dccprocessingworkspace__upload_cycle = tables.columns.Column(linkify=True)

    class Meta:
        model = Workspace
        fields = (
            "name",
            "dccprocessingworkspace__upload_cycle",
            "dccprocessingworkspace__purpose",
        )


class DCCProcessedDataWorkspaceTable(WorkspaceConsortiumAccessTable, tables.Table):
    """A table for Workspaces that includes fields from DCCProcessedDataWorkspace."""

    name = tables.columns.Column(linkify=True)
    dccprocesseddataworkspace__upload_cycle = tables.columns.Column(linkify=True)

    class Meta:
        model = Workspace
        fields = (
            "name",
            "dccprocesseddataworkspace__upload_cycle",
            "dccprocesseddataworkspace__consent_group",
            "consortium_access",
        )


class ExchangeWorkspaceTable(tables.Table):
    """Class to use for ExchangeWorkspace tables."""

    name = tables.Column(linkify=True, verbose_name="Workspace")
    billing_project = tables.Column()
    exchangeworkspace__research_center = tables.Column()

    class Meta:
        model = Workspace
        fields = ("name", "billing_project", "exchangeworkspace__research_center")
        order_by = ("name",)


class ExchangeWorkspaceStaffTable(ExchangeWorkspaceTable):
    """Class to use for ExchangeWorkspace tables."""

    billing_project = tables.Column(linkify=True)
    exchangeworkspace__research_center = tables.Column(linkify=True)
