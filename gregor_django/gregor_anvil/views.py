from anvil_consortium_manager.adapters.workspace import workspace_adapter_registry
from anvil_consortium_manager.auth import AnVILConsortiumManagerViewRequired
from anvil_consortium_manager.models import Account, WorkspaceGroupSharing
from dal import autocomplete
from django.db.models import Count
from django.views.generic import DetailView, TemplateView
from django_tables2 import SingleTableView

from . import models, reports, tables


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
        context[
            "number_upload_workspaces"
        ] = models.UploadWorkspace.objects.all().count()
        adapters = workspace_adapter_registry.get_registered_names()
        qs = (
            WorkspaceGroupSharing.objects.values("workspace__workspace_type")
            .filter(group__name="GREGOR_ALL")
            .annotate(total=Count("workspace__workspace_type"))
        )
        counts = {}
        for workspace_type in adapters.keys():
            this_type = [
                x for x in qs if x["workspace__workspace_type"] == workspace_type
            ]
            if len(this_type) == 1:
                workspace_type = this_type[0]["workspace__workspace_type"]
                r = reports.SharedWorkspaceReport(
                    workspace_type=workspace_type,
                    workspace_name=adapters[workspace_type],
                    count=this_type[0]["total"],
                )
            else:
                r = reports.SharedWorkspaceReport(
                    workspace_type=workspace_type,
                    workspace_name=adapters[workspace_type],
                    count=0,
                )
            counts[workspace_type] = r

        context["shared_with_consortium"] = counts
        context["verified_linked_accounts"] = Account.objects.filter(
            verified_email_entry__date_verified__isnull=False
        ).count()

        return context
