from anvil_consortium_manager.anvil_api import AnVILAPIError
from anvil_consortium_manager.exceptions import AnVILGroupNotFound
from anvil_consortium_manager.models import (
    ManagedGroup,
)
from django.contrib import messages
from django.db import transaction
from django.http import Http404, HttpResponse


class AuditMixin:
    """Mixin to assist with auditing views."""

    def run_audit(self):
        raise NotImplementedError("AuditMixin.run_audit() must be implemented in a subclass")

    def get_context_data(self, **kwargs):
        """Run the audit and add it to the context."""
        context = super().get_context_data(**kwargs)
        # Run the audit.
        audit_results = self.run_audit()
        context["verified_table"] = audit_results.get_verified_table()
        context["errors_table"] = audit_results.get_errors_table()
        context["needs_action_table"] = audit_results.get_needs_action_table()
        context["audit_results"] = audit_results
        return context


class AuditResolveMixin:
    """Mixin to assist with audit resolution views."""

    def get_workspace_data_object(self):
        raise NotImplementedError("AuditResolveMixin.get_workspace_data_object() must be implemented in a subclass")

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["workspace_data_object"] = self.workspace_data_object
        context["managed_group"] = self.managed_group
        context["audit_result"] = self.audit_result
        return context

    def get_managed_group(self, queryset=None):
        """Look up the ManagedGroup by name."""
        try:
            obj = ManagedGroup.objects.get(name=self.kwargs.get("managed_group_slug", None))
        except ManagedGroup.DoesNotExist:
            raise Http404("No ManagedGroups found matching the query")
        return obj

    def get(self, request, *args, **kwargs):
        self.workspace_data_object = self.get_workspace_data_object()
        self.managed_group = self.get_managed_group()
        self.audit_result = self.get_audit_result()
        return super().get(request, *args, **kwargs)

    def post(self, request, *args, **kwargs):
        self.workspace_data_object = self.get_workspace_data_object()
        self.managed_group = self.get_managed_group()
        self.audit_result = self.get_audit_result()
        return super().post(request, *args, **kwargs)

    def form_valid(self, form):
        # Handle the result.
        try:
            with transaction.atomic():
                self.audit_result.handle()
        except (AnVILAPIError, AnVILGroupNotFound) as e:
            if self.request.htmx:
                return HttpResponse(self.htmx_error)
            else:
                messages.error(self.request, "AnVIL API Error: " + str(e))
                return super().form_invalid(form)
        # Otherwise, the audit resolution succeeded.
        if self.request.htmx:
            return HttpResponse(self.htmx_success)
        else:
            return super().form_valid(form)

    def get_success_url(self):
        return self.workspace_data_object.get_absolute_url()
