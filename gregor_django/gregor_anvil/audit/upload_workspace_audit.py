import django_tables2 as tables
from anvil_consortium_manager.models import GroupGroupMembership, ManagedGroup, WorkspaceGroupSharing
from django.conf import settings
from django.db.models import Q, QuerySet

from ..models import CombinedConsortiumDataWorkspace, UploadWorkspace
from ..tables import BooleanIconColumn
from . import workspace_auth_domain_audit_results, workspace_sharing_audit_results
from .base import GREGoRAudit


class UploadWorkspaceAuthDomainAuditTable(tables.Table):
    """A table to show results from a UploadWorkspaceAuthDomainAudit subclass."""

    workspace = tables.Column(linkify=True)
    managed_group = tables.Column(linkify=True)
    # is_shared = tables.Column()
    role = tables.Column(verbose_name="Current role")
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
    RC_FUTURE_CYCLE = "RC groups should not be in the auth domain until the upload cycle starts."
    RC_UPLOADERS_BEFORE_QC = "RC uploader group should be a member of the auth domain before QC is complete."
    RC_UPLOADERS_AFTER_QC = "RC uploader group should not be a member of the auth domain after QC is complete."
    RC_MEMBERS_BEFORE_COMBINED = (
        "RC member group should be a member of the auth domain before the combined workspace is complete."
    )
    RC_MEMBERS_AFTER_COMBINED = (
        "RC member group should not be a member of the auth domain after the combined workspace is complete."
    )
    RC_NON_MEMBERS_AFTER_START = (
        "RC non-member group should be a member of the auth domain for current and past upload cycles."
    )

    # DCC notes.
    DCC_ADMINS = "DCC admin group should always be an admin of the auth domain."
    DCC_BEFORE_COMBINED = "DCC groups should be a member of the auth domain before the combined workspace is complete."
    DCC_AFTER_COMBINED = (
        "DCC groups should not be direct members of the auth domain after the combined workspace is complete."
    )

    # GREGOR_ALL notes.
    GREGOR_ALL_BEFORE_COMBINED = "GREGOR_ALL should not have access before the combined workspace is complete."
    GREGOR_ALL_AFTER_COMBINED = (
        "GREGOR_ALL should be a member of the auth domain after the combined workspace is complete."
    )

    # Other group notes.
    OTHER_GROUP = "This group should not have access to the auth domain."
    UNEXPECTED_ADMIN = "Only the DCC admins group should be an admin of the auth domain."

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
        group_names = [
            "GREGOR_ALL",
            "GREGOR_DCC_MEMBERS",
            "GREGOR_DCC_WRITERS",
            settings.ANVIL_DCC_ADMINS_GROUP_NAME,
        ]
        groups_to_audit = ManagedGroup.objects.filter(
            # RC uploader group.
            Q(research_center_of_uploaders=research_center)
            |
            # RC member group.
            Q(research_center_of_members=research_center)
            |
            # RC non-member group.
            Q(research_center_of_non_members=research_center)
            |
            # Other sepcific groups to include.
            Q(name__in=group_names)
            |
            # Any other groups that are members.
            Q(parent_memberships__parent_group=upload_workspace.workspace.authorization_domains.first())
        ).distinct()

        for group in groups_to_audit:
            self.audit_workspace_and_group(upload_workspace, group)

    def audit_workspace_and_group(self, upload_workspace, managed_group):
        if managed_group == upload_workspace.research_center.uploader_group:
            self._audit_workspace_and_group_for_rc_uploaders(upload_workspace, managed_group)
        elif managed_group == upload_workspace.research_center.member_group:
            self._audit_workspace_and_group_for_rc_members(upload_workspace, managed_group)
        elif managed_group == upload_workspace.research_center.non_member_group:
            self._audit_workspace_and_group_for_rc_non_members(upload_workspace, managed_group)
        elif managed_group.name == settings.ANVIL_DCC_ADMINS_GROUP_NAME:
            self._audit_workspace_and_group_for_dcc_admin(upload_workspace, managed_group)
        elif managed_group.name == "GREGOR_DCC_WRITERS":
            self._audit_workspace_and_group_for_dcc(upload_workspace, managed_group)
        elif managed_group.name == "GREGOR_DCC_MEMBERS":
            self._audit_workspace_and_group_for_dcc(upload_workspace, managed_group)
        elif managed_group.name == "GREGOR_ALL":
            self._audit_workspace_and_group_for_gregor_all(upload_workspace, managed_group)
        elif managed_group.name == "anvil-admins":
            self._audit_workspace_and_anvil_group(upload_workspace, managed_group)
        elif managed_group.name == "anvil_devs":
            self._audit_workspace_and_anvil_group(upload_workspace, managed_group)
        else:
            self._audit_workspace_and_other_group(upload_workspace, managed_group)

    def _audit_workspace_and_group_for_rc_uploaders(self, upload_workspace, managed_group):
        membership = self._get_current_membership(upload_workspace, managed_group)
        result_kwargs = {
            "workspace": upload_workspace.workspace,
            "managed_group": managed_group,
            "current_membership_instance": membership,
        }

        # Otherwise, proceed with other checks.
        if upload_workspace.upload_cycle.is_future:
            note = self.RC_FUTURE_CYCLE
            if membership and membership.role == GroupGroupMembership.ADMIN:
                self.errors.append(workspace_auth_domain_audit_results.Remove(note=note, **result_kwargs))
            elif membership:
                self.needs_action.append(workspace_auth_domain_audit_results.Remove(note=note, **result_kwargs))
            else:
                self.verified.append(workspace_auth_domain_audit_results.VerifiedNotMember(note=note, **result_kwargs))
        elif upload_workspace.upload_cycle.is_current:
            note = self.RC_UPLOADERS_BEFORE_QC
            if membership and membership.role == GroupGroupMembership.ADMIN:
                self.errors.append(workspace_auth_domain_audit_results.ChangeToMember(note=note, **result_kwargs))
            elif membership:
                self.verified.append(workspace_auth_domain_audit_results.VerifiedMember(note=note, **result_kwargs))
            else:
                self.needs_action.append(workspace_auth_domain_audit_results.AddMember(note=note, **result_kwargs))
        elif upload_workspace.upload_cycle.is_past and not upload_workspace.date_qc_completed:
            note = self.RC_UPLOADERS_BEFORE_QC
            if membership and membership.role == GroupGroupMembership.ADMIN:
                self.errors.append(workspace_auth_domain_audit_results.ChangeToMember(note=note, **result_kwargs))
            elif membership:
                self.verified.append(workspace_auth_domain_audit_results.VerifiedMember(note=note, **result_kwargs))
            else:
                self.needs_action.append(workspace_auth_domain_audit_results.AddMember(note=note, **result_kwargs))
        else:
            note = self.RC_UPLOADERS_AFTER_QC
            if membership and membership.role == GroupGroupMembership.ADMIN:
                self.errors.append(workspace_auth_domain_audit_results.Remove(note=note, **result_kwargs))
            elif membership:
                self.needs_action.append(workspace_auth_domain_audit_results.Remove(note=note, **result_kwargs))
            else:
                self.verified.append(workspace_auth_domain_audit_results.VerifiedNotMember(note=note, **result_kwargs))

    def _audit_workspace_and_group_for_rc_members(self, upload_workspace, managed_group):
        membership = self._get_current_membership(upload_workspace, managed_group)
        combined_workspace = self._get_combined_workspace(upload_workspace.upload_cycle)
        result_kwargs = {
            "workspace": upload_workspace.workspace,
            "managed_group": managed_group,
            "current_membership_instance": membership,
        }

        if upload_workspace.upload_cycle.is_future:
            note = self.RC_FUTURE_CYCLE
            if membership and membership.role == GroupGroupMembership.ADMIN:
                self.errors.append(workspace_auth_domain_audit_results.Remove(note=note, **result_kwargs))
            elif membership:
                self.needs_action.append(workspace_auth_domain_audit_results.Remove(note=note, **result_kwargs))
            else:
                self.verified.append(workspace_auth_domain_audit_results.VerifiedNotMember(note=note, **result_kwargs))
        elif not combined_workspace:
            note = self.RC_MEMBERS_BEFORE_COMBINED
            if membership and membership.role == GroupGroupMembership.ADMIN:
                self.errors.append(workspace_auth_domain_audit_results.ChangeToMember(note=note, **result_kwargs))
            elif membership:
                self.verified.append(workspace_auth_domain_audit_results.VerifiedMember(note=note, **result_kwargs))
            else:
                self.needs_action.append(workspace_auth_domain_audit_results.AddMember(note=note, **result_kwargs))
        else:
            note = self.RC_MEMBERS_AFTER_COMBINED
            if membership and membership.role == GroupGroupMembership.ADMIN:
                self.errors.append(workspace_auth_domain_audit_results.Remove(note=note, **result_kwargs))
            elif membership:
                self.needs_action.append(workspace_auth_domain_audit_results.Remove(note=note, **result_kwargs))
            else:
                self.verified.append(workspace_auth_domain_audit_results.VerifiedNotMember(note=note, **result_kwargs))

    def _audit_workspace_and_group_for_rc_non_members(self, upload_workspace, managed_group):
        membership = self._get_current_membership(upload_workspace, managed_group)
        result_kwargs = {
            "workspace": upload_workspace.workspace,
            "managed_group": managed_group,
            "current_membership_instance": membership,
        }

        if upload_workspace.upload_cycle.is_future:
            note = self.RC_FUTURE_CYCLE
            if membership and membership.role == GroupGroupMembership.ADMIN:
                self.errors.append(workspace_auth_domain_audit_results.Remove(note=note, **result_kwargs))
            elif membership:
                self.needs_action.append(workspace_auth_domain_audit_results.Remove(note=note, **result_kwargs))
            else:
                self.verified.append(workspace_auth_domain_audit_results.VerifiedNotMember(note=note, **result_kwargs))
        else:
            note = self.RC_NON_MEMBERS_AFTER_START
            if membership and membership.role == GroupGroupMembership.ADMIN:
                self.errors.append(workspace_auth_domain_audit_results.ChangeToMember(note=note, **result_kwargs))
            elif membership:
                self.verified.append(workspace_auth_domain_audit_results.VerifiedMember(note=note, **result_kwargs))
            else:
                self.needs_action.append(workspace_auth_domain_audit_results.AddMember(note=note, **result_kwargs))

    def _audit_workspace_and_group_for_dcc_admin(self, upload_workspace, managed_group):
        membership = self._get_current_membership(upload_workspace, managed_group)
        if not membership:
            self.needs_action.append(
                workspace_auth_domain_audit_results.AddAdmin(
                    workspace=upload_workspace.workspace,
                    managed_group=managed_group,
                    note=self.DCC_ADMINS,
                    current_membership_instance=membership,
                )
            )
        elif membership.role == GroupGroupMembership.ADMIN:
            self.verified.append(
                workspace_auth_domain_audit_results.VerifiedAdmin(
                    workspace=upload_workspace.workspace,
                    managed_group=managed_group,
                    note=self.DCC_ADMINS,
                    current_membership_instance=membership,
                )
            )
        else:
            self.needs_action.append(
                workspace_auth_domain_audit_results.ChangeToAdmin(
                    workspace=upload_workspace.workspace,
                    managed_group=managed_group,
                    note=self.DCC_ADMINS,
                    current_membership_instance=membership,
                )
            )

    def _audit_workspace_and_group_for_dcc(self, upload_workspace, managed_group):
        combined_workspace = self._get_combined_workspace(upload_workspace.upload_cycle)
        membership = self._get_current_membership(upload_workspace, managed_group)
        if combined_workspace:
            note = self.DCC_AFTER_COMBINED
        else:
            note = self.DCC_BEFORE_COMBINED
        result_kwargs = {
            "workspace": upload_workspace.workspace,
            "managed_group": managed_group,
            "current_membership_instance": membership,
            "note": note,
        }

        if not combined_workspace and not membership:
            self.needs_action.append(workspace_auth_domain_audit_results.AddMember(**result_kwargs))
        elif not combined_workspace and membership:
            if membership.role == GroupGroupMembership.MEMBER:
                self.verified.append(workspace_auth_domain_audit_results.VerifiedMember(**result_kwargs))
            else:
                self.errors.append(workspace_auth_domain_audit_results.ChangeToMember(**result_kwargs))
        elif combined_workspace and not membership:
            self.verified.append(workspace_auth_domain_audit_results.VerifiedNotMember(**result_kwargs))
        elif combined_workspace and membership:
            if membership.role == GroupGroupMembership.ADMIN:
                self.errors.append(workspace_auth_domain_audit_results.Remove(**result_kwargs))
            else:
                self.needs_action.append(workspace_auth_domain_audit_results.Remove(**result_kwargs))

    def _audit_workspace_and_group_for_gregor_all(self, upload_workspace, managed_group):
        combined_workspace = self._get_combined_workspace(upload_workspace.upload_cycle)
        membership = self._get_current_membership(upload_workspace, managed_group)
        if combined_workspace:
            note = self.GREGOR_ALL_AFTER_COMBINED
        else:
            note = self.GREGOR_ALL_BEFORE_COMBINED
        result_kwargs = {
            "workspace": upload_workspace.workspace,
            "managed_group": managed_group,
            "current_membership_instance": membership,
            "note": note,
        }

        if not combined_workspace and not membership:
            self.verified.append(workspace_auth_domain_audit_results.VerifiedNotMember(**result_kwargs))
        elif not combined_workspace and membership:
            self.errors.append(workspace_auth_domain_audit_results.Remove(**result_kwargs))
        elif combined_workspace and not membership:
            self.needs_action.append(workspace_auth_domain_audit_results.AddMember(**result_kwargs))
        elif combined_workspace and membership:
            if membership.role == GroupGroupMembership.MEMBER:
                self.verified.append(workspace_auth_domain_audit_results.VerifiedMember(**result_kwargs))
            else:
                self.errors.append(workspace_auth_domain_audit_results.ChangeToMember(**result_kwargs))

    def _audit_workspace_and_anvil_group(self, upload_workspace, managed_group):
        """Ignore the AnVIL groups in this audit.

        We don't want to make assumptions about what access level AnVIL has."""
        pass

    def _audit_workspace_and_other_group(self, upload_workspace, managed_group):
        membership = self._get_current_membership(upload_workspace, managed_group)
        result_kwargs = {
            "workspace": upload_workspace.workspace,
            "managed_group": managed_group,
            "current_membership_instance": membership,
            "note": self.OTHER_GROUP,
        }

        if not membership:
            self.verified.append(workspace_auth_domain_audit_results.VerifiedNotMember(**result_kwargs))
        elif membership:
            self.errors.append(workspace_auth_domain_audit_results.Remove(**result_kwargs))


