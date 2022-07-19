from anvil_consortium_manager.adapter import DefaultWorkspaceAdapter

from . import forms, models, tables


class UploadWorkspaceAdapter(DefaultWorkspaceAdapter):
    """Adapter for UploadWorkspaces."""

    list_table_class = tables.UploadWorkspaceTable
    workspace_data_model = models.UploadWorkspace
    workspace_data_form_class = forms.UploadWorkspaceForm
