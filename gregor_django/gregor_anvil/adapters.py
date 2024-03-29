from anvil_consortium_manager.adapters.account import BaseAccountAdapter
from anvil_consortium_manager.adapters.workspace import BaseWorkspaceAdapter
from anvil_consortium_manager.forms import WorkspaceForm
from django.db.models import Q

from . import filters, forms, models, tables


class AccountAdapter(BaseAccountAdapter):
    """Custom account adapter for PRIMED."""

    list_table_class = tables.AccountTable
    list_filterset_class = filters.AccountListFilter

    def get_autocomplete_queryset(self, queryset, q):
        """Filter to Accounts where the email or the associated user name matches the query `q`."""
        if q:
            queryset = queryset.filter(
                Q(email__icontains=q) | Q(user__name__icontains=q)
            )
        return queryset

    def get_autocomplete_label(self, account):
        """Adapter to provide a label for an account in autocomplete views."""
        if account.user:
            name = account.user.name
        else:
            name = "---"
        return "{} ({})".format(name, account.email)


class UploadWorkspaceAdapter(BaseWorkspaceAdapter):
    """Adapter for UploadWorkspaces."""

    type = "upload"
    name = "Upload workspace"
    description = "Workspaces that contain data uploaded by RCs in a given upload cycle"
    list_table_class = tables.UploadWorkspaceTable
    workspace_data_model = models.UploadWorkspace
    workspace_data_form_class = forms.UploadWorkspaceForm
    workspace_form_class = WorkspaceForm
    workspace_detail_template_name = "gregor_anvil/uploadworkspace_detail.html"

    def get_autocomplete_queryset(self, queryset, q, forwarded={}):
        """Filter to Accounts where the email or the associated user name matches the query `q`."""
        consent_group = forwarded.get("consent_group", None)
        if consent_group:
            queryset = queryset.filter(consent_group=consent_group)

        upload_cycle = forwarded.get("upload_cycle", None)
        if upload_cycle:
            queryset = queryset.filter(upload_cycle=upload_cycle)

        if q:
            queryset = queryset.filter(workspace__name__icontains=q)

        return queryset


class PartnerUploadWorkspaceAdapter(BaseWorkspaceAdapter):
    """Adapter for PartnerUploadWorkspaces."""

    type = "partner_upload"
    name = "Partner upload workspace"
    description = "Workspaces that contain data uploaded by a Partner Group "
    list_table_class = tables.PartnerUploadWorkspaceTable
    workspace_data_model = models.PartnerUploadWorkspace
    workspace_data_form_class = forms.PartnerUploadWorkspaceForm
    workspace_form_class = WorkspaceForm
    workspace_detail_template_name = "gregor_anvil/partneruploadworkspace_detail.html"


class ExampleWorkspaceAdapter(BaseWorkspaceAdapter):
    """Adapter for ExampleWorkspaces."""

    type = "example"
    name = "Example workspace"
    description = (
        "Workspaces that contain examples of using AnVIL, working with data, etc."
    )
    list_table_class = tables.DefaultWorkspaceTable
    workspace_data_model = models.ExampleWorkspace
    workspace_data_form_class = forms.ExampleWorkspaceForm
    workspace_detail_template_name = "anvil_consortium_manager/workspace_detail.html"
    workspace_form_class = WorkspaceForm


class TemplateWorkspaceAdapter(BaseWorkspaceAdapter):
    """Adapter for ExampleWorkspaces."""

    type = "template"
    name = "Template workspace"
    description = "Template workspaces that can be cloned to create other workspaces"
    list_table_class = tables.TemplateWorkspaceTable
    workspace_data_model = models.TemplateWorkspace
    workspace_data_form_class = forms.TemplateWorkspaceForm
    workspace_detail_template_name = "gregor_anvil/templateworkspace_detail.html"
    workspace_form_class = WorkspaceForm


class CombinedConsortiumDataWorkspaceAdapter(BaseWorkspaceAdapter):
    """Adapter for CombinedConsortiumDataWorkspace."""

    type = "combined_consortium"
    name = "Combined consortium data workspace"
    description = "Workspaces for internal consortium use that contain data tables combined across upload workspaces"
    list_table_class = tables.CombinedConsortiumDataWorkspaceTable
    workspace_data_model = models.CombinedConsortiumDataWorkspace
    workspace_data_form_class = forms.CombinedConsortiumDataWorkspaceForm
    workspace_detail_template_name = (
        "gregor_anvil/combinedconsortiumdataworkspace_detail.html"
    )
    workspace_form_class = WorkspaceForm


class ReleaseWorkspaceAdapter(BaseWorkspaceAdapter):
    """Adapter for ReleaseWorkspace."""

    type = "release"
    name = "Release workspace"
    description = "Workspaces for release to the general scientific community via dbGaP"
    list_table_class = tables.ReleaseWorkspaceTable
    workspace_data_model = models.ReleaseWorkspace
    workspace_data_form_class = forms.ReleaseWorkspaceForm
    workspace_detail_template_name = "gregor_anvil/releaseworkspace_detail.html"
    workspace_form_class = WorkspaceForm


class DCCProcessingWorkspaceAdapter(BaseWorkspaceAdapter):
    """Adapter for DCCProcessingWorkspace."""

    type = "dcc_processing"
    name = "DCC processing workspace"
    description = "Workspaces used for DCC processing of data"
    list_table_class = tables.DCCProcessingWorkspaceTable
    workspace_data_model = models.DCCProcessingWorkspace
    workspace_data_form_class = forms.DCCProcessingWorkspaceForm
    workspace_detail_template_name = "gregor_anvil/dccprocessingworkspace_detail.html"
    workspace_form_class = WorkspaceForm


class DCCProcessedDataWorkspaceAdapter(BaseWorkspaceAdapter):
    """Adapter for DCCProcessedDataWorkspace."""

    type = "dcc_processed_data"
    name = "DCC processed data workspace"
    description = "Workspaces containing data processed by the DCC and hosted by AnVIL"
    list_table_class = tables.DCCProcessedDataWorkspaceTable
    workspace_data_model = models.DCCProcessedDataWorkspace
    workspace_data_form_class = forms.DCCProcessedDataWorkspaceForm
    workspace_detail_template_name = (
        "gregor_anvil/dccprocesseddataworkspace_detail.html"
    )
    workspace_form_class = WorkspaceForm


class ExchangeWorkspaceAdapter(BaseWorkspaceAdapter):
    """Adapter for ExchangeWorkspaces."""

    type = "exchange"
    name = "Exchange workspace"
    description = "Workspaces for exchanging data with a Research Center outside of an upload cycle"
    list_table_class = tables.ExchangeWorkspaceTable
    workspace_data_model = models.ExchangeWorkspace
    workspace_data_form_class = forms.ExchangeWorkspaceForm
    workspace_form_class = WorkspaceForm
    workspace_detail_template_name = "gregor_anvil/exchangeworkspace_detail.html"
