"""Forms classes for the gregor_anvil app."""

from anvil_consortium_manager.forms import Bootstrap5MediaFormMixin
from django import forms

from . import models


class CustomDateInput(forms.widgets.DateInput):
    input_type = "date"


class UploadCycleForm(forms.ModelForm):
    """Form for a UploadCycle object."""

    class Meta:
        model = models.UploadCycle
        fields = (
            "cycle",
            "start_date",
            "end_date",
            "note",
        )

        widgets = {
            "start_date": CustomDateInput(),
            "end_date": CustomDateInput(),
        }


class UploadWorkspaceForm(forms.ModelForm):
    """Form for a UploadWorkspace object."""

    class Meta:
        model = models.UploadWorkspace
        fields = (
            "research_center",
            "consent_group",
            "upload_cycle",
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

    class Meta:
        model = models.CombinedConsortiumDataWorkspace
        fields = (
            "workspace",
            "upload_cycle",
        )


class ReleaseWorkspaceForm(Bootstrap5MediaFormMixin, forms.ModelForm):
    """Form for a ReleaseWorkspace object."""

    class Meta:
        model = models.ReleaseWorkspace
        fields = (
            "upload_cycle",
            "consent_group",
            "full_data_use_limitations",
            "dbgap_version",
            "dbgap_participant_set",
            "date_released",
            "workspace",
        )
        help_texts = {
            "date_released": """Do not select a date for this field unless the workspace has been
                               released to the scientific community.""",
        }
        widgets = {
            "date_released": CustomDateInput(),
        }


class DCCProcessingWorkspaceForm(Bootstrap5MediaFormMixin, forms.ModelForm):
    """Form for a DCCProcessingWorkspace object."""

    ERROR_UPLOAD_CYCLE = (
        "upload_cycle must match upload_cycle of all upload_workspaces."
    )

    class Meta:
        model = models.DCCProcessingWorkspace
        fields = (
            "upload_cycle",
            "purpose",
            "workspace",
        )


class DCCProcessedDataWorkspaceForm(Bootstrap5MediaFormMixin, forms.ModelForm):
    """Form for a DCCProcessedDataWorkspace object."""

    class Meta:
        model = models.DCCProcessedDataWorkspace
        fields = (
            "upload_cycle",
            "consent_group",
            "workspace",
        )
