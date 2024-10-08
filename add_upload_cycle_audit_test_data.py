from anvil_consortium_manager.models import GroupGroupMembership, WorkspaceGroupSharing
from anvil_consortium_manager.tests.factories import (
    GroupGroupMembershipFactory,
    ManagedGroupFactory,
    WorkspaceGroupSharingFactory,
)
from django.conf import settings
from django.utils import timezone

from gregor_django.gregor_anvil.tests import factories

# Create groups involved in the audit.
dcc_admin_group = ManagedGroupFactory(name=settings.ANVIL_DCC_ADMINS_GROUP_NAME)
dcc_writer_group = ManagedGroupFactory(name="GREGOR_DCC_WRITERS")
dcc_member_group = ManagedGroupFactory(name="GREGOR_DCC_MEMBERS")
rc_1_member_group = ManagedGroupFactory(name="DEMO_RC1_MEMBERS")
rc_1_uploader_group = ManagedGroupFactory(name="DEMO_RC1_UPLOADERS")
rc_1_nonmember_group = ManagedGroupFactory(name="DEMO_RC1_NONMEMBERS")
gregor_all_group = ManagedGroupFactory(name="GREGOR_ALL")
combined_auth_domain = ManagedGroupFactory(name="AUTH_GREGOR_COMBINED")

# Create an RC
rc = factories.ResearchCenterFactory.create(
    full_name="Research Center 1",
    short_name="RC1",
    member_group=rc_1_member_group,
    uploader_group=rc_1_uploader_group,
    non_member_group=rc_1_nonmember_group,
)

# Add GREGOR_ALL and DCC_ADMINS to the combined auth domain.
GroupGroupMembershipFactory.create(
    parent_group=combined_auth_domain,
    child_group=gregor_all_group,
    role=GroupGroupMembership.MEMBER,
)
GroupGroupMembershipFactory.create(
    parent_group=combined_auth_domain,
    child_group=dcc_admin_group,
    role=GroupGroupMembership.ADMIN,
)


## Future upload cycle.
upload_cycle = factories.UploadCycleFactory.create(
    cycle=1,
    is_future=True,
)
workspace = factories.UploadWorkspaceFactory.create(
    upload_cycle=upload_cycle,
    research_center=rc,
    workspace__name="TEST_U01_RC1",
)

## Current upload cycle before compute.
upload_cycle = factories.UploadCycleFactory.create(
    cycle=2,
    is_current=True,
)
workspace = factories.UploadWorkspaceFactory.create(
    upload_cycle=upload_cycle,
    research_center=rc,
    workspace__name="TEST_U02_RC1",
)
# Create records as appropriate for the previous point in the cycle - future cycle.
# Auth domain.
WorkspaceGroupSharingFactory.create(
    workspace=workspace.workspace,
    group=workspace.workspace.authorization_domains.first(),
    access=WorkspaceGroupSharing.READER,
    can_compute=False,
)
# DCC admins.
WorkspaceGroupSharingFactory.create(
    workspace=workspace.workspace,
    group=dcc_admin_group,
    access=WorkspaceGroupSharing.OWNER,
    can_compute=True,
)
# DCC writers.
WorkspaceGroupSharingFactory.create(
    workspace=workspace.workspace,
    group=dcc_writer_group,
    access=WorkspaceGroupSharing.WRITER,
    can_compute=True,
)
# RC uploaders.
WorkspaceGroupSharingFactory.create(
    workspace=workspace.workspace,
    group=rc_1_uploader_group,
    access=WorkspaceGroupSharing.WRITER,
    can_compute=False,
)
# Create auth domain membership as appropriate.
GroupGroupMembershipFactory.create(
    parent_group=workspace.workspace.authorization_domains.first(),
    child_group=rc_1_member_group,
    role=GroupGroupMembership.MEMBER,
)
GroupGroupMembershipFactory.create(
    parent_group=workspace.workspace.authorization_domains.first(),
    child_group=rc_1_nonmember_group,
    role=GroupGroupMembership.MEMBER,
)
GroupGroupMembershipFactory.create(
    parent_group=workspace.workspace.authorization_domains.first(),
    child_group=rc_1_uploader_group,
    role=GroupGroupMembership.MEMBER,
)
GroupGroupMembershipFactory.create(
    parent_group=workspace.workspace.authorization_domains.first(),
    child_group=dcc_member_group,
    role=GroupGroupMembership.MEMBER,
)
GroupGroupMembershipFactory.create(
    parent_group=workspace.workspace.authorization_domains.first(),
    child_group=dcc_writer_group,
    role=GroupGroupMembership.MEMBER,
)
GroupGroupMembershipFactory.create(
    parent_group=workspace.workspace.authorization_domains.first(),
    child_group=dcc_admin_group,
    role=GroupGroupMembership.ADMIN,
)


