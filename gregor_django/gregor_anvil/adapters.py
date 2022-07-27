from anvil_consortium_manager.adapter import BaseWorkspaceAdapter

from . import forms, models, tables


class UploadWorkspaceAdapter(BaseWorkspaceAdapter):
    """Adapter for UploadWorkspaces."""

    list_table_class = tables.UploadWorkspaceTable
    workspace_data_model = models.UploadWorkspace
    workspace_data_form_class = forms.UploadWorkspaceForm
