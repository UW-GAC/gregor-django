from anvil_consortium_manager.auth import AnVILConsortiumManagerViewRequired
from django.views.generic import DetailView, ListView

from . import models


class ResearchCenterDetail(AnVILConsortiumManagerViewRequired, DetailView):
    """View to show details about a `ResearchCenter`."""

    model = models.ResearchCenter


class ResearchCenterList(AnVILConsortiumManagerViewRequired, ListView):
    """View to show a list of `ResearchCenters`."""

    model = models.ResearchCenter
