"""Forms classes for the gregor_anvil app."""

from anvil_consortium_manager.forms import Bootstrap5MediaFormMixin
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


class CombinedConsortiumDataWorkspaceForm(Bootstrap5MediaFormMixin, forms.ModelForm):
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


class CustomDateInput(forms.widgets.DateInput):
    input_type = "date"


class ReleaseWorkspaceForm(Bootstrap5MediaFormMixin, forms.ModelForm):
    """Form for a ReleaseWorkspace object."""

    ERROR_CONSENT_DOES_NOT_MATCH = (
        "Consent group must match consent group of upload workspaces."
    )
    ERROR_UPLOAD_WORKSPACE_CONSENT = (
        "Consent group for upload workspaces must be the same."
    )

    class Meta:
        model = models.ReleaseWorkspace
        fields = (
            "consent_group",
            "upload_workspaces",
            "full_data_use_limitations",
            "dbgap_version",
            "dbgap_participant_set",
            "release_date",
            "workspace",
        )
        help_texts = {
            "upload_workspaces": """Upload workspaces contributing to this Release Workspace.
                                    All upload workspaces must have the same consent group.""",
            "release_date": """Do not select a date for this field unless the workspace has been
                               released to the scientific community.""",
        }
        widgets = {
            # We considered checkboxes for workspaces with default all checked.
            # Unfortunately we need to select only those with a given consent, not all workspaces.
            # So go back to the ModelSelect2Multiple widget.
            "upload_workspaces": autocomplete.ModelSelect2Multiple(
                url="gregor_anvil:upload_workspaces:autocomplete",
                attrs={"data-theme": "bootstrap-5"},
            ),
            # "release_date": forms.SelectDateInput(),
            # "release_date": forms.DateInput(),
            # "release_date": AdminDateWidget(),
            "release_date": CustomDateInput(),
        }

    def clean_upload_workspaces(self):
        """Validate that all UploadWorkspaces have the same consent group."""
        data = self.cleaned_data["upload_workspaces"]
        versions = set([x.consent_group for x in data])
        if len(versions) > 1:
            self.add_error(
                "upload_workspaces",
                ValidationError(self.ERROR_UPLOAD_WORKSPACE_CONSENT),
            )
        return data

    def clean(self):
        """Validate that consent_group matches the consent group for upload_workspaces."""
        cleaned_data = super().clean()
        # Make sure that the consent group specified matches the consent group for the upload_workspaces.
        consent_group = cleaned_data.get("consent_group")
        upload_workspaces = cleaned_data.get("upload_workspaces")
        if consent_group and upload_workspaces:
            # We only need to check the first workspace since the clean_upload_workspaces method checks
            # that all upload_workspaces have the same consent.
            if consent_group != upload_workspaces[0].consent_group:
                raise ValidationError(self.ERROR_CONSENT_DOES_NOT_MATCH)

        return cleaned_data
