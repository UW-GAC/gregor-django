from dataclasses import dataclass

import django_tables2 as tables
from anvil_consortium_manager.models import ManagedGroup, WorkspaceGroupSharing
from django.conf import settings
from django.db.models import Q, QuerySet

from ..models import CombinedConsortiumDataWorkspace, UploadWorkspace
from ..tables import BooleanIconColumn
from .base import GREGoRAudit, GREGoRAuditResult


@dataclass
class UploadWorkspaceSharingAuditResult(GREGoRAuditResult):
    """Base class to hold results for auditing upload workspace sharing."""

    workspace: UploadWorkspace
    note: str
    managed_group: ManagedGroup
    action: str = None
    current_sharing_instance: WorkspaceGroupSharing = None

    def get_action_url(self):
        """The URL that handles the action needed."""
        # return reverse(
        #     "gregor_anvil:audit:upload_workspaces:sharing:resolve",
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
            "access": self.current_sharing_instance.access if self.current_sharing_instance else None,
            "can_compute": self.current_sharing_instance.can_compute if self.current_sharing_instance else None,
            "note": self.note,
            "action": self.action,
            "action_url": self.get_action_url(),
        }
        return row


@dataclass
class VerifiedShared(UploadWorkspaceSharingAuditResult):
    """Audit results class for when Sharing has been verified."""

    is_shared: bool = True

    def __str__(self):
        return f"Verified sharing: {self.note}"


@dataclass
class VerifiedNotShared(UploadWorkspaceSharingAuditResult):
    """Audit results class for when no Sharing has been verified."""

    is_shared: bool = False

    def __str__(self):
        return f"Verified not shared: {self.note}"


@dataclass
class ShareAsReader(UploadWorkspaceSharingAuditResult):
    """Audit results class for when Sharing should be granted as a reader."""

    is_shared: bool = False
    action: str = "Share as reader"

    def __str__(self):
        return f"Share as reader: {self.note}"


@dataclass
class ShareAsWriter(UploadWorkspaceSharingAuditResult):
    """Audit results class for when Sharing should be granted as a writer."""

    is_shared: bool = False
    action: str = "Share as writer"

    def __str__(self):
        return f"Share as writer: {self.note}"


@dataclass
class ShareAsOwner(UploadWorkspaceSharingAuditResult):
    """Audit results class for when Sharing should be granted as an owner."""

    is_shared: bool = False
    action: str = "Share as owner"

    def __str__(self):
        return f"Share as owner: {self.note}"


@dataclass
class ShareWithCompute(UploadWorkspaceSharingAuditResult):
    """Audit results class for when Sharing should be granted with compute access."""

    is_shared: bool = False
    action: str = "Share with compute"

    def __str__(self):
        return f"Share with compute: {self.note}"


@dataclass
class StopSharing(UploadWorkspaceSharingAuditResult):
    """Audit results class for when Sharing should be removed for a known reason."""

    is_shared: bool = True
    action: str = "Stop sharing"

    def __str__(self):
        return f"Stop sharing: {self.note}"


@dataclass
class Error(UploadWorkspaceSharingAuditResult):
    """Audit results class for when an error has been detected (e.g., shared and never should have been)."""

    pass


class UploadWorkspaceSharingAuditTable(tables.Table):
    """A table to show results from a UploadWorkspaceSharingAudit subclass."""

    workspace = tables.Column(linkify=True)
    managed_group = tables.Column(linkify=True)
    # is_shared = tables.Column()
    access = tables.Column()
    can_compute = BooleanIconColumn(show_false_icon=True, null=True)
    note = tables.Column()
    # action = tables.Column()
    action = tables.TemplateColumn(
        template_name="gregor_anvil/snippets/upload_workspace_sharing_audit_action_button.html"
    )

    class Meta:
        attrs = {"class": "table align-middle"}


