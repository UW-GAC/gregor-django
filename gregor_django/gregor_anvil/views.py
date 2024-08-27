from anvil_consortium_manager.anvil_api import AnVILAPIError
from anvil_consortium_manager.auth import (
    AnVILConsortiumManagerStaffEditRequired,
    AnVILConsortiumManagerStaffViewRequired,
)
from anvil_consortium_manager.exceptions import AnVILGroupNotFound
from anvil_consortium_manager.models import (
    Account,
    GroupGroupMembership,
    ManagedGroup,
    Workspace,
    WorkspaceGroupSharing,
)
from django.contrib import messages
from django.contrib.auth import get_user_model
from django.contrib.messages.views import SuccessMessageMixin
from django.db import transaction
from django.db.models import Count, Q
from django.forms import Form
from django.http import Http404, HttpResponse
from django.utils.translation import gettext_lazy as _
from django.views.generic import CreateView, DetailView, FormView, TemplateView, UpdateView
from django_tables2 import MultiTableMixin, SingleTableView

from gregor_django.users.tables import UserTable

from . import forms, models, tables
from .audit import upload_workspace_auth_domain_audit, upload_workspace_sharing_audit

User = get_user_model()


class ConsentGroupDetail(AnVILConsortiumManagerStaffViewRequired, DetailView):
    """View to show details about a `ConsentGroups`."""

    model = models.ConsentGroup


class ConsentGroupList(AnVILConsortiumManagerStaffViewRequired, SingleTableView):
    """View to show a list of `ConsentGroups`."""

    model = models.ConsentGroup
    table_class = tables.ConsentGroupTable


class ResearchCenterDetail(AnVILConsortiumManagerStaffViewRequired, MultiTableMixin, DetailView):
    """View to show details about a `ResearchCenter`."""

    model = models.ResearchCenter

    def get_tables(self):
        if self.object.member_group is None:
            members = Account.objects.none()
        else:
            members = Account.objects.filter(
                groupaccountmembership__group=self.object.member_group,
            )
        if self.object.uploader_group is None:
            uploaders = Account.objects.none()
        else:
            uploaders = Account.objects.filter(
                groupaccountmembership__group=self.object.uploader_group,
            )
        return [
            UserTable(User.objects.filter(is_active=True, research_centers=self.object)),
            tables.AccountTable(members, exclude=("user__research_centers", "number_groups")),
            tables.AccountTable(uploaders, exclude=("user__research_centers", "number_groups")),
        ]


class ResearchCenterList(AnVILConsortiumManagerStaffViewRequired, SingleTableView):
    """View to show a list of `ResearchCenters`."""

    model = models.ResearchCenter
    table_class = tables.ResearchCenterTable


class PartnerGroupDetail(AnVILConsortiumManagerStaffViewRequired, MultiTableMixin, DetailView):
    """View to show details about a `PartnerGroup`."""

    model = models.PartnerGroup

    def get_tables(self):
        if self.object.member_group is None:
            members = Account.objects.none()
        else:
            members = Account.objects.filter(
                groupaccountmembership__group=self.object.member_group,
            )
        if self.object.uploader_group is None:
            uploaders = Account.objects.none()
        else:
            uploaders = Account.objects.filter(
                groupaccountmembership__group=self.object.uploader_group,
            )
        return [
            UserTable(User.objects.filter(is_active=True, partner_groups=self.object)),
            tables.AccountTable(members, exclude=("user__research_centers", "number_groups")),
            tables.AccountTable(uploaders, exclude=("user__research_centers", "number_groups")),
        ]


class PartnerGroupList(AnVILConsortiumManagerStaffViewRequired, SingleTableView):
    """View to show a list of `PartnerGroups`."""

    model = models.PartnerGroup
    table_class = tables.PartnerGroupTable


