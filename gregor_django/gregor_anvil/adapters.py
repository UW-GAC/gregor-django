from anvil_consortium_manager.adapters.workspace import BaseWorkspaceAdapter

from . import forms, models, tables


class UploadWorkspaceAdapter(BaseWorkspaceAdapter):
    """Adapter for UploadWorkspaces."""

    type = "upload"
    name = "Upload workspace"
    list_table_class = tables.UploadWorkspaceTable
    workspace_data_model = models.UploadWorkspace
    workspace_data_form_class = forms.UploadWorkspaceForm
