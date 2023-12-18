from anvil_consortium_manager.auth import (
    AnVILConsortiumManagerStaffEditRequired,
    AnVILConsortiumManagerStaffViewRequired,
)
from anvil_consortium_manager.models import Account, Workspace
from django.contrib.auth import get_user_model
from django.contrib.messages.views import SuccessMessageMixin
from django.db.models import Count, Q
from django.views.generic import CreateView, DetailView, TemplateView
from django_tables2 import MultiTableMixin, SingleTableMixin, SingleTableView

from gregor_django.users.tables import UserTable

from . import forms, models, tables

User = get_user_model()


class ConsentGroupDetail(AnVILConsortiumManagerStaffViewRequired, DetailView):
    """View to show details about a `ConsentGroups`."""

    model = models.ConsentGroup


class ConsentGroupList(AnVILConsortiumManagerStaffViewRequired, SingleTableView):
    """View to show a list of `ConsentGroups`."""

    model = models.ConsentGroup
    table_class = tables.ConsentGroupTable


class ResearchCenterDetail(
    AnVILConsortiumManagerStaffViewRequired, SingleTableMixin, DetailView
):
    """View to show details about a `ResearchCenter`."""

    model = models.ResearchCenter
    context_table_name = "site_user_table"

    def get_table(self):
        return UserTable(User.objects.filter(research_centers=self.object))


class ResearchCenterList(AnVILConsortiumManagerStaffViewRequired, SingleTableView):
    """View to show a list of `ResearchCenters`."""

    model = models.ResearchCenter
    table_class = tables.ResearchCenterTable


class PartnerGroupDetail(
    AnVILConsortiumManagerStaffViewRequired, SingleTableMixin, DetailView
):
    """View to show details about a `PartnerGroup`."""

    model = models.PartnerGroup
    context_table_name = "partner_group_user_table"

    def get_table(self):
        return UserTable(User.objects.filter(partner_groups=self.object))


class PartnerGroupList(AnVILConsortiumManagerStaffViewRequired, SingleTableView):
    """View to show a list of `PartnerGroups`."""

    model = models.PartnerGroup
    table_class = tables.PartnerGroupTable


class UploadCycleCreate(
    AnVILConsortiumManagerStaffEditRequired, SuccessMessageMixin, CreateView
):
    """View to create a new UploadCycle object."""

    model = models.UploadCycle
    form_class = forms.UploadCycleForm
    success_message = "Successfully created Upload Cycle."


class UploadCycleDetail(
    AnVILConsortiumManagerStaffViewRequired, MultiTableMixin, DetailView
):
    """View to show details about an `UploadCycle`."""

    model = models.UploadCycle
    slug_field = "cycle"
    tables = [
        tables.UploadWorkspaceTable,
        tables.CombinedConsortiumDataWorkspaceTable,
        tables.ReleaseWorkspaceTable,
        tables.DCCProcessingWorkspaceTable,
        tables.DCCProcessedDataWorkspaceTable,
        tables.PartnerUploadWorkspaceTable,
    ]

    def get_tables_data(self):
        upload_workspace_qs = Workspace.objects.filter(
            uploadworkspace__upload_cycle=self.object
        )
        combined_workspace_qs = Workspace.objects.filter(
            combinedconsortiumdataworkspace__upload_cycle=self.object
        )
        release_workspace_qs = Workspace.objects.filter(
            releaseworkspace__upload_cycle=self.object
        )
        dcc_processing_workspace_qs = Workspace.objects.filter(
            dccprocessingworkspace__upload_cycle=self.object,
        )
        dcc_processed_data_workspace_qs = Workspace.objects.filter(
            dccprocesseddataworkspace__upload_cycle=self.object,
        )
        partner_workspaces = self.object.get_partner_upload_workspaces()
        partner_workspace_qs = Workspace.objects.filter(
            partneruploadworkspace__in=partner_workspaces
        )
        return [
            upload_workspace_qs,
            combined_workspace_qs,
            release_workspace_qs,
            dcc_processing_workspace_qs,
            dcc_processed_data_workspace_qs,
            partner_workspace_qs,
        ]


class UploadCycleList(AnVILConsortiumManagerStaffViewRequired, SingleTableView):
    """View to show a list of `UploadCycle` objects."""

    model = models.UploadCycle
    table_class = tables.UploadCycleTable


class WorkspaceReport(AnVILConsortiumManagerStaffViewRequired, TemplateView):
    """View to show report on workspaces"""

    template_name = "gregor_anvil/workspace_report.html"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["verified_linked_accounts"] = Account.objects.filter(
            verified_email_entry__date_verified__isnull=False
        ).count()
        qs = Workspace.objects.values("workspace_type").annotate(
            n_total=Count("pk", distinct=True),
            n_shared=Count(
                "workspacegroupsharing",
                filter=Q(workspacegroupsharing__group__name="GREGOR_ALL"),
            ),
        )
        context["workspace_count_table"] = tables.WorkspaceReportTable(qs)
        return context
