from anvil_consortium_manager.adapters.account import BaseAccountAdapter
from anvil_consortium_manager.adapters.managed_group import BaseManagedGroupAdapter
from anvil_consortium_manager.adapters.mixins import (
    GroupGroupMembershipAdapterMixin,
    GroupGroupMembershipRole,
    WorkspaceSharingAdapterMixin,
    WorkspaceSharingPermission,
)
from anvil_consortium_manager.adapters.workspace import BaseWorkspaceAdapter
from anvil_consortium_manager.forms import WorkspaceForm
from anvil_consortium_manager.models import (
    GroupAccountMembership,
    ManagedGroup,
    Workspace,
    WorkspaceGroupSharing,
)
from anvil_consortium_manager.tables import ManagedGroupStaffTable
from django.conf import settings
from django.db.models import Q

from . import filters, forms, models, tables

workspace_admin_sharing_permission = WorkspaceSharingPermission(
    group_name=settings.ANVIL_DCC_ADMINS_GROUP_NAME,
    access=WorkspaceGroupSharing.OWNER,
    can_compute=True,
)


class AccountAdapter(BaseAccountAdapter):
    """Custom account adapter for PRIMED."""

    list_table_class = tables.AccountTable
    list_filterset_class = filters.AccountListFilter
    account_link_verify_redirect = "users:redirect"
    account_link_email_subject = "Verify your AnVIL account email"
    account_verification_notification_email = "gregorconsortium@uw.edu"
    account_verification_notification_template = "gregor_anvil/account_notification_email.html"

    after_account_verification_change_reason = "added automatically after account verification"

    def get_autocomplete_queryset(self, queryset, q):
        """Filter to Accounts where the email or the associated user name matches the query `q`."""
        if q:
            queryset = queryset.filter(Q(email__icontains=q) | Q(user__name__icontains=q))
        return queryset

    def get_autocomplete_label(self, account):
        """Adapter to provide a label for an account in autocomplete views."""
        if account.user:
            name = account.user.name
        else:
            name = "---"
        return "{} ({})".format(name, account.email)

    def after_account_verification(self, account):
        """Add the user to appropriate MEMBERS groups."""
        super().after_account_verification(account)
        # Get a list of RC and PartnerGroup member groups.
        groups = ManagedGroup.objects.filter(
            Q(research_center_of_members__user=account.user) | Q(partner_group_of_members__user=account.user),
        ).distinct()
        for group in groups:
            try:
                membership = GroupAccountMembership.objects.get(
                    group=group,
                    account=account,
                )
            except GroupAccountMembership.DoesNotExist:
                membership = GroupAccountMembership(
                    group=group,
                    account=account,
                    role=GroupAccountMembership.RoleChoices.MEMBER,
                )
                membership.full_clean()
                membership._change_reason = self.after_account_verification_change_reason
                membership.save()
                membership.anvil_create()

    def get_account_verification_notification_context(self, account):
        """Get the context for the account verification notification email."""
        context = super().get_account_verification_notification_context(account)
        # Add the list of groups that the account is already in.
        memberships = GroupAccountMembership.objects.filter(account=account)
        context["memberships"] = memberships
        return context


class ManagedGroupAdapter(GroupGroupMembershipAdapterMixin, BaseManagedGroupAdapter):
    """Adapter for ManagedGroups."""

    list_table_class = ManagedGroupStaffTable
    membership_roles = [
        GroupGroupMembershipRole(
            # Name of the group to add as a member.
            child_group_name=settings.ANVIL_DCC_ADMINS_GROUP_NAME,
            # Role that this group should have.
            role="ADMIN",
        )
    ]


