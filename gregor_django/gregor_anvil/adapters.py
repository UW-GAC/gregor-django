from anvil_consortium_manager.adapters.workspace import BaseWorkspaceAdapter
from anvil_consortium_manager.tables import WorkspaceTable

from . import forms, models, tables


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
