from anvil_consortium_manager.auth import AnVILConsortiumManagerViewRequired
from anvil_consortium_manager.models import Account, Workspace
from dal import autocomplete
from django.db.models import Count, Q
from django.views.generic import DetailView, TemplateView
from django_tables2 import SingleTableView

from . import models, tables


class ConsentGroupDetail(AnVILConsortiumManagerViewRequired, DetailView):
    """View to show details about a `ConsentGroups`."""

    model = models.ConsentGroup


class ConsentGroupList(AnVILConsortiumManagerViewRequired, SingleTableView):
    """View to show a list of `ConsentGroups`."""

    model = models.ConsentGroup
    table_class = tables.ConsentGroupTable


class ResearchCenterDetail(AnVILConsortiumManagerViewRequired, DetailView):
    """View to show details about a `ResearchCenter`."""

    model = models.ResearchCenter


class ResearchCenterList(AnVILConsortiumManagerViewRequired, SingleTableView):
    """View to show a list of `ResearchCenters`."""

    model = models.ResearchCenter
    table_class = tables.ResearchCenterTable


class UploadWorkspaceAutocomplete(
    AnVILConsortiumManagerViewRequired, autocomplete.Select2QuerySetView
):
    """View to provide autocompletion for UploadWorkspaces."""

    def get_queryset(self):
        # Filter out unathorized users, or does the auth mixin do that?
        qs = models.UploadWorkspace.objects.filter().order_by(
            "workspace__billing_project__name", "workspace__name"
        )

        if self.q:
            qs = qs.filter(workspace__name__icontains=self.q)

        return qs


class WorkspaceReport(AnVILConsortiumManagerViewRequired, TemplateView):
    """View to show report on workspaces"""

    template_name = "gregor_anvil/workspace_report.html"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["verified_linked_accounts"] = Account.objects.filter(
            verified_email_entry__date_verified__isnull=False
        ).count()
        qs = Workspace.objects.values("workspace_type").annotate(
            n_total=Count("workspace_type", distinct=True),
            n_shared=Count(
                "workspacegroupsharing",
                filter=Q(workspacegroupsharing__group__name="GREGOR_ALL"),
            ),
        )
        context["workspace_count_table"] = tables.WorkspaceReportTable(qs)
        return context