class UploadCycleCreate(AnVILConsortiumManagerStaffEditRequired, SuccessMessageMixin, CreateView):
    """View to create a new UploadCycle object."""

    model = models.UploadCycle
    form_class = forms.UploadCycleCreateForm
    success_message = "Successfully created Upload Cycle."


class UploadCycleUpdate(AnVILConsortiumManagerStaffEditRequired, SuccessMessageMixin, UpdateView):
    """View to create a new UploadCycle object."""

    model = models.UploadCycle
    slug_field = "cycle"
    form_class = forms.UploadCycleUpdateForm
    success_message = "Successfully updated Upload Cycle."


class UploadCycleDetail(AnVILConsortiumManagerStaffViewRequired, MultiTableMixin, DetailView):
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
        upload_workspace_qs = Workspace.objects.filter(uploadworkspace__upload_cycle=self.object)
        combined_workspace_qs = Workspace.objects.filter(combinedconsortiumdataworkspace__upload_cycle=self.object)
        release_workspace_qs = Workspace.objects.filter(releaseworkspace__upload_cycle=self.object)
        dcc_processing_workspace_qs = Workspace.objects.filter(
            dccprocessingworkspace__upload_cycle=self.object,
        )
        dcc_processed_data_workspace_qs = Workspace.objects.filter(
            dccprocesseddataworkspace__upload_cycle=self.object,
        )
        partner_workspaces = self.object.get_partner_upload_workspaces()
        partner_workspace_qs = Workspace.objects.filter(partneruploadworkspace__in=partner_workspaces)
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


class UploadWorkspaceSharingAuditByWorkspace(AnVILConsortiumManagerStaffViewRequired, DetailView):
    """View to audit UploadWorkspace sharing for a specific UploadWorkspace."""

    template_name = "gregor_anvil/upload_workspace_sharing_audit.html"
    model = models.UploadWorkspace

    def get_object(self, queryset=None):
        """Look up the UploadWorkspace by billing project and name."""
        # Filter the queryset based on kwargs.
        billing_project_slug = self.kwargs.get("billing_project_slug", None)
        workspace_slug = self.kwargs.get("workspace_slug", None)
        queryset = models.UploadWorkspace.objects.filter(
            workspace__billing_project__name=billing_project_slug,
            workspace__name=workspace_slug,
        )
        try:
            # Get the single item from the filtered queryset
            obj = queryset.get()
        except queryset.model.DoesNotExist:
            raise Http404(
                _("No %(verbose_name)s found matching the query") % {"verbose_name": queryset.model._meta.verbose_name}
            )
        return obj

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        # Run the audit.
        audit = upload_workspace_sharing_audit.UploadWorkspaceSharingAudit(
            queryset=self.model.objects.filter(pk=self.object.pk)
        )
        audit.run_audit()
        context["verified_table"] = audit.get_verified_table()
        context["errors_table"] = audit.get_errors_table()
        context["needs_action_table"] = audit.get_needs_action_table()
        context["audit_results"] = audit
        return context


class UploadWorkspaceSharingAuditByUploadCycle(AnVILConsortiumManagerStaffViewRequired, DetailView):
    """View to audit UploadWorkspace sharing for a specific UploadWorkspace."""

    template_name = "gregor_anvil/upload_workspace_sharing_audit.html"
    model = models.UploadCycle

    def get_object(self, queryset=None):
        """Look up the UploadWorkspace by billing project and name."""
        # Filter the queryset based on kwargs.
        cycle = self.kwargs.get("cycle", None)
        queryset = self.model.objects.filter(cycle=cycle)
        try:
            # Get the single item from the filtered queryset
            obj = queryset.get()
        except queryset.model.DoesNotExist:
            raise Http404(
                _("No %(verbose_name)s found matching the query") % {"verbose_name": queryset.model._meta.verbose_name}
            )
        return obj

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        # Run the audit.
        audit = upload_workspace_sharing_audit.UploadWorkspaceSharingAudit(
            queryset=models.UploadWorkspace.objects.filter(upload_cycle=self.object)
        )
        audit.run_audit()
        context["verified_table"] = audit.get_verified_table()
        context["errors_table"] = audit.get_errors_table()
        context["needs_action_table"] = audit.get_needs_action_table()
        context["audit_results"] = audit
        return context


