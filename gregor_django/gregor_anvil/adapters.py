from anvil_consortium_manager.adapters.account import BaseAccountAdapter
from anvil_consortium_manager.adapters.managed_group import BaseManagedGroupAdapter
from anvil_consortium_manager.adapters.workspace import BaseWorkspaceAdapter
from anvil_consortium_manager.forms import WorkspaceForm
from anvil_consortium_manager.models import (
    GroupGroupMembership,
    ManagedGroup,
    WorkspaceGroupSharing,
)
from anvil_consortium_manager.tables import ManagedGroupStaffTable
from django.conf import settings
from django.db.models import Q

from . import filters, forms, models, tables


class WorkspaceAdminSharingAdapterMixin:
    """Helper class to share workspaces with the GREGOR_DCC_ADMINs group."""

    def after_anvil_create(self, workspace):
        super().after_anvil_create(workspace)
        # Share the workspace with the ADMINs group as an owner.
        try:
            admins_group = ManagedGroup.objects.get(name=settings.ANVIL_DCC_ADMINS_GROUP_NAME)
        except ManagedGroup.DoesNotExist:
            return
        sharing = WorkspaceGroupSharing.objects.create(
            workspace=workspace,
            group=admins_group,
            access=WorkspaceGroupSharing.OWNER,
            can_compute=True,
        )
        sharing.anvil_create_or_update()

    def after_anvil_import(self, workspace):
        super().after_anvil_import(workspace)
        # # Check if the workspace is already shared with the ADMINs group.
        try:
            admins_group = ManagedGroup.objects.get(name=settings.ANVIL_DCC_ADMINS_GROUP_NAME)
        except ManagedGroup.DoesNotExist:
            return
        try:
            sharing = WorkspaceGroupSharing.objects.get(
                workspace=workspace,
                group=admins_group,
            )
        except WorkspaceGroupSharing.DoesNotExist:
            sharing = WorkspaceGroupSharing.objects.create(
                workspace=workspace,
                group=admins_group,
                access=WorkspaceGroupSharing.OWNER,
                can_compute=True,
            )
            sharing.save()
            sharing.anvil_create_or_update()
        else:
            # If the existing sharing record exists, make sure it has the correct permissions.
            if not sharing.can_compute or sharing.access != WorkspaceGroupSharing.OWNER:
                sharing.can_compute = True
                sharing.access = WorkspaceGroupSharing.OWNER
                sharing.save()
                sharing.anvil_create_or_update()


class AccountAdapter(BaseAccountAdapter):
    """Custom account adapter for PRIMED."""

    list_table_class = tables.AccountTable
    list_filterset_class = filters.AccountListFilter
    account_link_verify_redirect = "users:redirect"
    account_link_email_subject = "Verify your AnVIL account email"
    account_verify_notification_email = "gregorconsortium@uw.edu"

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


class ManagedGroupAdapter(BaseManagedGroupAdapter):
    """Adapter for ManagedGroups."""

    list_table_class = ManagedGroupStaffTable

    def after_anvil_create(self, managed_group):
        super().after_anvil_create(managed_group)
        # Add the ADMINs group as an admin of the auth domain.
        try:
            admins_group = ManagedGroup.objects.get(name=settings.ANVIL_DCC_ADMINS_GROUP_NAME)
        except ManagedGroup.DoesNotExist:
            return
        membership = GroupGroupMembership.objects.create(
            parent_group=managed_group,
            child_group=admins_group,
            role=GroupGroupMembership.ADMIN,
        )
        membership.anvil_create()


class UploadWorkspaceAdapter(WorkspaceAdminSharingAdapterMixin, BaseWorkspaceAdapter):
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


class PartnerUploadWorkspaceAdapter(WorkspaceAdminSharingAdapterMixin, BaseWorkspaceAdapter):
    """Adapter for PartnerUploadWorkspaces."""

    type = "partner_upload"
    name = "Partner upload workspace"
    description = "Workspaces that contain data uploaded by a Partner Group "
    list_table_class_view = tables.PartnerUploadWorkspaceTable
    list_table_class_staff_view = tables.PartnerUploadWorkspaceTable

    workspace_data_model = models.PartnerUploadWorkspace
    workspace_data_form_class = forms.PartnerUploadWorkspaceForm
    workspace_form_class = WorkspaceForm
    workspace_detail_template_name = "gregor_anvil/partneruploadworkspace_detail.html"


class ResourceWorkspaceAdapter(WorkspaceAdminSharingAdapterMixin, BaseWorkspaceAdapter):
    """Adapter for ResourceWorkspaces."""

    type = "resource"
    name = "Resource workspace"
    description = (
        "Workspaces that contain general Consortium resources (e.g., examples of using AnVIL, working with data, etc.)"  # noqa: E501
    )
    list_table_class_view = tables.DefaultWorkspaceTable
    list_table_class_staff_view = tables.DefaultWorkspaceTable
    workspace_data_model = models.ResourceWorkspace
    workspace_data_form_class = forms.ResourceWorkspaceForm
    workspace_detail_template_name = "gregor_anvil/resourceworkspace_detail.html"
    workspace_form_class = WorkspaceForm


class TemplateWorkspaceAdapter(WorkspaceAdminSharingAdapterMixin, BaseWorkspaceAdapter):
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


class CombinedConsortiumDataWorkspaceAdapter(WorkspaceAdminSharingAdapterMixin, BaseWorkspaceAdapter):
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


class ReleaseWorkspaceAdapter(WorkspaceAdminSharingAdapterMixin, BaseWorkspaceAdapter):
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


class DCCProcessingWorkspaceAdapter(WorkspaceAdminSharingAdapterMixin, BaseWorkspaceAdapter):
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


class DCCProcessedDataWorkspaceAdapter(WorkspaceAdminSharingAdapterMixin, BaseWorkspaceAdapter):
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


class ExchangeWorkspaceAdapter(WorkspaceAdminSharingAdapterMixin, BaseWorkspaceAdapter):
    """Adapter for ExchangeWorkspaces."""

    type = "exchange"
    name = "Exchange workspace"
    description = "Workspaces for exchanging data with a Research Center outside of an upload cycle"
    list_table_class_view = tables.ExchangeWorkspaceTable
    list_table_class_staff_view = tables.ExchangeWorkspaceTable
    workspace_data_model = models.ExchangeWorkspace
    workspace_data_form_class = forms.ExchangeWorkspaceForm
    workspace_form_class = WorkspaceForm
    workspace_detail_template_name = "gregor_anvil/exchangeworkspace_detail.html"
    workspace_list_template_name = "gregor_anvil/exchangeworkspace_list.html"
