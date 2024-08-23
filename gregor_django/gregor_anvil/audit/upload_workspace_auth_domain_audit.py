from dataclasses import dataclass

import django_tables2 as tables
from anvil_consortium_manager.models import GroupGroupMembership, ManagedGroup
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

    # Before combined workspace.
    RC_BEFORE_COMBINED = (
        "RC uploader and member group should be members of the auth domain before the combined workspace is complete."
    )

    # After combined workspace.
    RC_AFTER_COMBINED = (
        "RC uploader and member group should not be direct members of the auth domain"
        " after the combined workspace is complete."
    )

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
        ).distinct()

        for group in groups_to_audit:
            self.audit_workspace_and_group(upload_workspace, group)

    def audit_workspace_and_group(self, upload_workspace, managed_group):
        if managed_group.research_center_of_uploaders == upload_workspace.research_center:
            self._audit_workspace_and_group_for_rc(upload_workspace, managed_group)

    def _audit_workspace_and_group_for_rc(self, upload_workspace, managed_group):
        combined_workspace = self._get_combined_workspace(upload_workspace.upload_cycle)
        membership = self._get_current_membership(upload_workspace, managed_group)
        if not combined_workspace and not membership:
            self.needs_action.append(
                AddMember(
                    workspace=upload_workspace,
                    managed_group=managed_group,
                    note=self.RC_BEFORE_COMBINED,
                    current_membership_instance=membership,
                )
            )
        elif not combined_workspace and membership:
            if membership.role == GroupGroupMembership.MEMBER:
                self.verified.append(
                    VerifiedMember(
                        workspace=upload_workspace,
                        managed_group=managed_group,
                        note=self.RC_BEFORE_COMBINED,
                        current_membership_instance=membership,
                    )
                )
            else:
                self.errors.append(
                    ChangeToMember(
                        workspace=upload_workspace,
                        managed_group=managed_group,
                        note=self.RC_BEFORE_COMBINED,
                        current_membership_instance=membership,
                    )
                )
        elif combined_workspace and not membership:
            self.verified.append(
                VerifiedNotMember(
                    workspace=upload_workspace,
                    managed_group=managed_group,
                    note=self.RC_AFTER_COMBINED,
                    current_membership_instance=membership,
                )
            )
        elif combined_workspace and membership:
            if membership.role == "ADMIN":
                self.errors.append(
                    Remove(
                        workspace=upload_workspace,
                        managed_group=managed_group,
                        note=self.RC_AFTER_COMBINED,
                        current_membership_instance=membership,
                    )
                )
            else:
                self.needs_action.append(
                    Remove(
                        workspace=upload_workspace,
                        managed_group=managed_group,
                        note=self.RC_AFTER_COMBINED,
                        current_membership_instance=membership,
                    )
                )