class UploadWorkspaceSharingAuditResolve(AnVILConsortiumManagerStaffEditRequired, FormView):
    """View to resolve UploadWorkspace audit results."""

    form_class = Form
    template_name = "gregor_anvil/upload_workspace_sharing_audit_resolve.html"
    htmx_success = """<i class="bi bi-check-circle-fill"></i> Handled!"""
    htmx_error = """<i class="bi bi-x-circle-fill"></i> Error!"""

    def get_upload_workspace(self):
        """Look up the UploadWorkspace by billing project and name."""
        # Filter the queryset based on kwargs.
        billing_project_slug = self.kwargs.get("billing_project_slug", None)
        workspace_slug = self.kwargs.get("workspace_slug", None)
        queryset = models.UploadWorkspace.objects.filter(
            workspace__billing_project__name=billing_project_slug,
            workspace__name=workspace_slug,
        )
        try:
            # Get the single item from the filtered queryset
            obj = queryset.get()
        except queryset.model.DoesNotExist:
            raise Http404(
                _("No %(verbose_name)s found matching the query") % {"verbose_name": queryset.model._meta.verbose_name}
            )
        return obj

    def get_managed_group(self, queryset=None):
        """Look up the ManagedGroup by name."""
        try:
            obj = ManagedGroup.objects.get(name=self.kwargs.get("managed_group_slug", None))
        except ManagedGroup.DoesNotExist:
            raise Http404("No ManagedGroups found matching the query")
        return obj

    def get_audit_result(self):
        audit = upload_workspace_sharing_audit.UploadWorkspaceSharingAudit()
        # No way to set the group queryset, since it is dynamically determined by the workspace.
        audit.audit_workspace_and_group(self.upload_workspace, self.managed_group)
        # Set to completed, because we are just running this one specific check.
        audit.completed = True
        return audit.get_all_results()[0]

    def get(self, request, *args, **kwargs):
        self.upload_workspace = self.get_upload_workspace()
        self.managed_group = self.get_managed_group()
        self.audit_result = self.get_audit_result()
        return super().get(request, *args, **kwargs)

    def post(self, request, *args, **kwargs):
        self.upload_workspace = self.get_upload_workspace()
        self.managed_group = self.get_managed_group()
        self.audit_result = self.get_audit_result()
        return super().post(request, *args, **kwargs)

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["upload_workspace"] = self.upload_workspace
        context["managed_group"] = self.managed_group
        context["audit_result"] = self.audit_result
        return context

    def get_success_url(self):
        return self.upload_workspace.get_absolute_url()

    def form_valid(self, form):
        # Handle the result.
        try:
            # Set up the sharing instance.
            if self.audit_result.current_sharing_instance:
                sharing = self.audit_result.current_sharing_instance
            else:
                sharing = WorkspaceGroupSharing(
                    workspace=self.upload_workspace.workspace,
                    group=self.managed_group,
                )
            with transaction.atomic():
                if isinstance(self.audit_result, upload_workspace_sharing_audit.VerifiedShared):
                    # No changes needed.
                    pass
                elif isinstance(self.audit_result, upload_workspace_sharing_audit.VerifiedNotShared):
                    # No changes needed.
                    pass
                elif isinstance(self.audit_result, upload_workspace_sharing_audit.StopSharing):
                    sharing.anvil_delete()
                    sharing.delete()
                else:
                    if isinstance(self.audit_result, upload_workspace_sharing_audit.ShareAsReader):
                        sharing.access = WorkspaceGroupSharing.READER
                        sharing.can_compute = False
                    elif isinstance(self.audit_result, upload_workspace_sharing_audit.ShareAsWriter):
                        sharing.access = WorkspaceGroupSharing.WRITER
                        sharing.can_compute = False
                    elif isinstance(self.audit_result, upload_workspace_sharing_audit.ShareWithCompute):
                        sharing.access = WorkspaceGroupSharing.WRITER
                        sharing.can_compute = True
                    elif isinstance(self.audit_result, upload_workspace_sharing_audit.ShareAsOwner):
                        sharing.access = WorkspaceGroupSharing.OWNER
                        sharing.can_compute = True
                    sharing.full_clean()
                    sharing.save()
                    sharing.anvil_create_or_update()
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