class UploadWorkspaceAdapter(WorkspaceSharingAdapterMixin, BaseWorkspaceAdapter):
    """Adapter for UploadWorkspaces."""

    type = "upload"
    name = "Upload workspace"
    description = "Workspaces that contain data uploaded by RCs in a given upload cycle"
    list_table_class_view = tables.UploadWorkspaceTable
    list_table_class_staff_view = tables.UploadWorkspaceTable
    workspace_data_model = models.UploadWorkspace
    workspace_data_form_class = forms.UploadWorkspaceForm
    workspace_form_class = WorkspaceForm
    workspace_detail_template_name = "gregor_anvil/uploadworkspace_detail.html"
    workspace_list_template_name = "gregor_anvil/uploadworkspace_list.html"
    share_permissions = [workspace_admin_sharing_permission]

    def get_autocomplete_queryset(self, queryset, q, forwarded={}):
        """Filter to Accounts where the email or the associated user name matches the query `q`."""
        consent_group = forwarded.get("consent_group", None)
        if consent_group:
            queryset = queryset.filter(consent_group=consent_group)

        upload_cycle = forwarded.get("upload_cycle", None)
        if upload_cycle:
            queryset = queryset.filter(upload_cycle=upload_cycle)

        if q:
            queryset = queryset.filter(workspace__name__icontains=q)

        return queryset


class PartnerUploadWorkspaceAdapter(WorkspaceSharingAdapterMixin, BaseWorkspaceAdapter):
    """Adapter for PartnerUploadWorkspaces."""

    type = "partner_upload"
    name = "Partner upload workspace"
    description = "Workspaces that contain data uploaded by a Partner Group "
    list_table_class_view = tables.PartnerUploadWorkspaceTable
    list_table_class_staff_view = tables.PartnerUploadWorkspaceStaffTable

    workspace_data_model = models.PartnerUploadWorkspace
    workspace_data_form_class = forms.PartnerUploadWorkspaceForm
    workspace_form_class = WorkspaceForm
    workspace_detail_template_name = "gregor_anvil/partneruploadworkspace_detail.html"
    share_permissions = [workspace_admin_sharing_permission]


class ResourceWorkspaceAdapter(WorkspaceSharingAdapterMixin, BaseWorkspaceAdapter):
    """Adapter for ResourceWorkspaces."""

    type = "resource"
    name = "Resource workspace"
    description = (
        "Workspaces that contain general Consortium resources (e.g., examples of using AnVIL, working with data, etc.)"  # noqa: E501
    )
    list_table_class_view = tables.DefaultWorkspaceTable
    list_table_class_staff_view = tables.DefaultWorkspaceStaffTable
    workspace_data_model = models.ResourceWorkspace
    workspace_data_form_class = forms.ResourceWorkspaceForm
    workspace_detail_template_name = "gregor_anvil/resourceworkspace_detail.html"
    workspace_form_class = WorkspaceForm
    share_permissions = [workspace_admin_sharing_permission]


class TemplateWorkspaceAdapter(WorkspaceSharingAdapterMixin, BaseWorkspaceAdapter):
    """Adapter for ExampleWorkspaces."""

    type = "template"
    name = "Template workspace"
    description = "Template workspaces that can be cloned to create other workspaces"
    list_table_class_view = tables.TemplateWorkspaceTable
    list_table_class_staff_view = tables.TemplateWorkspaceTable
    workspace_data_model = models.TemplateWorkspace
    workspace_data_form_class = forms.TemplateWorkspaceForm
    workspace_detail_template_name = "gregor_anvil/templateworkspace_detail.html"
    workspace_form_class = WorkspaceForm
    share_permissions = [workspace_admin_sharing_permission]


class CombinedConsortiumDataWorkspaceAdapter(WorkspaceSharingAdapterMixin, BaseWorkspaceAdapter):
    """Adapter for CombinedConsortiumDataWorkspace."""

    type = "combined_consortium"
    name = "Combined consortium data workspace"
    description = "Workspaces for internal consortium use that contain data tables combined across upload workspaces"
    list_table_class_view = tables.CombinedConsortiumDataWorkspaceTable
    list_table_class_staff_view = tables.CombinedConsortiumDataWorkspaceTable
    workspace_data_model = models.CombinedConsortiumDataWorkspace
    workspace_data_form_class = forms.CombinedConsortiumDataWorkspaceForm
    workspace_detail_template_name = "gregor_anvil/combinedconsortiumdataworkspace_detail.html"
    workspace_form_class = WorkspaceForm
    workspace_list_template_name = "gregor_anvil/combinedconsortiumdataworkspace_list.html"
    share_permissions = [workspace_admin_sharing_permission]