## Current upload cycle after compute.
upload_cycle = factories.UploadCycleFactory.create(
    cycle=3,
    is_current=True,
)
upload_cycle.date_ready_for_compute = upload_cycle.start_date
upload_cycle.save()
workspace = factories.UploadWorkspaceFactory.create(
    upload_cycle=upload_cycle,
    research_center=rc,
    workspace__name="TEST_U03_RC1",
)
# Create records as appropriate for the previous point in the cycle - current cycle before compute.
# Auth domain.
WorkspaceGroupSharingFactory.create(
    workspace=workspace.workspace,
    group=workspace.workspace.authorization_domains.first(),
    access=WorkspaceGroupSharing.READER,
    can_compute=False,
)
# DCC admins.
WorkspaceGroupSharingFactory.create(
    workspace=workspace.workspace,
    group=dcc_admin_group,
    access=WorkspaceGroupSharing.OWNER,
    can_compute=True,
)
# DCC writers.
WorkspaceGroupSharingFactory.create(
    workspace=workspace.workspace,
    group=dcc_writer_group,
    access=WorkspaceGroupSharing.WRITER,
    can_compute=True,
)
# RC uploaders.
WorkspaceGroupSharingFactory.create(
    workspace=workspace.workspace,
    group=rc_1_uploader_group,
    access=WorkspaceGroupSharing.WRITER,
    can_compute=False,
)
# Create auth domain membership as appropriate.
GroupGroupMembershipFactory.create(
    parent_group=workspace.workspace.authorization_domains.first(),
    child_group=rc_1_member_group,
    role=GroupGroupMembership.MEMBER,
)
GroupGroupMembershipFactory.create(
    parent_group=workspace.workspace.authorization_domains.first(),
    child_group=rc_1_nonmember_group,
    role=GroupGroupMembership.MEMBER,
)
GroupGroupMembershipFactory.create(
    parent_group=workspace.workspace.authorization_domains.first(),
    child_group=rc_1_uploader_group,
    role=GroupGroupMembership.MEMBER,
)
GroupGroupMembershipFactory.create(
    parent_group=workspace.workspace.authorization_domains.first(),
    child_group=dcc_member_group,
    role=GroupGroupMembership.MEMBER,
)
GroupGroupMembershipFactory.create(
    parent_group=workspace.workspace.authorization_domains.first(),
    child_group=dcc_writer_group,
    role=GroupGroupMembership.MEMBER,
)
GroupGroupMembershipFactory.create(
    parent_group=workspace.workspace.authorization_domains.first(),
    child_group=dcc_admin_group,
    role=GroupGroupMembership.ADMIN,
)