class UploadWorkspaceAuthDomainAuditByWorkspace(AnVILConsortiumManagerStaffEditRequired, DetailView):
    """View to audit UploadWorkspace sharing for a specific UploadWorkspace."""

    template_name = "gregor_anvil/upload_workspace_auth_domain_audit.html"
    model = models.UploadWorkspace

    def get_object(self, queryset=None):
        """Look up the UploadWorkspace by billing project and name."""
        # Filter the queryset based on kwargs.
        billing_project_slug = self.kwargs.get("billing_project_slug", None)
        workspace_slug = self.kwargs.get("workspace_slug", None)
        queryset = models.UploadWorkspace.objects.filter(
            workspace__billing_project__name=billing_project_slug,
            workspace__name=workspace_slug,
        )
        try:
            # Get the single item from the filtered queryset
            obj = queryset.get()
        except queryset.model.DoesNotExist:
            raise Http404(
                _("No %(verbose_name)s found matching the query") % {"verbose_name": queryset.model._meta.verbose_name}
            )
        return obj

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        # Run the audit.
        audit = upload_workspace_auth_domain_audit.UploadWorkspaceAuthDomainAudit(
            queryset=self.model.objects.filter(pk=self.object.pk)
        )
        audit.run_audit()
        context["verified_table"] = audit.get_verified_table()
        context["errors_table"] = audit.get_errors_table()
        context["needs_action_table"] = audit.get_needs_action_table()
        context["audit_results"] = audit
        return context


class UploadWorkspaceAuthDomainAuditByUploadCycle(AnVILConsortiumManagerStaffViewRequired, DetailView):
    """View to audit UploadWorkspace sharing for a specific UploadWorkspace."""

    template_name = "gregor_anvil/upload_workspace_auth_domain_audit.html"
    model = models.UploadCycle

    def get_object(self, queryset=None):
        """Look up the UploadWorkspace by billing project and name."""
        # Filter the queryset based on kwargs.
        cycle = self.kwargs.get("cycle", None)
        queryset = self.model.objects.filter(cycle=cycle)
        try:
            # Get the single item from the filtered queryset
            obj = queryset.get()
        except queryset.model.DoesNotExist:
            raise Http404(
                _("No %(verbose_name)s found matching the query") % {"verbose_name": queryset.model._meta.verbose_name}
            )
        return obj

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        # Run the audit.
        audit = upload_workspace_auth_domain_audit.UploadWorkspaceAuthDomainAudit(
            queryset=models.UploadWorkspace.objects.filter(upload_cycle=self.object)
        )
        audit.run_audit()
        context["verified_table"] = audit.get_verified_table()
        context["errors_table"] = audit.get_errors_table()
        context["needs_action_table"] = audit.get_needs_action_table()
        context["audit_results"] = audit
        return context


