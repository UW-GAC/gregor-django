import django_tables2 as tables
from anvil_consortium_manager.models import GroupGroupMembership, ManagedGroup
from django.conf import settings
from django.db.models import Q, QuerySet

from ..models import CombinedConsortiumDataWorkspace, UploadWorkspace
from . import workspace_auth_domain_audit_results as audit_results
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
            "workspace": upload_workspace,
            "managed_group": managed_group,
            "current_membership_instance": membership,
        }

        # Otherwise, proceed with other checks.
        if upload_workspace.upload_cycle.is_future:
            note = self.RC_FUTURE_CYCLE
            if membership and membership.role == GroupGroupMembership.ADMIN:
                self.errors.append(audit_results.Remove(note=note, **result_kwargs))
            elif membership:
                self.needs_action.append(audit_results.Remove(note=note, **result_kwargs))
            else:
                self.verified.append(audit_results.VerifiedNotMember(note=note, **result_kwargs))
        elif upload_workspace.upload_cycle.is_current:
            note = self.RC_UPLOADERS_BEFORE_QC
            if membership and membership.role == GroupGroupMembership.ADMIN:
                self.errors.append(audit_results.ChangeToMember(note=note, **result_kwargs))
            elif membership:
                self.verified.append(audit_results.VerifiedMember(note=note, **result_kwargs))
            else:
                self.needs_action.append(audit_results.AddMember(note=note, **result_kwargs))
        elif upload_workspace.upload_cycle.is_past and not upload_workspace.date_qc_completed:
            note = self.RC_UPLOADERS_BEFORE_QC
            if membership and membership.role == GroupGroupMembership.ADMIN:
                self.errors.append(audit_results.ChangeToMember(note=note, **result_kwargs))
            elif membership:
                self.verified.append(audit_results.VerifiedMember(note=note, **result_kwargs))
            else:
                self.needs_action.append(audit_results.AddMember(note=note, **result_kwargs))
        else:
            note = self.RC_UPLOADERS_AFTER_QC
            if membership and membership.role == GroupGroupMembership.ADMIN:
                self.errors.append(audit_results.Remove(note=note, **result_kwargs))
            elif membership:
                self.needs_action.append(audit_results.Remove(note=note, **result_kwargs))
            else:
                self.verified.append(audit_results.VerifiedNotMember(note=note, **result_kwargs))

    def _audit_workspace_and_group_for_rc_members(self, upload_workspace, managed_group):
        membership = self._get_current_membership(upload_workspace, managed_group)
        combined_workspace = self._get_combined_workspace(upload_workspace.upload_cycle)
        result_kwargs = {
            "workspace": upload_workspace,
            "managed_group": managed_group,
            "current_membership_instance": membership,
        }

        if upload_workspace.upload_cycle.is_future:
            note = self.RC_FUTURE_CYCLE
            if membership and membership.role == GroupGroupMembership.ADMIN:
                self.errors.append(audit_results.Remove(note=note, **result_kwargs))
            elif membership:
                self.needs_action.append(audit_results.Remove(note=note, **result_kwargs))
            else:
                self.verified.append(audit_results.VerifiedNotMember(note=note, **result_kwargs))
        elif not combined_workspace:
            note = self.RC_MEMBERS_BEFORE_COMBINED
            if membership and membership.role == GroupGroupMembership.ADMIN:
                self.errors.append(audit_results.ChangeToMember(note=note, **result_kwargs))
            elif membership:
                self.verified.append(audit_results.VerifiedMember(note=note, **result_kwargs))
            else:
                self.needs_action.append(audit_results.AddMember(note=note, **result_kwargs))
        else:
            note = self.RC_MEMBERS_AFTER_COMBINED
            if membership and membership.role == GroupGroupMembership.ADMIN:
                self.errors.append(audit_results.Remove(note=note, **result_kwargs))
            elif membership:
                self.needs_action.append(audit_results.Remove(note=note, **result_kwargs))
            else:
                self.verified.append(audit_results.VerifiedNotMember(note=note, **result_kwargs))

    def _audit_workspace_and_group_for_rc_non_members(self, upload_workspace, managed_group):
        membership = self._get_current_membership(upload_workspace, managed_group)
        result_kwargs = {
            "workspace": upload_workspace,
            "managed_group": managed_group,
            "current_membership_instance": membership,
        }

        if upload_workspace.upload_cycle.is_future:
            note = self.RC_FUTURE_CYCLE
            if membership and membership.role == GroupGroupMembership.ADMIN:
                self.errors.append(audit_results.Remove(note=note, **result_kwargs))
            elif membership:
                self.needs_action.append(audit_results.Remove(note=note, **result_kwargs))
            else:
                self.verified.append(audit_results.VerifiedNotMember(note=note, **result_kwargs))
        else:
            note = self.RC_NON_MEMBERS_AFTER_START
            if membership and membership.role == GroupGroupMembership.ADMIN:
                self.errors.append(audit_results.ChangeToMember(note=note, **result_kwargs))
            elif membership:
                self.verified.append(audit_results.VerifiedMember(note=note, **result_kwargs))
            else:
                self.needs_action.append(audit_results.AddMember(note=note, **result_kwargs))

    def _audit_workspace_and_group_for_dcc_admin(self, upload_workspace, managed_group):
        membership = self._get_current_membership(upload_workspace, managed_group)
        if not membership:
            self.needs_action.append(
                audit_results.AddAdmin(
                    workspace=upload_workspace,
                    managed_group=managed_group,
                    note=self.DCC_ADMINS,
                    current_membership_instance=membership,
                )
            )
        elif membership.role == GroupGroupMembership.ADMIN:
            self.verified.append(
                audit_results.VerifiedAdmin(
                    workspace=upload_workspace,
                    managed_group=managed_group,
                    note=self.DCC_ADMINS,
                    current_membership_instance=membership,
                )
            )
        else:
            self.needs_action.append(
                audit_results.ChangeToAdmin(
                    workspace=upload_workspace,
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
            "workspace": upload_workspace,
            "managed_group": managed_group,
            "current_membership_instance": membership,
            "note": note,
        }

        if not combined_workspace and not membership:
            self.needs_action.append(audit_results.AddMember(**result_kwargs))
        elif not combined_workspace and membership:
            if membership.role == GroupGroupMembership.MEMBER:
                self.verified.append(audit_results.VerifiedMember(**result_kwargs))
            else:
                self.errors.append(audit_results.ChangeToMember(**result_kwargs))
        elif combined_workspace and not membership:
            self.verified.append(audit_results.VerifiedNotMember(**result_kwargs))
        elif combined_workspace and membership:
            if membership.role == GroupGroupMembership.ADMIN:
                self.errors.append(audit_results.Remove(**result_kwargs))
            else:
                self.needs_action.append(audit_results.Remove(**result_kwargs))

    def _audit_workspace_and_group_for_gregor_all(self, upload_workspace, managed_group):
        combined_workspace = self._get_combined_workspace(upload_workspace.upload_cycle)
        membership = self._get_current_membership(upload_workspace, managed_group)
        if combined_workspace:
            note = self.GREGOR_ALL_AFTER_COMBINED
        else:
            note = self.GREGOR_ALL_BEFORE_COMBINED
        result_kwargs = {
            "workspace": upload_workspace,
            "managed_group": managed_group,
            "current_membership_instance": membership,
            "note": note,
        }

        if not combined_workspace and not membership:
            self.verified.append(audit_results.VerifiedNotMember(**result_kwargs))
        elif not combined_workspace and membership:
            self.errors.append(audit_results.Remove(**result_kwargs))
        elif combined_workspace and not membership:
            self.needs_action.append(audit_results.AddMember(**result_kwargs))
        elif combined_workspace and membership:
            if membership.role == GroupGroupMembership.MEMBER:
                self.verified.append(audit_results.VerifiedMember(**result_kwargs))
            else:
                self.errors.append(audit_results.ChangeToMember(**result_kwargs))

    def _audit_workspace_and_anvil_group(self, upload_workspace, managed_group):
        """Ignore the AnVIL groups in this audit.

        We don't want to make assumptions about what access level AnVIL has."""
        pass

    def _audit_workspace_and_other_group(self, upload_workspace, managed_group):
        membership = self._get_current_membership(upload_workspace, managed_group)
        result_kwargs = {
            "workspace": upload_workspace,
            "managed_group": managed_group,
            "current_membership_instance": membership,
            "note": self.OTHER_GROUP,
        }

        if not membership:
            self.verified.append(audit_results.VerifiedNotMember(**result_kwargs))
        elif membership:
            self.errors.append(audit_results.Remove(**result_kwargs))
