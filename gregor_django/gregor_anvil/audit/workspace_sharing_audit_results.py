from dataclasses import dataclass

from anvil_consortium_manager.models import (
    ManagedGroup,
    Workspace,
    WorkspaceGroupSharing,
)

from .base import GREGoRAuditResult


@dataclass
class WorkspaceSharingAuditResult(GREGoRAuditResult):
    """Base class to hold results for auditing upload workspace sharing."""

    workspace: Workspace
    note: str
    managed_group: ManagedGroup
    action: str = None
    current_sharing_instance: WorkspaceGroupSharing = None
    handled: bool = False

    def get_table_dictionary(self):
        """Return a dictionary that can be used to populate an instance of `dbGaPDataSharingSnapshotAuditTable`."""
        can_compute = None
        if self.current_sharing_instance and self.current_sharing_instance.access != WorkspaceGroupSharing.READER:
            can_compute = self.current_sharing_instance.can_compute
        row = {
            "workspace": self.workspace,
            "managed_group": self.managed_group,
            "access": self.current_sharing_instance.access if self.current_sharing_instance else None,
            "can_compute": can_compute,
            "note": self.note,
            "action": self.action,
        }
        return row

    def _handle(self):
        raise NotImplementedError("Subclasses must implement this method.")

    def handle(self):
        self._handle()
        self.handled = True


@dataclass
class VerifiedShared(WorkspaceSharingAuditResult):
    """Audit results class for when Sharing has been verified."""

    def __str__(self):
        return f"Verified sharing: {self.note}"

    def _handle(self):
        pass


@dataclass
class VerifiedNotShared(WorkspaceSharingAuditResult):
    """Audit results class for when no Sharing has been verified."""

    def __str__(self):
        return f"Verified not shared: {self.note}"

    def _handle(self):
        pass


@dataclass
class ShareAsReader(WorkspaceSharingAuditResult):
    """Audit results class for when Sharing should be granted as a reader."""

    action: str = "Share as reader"

    def __str__(self):
        return f"Share as reader: {self.note}"

    def _handle(self):
        # Create or update the sharing record.
        if self.current_sharing_instance:
            sharing = self.current_sharing_instance
        else:
            sharing = WorkspaceGroupSharing(
                workspace=self.workspace,
                group=self.managed_group,
            )
        sharing.access = WorkspaceGroupSharing.READER
        sharing.can_compute = False
        sharing.full_clean()
        sharing.save()
        sharing.anvil_create_or_update()


@dataclass
class ShareAsWriter(WorkspaceSharingAuditResult):
    """Audit results class for when Sharing should be granted as a writer."""

    action: str = "Share as writer"

    def __str__(self):
        return f"Share as writer: {self.note}"

    def _handle(self):
        # Create or update the sharing record.
        if self.current_sharing_instance:
            sharing = self.current_sharing_instance
        else:
            sharing = WorkspaceGroupSharing(
                workspace=self.workspace,
                group=self.managed_group,
            )
        sharing.access = WorkspaceGroupSharing.WRITER
        sharing.can_compute = False
        sharing.full_clean()
        sharing.save()
        sharing.anvil_create_or_update()


@dataclass
class ShareAsOwner(WorkspaceSharingAuditResult):
    """Audit results class for when Sharing should be granted as an owner."""

    action: str = "Share as owner"

    def __str__(self):
        return f"Share as owner: {self.note}"

    def _handle(self):
        # Create or update the sharing record.
        if self.current_sharing_instance:
            sharing = self.current_sharing_instance
        else:
            sharing = WorkspaceGroupSharing(
                workspace=self.workspace,
                group=self.managed_group,
            )
        sharing.access = WorkspaceGroupSharing.OWNER
        sharing.can_compute = True
        sharing.full_clean()
        sharing.save()
        sharing.anvil_create_or_update()


@dataclass
class ShareWithCompute(WorkspaceSharingAuditResult):
    """Audit results class for when Sharing should be granted with compute access."""

    action: str = "Share with compute"

    def __str__(self):
        return f"Share with compute: {self.note}"

    def _handle(self):
        # Create or update the sharing record.
        if self.current_sharing_instance:
            sharing = self.current_sharing_instance
        else:
            sharing = WorkspaceGroupSharing(
                workspace=self.workspace,
                group=self.managed_group,
            )
        sharing.access = WorkspaceGroupSharing.WRITER
        sharing.can_compute = True
        sharing.full_clean()
        sharing.save()
        sharing.anvil_create_or_update()


@dataclass
class StopSharing(WorkspaceSharingAuditResult):
    """Audit results class for when Sharing should be removed for a known reason."""

    action: str = "Stop sharing"

    def __str__(self):
        return f"Stop sharing: {self.note}"

    def _handle(self):
        # Remove the sharing record.
        self.current_sharing_instance.anvil_delete()
        self.current_sharing_instance.delete()


@dataclass
class Error(WorkspaceSharingAuditResult):
    """Audit results class for when an error has been detected (e.g., shared and never should have been)."""

    pass