# Create a past upload cycle before qc is completed.
upload_cycle = factories.UploadCycleFactory.create(
    cycle=4,
    is_past=True,
)
workspace = factories.UploadWorkspaceFactory.create(
    upload_cycle=upload_cycle,
    research_center=rc,
    workspace__name="TEST_U04_RC1",
    date_qc_completed=None,
)
# Create records as appropriate for the previous point in the cycle - current cycle after compute.
# Auth domain.
WorkspaceGroupSharingFactory.create(
    workspace=workspace.workspace,
    group=workspace.workspace.authorization_domains.first(),
    access=WorkspaceGroupSharing.READER,
    can_compute=False,
)
# DCC admins.
WorkspaceGroupSharingFactory.create(
    workspace=workspace.workspace,
    group=dcc_admin_group,
    access=WorkspaceGroupSharing.OWNER,
    can_compute=True,
)
# DCC writers.
WorkspaceGroupSharingFactory.create(
    workspace=workspace.workspace,
    group=dcc_writer_group,
    access=WorkspaceGroupSharing.WRITER,
    can_compute=True,
)
# RC uploaders.
WorkspaceGroupSharingFactory.create(
    workspace=workspace.workspace,
    group=rc_1_uploader_group,
    access=WorkspaceGroupSharing.WRITER,
    can_compute=True,
)
# Create auth domain membership as appropriate.
GroupGroupMembershipFactory.create(
    parent_group=workspace.workspace.authorization_domains.first(),
    child_group=rc_1_member_group,
    role=GroupGroupMembership.MEMBER,
)
GroupGroupMembershipFactory.create(
    parent_group=workspace.workspace.authorization_domains.first(),
    child_group=rc_1_nonmember_group,
    role=GroupGroupMembership.MEMBER,
)
GroupGroupMembershipFactory.create(
    parent_group=workspace.workspace.authorization_domains.first(),
    child_group=rc_1_uploader_group,
    role=GroupGroupMembership.MEMBER,
)
GroupGroupMembershipFactory.create(
    parent_group=workspace.workspace.authorization_domains.first(),
    child_group=dcc_member_group,
    role=GroupGroupMembership.MEMBER,
)
GroupGroupMembershipFactory.create(
    parent_group=workspace.workspace.authorization_domains.first(),
    child_group=dcc_writer_group,
    role=GroupGroupMembership.MEMBER,
)
GroupGroupMembershipFactory.create(
    parent_group=workspace.workspace.authorization_domains.first(),
    child_group=dcc_admin_group,
    role=GroupGroupMembership.ADMIN,
)

## Past upload cycle after QC is completed; combined workspace is not complete.
upload_cycle = factories.UploadCycleFactory.create(
    cycle=5,
    is_past=True,
)
workspace = factories.UploadWorkspaceFactory.create(
    upload_cycle=upload_cycle,
    research_center=rc,
    workspace__name="TEST_U05_RC1",
    date_qc_completed=timezone.now(),
)
# Create records as appropriate for the previous point in the cycle - past cycle before QC complete.
# Auth domain.
WorkspaceGroupSharingFactory.create(
    workspace=workspace.workspace,
    group=workspace.workspace.authorization_domains.first(),
    access=WorkspaceGroupSharing.READER,
    can_compute=False,
)
# DCC admins.
WorkspaceGroupSharingFactory.create(
    workspace=workspace.workspace,
    group=dcc_admin_group,
    access=WorkspaceGroupSharing.OWNER,
    can_compute=True,
)
# DCC writers.
WorkspaceGroupSharingFactory.create(
    workspace=workspace.workspace,
    group=dcc_writer_group,
    access=WorkspaceGroupSharing.WRITER,
    can_compute=True,
)
# Create auth domain membership as appropriate.
GroupGroupMembershipFactory.create(
    parent_group=workspace.workspace.authorization_domains.first(),
    child_group=rc_1_member_group,
    role=GroupGroupMembership.MEMBER,
)
GroupGroupMembershipFactory.create(
    parent_group=workspace.workspace.authorization_domains.first(),
    child_group=rc_1_nonmember_group,
    role=GroupGroupMembership.MEMBER,
)
GroupGroupMembershipFactory.create(
    parent_group=workspace.workspace.authorization_domains.first(),
    child_group=rc_1_uploader_group,
    role=GroupGroupMembership.MEMBER,
)
GroupGroupMembershipFactory.create(
    parent_group=workspace.workspace.authorization_domains.first(),
    child_group=dcc_member_group,
    role=GroupGroupMembership.MEMBER,
)
GroupGroupMembershipFactory.create(
    parent_group=workspace.workspace.authorization_domains.first(),
    child_group=dcc_writer_group,
    role=GroupGroupMembership.MEMBER,
)
GroupGroupMembershipFactory.create(
    parent_group=workspace.workspace.authorization_domains.first(),
    child_group=dcc_admin_group,
    role=GroupGroupMembership.ADMIN,
)
# Create the combined workspace and its records.
combined_workspace = factories.CombinedConsortiumDataWorkspaceFactory.create(
    upload_cycle=upload_cycle,
    workspace__name="TEST_U05_COMBINED",
)
# Delete the auth domain created by the factory and add the shared auth domain.
combined_workspace.workspace.authorization_domains.clear()
combined_workspace.workspace.authorization_domains.add(combined_auth_domain)
# No sharing records yet.


