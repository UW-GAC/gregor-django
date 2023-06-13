from anvil_consortium_manager.auth import (
    AnVILConsortiumManagerEditRequired,
    AnVILConsortiumManagerViewRequired,
)
from anvil_consortium_manager.models import Account, Workspace
from django.contrib.auth import get_user_model
from django.contrib.messages.views import SuccessMessageMixin
from django.db.models import Count, Q
from django.views.generic import CreateView, DetailView, TemplateView
from django_tables2 import SingleTableMixin, SingleTableView

from gregor_django.users.tables import UserTable

from . import forms, models, tables

User = get_user_model()


class ConsentGroupDetail(AnVILConsortiumManagerViewRequired, DetailView):
    """View to show details about a `ConsentGroups`."""

    model = models.ConsentGroup


class ConsentGroupList(AnVILConsortiumManagerViewRequired, SingleTableView):
    """View to show a list of `ConsentGroups`."""

    model = models.ConsentGroup
    table_class = tables.ConsentGroupTable


class ResearchCenterDetail(
    AnVILConsortiumManagerViewRequired, SingleTableMixin, DetailView
):
    """View to show details about a `ResearchCenter`."""

    model = models.ResearchCenter
    context_table_name = "site_user_table"

    def get_table(self):
        return UserTable(User.objects.filter(research_centers=self.object))


class ResearchCenterList(AnVILConsortiumManagerViewRequired, SingleTableView):
    """View to show a list of `ResearchCenters`."""

    model = models.ResearchCenter
    table_class = tables.ResearchCenterTable


class PartnerGroupDetail(
    AnVILConsortiumManagerViewRequired, SingleTableMixin, DetailView
):
    """View to show details about a `PartnerGroup`."""

    model = models.PartnerGroup
    context_table_name = "partner_group_user_table"

    def get_table(self):
        return UserTable(User.objects.filter(partner_groups=self.object))


class PartnerGroupList(AnVILConsortiumManagerViewRequired, SingleTableView):
    """View to show a list of `PartnerGroups`."""

    model = models.PartnerGroup
    table_class = tables.PartnerGroupTable


class UploadCycleCreate(
    AnVILConsortiumManagerEditRequired, SuccessMessageMixin, CreateView
):
    """View to create a new UploadCycle object."""

    model = models.UploadCycle
    form_class = forms.UploadCycleForm
    success_message = "Successfully created Upload Cycle."


class UploadCycleDetail(
    AnVILConsortiumManagerViewRequired, SingleTableMixin, DetailView
):
    """View to show details about an `UploadCycle`."""

    model = models.UploadCycle
    slug_field = "cycle"


class WorkspaceReport(AnVILConsortiumManagerViewRequired, TemplateView):
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
