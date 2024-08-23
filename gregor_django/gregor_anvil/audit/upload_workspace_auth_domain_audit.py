from dataclasses import dataclass

import django_tables2 as tables
from anvil_consortium_manager.models import GroupGroupMembership, ManagedGroup
from django.conf import settings
from django.db.models import Q, QuerySet

from ..models import CombinedConsortiumDataWorkspace, UploadWorkspace
from .base import GREGoRAudit, GREGoRAuditResult


@dataclass
class UploadWorkspaceAuthDomainAuditResult(GREGoRAuditResult):
    """Base class to hold results for auditing upload workspace sharing."""

    workspace: UploadWorkspace
    note: str
    managed_group: ManagedGroup
    action: str = None
    current_membership_instance: GroupGroupMembership = None

    def get_table_dictionary(self):
        """Return a dictionary that can be used to populate an instance of `dbGaPDataSharingSnapshotAuditTable`."""
        row = {
            "workspace": self.workspace,
            "managed_group": self.managed_group,
            "role": self.current_membership_instance.role if self.current_membership_instance else None,
            "note": self.note,
            "action": self.action,
        }
        return row


@dataclass
class VerifiedMember(UploadWorkspaceAuthDomainAuditResult):
    """Audit results class for when member membership has been verified."""

    def __str__(self):
        return f"Verified member: {self.note}"


@dataclass
class VerifiedAdmin(UploadWorkspaceAuthDomainAuditResult):
    """Audit results class for when membership with an admin role has been verified."""

    is_shared: bool = False

    def __str__(self):
        return f"Verified admin: {self.note}"


@dataclass
class VerifiedNotMember(UploadWorkspaceAuthDomainAuditResult):
    """Audit results class for when member membership has been verified."""

    def __str__(self):
        return f"Verified member: {self.note}"


@dataclass
class AddMember(UploadWorkspaceAuthDomainAuditResult):
    """Audit results class for when a member role should be added."""

    action: str = "Add member"

    def __str__(self):
        return f"Add member: {self.note}"


@dataclass
class AddAdmin(UploadWorkspaceAuthDomainAuditResult):
    """Audit results class for when an admin role should be added."""

    action: str = "Add admin"

    def __str__(self):
        return f"Add admin: {self.note}"


@dataclass
class ChangeToMember(UploadWorkspaceAuthDomainAuditResult):
    """Audit results class for when an admin role should be changed to a member role."""

    action: str = "Change to member"

    def __str__(self):
        return f"Change to member: {self.note}"


@dataclass
class ChangeToAdmin(UploadWorkspaceAuthDomainAuditResult):
    """Audit results class for when a member role should be changed to an admin role."""

    action: str = "Change to admin"

    def __str__(self):
        return f"Change to admin: {self.note}"


@dataclass
class Remove(UploadWorkspaceAuthDomainAuditResult):
    """Audit results class for when group membership should be removed."""

    action: str = "Share as owner"

    def __str__(self):
        return f"Share as owner: {self.note}"


class UploadWorkspaceAuthDomainAuditTable(tables.Table):
    """A table to show results from a UploadWorkspaceAuthDomainAudit subclass."""

    workspace = tables.Column(linkify=True)
    managed_group = tables.Column(linkify=True)
    # is_shared = tables.Column()
    role = tables.Column()
    note = tables.Column()
    # action = tables.Column()
    action = tables.TemplateColumn(
        template_name="gregor_anvil/snippets/upload_workspace_auth_domain_audit_action_button.html"
    )

    class Meta:
        attrs = {"class": "table align-middle"}


