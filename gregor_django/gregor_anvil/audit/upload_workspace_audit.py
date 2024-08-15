from dataclasses import dataclass

import django_tables2 as tables
from anvil_consortium_manager.models import ManagedGroup, WorkspaceGroupSharing
from django.conf import settings
from django.db.models import Q, QuerySet
from django.utils import timezone

from ..models import UploadWorkspace

# from primed.primed_anvil.tables import BooleanIconColumn
from .base import GREGoRAudit, GREGoRAuditResult


@dataclass
class UploadWorkspaceAuditResult(GREGoRAuditResult):
    """Base class to hold results for auditing upload workspace sharing."""

    workspace: UploadWorkspace
    note: str
    managed_group: ManagedGroup
    is_shared: bool
    action: str = None

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
        }
        return row


@dataclass
class VerifiedShared(UploadWorkspaceAuditResult):
    """Audit results class for when Sharing has been verified."""

    has_Sharing: bool = True

    def __str__(self):
        return f"Verified sharing: {self.note}"


@dataclass
class VerifiedNotShared(UploadWorkspaceAuditResult):
    """Audit results class for when no Sharing has been verified."""

    has_Sharing: bool = False

    def __str__(self):
        return f"Verified not shared: {self.note}"


@dataclass
class Share(UploadWorkspaceAuditResult):
    """Audit results class for when Sharing should be granted."""

    has_Sharing: bool = False
    action: str = "Share"

    def __str__(self):
        return f"Share: {self.note}"


@dataclass
class StopSharing(UploadWorkspaceAuditResult):
    """Audit results class for when Sharing should be removed for a known reason."""

    has_Sharing: bool = True
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
    # action = tables.TemplateColumn(template_name="gregor_anvil/snippets/upload_workspace_audit_action_button.html")

    class Meta:
        attrs = {"class": "table align-middle"}


class UploadWorkspaceAudit(GREGoRAudit):
    """A class to hold audit results for the GREGoR UploadWorkspace audit."""

    CURRENT_CYCLE_RC_MEMBER_GROUP = "RC member group has access during current upload cycle."

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
        # Check if the workspace is from a past, current, or future upload cycle.
        if upload_workspace.upload_cycle.start_date > timezone.localdate():
            self._audit_workspace_and_group_for_future_upload_cycle(upload_workspace, managed_group)
        elif upload_workspace.upload_cycle.end_date >= timezone.localdate():
            self._audit_workspace_and_group_for_current_upload_cycle(upload_workspace, managed_group)
        elif upload_workspace.upload_cycle.end_date < timezone.localdate():
            self._audit_workspace_and_group_for_previous_upload_cycle(upload_workspace, managed_group)
        else:
            raise ValueError("Upload cycle is not in the past, present, or future.")

    def _audit_workspace_and_group_for_current_upload_cycle(self, upload_workspace, managed_group):
        """Audit a workspace from the current upload cycle.

        Groups that should have access are:
        - GREGOR_DCC_WRITERS: write access
        - GREGOR_DCC_ADMINS: owner access
        - RC uploader group: write access
        - Auth domain: read access
        """
        try:
            WorkspaceGroupSharing.objects.get(workspace=upload_workspace.workspace, group=managed_group)
        except WorkspaceGroupSharing.DoesNotExist:
            pass
        else:
            self.verified.append(
                VerifiedShared(
                    workspace=upload_workspace,
                    note=self.CURRENT_CYCLE_RC_MEMBER_GROUP,
                    managed_group=managed_group,
                    is_shared=True,
                )
            )

        # Groups that should have access

    def _audit_workspace_and_group_for_future_upload_cycle(self, upload_workspace, managed_group):
        pass

    def _audit_workspace_and_group_for_previous_upload_cycle(self, upload_workspace, managed_group):
        pass