class UploadWorkspaceAuthDomainAuditResolve(AnVILConsortiumManagerStaffEditRequired, FormView):
    """View to resolve UploadWorkspace auth domain audit results."""

    form_class = Form
    template_name = "gregor_anvil/upload_workspace_auth_domain_audit_resolve.html"
    htmx_success = """<i class="bi bi-check-circle-fill"></i> Handled!"""
    htmx_error = """<i class="bi bi-x-circle-fill"></i> Error!"""

    def get_upload_workspace(self):
        """Look up the UploadWorkspace by billing project and name."""
        # Filter the queryset based on kwargs.
        billing_project_slug = self.kwargs.get("billing_project_slug", None)
        workspace_slug = self.kwargs.get("workspace_slug", None)
        queryset = models.UploadWorkspace.objects.filter(
            workspace__billing_project__name=billing_project_slug,
            workspace__name=workspace_slug,
        )
        try:
            # Get the single item from the filtered queryset
            obj = queryset.get()
        except queryset.model.DoesNotExist:
            raise Http404(
                _("No %(verbose_name)s found matching the query") % {"verbose_name": queryset.model._meta.verbose_name}
            )
        return obj

    def get_managed_group(self, queryset=None):
        """Look up the ManagedGroup by name."""
        try:
            obj = ManagedGroup.objects.get(name=self.kwargs.get("managed_group_slug", None))
        except ManagedGroup.DoesNotExist:
            raise Http404("No ManagedGroups found matching the query")
        return obj

    def get_audit_result(self):
        audit = upload_workspace_auth_domain_audit.UploadWorkspaceAuthDomainAudit()
        # No way to set the group queryset, since it is dynamically determined by the workspace.
        audit.audit_workspace_and_group(self.upload_workspace, self.managed_group)
        # Set to completed, because we are just running this one specific check.
        audit.completed = True
        return audit.get_all_results()[0]

    def get(self, request, *args, **kwargs):
        self.upload_workspace = self.get_upload_workspace()
        self.managed_group = self.get_managed_group()
        self.audit_result = self.get_audit_result()
        return super().get(request, *args, **kwargs)

    def post(self, request, *args, **kwargs):
        self.upload_workspace = self.get_upload_workspace()
        self.managed_group = self.get_managed_group()
        self.audit_result = self.get_audit_result()
        return super().post(request, *args, **kwargs)

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["upload_workspace"] = self.upload_workspace
        context["managed_group"] = self.managed_group
        context["audit_result"] = self.audit_result
        return context

    def get_success_url(self):
        return self.upload_workspace.get_absolute_url()

    def form_valid(self, form):
        # Handle the result.
        try:
            with transaction.atomic():
                # Set up the membership instance.
                if self.audit_result.current_membership_instance:
                    membership = self.audit_result.current_membership_instance
                else:
                    membership = GroupGroupMembership(
                        parent_group=self.upload_workspace.workspace.authorization_domains.first(),
                        child_group=self.managed_group,
                    )
                # Now process the result.
                if isinstance(self.audit_result, upload_workspace_auth_domain_audit.VerifiedMember):
                    pass
                elif isinstance(self.audit_result, upload_workspace_auth_domain_audit.VerifiedAdmin):
                    pass
                elif isinstance(self.audit_result, upload_workspace_auth_domain_audit.VerifiedNotMember):
                    pass
                elif isinstance(self.audit_result, upload_workspace_auth_domain_audit.Remove):
                    membership.anvil_delete()
                    membership.delete()
                else:
                    if isinstance(self.audit_result, upload_workspace_auth_domain_audit.ChangeToMember):
                        membership.anvil_delete()
                        membership.role = GroupGroupMembership.MEMBER
                    elif isinstance(self.audit_result, upload_workspace_auth_domain_audit.ChangeToAdmin):
                        membership.anvil_delete()
                        membership.role = GroupGroupMembership.ADMIN
                    else:
                        if isinstance(self.audit_result, upload_workspace_auth_domain_audit.AddMember):
                            membership.role = GroupGroupMembership.MEMBER
                        elif isinstance(self.audit_result, upload_workspace_auth_domain_audit.AddAdmin):
                            membership.role = GroupGroupMembership.ADMIN
                    membership.full_clean()
                    membership.save()
                    membership.anvil_create()
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