## Past upload cycle with a combined workspace.
upload_cycle = factories.UploadCycleFactory.create(
    cycle=6,
    is_past=True,
)
workspace = factories.UploadWorkspaceFactory.create(
    upload_cycle=upload_cycle,
    research_center=rc,
    workspace__name="TEST_U06_RC1",
    date_qc_completed=timezone.now(),
)
# Create records as appropriate for the previous point in the cycle - past cycle before QC complete.
# Auth domain.
WorkspaceGroupSharingFactory.create(
    workspace=workspace.workspace,
    group=workspace.workspace.authorization_domains.first(),
    access=WorkspaceGroupSharing.READER,
    can_compute=False,
)
# DCC admins.
WorkspaceGroupSharingFactory.create(
    workspace=workspace.workspace,
    group=dcc_admin_group,
    access=WorkspaceGroupSharing.OWNER,
    can_compute=True,
)
# Create auth domain membership as appropriate.
GroupGroupMembershipFactory.create(
    parent_group=workspace.workspace.authorization_domains.first(),
    child_group=rc_1_member_group,
    role=GroupGroupMembership.MEMBER,
)
GroupGroupMembershipFactory.create(
    parent_group=workspace.workspace.authorization_domains.first(),
    child_group=rc_1_nonmember_group,
    role=GroupGroupMembership.MEMBER,
)
GroupGroupMembershipFactory.create(
    parent_group=workspace.workspace.authorization_domains.first(),
    child_group=rc_1_uploader_group,
    role=GroupGroupMembership.MEMBER,
)
GroupGroupMembershipFactory.create(
    parent_group=workspace.workspace.authorization_domains.first(),
    child_group=dcc_member_group,
    role=GroupGroupMembership.MEMBER,
)
GroupGroupMembershipFactory.create(
    parent_group=workspace.workspace.authorization_domains.first(),
    child_group=dcc_writer_group,
    role=GroupGroupMembership.MEMBER,
)
GroupGroupMembershipFactory.create(
    parent_group=workspace.workspace.authorization_domains.first(),
    child_group=dcc_admin_group,
    role=GroupGroupMembership.ADMIN,
)
# Create the combined workspace and its records.
combined_workspace = factories.CombinedConsortiumDataWorkspaceFactory.create(
    upload_cycle=upload_cycle,
    date_completed=timezone.now(),
    workspace__name="TEST_U06_COMBINED",
)
# Delete the auth domain created by the factory and add the shared auth domain.
combined_workspace.workspace.authorization_domains.clear()
combined_workspace.workspace.authorization_domains.add(combined_auth_domain)
# Add sharing records from previous step - DCC admins, writers, and members.
WorkspaceGroupSharingFactory.create(
    workspace=combined_workspace.workspace,
    group=dcc_admin_group,
    access=WorkspaceGroupSharing.OWNER,
    can_compute=True,
)
WorkspaceGroupSharingFactory.create(
    workspace=combined_workspace.workspace,
    group=dcc_writer_group,
    access=WorkspaceGroupSharing.WRITER,
    can_compute=True,
)
WorkspaceGroupSharingFactory.create(
    workspace=combined_workspace.workspace,
    group=dcc_member_group,
    access=WorkspaceGroupSharing.READER,
    can_compute=False,
)
