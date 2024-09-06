import django_tables2 as tables
from anvil_consortium_manager.models import ManagedGroup, WorkspaceGroupSharing
from django.conf import settings
from django.db.models import Q, QuerySet

from ..models import CombinedConsortiumDataWorkspace
from . import workspace_sharing_audit_results
from .base import GREGoRAudit


class CombinedConsortiumDataWorkspaceSharingAuditTable(tables.Table):
    """A table to display the audit results of the sharing of a combined consortium data workspace."""

    workspace = tables.Column(verbose_name="Workspace")
    managed_group = tables.Column(verbose_name="Group")

    class Meta:
        attrs = {"class": "table align-middle"}


class CombinedConsortiumDataWorkspaceSharingAudit(GREGoRAudit):
    """A class to audit the sharing of a combined consortium data workspace."""

    DCC_ADMIN_AS_OWNER = "DCC Admins should always be a workspace owner."
    DCC_WRITERS_BEFORE_COMPLETE = "DCC writers should have write and compute access before the workspace is completed."
    DCC_WRITERS_AFTER_COMPLETE = "DCC writers should not have direct access after the workspace is completed."
    DCC_MEMBERS_BEFORE_COMPLETE = "DCC members should have read access before the workspace is completed."
    DCC_MEMBERS_AFTER_COMPLETE = "DCC members should not have direct access after the workspace is completed."
    AUTH_DOMAIN_BEFORE_COMPLETE = "The auth domain should not have access before the workspace is completed."
    AUTH_DOMAIN_AFTER_COMPLETE = "The auth domain should have read access after the workspace is completed."
    GREGOR_ALL_BEFORE = "This group should not have access to this workspace before it is completed."
    GREGOR_ALL_AFTER = "This group should have read access to this workspace after it is completed."
    OTHER_GROUP = "This group should not have access to this workspace."

    results_table_class = CombinedConsortiumDataWorkspaceSharingAuditTable

    def __init__(self, queryset=None):
        super().__init__()
        if queryset is None:
            queryset = CombinedConsortiumDataWorkspace.objects.all()
        elif not (isinstance(queryset, QuerySet) and queryset.model == CombinedConsortiumDataWorkspace):
            raise ValueError("queryset must be a QuerySet of CombinedConsortiumDataWorkspace objects.")
        self.queryset = queryset

    def _run_audit(self):
        for workspace in self.queryset:
            self.audit_combined_workspace(workspace)

    def _get_current_sharing(self, upload_workspace, managed_group):
        try:
            current_sharing = WorkspaceGroupSharing.objects.get(
                workspace=upload_workspace.workspace, group=managed_group
            )
        except WorkspaceGroupSharing.DoesNotExist:
            current_sharing = None
        return current_sharing

    def audit_combined_workspace(self, combined_workspace):
        """Audit sharing for a specific combined workspace."""
        # raise NotImplementedError("write this.")
        # Get a list of managed groups that should be included in this audit.
        group_names_to_include = [
            "GREGOR_DCC_MEMBERS",  # DCC members
            "GREGOR_DCC_WRITERS",  # DCC writers
            "GREGOR_ALL",  # All GREGOR users
            settings.ANVIL_DCC_ADMINS_GROUP_NAME,  # DCC admins
            "anvil-admins",  # AnVIL admins
            "anvil_devs",  # AnVIL devs
        ]
        groups_to_audit = ManagedGroup.objects.filter(
            # Specific groups from above.
            Q(name__in=group_names_to_include)
            |
            # Auth domain.
            Q(workspaceauthorizationdomain__workspace=combined_workspace.workspace)
            |
            # Groups that the workspace is shared with.
            Q(workspacegroupsharing__workspace=combined_workspace.workspace)
        ).distinct()

        for group in groups_to_audit:
            self.audit_workspace_and_group(combined_workspace, group)

    def audit_workspace_and_group(self, combined_workspace, managed_group):
        """Audit sharing for a specific workspace and group."""
        if managed_group.name == settings.ANVIL_DCC_ADMINS_GROUP_NAME:
            self._audit_workspace_and_dcc_admin_group(combined_workspace, managed_group)
        elif managed_group.name == "GREGOR_DCC_WRITERS":
            self._audit_combined_workspace_and_dcc_writer_group(combined_workspace, managed_group)
        elif managed_group.name == "GREGOR_DCC_MEMBERS":
            self._audit_combined_workspace_and_dcc_member_group(combined_workspace, managed_group)
        elif managed_group in combined_workspace.workspace.authorization_domains.all():
            self._audit_combined_workspace_and_auth_domain(combined_workspace, managed_group)
        elif managed_group.name in ["anvil-admins", "anvil_devs"]:
            self._audit_combined_workspace_and_anvil_group(combined_workspace, managed_group)
        else:
            self._audit_combined_workspace_and_other_group(combined_workspace, managed_group)

    def _audit_workspace_and_dcc_admin_group(self, combined_workspace, managed_group):
        """Audit access for a specific UploadWorkspace and the DCC admin group.

        Sharing expectations:
        - Owner access at all times.
        """
        current_sharing = self._get_current_sharing(combined_workspace, managed_group)

        audit_result_args = {
            "workspace": combined_workspace.workspace,
            "managed_group": managed_group,
            "current_sharing_instance": current_sharing,
            "note": self.DCC_ADMIN_AS_OWNER,
        }

        if current_sharing and current_sharing.access == WorkspaceGroupSharing.OWNER:
            self.verified.append(workspace_sharing_audit_results.VerifiedShared(**audit_result_args))
        else:
            self.needs_action.append(workspace_sharing_audit_results.ShareAsOwner(**audit_result_args))

    def _audit_combined_workspace_and_dcc_writer_group(self, combined_workspace, managed_group):
        """Audit access for a specific combined workspace and the DCC Writers group.

        Sharing expectations:
        - Write+compute access before the workspace is completed.
        - No access after the workspace is completed.
        """
        current_sharing = self._get_current_sharing(combined_workspace, managed_group)
        audit_result_args = {
            "workspace": combined_workspace.workspace,
            "managed_group": managed_group,
            "current_sharing_instance": current_sharing,
        }

        if not combined_workspace.date_completed:
            note = self.DCC_WRITERS_BEFORE_COMPLETE
            if current_sharing and current_sharing.access == WorkspaceGroupSharing.OWNER:
                self.errors.append(workspace_sharing_audit_results.ShareWithCompute(note=note, **audit_result_args))
            elif (
                current_sharing
                and current_sharing.access == WorkspaceGroupSharing.WRITER
                and current_sharing.can_compute
            ):
                self.verified.append(workspace_sharing_audit_results.VerifiedShared(note=note, **audit_result_args))
            else:
                self.needs_action.append(
                    workspace_sharing_audit_results.ShareWithCompute(note=note, **audit_result_args)
                )
        else:
            note = self.DCC_WRITERS_AFTER_COMPLETE
            if not current_sharing:
                self.verified.append(workspace_sharing_audit_results.VerifiedNotShared(note=note, **audit_result_args))
            elif current_sharing and current_sharing.access == WorkspaceGroupSharing.OWNER:
                self.errors.append(workspace_sharing_audit_results.StopSharing(note=note, **audit_result_args))
            else:
                self.needs_action.append(workspace_sharing_audit_results.StopSharing(note=note, **audit_result_args))

    def _audit_combined_workspace_and_dcc_member_group(self, combined_workspace, managed_group):
        """Audit access for a specific combined workspace and the DCC members group.

        Sharing expectations:
        - Read access before the workspace is completed.
        - No access after the workspace is completed.
        """
        current_sharing = self._get_current_sharing(combined_workspace, managed_group)
        audit_result_args = {
            "workspace": combined_workspace.workspace,
            "managed_group": managed_group,
            "current_sharing_instance": current_sharing,
        }

        if not combined_workspace.date_completed:
            note = self.DCC_MEMBERS_BEFORE_COMPLETE
            if not current_sharing:
                self.needs_action.append(workspace_sharing_audit_results.ShareAsReader(note=note, **audit_result_args))
            elif current_sharing and current_sharing.access == WorkspaceGroupSharing.READER:
                self.verified.append(workspace_sharing_audit_results.VerifiedShared(note=note, **audit_result_args))
            else:
                self.errors.append(workspace_sharing_audit_results.ShareAsReader(note=note, **audit_result_args))
        else:
            note = self.DCC_MEMBERS_AFTER_COMPLETE
            if not current_sharing:
                self.verified.append(workspace_sharing_audit_results.VerifiedNotShared(note=note, **audit_result_args))
            elif current_sharing and current_sharing.access == WorkspaceGroupSharing.READER:
                self.needs_action.append(workspace_sharing_audit_results.StopSharing(note=note, **audit_result_args))
            else:
                self.errors.append(workspace_sharing_audit_results.StopSharing(note=note, **audit_result_args))

    def _audit_combined_workspace_and_auth_domain(self, combined_workspace, managed_group):
        """Audit access for a specific combined workspace and its auth domain.

        Sharing expectations:
        - Not shared before the workspace is completed.
        - Read after the workspace is completed.
        """
        current_sharing = self._get_current_sharing(combined_workspace, managed_group)
        audit_result_args = {
            "workspace": combined_workspace.workspace,
            "managed_group": managed_group,
            "current_sharing_instance": current_sharing,
        }

        if not combined_workspace.date_completed:
            note = self.AUTH_DOMAIN_BEFORE_COMPLETE
            if not current_sharing:
                self.verified.append(workspace_sharing_audit_results.VerifiedNotShared(note=note, **audit_result_args))
            else:
                self.errors.append(workspace_sharing_audit_results.StopSharing(note=note, **audit_result_args))
        else:
            note = self.AUTH_DOMAIN_AFTER_COMPLETE
            if not current_sharing:
                self.needs_action.append(workspace_sharing_audit_results.ShareAsReader(note=note, **audit_result_args))
            elif current_sharing and current_sharing.access == WorkspaceGroupSharing.READER:
                self.verified.append(workspace_sharing_audit_results.VerifiedShared(note=note, **audit_result_args))
            else:
                self.errors.append(workspace_sharing_audit_results.ShareAsReader(note=note, **audit_result_args))

    def _audit_combined_workspace_and_anvil_group(self, combined_workspace, managed_group):
        pass

    def _audit_combined_workspace_and_other_group(self, combined_workspace, managed_group):
        current_sharing = self._get_current_sharing(combined_workspace, managed_group)
        audit_result_args = {
            "workspace": combined_workspace.workspace,
            "managed_group": managed_group,
            "current_sharing_instance": current_sharing,
            "note": self.OTHER_GROUP,
        }

        if current_sharing:
            self.errors.append(workspace_sharing_audit_results.StopSharing(**audit_result_args))
        else:
            self.verified.append(workspace_sharing_audit_results.VerifiedNotShared(**audit_result_args))
