from dataclasses import dataclass

import django_tables2 as tables
from anvil_consortium_manager.models import GroupGroupMembership, ManagedGroup
from django.db.models import QuerySet

from ..models import UploadWorkspace
from .base import GREGoRAudit, GREGoRAuditResult


@dataclass
class UploadWorkspaceAuthDomainAuditResult(GREGoRAuditResult):
    """Base class to hold results for auditing upload workspace sharing."""

    workspace: UploadWorkspace
    note: str
    managed_group: ManagedGroup
    action: str = None
    current_membership_instance: GroupGroupMembership = None

    def get_action_url(self):
        """The URL that handles the action needed."""
        return ""

    def get_table_dictionary(self):
        """Return a dictionary that can be used to populate an instance of `dbGaPDataSharingSnapshotAuditTable`."""
        row = {
            "workspace": self.workspace,
            "managed_group": self.managed_group,
            "access": self.current_membership_instance.access if self.current_membership_instance else None,
            "can_compute": self.current_membership_instance.can_compute if self.current_membership_instance else None,
            "note": self.note,
            "action": self.action,
            "action_url": self.get_action_url(),
        }
        return row


@dataclass
class VerifiedMember(UploadWorkspaceAuthDomainAuditResult):
    """Audit results class for when member membership has been verified."""

    is_shared: bool = True

    def __str__(self):
        return f"Verified member: {self.note}"


@dataclass
class VerifiedAdmin(UploadWorkspaceAuthDomainAuditResult):
    """Audit results class for when membership with an admin role has been verified."""

    is_shared: bool = False

    def __str__(self):
        return f"Verified admin: {self.note}"


@dataclass
class ChangeToMember(UploadWorkspaceAuthDomainAuditResult):
    """Audit results class for when an admin role should be changed to a member role."""

    is_shared: bool = False
    action: str = "Change to member"

    def __str__(self):
        return f"Change to member: {self.note}"


@dataclass
class ChangeToAdmin(UploadWorkspaceAuthDomainAuditResult):
    """Audit results class for when a member role should be changed to an admin role."""

    is_shared: bool = False
    action: str = "Change to admin"

    def __str__(self):
        return f"Change to admin: {self.note}"


@dataclass
class Remove(UploadWorkspaceAuthDomainAuditResult):
    """Audit results class for when group membership should be removed."""

    is_shared: bool = False
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

    def audit_upload_workspace(self, upload_workspace):
        """Audit the auth domain membership of a single UploadWorkspace."""
        pass
