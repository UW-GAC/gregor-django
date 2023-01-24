from anvil_consortium_manager.adapters.account import BaseAccountAdapter
from anvil_consortium_manager.adapters.workspace import BaseWorkspaceAdapter
from anvil_consortium_manager.tables import WorkspaceTable

from . import forms, models, tables

# from django.db.models import Q


class AccountAdapter(BaseAccountAdapter):
    """Custom account adapter for PRIMED."""

    list_table_class = tables.AccountTable

    # def get_autocomplete_queryset(self, queryset, q):
    #     """Filter to Accounts where the email or the associated user name matches the query `q`."""
    #     queryset = queryset.filter(Q(email__icontains=q) | Q(user__name__icontains=q))
    #     return queryset
    #
    # def get_autocomplete_label(self, account):
    #     """Adapter to provide a label for an account in autocomplete views."""
    #     if account.user:
    #         name = account.user.name
    #     else:
    #         name = "---"
    #     return "{} ({})".format(name, account.email)


class UploadWorkspaceAdapter(BaseWorkspaceAdapter):
    """Adapter for UploadWorkspaces."""

    type = "upload"
    name = "Upload workspace"
    list_table_class = tables.UploadWorkspaceTable
    workspace_data_model = models.UploadWorkspace
    workspace_data_form_class = forms.UploadWorkspaceForm
    workspace_detail_template_name = "gregor_anvil/uploadworkspace_detail.html"


class ExampleWorkspaceAdapter(BaseWorkspaceAdapter):
    """Adapter for ExampleWorkspaces."""

    type = "example"
    name = "Example workspace"
    list_table_class = WorkspaceTable
    workspace_data_model = models.ExampleWorkspace
    workspace_data_form_class = forms.ExampleWorkspaceForm
    workspace_detail_template_name = "anvil_consortium_manager/workspace_detail.html"


class TemplateWorkspaceAdapter(BaseWorkspaceAdapter):
    """Adapter for ExampleWorkspaces."""

    type = "template"
    name = "Template workspace"
    list_table_class = tables.TemplateWorkspaceTable
    workspace_data_model = models.TemplateWorkspace
    workspace_data_form_class = forms.TemplateWorkspaceForm
    workspace_detail_template_name = "gregor_anvil/templateworkspace_detail.html"