class UploadWorkspaceSharingAuditTable(tables.Table):
    """A table to show results from a UploadWorkspaceSharingAudit subclass."""

    workspace = tables.Column(linkify=True)
    managed_group = tables.Column(linkify=True)
    access = tables.Column(verbose_name="Current access")
    can_compute = BooleanIconColumn(show_false_icon=True, null=True, true_color="black", false_color="black")
    note = tables.Column()
    action = tables.TemplateColumn(
        template_name="gregor_anvil/snippets/upload_workspace_sharing_audit_action_button.html"
    )

    class Meta:
        attrs = {"class": "table align-middle"}


class UploadWorkspaceSharingAudit(GREGoRAudit):
    """A class to hold audit results for the GREGoR UploadWorkspace audit."""

    # RC uploader statues.
    RC_UPLOADERS_FUTURE_CYCLE = "Uploaders should not have access to future cycles."
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
        - No access to future upload cycle.
        - Write access before compute is enabled for current upload cycle.
        - Write+compute access after compute is enabled for current upload cycle.
        - Read access to past upload cycle workspaces before QC is completed.
        - No access to past upload cycle workspaces after QC is completed (read access via auth domain).
        """
        upload_cycle = upload_workspace.upload_cycle
        current_sharing = self._get_current_sharing(upload_workspace, managed_group)
        combined_workspace = self._get_combined_workspace(upload_cycle)

        audit_result_args = {
            "workspace": upload_workspace.workspace,
            "managed_group": managed_group,
            "current_sharing_instance": current_sharing,
        }

        if upload_cycle.is_future:
            note = self.RC_UPLOADERS_FUTURE_CYCLE
            if not current_sharing:
                self.verified.append(workspace_sharing_audit_results.VerifiedNotShared(note=note, **audit_result_args))
            elif current_sharing and current_sharing.access == WorkspaceGroupSharing.OWNER:
                self.errors.append(workspace_sharing_audit_results.StopSharing(note=note, **audit_result_args))
            else:
                self.needs_action.append(workspace_sharing_audit_results.StopSharing(note=note, **audit_result_args))
        elif upload_cycle.is_current and not upload_cycle.date_ready_for_compute:
            note = self.RC_UPLOADERS_CURRENT_CYCLE_BEFORE_COMPUTE
            if current_sharing and current_sharing.access == WorkspaceGroupSharing.OWNER:
                self.errors.append(workspace_sharing_audit_results.ShareAsWriter(note=note, **audit_result_args))
            elif (
                current_sharing
                and current_sharing.access == WorkspaceGroupSharing.WRITER
                and not current_sharing.can_compute
            ):
                self.verified.append(workspace_sharing_audit_results.VerifiedShared(note=note, **audit_result_args))
            else:
                self.needs_action.append(workspace_sharing_audit_results.ShareAsWriter(note=note, **audit_result_args))
        elif upload_cycle.is_current and upload_cycle.date_ready_for_compute:
            note = self.RC_UPLOADERS_CURRENT_CYCLE_AFTER_COMPUTE
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
        elif upload_cycle.is_past and not upload_workspace.date_qc_completed:
            note = self.RC_UPLOADERS_PAST_CYCLE_BEFORE_QC_COMPLETE
            if not current_sharing:
                self.verified.append(workspace_sharing_audit_results.VerifiedNotShared(note=note, **audit_result_args))
            elif current_sharing and current_sharing.access == WorkspaceGroupSharing.OWNER:
                self.errors.append(workspace_sharing_audit_results.StopSharing(note=note, **audit_result_args))
            else:
                self.needs_action.append(workspace_sharing_audit_results.StopSharing(note=note, **audit_result_args))
        elif upload_cycle.is_past and upload_workspace.date_qc_completed and not combined_workspace:
            note = self.RC_UPLOADERS_PAST_CYCLE_AFTER_QC_COMPLETE
            if not current_sharing:
                self.verified.append(workspace_sharing_audit_results.VerifiedNotShared(note=note, **audit_result_args))
            elif current_sharing and current_sharing.access == WorkspaceGroupSharing.OWNER:
                self.errors.append(workspace_sharing_audit_results.StopSharing(note=note, **audit_result_args))
            else:
                self.needs_action.append(workspace_sharing_audit_results.StopSharing(note=note, **audit_result_args))
        elif upload_cycle.is_past and combined_workspace:
            note = self.RC_UPLOADERS_PAST_CYCLE_COMBINED_WORKSPACE_READY
            if not current_sharing:
                self.verified.append(workspace_sharing_audit_results.VerifiedNotShared(note=note, **audit_result_args))
            elif current_sharing and current_sharing.access == WorkspaceGroupSharing.OWNER:
                self.errors.append(workspace_sharing_audit_results.StopSharing(note=note, **audit_result_args))
            else:
                self.needs_action.append(workspace_sharing_audit_results.StopSharing(note=note, **audit_result_args))
        else:  # pragma: no cover
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
            "workspace": upload_workspace.workspace,
            "managed_group": managed_group,
            "current_sharing_instance": current_sharing,
        }

        if upload_cycle.is_future:
            note = self.DCC_WRITERS_FUTURE_CYCLE
            if current_sharing and current_sharing.access == WorkspaceGroupSharing.OWNER:
                self.errors.append(workspace_sharing_audit_results.ShareWithCompute(note=note, **audit_result_args))
            elif (
                current_sharing
                and current_sharing.access == WorkspaceGroupSharing.WRITER
                and current_sharing.can_compute
            ):
                self.verified.append(
                    workspace_sharing_audit_results.VerifiedShared(
                        note=note,
                        **audit_result_args,
                    )
                )
            else:
                self.needs_action.append(
                    workspace_sharing_audit_results.ShareWithCompute(
                        note=note,
                        **audit_result_args,
                    )
                )
        elif upload_cycle.is_current:
            note = self.DCC_WRITERS_CURRENT_CYCLE
            if current_sharing and current_sharing.access == WorkspaceGroupSharing.OWNER:
                self.errors.append(workspace_sharing_audit_results.ShareWithCompute(note=note, **audit_result_args))
            elif (
                current_sharing
                and current_sharing.access == WorkspaceGroupSharing.WRITER
                and current_sharing.can_compute
            ):
                self.verified.append(
                    workspace_sharing_audit_results.VerifiedShared(
                        note=note,
                        **audit_result_args,
                    )
                )
            else:
                self.needs_action.append(
                    workspace_sharing_audit_results.ShareWithCompute(
                        note=note,
                        **audit_result_args,
                    )
                )
        elif upload_cycle.is_past and not upload_workspace.date_qc_completed:
            note = self.DCC_WRITERS_PAST_CYCLE_BEFORE_QC_COMPLETE
            if current_sharing and current_sharing.access == WorkspaceGroupSharing.OWNER:
                self.errors.append(workspace_sharing_audit_results.ShareWithCompute(note=note, **audit_result_args))
            elif (
                current_sharing
                and current_sharing.access == WorkspaceGroupSharing.WRITER
                and current_sharing.can_compute
            ):
                self.verified.append(
                    workspace_sharing_audit_results.VerifiedShared(
                        note=note,
                        **audit_result_args,
                    )
                )
            else:
                self.needs_action.append(
                    workspace_sharing_audit_results.ShareWithCompute(
                        note=note,
                        **audit_result_args,
                    )
                )
        elif upload_cycle.is_past and upload_workspace.date_qc_completed and not combined_workspace:
            note = self.DCC_WRITERS_PAST_CYCLE_AFTER_QC_COMPLETE
            if current_sharing and current_sharing.access == WorkspaceGroupSharing.OWNER:
                self.errors.append(workspace_sharing_audit_results.StopSharing(note=note, **audit_result_args))
            elif not current_sharing:
                self.verified.append(
                    workspace_sharing_audit_results.VerifiedNotShared(
                        note=note,
                        **audit_result_args,
                    )
                )
            else:
                self.needs_action.append(
                    workspace_sharing_audit_results.StopSharing(
                        note=note,
                        **audit_result_args,
                    )
                )
        elif upload_cycle.is_past and combined_workspace:
            note = self.DCC_WRITERS_PAST_CYCLE_COMBINED_WORKSPACE_READY
            if current_sharing and current_sharing.access == WorkspaceGroupSharing.OWNER:
                self.errors.append(workspace_sharing_audit_results.StopSharing(note=note, **audit_result_args))
            elif not current_sharing:
                self.verified.append(
                    workspace_sharing_audit_results.VerifiedNotShared(
                        note=note,
                        **audit_result_args,
                    )
                )
            else:
                self.needs_action.append(
                    workspace_sharing_audit_results.StopSharing(
                        note=note,
                        **audit_result_args,
                    )
                )

        else:  # pragma: no cover
            raise ValueError("No case matched for DCC writer group.")

    def _audit_workspace_and_auth_domain(self, upload_workspace, managed_group):
        """Audit access for a specific UploadWorkspace and its auth domain.

        Sharing expectations:
        - Read access at all times.
        """
        current_sharing = self._get_current_sharing(upload_workspace, managed_group)

        audit_result_args = {
            "workspace": upload_workspace.workspace,
            "managed_group": managed_group,
            "current_sharing_instance": current_sharing,
        }

        note = self.AUTH_DOMAIN_AS_READER
        if current_sharing and current_sharing.access == WorkspaceGroupSharing.OWNER:
            self.errors.append(workspace_sharing_audit_results.ShareAsReader(note=note, **audit_result_args))
        elif current_sharing and current_sharing.access == WorkspaceGroupSharing.READER:
            self.verified.append(
                workspace_sharing_audit_results.VerifiedShared(
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

    def _audit_workspace_and_dcc_admin_group(self, upload_workspace, managed_group):
        """Audit access for a specific UploadWorkspace and the DCC admin group.

        Sharing expectations:
        - Owner access at all times.
        """
        current_sharing = self._get_current_sharing(upload_workspace, managed_group)

        audit_result_args = {
            "workspace": upload_workspace.workspace,
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

    def _audit_workspace_and_other_group(self, upload_workspace, managed_group):
        """Audit access for a specific UploadWorkspace and other groups.

        Sharing expectations:
        - No access.
        """
        current_sharing = self._get_current_sharing(upload_workspace, managed_group)

        audit_result_args = {
            "workspace": upload_workspace.workspace,
            "managed_group": managed_group,
            "current_sharing_instance": current_sharing,
        }

        if not current_sharing:
            self.verified.append(
                workspace_sharing_audit_results.VerifiedNotShared(
                    note=self.OTHER_GROUP_NO_ACCESS,
                    **audit_result_args,
                )
            )
        else:
            self.errors.append(
                workspace_sharing_audit_results.StopSharing(
                    note=self.OTHER_GROUP_NO_ACCESS,
                    **audit_result_args,
                )
            )