class UploadWorkspaceSharingAudit(GREGoRAudit):
    """A class to hold audit results for the GREGoR UploadWorkspace audit."""

    # RC uploader statues.
    RC_UPLOADERS_FUTURE_CYCLE = "Uploaders should have write access for future cycles."
    RC_UPLOADERS_CURRENT_CYCLE_BEFORE_COMPUTE = (
        "Uploaders should have write access before compute is enabled for this upload cycle."
    )
    RC_UPLOADERS_CURRENT_CYCLE_AFTER_COMPUTE = "Uploaders should have write access with compute for this upload cycle."
    RC_UPLOADERS_PAST_CYCLE_BEFORE_QC_COMPLETE = "Uploaders should not have direct access before QC is complete."
    RC_UPLOADERS_PAST_CYCLE_AFTER_QC_COMPLETE = "Uploader group should not have direct access after QC is complete."
    RC_UPLOADERS_PAST_CYCLE_COMBINED_WORKSPACE_READY = (
        "Uploader group should not have direct access when the combined workspace is ready to share or shared."
    )

    # DCC writer group status.
    DCC_WRITERS_FUTURE_CYCLE = "DCC writers should have write and compute access for future cycles."
    DCC_WRITERS_CURRENT_CYCLE = "DCC writers should have write and compute access for the current upload cycle."
    DCC_WRITERS_PAST_CYCLE_BEFORE_QC_COMPLETE = (
        "DCC writers should have write and compute access before QC is complete."
    )
    DCC_WRITERS_PAST_CYCLE_AFTER_QC_COMPLETE = "DCC writers should not have direct access after QC is complete."
    DCC_WRITERS_PAST_CYCLE_COMBINED_WORKSPACE_READY = (
        "DCC writers should not have direct access when the combined workspace is ready to share or shared."
    )

    # DCC admin group status.
    DCC_ADMIN_AS_OWNER = "The DCC admin group should always be an owner."

    # Auth domain status.
    AUTH_DOMAIN_AS_READER = "The auth domain should always be a reader."

    # Other group.
    OTHER_GROUP_NO_ACCESS = "Other groups should not have direct access."

    results_table_class = UploadWorkspaceSharingAuditTable

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

    def _get_current_sharing(self, upload_workspace, managed_group):
        try:
            current_sharing = WorkspaceGroupSharing.objects.get(
                workspace=upload_workspace.workspace, group=managed_group
            )
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

    def audit_upload_workspace(self, upload_workspace):
        """Audit access for a specific UploadWorkspace."""
        # Get a list of managed groups that should be included in this audit.
        # This includes the members group for the RC, the DCC groups, GREGOR_ALL, and the auth domain.
        research_center = upload_workspace.research_center
        group_names_to_include = [
            "GREGOR_DCC_WRITERS",  # DCC writers
            settings.ANVIL_DCC_ADMINS_GROUP_NAME,  # DCC admins
            "anvil-admins",  # AnVIL admins
            "anvil_devs",  # AnVIL devs
        ]
        groups_to_audit = ManagedGroup.objects.filter(
            # RC uploader group.
            Q(research_center_of_uploaders=research_center)
            |
            # Specific groups from above.
            Q(name__in=group_names_to_include)
            |
            # Auth domain.
            Q(workspaceauthorizationdomain__workspace=upload_workspace.workspace)
            |
            # Groups that the workspace is shared with.
            Q(workspacegroupsharing__workspace=upload_workspace.workspace)
        ).distinct()

        for group in groups_to_audit:
            self.audit_workspace_and_group(upload_workspace, group)

    def audit_workspace_and_group(self, upload_workspace, managed_group):
        """Audit access for a specific UploadWorkspace and ManagedGroup."""
        # Check the group type, and then call the appropriate audit method.
        if upload_workspace.research_center.uploader_group == managed_group:
            self._audit_workspace_and_rc_uploader_group(upload_workspace, managed_group)
        elif managed_group.name == "GREGOR_DCC_WRITERS":
            self._audit_workspace_and_dcc_writer_group(upload_workspace, managed_group)
        elif managed_group in upload_workspace.workspace.authorization_domains.all():
            self._audit_workspace_and_auth_domain(upload_workspace, managed_group)
        elif managed_group.name == settings.ANVIL_DCC_ADMINS_GROUP_NAME:
            self._audit_workspace_and_dcc_admin_group(upload_workspace, managed_group)
        elif managed_group.name in ["anvil-admins", "anvil_devs"]:
            self._audit_workspace_and_anvil_group(upload_workspace, managed_group)
        else:
            self._audit_workspace_and_other_group(upload_workspace, managed_group)

    def _audit_workspace_and_anvil_group(self, upload_workspace, managed_group):
        """Ignore the AnVIL groups in this audit.

        We don't want to make assumptions about what access level AnVIL has."""
        pass

    def _audit_workspace_and_rc_uploader_group(self, upload_workspace, managed_group):
        """Audit access for a specific UploadWorkspace and RC uploader group.

        Sharing expectations:
        - Write access to future upload cycle.
        - Write access before compute is enabled for current upload cycle.
        - Write+compute access after compute is enabled for current upload cycle.
        - Read access to past upload cycle workspaces before QC is completed.
        - No access to past upload cycle workspaces after QC is completed (read access via auth domain).
        """
        upload_cycle = upload_workspace.upload_cycle
        current_sharing = self._get_current_sharing(upload_workspace, managed_group)
        combined_workspace = self._get_combined_workspace(upload_cycle)

        audit_result_args = {
            "workspace": upload_workspace,
            "managed_group": managed_group,
            "current_sharing_instance": current_sharing,
        }

        if upload_cycle.is_future:
            note = self.RC_UPLOADERS_FUTURE_CYCLE
            if (
                current_sharing
                and current_sharing.access == WorkspaceGroupSharing.WRITER
                and not current_sharing.can_compute
            ):
                self.verified.append(
                    VerifiedShared(
                        note=note,
                        **audit_result_args,
                    )
                )
            else:
                self.needs_action.append(
                    ShareAsWriter(
                        note=note,
                        **audit_result_args,
                    )
                )
        elif upload_cycle.is_current and not upload_cycle.date_ready_for_compute:
            note = self.RC_UPLOADERS_CURRENT_CYCLE_BEFORE_COMPUTE
            if (
                current_sharing
                and current_sharing.access == WorkspaceGroupSharing.WRITER
                and not current_sharing.can_compute
            ):
                self.verified.append(
                    VerifiedShared(
                        note=note,
                        **audit_result_args,
                    )
                )
            else:
                self.needs_action.append(
                    ShareAsWriter(
                        note=note,
                        **audit_result_args,
                    )
                )
        elif upload_cycle.is_current and upload_cycle.date_ready_for_compute:
            note = self.RC_UPLOADERS_CURRENT_CYCLE_AFTER_COMPUTE
            if (
                current_sharing
                and current_sharing.access == WorkspaceGroupSharing.WRITER
                and current_sharing.can_compute
            ):
                self.verified.append(
                    VerifiedShared(
                        note=note,
                        **audit_result_args,
                    )
                )
            else:
                self.needs_action.append(
                    ShareWithCompute(
                        note=note,
                        **audit_result_args,
                    )
                )
        elif upload_cycle.is_past and not upload_workspace.date_qc_completed:
            note = self.RC_UPLOADERS_PAST_CYCLE_BEFORE_QC_COMPLETE
            if not current_sharing:
                self.verified.append(
                    VerifiedNotShared(
                        note=note,
                        **audit_result_args,
                    )
                )
            else:
                self.needs_action.append(
                    StopSharing(
                        note=note,
                        **audit_result_args,
                    )
                )
        elif upload_cycle.is_past and upload_workspace.date_qc_completed and not combined_workspace:
            note = self.RC_UPLOADERS_PAST_CYCLE_AFTER_QC_COMPLETE
            if not current_sharing:
                self.verified.append(
                    VerifiedNotShared(
                        note=note,
                        **audit_result_args,
                    )
                )
            else:
                self.needs_action.append(
                    StopSharing(
                        note=note,
                        **audit_result_args,
                    )
                )
        elif upload_cycle.is_past and combined_workspace:
            note = self.RC_UPLOADERS_PAST_CYCLE_COMBINED_WORKSPACE_READY
            if not current_sharing:
                self.verified.append(
                    VerifiedNotShared(
                        note=note,
                        **audit_result_args,
                    )
                )
            else:
                self.needs_action.append(
                    StopSharing(
                        note=note,
                        **audit_result_args,
                    )
                )
        else:
            raise ValueError("No case matched for RC uploader group.")

    def _audit_workspace_and_dcc_writer_group(self, upload_workspace, managed_group):
        """Audit access for a specific UploadWorkspace and the DCC writer group.

        Sharing expectations:
        - Write+compute access to future and current upload cycles.
        - Write+compute access to past upload cycles before QC is complete.
        - No direct access to past upload cycle workspaces after QC is completed (read access via auth domain).
        """
        upload_cycle = upload_workspace.upload_cycle
        current_sharing = self._get_current_sharing(upload_workspace, managed_group)
        combined_workspace = self._get_combined_workspace(upload_cycle)

        audit_result_args = {
            "workspace": upload_workspace,
            "managed_group": managed_group,
            "current_sharing_instance": current_sharing,
        }

        if upload_cycle.is_future:
            note = self.DCC_WRITERS_FUTURE_CYCLE
            if (
                current_sharing
                and current_sharing.access == WorkspaceGroupSharing.WRITER
                and current_sharing.can_compute
            ):
                self.verified.append(
                    VerifiedShared(
                        note=note,
                        **audit_result_args,
                    )
                )
            else:
                self.needs_action.append(
                    ShareWithCompute(
                        note=note,
                        **audit_result_args,
                    )
                )
        elif upload_cycle.is_current:
            note = self.DCC_WRITERS_CURRENT_CYCLE
            if (
                current_sharing
                and current_sharing.access == WorkspaceGroupSharing.WRITER
                and current_sharing.can_compute
            ):
                self.verified.append(
                    VerifiedShared(
                        note=note,
                        **audit_result_args,
                    )
                )
            else:
                self.needs_action.append(
                    ShareWithCompute(
                        note=note,
                        **audit_result_args,
                    )
                )
        elif upload_cycle.is_past and not upload_workspace.date_qc_completed:
            note = self.DCC_WRITERS_PAST_CYCLE_BEFORE_QC_COMPLETE
            if (
                current_sharing
                and current_sharing.access == WorkspaceGroupSharing.WRITER
                and current_sharing.can_compute
            ):
                self.verified.append(
                    VerifiedShared(
                        note=note,
                        **audit_result_args,
                    )
                )
            else:
                self.needs_action.append(
                    ShareWithCompute(
                        note=note,
                        **audit_result_args,
                    )
                )
        elif upload_cycle.is_past and upload_workspace.date_qc_completed and not combined_workspace:
            note = self.DCC_WRITERS_PAST_CYCLE_AFTER_QC_COMPLETE
            if not current_sharing:
                self.verified.append(
                    VerifiedNotShared(
                        note=note,
                        **audit_result_args,
                    )
                )
            else:
                self.needs_action.append(
                    StopSharing(
                        note=note,
                        **audit_result_args,
                    )
                )
        elif upload_cycle.is_past and combined_workspace:
            note = self.DCC_WRITERS_PAST_CYCLE_COMBINED_WORKSPACE_READY
            if not current_sharing:
                self.verified.append(
                    VerifiedNotShared(
                        note=note,
                        **audit_result_args,
                    )
                )
            else:
                self.needs_action.append(
                    StopSharing(
                        note=note,
                        **audit_result_args,
                    )
                )

        else:
            raise ValueError("No case matched for DCC writer group.")

    def _audit_workspace_and_auth_domain(self, upload_workspace, managed_group):
        """Audit access for a specific UploadWorkspace and its auth domain.

        Sharing expectations:
        - Read access at all times.
        """
        current_sharing = self._get_current_sharing(upload_workspace, managed_group)

        audit_result_args = {
            "workspace": upload_workspace,
            "managed_group": managed_group,
            "current_sharing_instance": current_sharing,
        }

        note = self.AUTH_DOMAIN_AS_READER
        if current_sharing and current_sharing.access == WorkspaceGroupSharing.READER:
            self.verified.append(
                VerifiedShared(
                    note=note,
                    **audit_result_args,
                )
            )
        else:
            self.needs_action.append(
                ShareAsReader(
                    note=note,
                    **audit_result_args,
                )
            )

    def _audit_workspace_and_dcc_admin_group(self, upload_workspace, managed_group):
        """Audit access for a specific UploadWorkspace and the DCC admin group.

        Sharing expectations:
        - Owner access at all times.
        """
        current_sharing = self._get_current_sharing(upload_workspace, managed_group)

        audit_result_args = {
            "workspace": upload_workspace,
            "managed_group": managed_group,
            "current_sharing_instance": current_sharing,
        }

        note = self.DCC_ADMIN_AS_OWNER
        if current_sharing and current_sharing.access == WorkspaceGroupSharing.OWNER:
            self.verified.append(
                VerifiedShared(
                    note=note,
                    **audit_result_args,
                )
            )
        else:
            self.needs_action.append(
                ShareAsOwner(
                    note=note,
                    **audit_result_args,
                )
            )

    def _audit_workspace_and_other_group(self, upload_workspace, managed_group):
        """Audit access for a specific UploadWorkspace and other groups.

        Sharing expectations:
        - No access.
        """
        current_sharing = self._get_current_sharing(upload_workspace, managed_group)

        audit_result_args = {
            "workspace": upload_workspace,
            "managed_group": managed_group,
            "current_sharing_instance": current_sharing,
        }

        if not current_sharing:
            self.verified.append(
                VerifiedNotShared(
                    note=self.OTHER_GROUP_NO_ACCESS,
                    **audit_result_args,
                )
            )
        else:
            self.errors.append(
                StopSharing(
                    note=self.OTHER_GROUP_NO_ACCESS,
                    **audit_result_args,
                )
            )
