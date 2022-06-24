import anvil_consortium_manager.forms as acm_forms
from django.forms import ModelForm

from . import models


class WorkspaceDataImportForm(acm_forms.WorkspaceImportForm, ModelForm):
    """Form to import a workspace from AnVIL."""

    class Meta:
        model = models.WorkspaceData
        fields = ["research_center", "consent_group", "version"]