class ReleaseWorkspaceAdapter(WorkspaceSharingAdapterMixin, BaseWorkspaceAdapter):
    """Adapter for ReleaseWorkspace."""

    type = "release"
    name = "Release prep workspace"
    description = "Workspaces for preparing releases for the general scientific community via dbGaP"
    list_table_class_view = tables.ReleaseWorkspaceTable
    list_table_class_staff_view = tables.ReleaseWorkspaceTable
    workspace_data_model = models.ReleaseWorkspace
    workspace_data_form_class = forms.ReleaseWorkspaceForm
    workspace_detail_template_name = "gregor_anvil/releaseworkspace_detail.html"
    workspace_form_class = WorkspaceForm
    share_permissions = [workspace_admin_sharing_permission]

    def get_extra_detail_context_data(self, workspace, request):
        """Get extra context data for the release workspace detail view."""
        context = super().get_extra_detail_context_data(workspace, request)
        # Add the list of upload workspaces associated with this release workspace.
        context["contributing_upload_workspace_table"] = tables.UploadWorkspaceTable(
            Workspace.objects.filter(
                pk__in=workspace.releaseworkspace.contributing_upload_workspaces.values_list("workspace__pk", flat=True)
            ),
        )
        context["contributing_dcc_processed_data_workspace_table"] = tables.DCCProcessedDataWorkspaceTable(
            Workspace.objects.filter(
                pk__in=workspace.releaseworkspace.contributing_dcc_processed_data_workspaces.values_list(
                    "workspace__pk", flat=True
                )
            ),
        )
        context["contributing_partner_upload_workspace_table"] = tables.PartnerUploadWorkspaceTable(
            Workspace.objects.filter(
                pk__in=workspace.releaseworkspace.contributing_partner_upload_workspaces.values_list(
                    "workspace__pk", flat=True
                )
            ),
        )
        return context


class DCCProcessingWorkspaceAdapter(WorkspaceSharingAdapterMixin, BaseWorkspaceAdapter):
    """Adapter for DCCProcessingWorkspace."""

    type = "dcc_processing"
    name = "DCC processing workspace"
    description = "Workspaces used for DCC processing of data"
    list_table_class_view = tables.DCCProcessingWorkspaceTable
    list_table_class_staff_view = tables.DCCProcessingWorkspaceTable
    workspace_data_model = models.DCCProcessingWorkspace
    workspace_data_form_class = forms.DCCProcessingWorkspaceForm
    workspace_detail_template_name = "gregor_anvil/dccprocessingworkspace_detail.html"
    workspace_form_class = WorkspaceForm
    share_permissions = [workspace_admin_sharing_permission]


class DCCProcessedDataWorkspaceAdapter(WorkspaceSharingAdapterMixin, BaseWorkspaceAdapter):
    """Adapter for DCCProcessedDataWorkspace."""

    type = "dcc_processed_data"
    name = "DCC processed data workspace"
    description = "Workspaces containing data processed by the DCC and hosted by AnVIL"
    list_table_class_view = tables.DCCProcessedDataWorkspaceTable
    list_table_class_staff_view = tables.DCCProcessedDataWorkspaceTable
    workspace_data_model = models.DCCProcessedDataWorkspace
    workspace_data_form_class = forms.DCCProcessedDataWorkspaceForm
    workspace_detail_template_name = "gregor_anvil/dccprocesseddataworkspace_detail.html"
    workspace_form_class = WorkspaceForm
    share_permissions = [workspace_admin_sharing_permission]


class ExchangeWorkspaceAdapter(WorkspaceSharingAdapterMixin, BaseWorkspaceAdapter):
    """Adapter for ExchangeWorkspaces."""

    type = "exchange"
    name = "Exchange workspace"
    description = "Workspaces for exchanging data with a Research Center outside of an upload cycle"
    list_table_class_view = tables.ExchangeWorkspaceTable
    list_table_class_staff_view = tables.ExchangeWorkspaceStaffTable
    workspace_data_model = models.ExchangeWorkspace
    workspace_data_form_class = forms.ExchangeWorkspaceForm
    workspace_form_class = WorkspaceForm
    workspace_detail_template_name = "gregor_anvil/exchangeworkspace_detail.html"
    workspace_list_template_name = "gregor_anvil/exchangeworkspace_list.html"
    share_permissions = [workspace_admin_sharing_permission]
