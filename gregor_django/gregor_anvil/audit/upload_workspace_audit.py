from dataclasses import dataclass

import django_tables2 as tables
from anvil_consortium_manager.models import ManagedGroup, WorkspaceGroupSharing
from django.conf import settings
from django.db.models import Q, QuerySet

from ..models import UploadWorkspace

# from primed.primed_anvil.tables import BooleanIconColumn
from .base import GREGoRAudit, GREGoRAuditResult


@dataclass
class UploadWorkspaceAuditResult(GREGoRAuditResult):
    """Base class to hold results for auditing upload workspace sharing."""

    workspace: UploadWorkspace
    note: str
    managed_group: ManagedGroup
    action: str = None
    current_sharing_instance: WorkspaceGroupSharing = None

    def get_action_url(self):
        """The URL that handles the action needed."""
        # return reverse(
        #     "gregor_anvil:audit:upload_workspaces:resolve",
        #     args=[
        #         self.dbgap_application.dbgap_project_id,
        #         self.workspace.workspace.billing_project.name,
        #         self.workspace.workspace.name,
        #     ],
        # )
        return ""

    def get_table_dictionary(self):
        """Return a dictionary that can be used to populate an instance of `dbGaPDataSharingSnapshotAuditTable`."""
        row = {
            "workspace": self.workspace,
            "managed_group": self.managed_group,
            "is_shared": self.is_shared,
            "note": self.note,
            "action": self.action,
            "action_url": self.get_action_url(),
            "current_sharing_instance": self.current_sharing_instance,
        }
        return row


@dataclass
class VerifiedShared(UploadWorkspaceAuditResult):
    """Audit results class for when Sharing has been verified."""

    is_shared: bool = True

    def __str__(self):
        return f"Verified sharing: {self.note}"


@dataclass
class VerifiedNotShared(UploadWorkspaceAuditResult):
    """Audit results class for when no Sharing has been verified."""

    is_shared: bool = False

    def __str__(self):
        return f"Verified not shared: {self.note}"


@dataclass
class ShareAsReader(UploadWorkspaceAuditResult):
    """Audit results class for when Sharing should be granted as a reader."""

    is_shared: bool = False
    action: str = "Share as reader"

    def __str__(self):
        return f"Share as reader: {self.note}"


@dataclass
class ShareAsWriter(UploadWorkspaceAuditResult):
    """Audit results class for when Sharing should be granted as a writer."""

    is_shared: bool = False
    action: str = "Share as writer"

    def __str__(self):
        return f"Share as writer: {self.note}"


@dataclass
class ShareAsOwner(UploadWorkspaceAuditResult):
    """Audit results class for when Sharing should be granted as an owner."""

    is_shared: bool = False
    action: str = "Share as owner"

    def __str__(self):
        return f"Share as owner: {self.note}"


@dataclass
class ShareWithCompute(UploadWorkspaceAuditResult):
    """Audit results class for when Sharing should be granted with compute access."""

    is_shared: bool = False
    action: str = "Share with compute"

    def __str__(self):
        return f"Share with compute: {self.note}"


@dataclass
class StopSharing(UploadWorkspaceAuditResult):
    """Audit results class for when Sharing should be removed for a known reason."""

    is_shared: bool = True
    action: str = "Stop sharing"

    def __str__(self):
        return f"Stop sharing: {self.note}"


@dataclass
class Error(UploadWorkspaceAuditResult):
    """Audit results class for when an error has been detected (e.g., shared and never should have been)."""

    pass


class UploadWorkspaceAuditTable(tables.Table):
    """A table to show results from a UploadWorkspaceAudit subclass."""

    workspace = tables.Column(linkify=True)
    managed_group = tables.Column(linkify=True)
    is_shared = tables.Column()
    note = tables.Column()
    action = tables.Column()
    current_sharing_instance = tables.Column(linkify=True)
    # action = tables.TemplateColumn(template_name="gregor_anvil/snippets/upload_workspace_audit_action_button.html")

    class Meta:
        attrs = {"class": "table align-middle"}


class UploadWorkspaceAudit(GREGoRAudit):
    """A class to hold audit results for the GREGoR UploadWorkspace audit."""

    # Reasons for access/sharing.
    RC_MEMBERS_GROUP_AS_READER = "RC member group should have read access."
    RC_UPLOADER_GROUP_AS_READER = "RC upload group should have read access to past cycles."
    RC_UPLOADER_GROUP_AS_WRITER = "RC upload group should have write access for current and future cycles."
    RC_UPLOADER_GROUP_WITH_COMPUTE = "RC upload group should be able to run compute for the current cycle."

    # Other errors

    results_table_class = UploadWorkspaceAuditTable

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
        """Audit access for a specific UploadWorkspace."""
        # Get a list of managed groups that should be included in this audit.
        # This includes the members group for the RC, the DCC groups, GREGOR_ALL, and the auth domain.
        research_center = upload_workspace.research_center
        groups_to_audit = ManagedGroup.objects.filter(
            # RC member or uploader groups.
            Q(research_center_of_members=research_center)
            | Q(research_center_of_uploaders=research_center)
            |
            # Specific groups.
            Q(name__in=["GREGOR_DCC_WRITERS", "GREGOR_ALL", settings.ANVIL_DCC_ADMINS_GROUP_NAME])
            |
            # Auth domain.
            Q(authorization_domains__workspace=upload_workspace.workspace)
            |
            # Groups that the workspace is shared with.
            Q(workspace_group_sharing__workspace=upload_workspace.workspace)
        )

        for group in groups_to_audit:
            self.audit_workspace_and_group(upload_workspace, group)

    def audit_workspace_and_group(self, upload_workspace, managed_group):
        """Audit access for a specific UploadWorkspace and ManagedGroup."""
        # Check the group type, and then call the appropriate audit method.
        if upload_workspace.research_center.member_group == managed_group:
            self._audit_workspace_and_rc_member_group(upload_workspace, managed_group)
        if upload_workspace.research_center.uploader_group == managed_group:
            self._audit_workspace_and_rc_uploader_group(upload_workspace, managed_group)

    def _audit_workspace_and_rc_member_group(self, upload_workspace, managed_group):
        """Run an audit of the upload workspace for the RC member group.

        The RC member group should always have read access."""
        try:
            sharing_instance = WorkspaceGroupSharing.objects.get(
                workspace=upload_workspace.workspace, group=managed_group
            )
        except WorkspaceGroupSharing.DoesNotExist:
            self.needs_action.append(
                ShareAsReader(
                    workspace=upload_workspace,
                    note=self.RC_MEMBERS_GROUP_AS_READER,
                    managed_group=managed_group,
                    current_sharing_instance=None,
                )
            )
            return

        if sharing_instance.access == sharing_instance.READER:
            self.verified.append(
                VerifiedShared(
                    workspace=upload_workspace,
                    note=self.RC_MEMBERS_GROUP_AS_READER,
                    managed_group=managed_group,
                    current_sharing_instance=sharing_instance,
                )
            )
        else:
            self.needs_action.append(
                ShareAsReader(
                    workspace=upload_workspace,
                    note=self.RC_MEMBERS_GROUP_AS_READER,
                    managed_group=managed_group,
                    current_sharing_instance=sharing_instance,
                )
            )
