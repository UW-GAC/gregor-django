"""Forms classes for the gregor_anvil app."""

from dal import autocomplete
from django import forms
from django.core.exceptions import ValidationError

from . import models


class UploadWorkspaceForm(forms.ModelForm):
    """Form for a UploadWorkspace object."""

    class Meta:
        model = models.UploadWorkspace
        fields = (
            "research_center",
            "consent_group",
            "version",
            "workspace",
        )


class ExampleWorkspaceForm(forms.ModelForm):
    """Form for a ExampleWorkspace object."""

    class Meta:
        model = models.ExampleWorkspace
        fields = ("workspace",)


class TemplateWorkspaceForm(forms.ModelForm):
    """Form for a TemplateWorkspace object."""

    class Meta:
        model = models.TemplateWorkspace
        fields = ("workspace", "intended_use")


class CombinedConsortiumDataWorkspaceForm(forms.ModelForm):
    """Form for a CombinedConsortiumDataWorkspace object."""

    ERROR_UPLOAD_VERSION_DOES_NOT_MATCH = "Version of upload workspaces does not match."

    class Meta:
        model = models.CombinedConsortiumDataWorkspace
        fields = ("workspace", "upload_workspaces")
        help_texts = {
            "upload_workspaces": """Upload workspaces contributing to the combined workspace.
                                    All upload workspaces must have the same version."""
        }
        widgets = {
            "upload_workspaces": autocomplete.ModelSelect2Multiple(
                url="gregor_anvil:upload_workspaces:autocomplete",
                attrs={"data-theme": "bootstrap-5"},
            ),
        }

    def clean_upload_workspaces(self):
        """Validate that all UploadWorkspaces have the same version."""
        data = self.cleaned_data["upload_workspaces"]
        versions = set([x.version for x in data])
        if len(versions) > 1:
            self.add_error(
                "upload_workspaces",
                ValidationError(self.ERROR_UPLOAD_VERSION_DOES_NOT_MATCH),
            )
        return data