class UploadWorkspaceAuthDomainAudit(GREGoRAudit):
    """A class to hold audit results for the GREGoR UploadWorkspace auth domain audit."""

    # RC notes.
    RC_BEFORE_COMBINED = (
        "RC uploader and member group should be members of the auth domain before the combined workspace is complete."
    )
    RC_AFTER_COMBINED = (
        "RC uploader and member group should not be direct members of the auth domain"
        " after the combined workspace is complete."
    )
    RC_NON_MEMBERS = "RC non-member group should always be a member of the auth domain."

    # DCC notes.
    DCC_ADMINS = "DCC admin group should always be an admin of the auth domain."

    results_table_class = UploadWorkspaceAuthDomainAuditTable

    def __init__(self, queryset=None):
        super().__init__()
        if queryset is None:
            queryset = UploadWorkspace.objects.all()
        if not (isinstance(queryset, QuerySet) and queryset.model is UploadWorkspace):
            raise ValueError("queryset must be a queryset of UploadWorkspace objects.")
        self.queryset = queryset

    def _run_audit(self):
        for workspace in self.queryset:
            self.audit_upload_workspace(workspace)

    def _get_current_membership(self, upload_workspace, managed_group):
        try:
            current_membership = GroupGroupMembership.objects.get(
                parent_group=upload_workspace.workspace.authorization_domains.first(), child_group=managed_group
            )
        except GroupGroupMembership.DoesNotExist:
            current_membership = None
        return current_membership

    def _get_combined_workspace(self, upload_cycle):
        """Returns the combined workspace, but only if it is ready for sharing."""
        try:
            combined_workspace = CombinedConsortiumDataWorkspace.objects.get(
                upload_cycle=upload_cycle, date_completed__isnull=False
            )
        except CombinedConsortiumDataWorkspace.DoesNotExist:
            combined_workspace = None
        return combined_workspace

    def audit_upload_workspace(self, upload_workspace):
        """Audit the auth domain membership of a single UploadWorkspace."""
        research_center = upload_workspace.research_center
        groups_to_audit = ManagedGroup.objects.filter(
            # RC uploader group.
            Q(research_center_of_uploaders=research_center)
            |
            # RC member group.
            Q(research_center_of_members=research_center)
        ).distinct()

        for group in groups_to_audit:
            self.audit_workspace_and_group(upload_workspace, group)

    def audit_workspace_and_group(self, upload_workspace, managed_group):
        if managed_group == upload_workspace.research_center.uploader_group:
            self._audit_workspace_and_group_for_rc(upload_workspace, managed_group)
        elif managed_group == upload_workspace.research_center.member_group:
            self._audit_workspace_and_group_for_rc(upload_workspace, managed_group)
        elif managed_group == upload_workspace.research_center.non_member_group:
            self._audit_workspace_and_group_for_rc_non_members(upload_workspace, managed_group)
        elif managed_group.name == settings.ANVIL_DCC_ADMINS_GROUP_NAME:
            self._audit_workspace_and_group_for_dcc_admin(upload_workspace, managed_group)

    def _audit_workspace_and_group_for_rc(self, upload_workspace, managed_group):
        combined_workspace = self._get_combined_workspace(upload_workspace.upload_cycle)
        membership = self._get_current_membership(upload_workspace, managed_group)
        if combined_workspace:
            note = self.RC_AFTER_COMBINED
        else:
            note = self.RC_BEFORE_COMBINED
        result_kwargs = {
            "workspace": upload_workspace,
            "managed_group": managed_group,
            "current_membership_instance": membership,
            "note": note,
        }

        if not combined_workspace and not membership:
            self.needs_action.append(AddMember(**result_kwargs))
        elif not combined_workspace and membership:
            if membership.role == GroupGroupMembership.MEMBER:
                self.verified.append(VerifiedMember(**result_kwargs))
            else:
                self.errors.append(ChangeToMember(**result_kwargs))
        elif combined_workspace and not membership:
            self.verified.append(VerifiedNotMember(**result_kwargs))
        elif combined_workspace and membership:
            if membership.role == "ADMIN":
                self.errors.append(Remove(**result_kwargs))
            else:
                self.needs_action.append(Remove(**result_kwargs))

    def _audit_workspace_and_group_for_rc_non_members(self, upload_workspace, managed_group):
        membership = self._get_current_membership(upload_workspace, managed_group)
        if not membership:
            self.needs_action.append(
                AddMember(
                    workspace=upload_workspace,
                    managed_group=managed_group,
                    note=self.RC_NON_MEMBERS,
                    current_membership_instance=membership,
                )
            )
        elif membership.role == GroupGroupMembership.MEMBER:
            self.verified.append(
                VerifiedMember(
                    workspace=upload_workspace,
                    managed_group=managed_group,
                    note=self.RC_NON_MEMBERS,
                    current_membership_instance=membership,
                )
            )
        else:
            self.errors.append(
                ChangeToMember(
                    workspace=upload_workspace,
                    managed_group=managed_group,
                    note=self.RC_NON_MEMBERS,
                    current_membership_instance=membership,
                )
            )

    def _audit_workspace_and_group_for_dcc_admin(self, upload_workspace, managed_group):
        membership = self._get_current_membership(upload_workspace, managed_group)
        if not membership:
            self.needs_action.append(
                AddAdmin(
                    workspace=upload_workspace,
                    managed_group=managed_group,
                    note=self.DCC_ADMINS,
                    current_membership_instance=membership,
                )
            )
        elif membership.role == GroupGroupMembership.ADMIN:
            self.verified.append(
                VerifiedAdmin(
                    workspace=upload_workspace,
                    managed_group=managed_group,
                    note=self.DCC_ADMINS,
                    current_membership_instance=membership,
                )
            )
        else:
            self.needs_action.append(
                ChangeToAdmin(
                    workspace=upload_workspace,
                    managed_group=managed_group,
                    note=self.DCC_ADMINS,
                    current_membership_instance=membership,
                )
            )
