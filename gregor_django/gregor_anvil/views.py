from anvil_consortium_manager.auth import AnVILConsortiumManagerViewRequired
from dal import autocomplete
from django.views.generic import DetailView
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
