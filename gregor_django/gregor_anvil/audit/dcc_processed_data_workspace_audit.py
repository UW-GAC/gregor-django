from anvil_consortium_manager.models import ManagedGroup, WorkspaceGroupSharing
from django.conf import settings
from django.db.models import Q, QuerySet

from ..models import CombinedConsortiumDataWorkspace, DCCProcessedDataWorkspace
from . import workspace_sharing_audit_results
from .base import GREGoRAudit


class DCCProcessedDataWorkspaceSharingAudit(GREGoRAudit):
    """A class to hold audit results for the GREGoR DCCProcessedDataWorkspace audit."""

    # DCC admins.
    DCC_ADMIN_AS_OWNER = "The DCC admins group should always be an admin."
    # DCC members.
    DCC_MEMBERS_BEFORE_COMBINED_COMPLETE = "DCC members should have read access before the combined workspace is ready."
    DCC_MEMBERS_AFTER_COMBINED_COMPLETE = (
        "DCC members should not have direct access after the combined workspace is ready."
    )
    # DCC writers.
    DCC_WRITERS_BEFORE_COMBINED_COMPLETE = (
        "DCC writers should have write and compute access before the combined workspace is ready."
    )
    DCC_WRITERS_AFTER_COMBINED_COMPLETE = (
        "DCC writers should not have direct access after the combined workspace is ready."
    )
    # Auth domain status.
    AUTH_DOMAIN_AS_READER = "The auth domain should always be a reader."
    # Other groups.
    OTHER_GROUP = "This group should not have access to this workspace."

    results_table_class = "foo"

    def __init__(self, queryset=None):
        super().__init__()
        if queryset is None:
            queryset = DCCProcessedDataWorkspace.objects.all()
        if not (isinstance(queryset, QuerySet) and queryset.model is DCCProcessedDataWorkspace):
            raise ValueError("queryset must be a queryset of DCCProcessedDataWorkspace objects.")
        self.queryset = queryset

    def _run_audit(self):
        for workspace in self.queryset:
            self.audit_workspace(workspace)

    def _get_current_sharing(self, workspace_data, managed_group):
        try:
            current_sharing = WorkspaceGroupSharing.objects.get(workspace=workspace_data.workspace, group=managed_group)
        except WorkspaceGroupSharing.DoesNotExist:
            current_sharing = None
        return current_sharing

    def _get_combined_workspace(self, upload_cycle):
        """Returns the combined workspace, but only if it is ready for sharing."""
        try:
            combined_workspace = CombinedConsortiumDataWorkspace.objects.get(
                upload_cycle=upload_cycle, date_completed__isnull=False
            )
        except CombinedConsortiumDataWorkspace.DoesNotExist:
            combined_workspace = None
        return combined_workspace

    def audit_workspace(self, workspace_data):
        """Audit access for a specific DCCProcessedDataWorkspace."""
        # Get a list of managed groups that should be included in this audit.
        # This includes the members group for the RC, the DCC groups, GREGOR_ALL, and the auth domain.
        group_names_to_include = [
            "GREGOR_DCC_WRITERS",  # DCC writers
            settings.ANVIL_DCC_ADMINS_GROUP_NAME,  # DCC admins
            # "anvil-admins",  # AnVIL admins
            # "anvil_devs",  # AnVIL devs
        ]
        groups_to_audit = ManagedGroup.objects.filter(
            # Specific groups from above.
            Q(name__in=group_names_to_include)
            |
            # Auth domain.
            Q(workspaceauthorizationdomain__workspace=workspace_data.workspace)
            |
            # Groups that the workspace is shared with.
            Q(workspacegroupsharing__workspace=workspace_data.workspace)
        ).distinct()

        for group in groups_to_audit:
            self.audit_workspace_and_group(workspace_data, group)

    def audit_workspace_and_group(self, workspace_data, managed_group):
        """Audit access for a specific UploadWorkspace and ManagedGroup."""
        # Check the group type, and then call the appropriate audit method.
        if managed_group in workspace_data.workspace.authorization_domains.all():
            self._audit_workspace_and_auth_domain(workspace_data, managed_group)
        elif managed_group.name == settings.ANVIL_DCC_ADMINS_GROUP_NAME:
            self._audit_workspace_and_dcc_admin_group(workspace_data, managed_group)
        elif managed_group.name == "GREGOR_DCC_WRITERS":
            self._audit_workspace_and_dcc_writer_group(workspace_data, managed_group)
        elif managed_group.name in ["anvil-admins", "anvil_devs"]:
            self._audit_workspace_and_anvil_group(workspace_data, managed_group)
        else:
            self._audit_workspace_and_other_group(workspace_data, managed_group)

    def _audit_workspace_and_dcc_writer_group(self, workspace_data, managed_group):
        """Audit access for a specific UploadWorkspace and the DCC writer group.

        Sharing expectations:
        - Write+compute access before combined workspace is ready.
        - No direct access to after combined workspace is ready (read access via auth domain).
        """
        current_sharing = self._get_current_sharing(workspace_data, managed_group)
        combined_workspace = self._get_combined_workspace(workspace_data.upload_cycle)
        audit_results_arg = {
            "workspace": workspace_data.workspace,
            "managed_group": managed_group,
            "current_sharing_instance": current_sharing,
        }

        if not combined_workspace or combined_workspace.date_completed is None:
            note = self.DCC_WRITERS_BEFORE_COMBINED_COMPLETE
            if (
                current_sharing
                and current_sharing.access == WorkspaceGroupSharing.WRITER
                and current_sharing.can_compute
            ):
                self.verified.append(
                    workspace_sharing_audit_results.VerifiedShared(
                        note=note,
                        **audit_results_arg,
                    )
                )
            elif current_sharing and current_sharing.access == WorkspaceGroupSharing.OWNER:
                self.errors.append(
                    workspace_sharing_audit_results.ShareWithCompute(
                        note=note,
                        **audit_results_arg,
                    )
                )
            else:
                self.needs_action.append(
                    workspace_sharing_audit_results.ShareWithCompute(
                        note=note,
                        **audit_results_arg,
                    )
                )
        elif combined_workspace and combined_workspace.date_completed:
            note = self.DCC_WRITERS_AFTER_COMBINED_COMPLETE
            if current_sharing and current_sharing.access == WorkspaceGroupSharing.OWNER:
                self.errors.append(
                    workspace_sharing_audit_results.StopSharing(
                        note=note,
                        **audit_results_arg,
                    )
                )
            elif current_sharing:
                self.needs_action.append(
                    workspace_sharing_audit_results.StopSharing(
                        note=note,
                        **audit_results_arg,
                    )
                )
            else:
                self.verified.append(
                    workspace_sharing_audit_results.VerifiedNotShared(
                        note=note,
                        **audit_results_arg,
                    )
                )
        else:
            raise ValueError("No case matched.")

    def _audit_workspace_and_auth_domain(self, workspace_data, managed_group):
        """Audit access for a specific DCCProcessedDataWorkspace and its auth domain.

        Sharing expectations:
        - Read access at all times.
        """
        current_sharing = self._get_current_sharing(workspace_data, managed_group)

        audit_result_args = {
            "workspace": workspace_data.workspace,
            "managed_group": managed_group,
            "current_sharing_instance": current_sharing,
        }

        note = self.AUTH_DOMAIN_AS_READER
        if current_sharing and current_sharing.access == WorkspaceGroupSharing.READER:
            self.verified.append(
                workspace_sharing_audit_results.VerifiedShared(
                    note=note,
                    **audit_result_args,
                )
            )
        elif current_sharing:
            self.errors.append(
                workspace_sharing_audit_results.ShareAsReader(
                    note=note,
                    **audit_result_args,
                )
            )
        else:
            self.needs_action.append(
                workspace_sharing_audit_results.ShareAsReader(
                    note=note,
                    **audit_result_args,
                )
            )

    def _audit_workspace_and_dcc_admin_group(self, workspace_data, managed_group):
        """Audit access for a specific DCCProcessedDataWorkspace and the DCC admin group.

        Sharing expectations:
        - Owner access at all times.
        """
        current_sharing = self._get_current_sharing(workspace_data, managed_group)

        audit_result_args = {
            "workspace": workspace_data.workspace,
            "managed_group": managed_group,
            "current_sharing_instance": current_sharing,
        }

        note = self.DCC_ADMIN_AS_OWNER
        if current_sharing and current_sharing.access == WorkspaceGroupSharing.OWNER:
            self.verified.append(
                workspace_sharing_audit_results.VerifiedShared(
                    note=note,
                    **audit_result_args,
                )
            )
        else:
            self.needs_action.append(
                workspace_sharing_audit_results.ShareAsOwner(
                    note=note,
                    **audit_result_args,
                )
            )

    def _audit_workspace_and_anvil_group(self, upload_workspace, managed_group):
        """Ignore the AnVIL groups in this audit.

        We don't want to make assumptions about what access level AnVIL has."""
        pass

    def _audit_workspace_and_other_group(self, workspace_data, managed_group):
        """Audit access for a specific UploadWorkspace and other groups.

        Sharing expectations:
        - No access.
        """
        current_sharing = self._get_current_sharing(workspace_data, managed_group)

        audit_result_args = {
            "workspace": workspace_data.workspace,
            "managed_group": managed_group,
            "current_sharing_instance": current_sharing,
        }

        if not current_sharing:
            self.verified.append(
                workspace_sharing_audit_results.VerifiedNotShared(
                    note=self.OTHER_GROUP,
                    **audit_result_args,
                )
            )
        else:
            self.errors.append(
                workspace_sharing_audit_results.StopSharing(
                    note=self.OTHER_GROUP,
                    **audit_result_args,
                )
            )
