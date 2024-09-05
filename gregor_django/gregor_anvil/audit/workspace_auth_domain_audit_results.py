from dataclasses import dataclass

from anvil_consortium_manager.models import GroupGroupMembership, ManagedGroup

from ..models import UploadWorkspace
from .base import GREGoRAuditResult


@dataclass
class WorkspaceAuthDomainAuditResult(GREGoRAuditResult):
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
class VerifiedMember(WorkspaceAuthDomainAuditResult):
    """Audit results class for when member membership has been verified."""

    def __str__(self):
        return f"Verified member: {self.note}"


@dataclass
class VerifiedAdmin(WorkspaceAuthDomainAuditResult):
    """Audit results class for when membership with an admin role has been verified."""

    is_shared: bool = False

    def __str__(self):
        return f"Verified admin: {self.note}"


@dataclass
class VerifiedNotMember(WorkspaceAuthDomainAuditResult):
    """Audit results class for when member membership has been verified."""

    def __str__(self):
        return f"Verified member: {self.note}"


@dataclass
class AddMember(WorkspaceAuthDomainAuditResult):
    """Audit results class for when a member role should be added."""

    action: str = "Add member"

    def __str__(self):
        return f"Add member: {self.note}"


@dataclass
class AddAdmin(WorkspaceAuthDomainAuditResult):
    """Audit results class for when an admin role should be added."""

    action: str = "Add admin"

    def __str__(self):
        return f"Add admin: {self.note}"


@dataclass
class ChangeToMember(WorkspaceAuthDomainAuditResult):
    """Audit results class for when an admin role should be changed to a member role."""

    action: str = "Change to member"

    def __str__(self):
        return f"Change to member: {self.note}"


@dataclass
class ChangeToAdmin(WorkspaceAuthDomainAuditResult):
    """Audit results class for when a member role should be changed to an admin role."""

    action: str = "Change to admin"

    def __str__(self):
        return f"Change to admin: {self.note}"


@dataclass
class Remove(WorkspaceAuthDomainAuditResult):
    """Audit results class for when group membership should be removed."""

    action: str = "Remove"

    def __str__(self):
        return f"Share as owner: {self.note}"
