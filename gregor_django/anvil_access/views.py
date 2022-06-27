from anvil_consortium_manager import anvil_api
from anvil_consortium_manager.auth import (
    AnVILConsortiumManagerEditRequired,
    AnVILConsortiumManagerViewRequired,
)
from anvil_consortium_manager.viewmixins import (
    SuccessMessageMixin,
    WorkspaceImportMixin,
)
from django.http import Http404
from django.views import defaults as default_views
from django.views.generic import CreateView, DetailView, View
from django_tables2 import SingleTableView

from . import forms, models, tables


def page_not_found_extra(request, exception, *args, **kwargs):
    """Extend the page_not_found function to accept additional arguments."""
    return default_views.page_not_found(request, exception)


class PageNotFound(View):
    """Flexible way to display a 404."""

    def dispatch(self, request, *args, **kwargs):
        raise Http404


class ResearchCenterDetail(AnVILConsortiumManagerViewRequired, DetailView):
    """View to show details about a `ResearchCenter`."""

    model = models.ResearchCenter


class ResearchCenterList(AnVILConsortiumManagerViewRequired, SingleTableView):
    """View to show a list of `ResearchCenters`."""

    model = models.ResearchCenter
    table_class = tables.ResearchCenterTable


class ConsentGroupDetail(AnVILConsortiumManagerViewRequired, DetailView):
    """View to show details about a `ConsentGroups`."""

    model = models.ConsentGroup


class ConsentGroupList(AnVILConsortiumManagerViewRequired, SingleTableView):
    """View to show a list of `ConsentGroups`."""

    model = models.ConsentGroup
    table_class = tables.ConsentGroupTable


class WorkspaceDataList(AnVILConsortiumManagerViewRequired, SingleTableView):
    """View to show a list of `WorkspaceData` objects."""

    model = models.WorkspaceData
    table_class = tables.WorkspaceDataTable


class WorkspaceDataImport(
    AnVILConsortiumManagerEditRequired,
    SuccessMessageMixin,
    WorkspaceImportMixin,
    CreateView,
):
    """Import a `Workspace` from AnVIL and create a related `WorkspaceData` object."""

    model = models.WorkspaceData
    form_class = forms.WorkspaceDataImportForm
    template_name = "anvil_access/workspacedata_import.html"
    success_msg = "Successfully imported Workspace from AnVIL."
    """Message to display if the Workspace was successfully imported."""

    def get_form_kwargs(self):
        """Initializes a form by setting workspace_choices to the list of workspaces available for import."""
        kwargs = super().get_form_kwargs()
        kwargs["workspace_choices"] = self.get_workspace_choices()
        return kwargs

    def form_valid(self, form):
        # Separate the billing project and workspace name.
        billing_project_name, workspace_name = form.cleaned_data["workspace"].split("/")

        # Import the workspace.
        try:
            self.import_workspace(billing_project_name, workspace_name)
        except anvil_api.AnVILAPIError:
            return self.render_to_response(self.get_context_data(form=form))
        # Now link the imported workspace to the object and save the new object.
        form.instance.workspace = self.workspace
        # object = form.save(commit=False)
        # object.workspace = self.workspace
        # object.save()
        return super().form_valid(form)

    def get_success_url(self):
        return self.object.workspace.get_absolute_url()
