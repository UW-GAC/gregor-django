"""Forms classes for the gregor_anvil app."""

from django import forms

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
