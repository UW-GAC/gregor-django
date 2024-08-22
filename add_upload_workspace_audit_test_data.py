from anvil_consortium_manager.models import WorkspaceGroupSharing
from anvil_consortium_manager.tests.factories import (
    ManagedGroupFactory,
    WorkspaceGroupSharingFactory,
)
from django.conf import settings
from django.utils import timezone

from gregor_django.gregor_anvil.tests import factories

# Create groups involved in the audit.
dcc_admin_group = ManagedGroupFactory(name=settings.ANVIL_DCC_ADMINS_GROUP_NAME)
dcc_writer_group = ManagedGroupFactory(name="GREGOR_DCC_WRITERS")
rc_1_member_group = ManagedGroupFactory(name="DEMO_RC1_MEMBERS")
rc_1_uploader_group = ManagedGroupFactory(name="DEMO_RC1_UPLOADERS")
rc_1_nonmember_group = ManagedGroupFactory(name="DEMO_RC1_NONMEMBERS")

# Create an RC
rc = factories.ResearchCenterFactory.create(
    full_name="Research Center 1",
    short_name="RC1",
    member_group=rc_1_member_group,
    uploader_group=rc_1_uploader_group,
    non_member_group=rc_1_nonmember_group,
)


# Create a future upload cycle.
upload_cycle = factories.UploadCycleFactory.create(
    cycle=1,
    is_future=True,
    is_ready_for_compute=False,
)
workspace = factories.UploadWorkspaceFactory.create(
    upload_cycle=upload_cycle,
    research_center=rc,
    workspace__name="TEST_U01_RC1",
)

# Create a current upload cycle before compute.
upload_cycle = factories.UploadCycleFactory.create(
    cycle=2,
    is_current=True,
    is_ready_for_compute=False,
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


# Create a current upload cycle after compute.
upload_cycle = factories.UploadCycleFactory.create(
    cycle=3,
    is_current=True,
    is_ready_for_compute=True,
)
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

# Create a past upload cycle before qc is completed.
upload_cycle = factories.UploadCycleFactory.create(
    cycle=4,
    is_past=True,
    is_ready_for_compute=True,
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

# Create a past upload cycle after QC is completed.
upload_cycle = factories.UploadCycleFactory.create(
    cycle=5,
    is_past=True,
    is_ready_for_compute=True,
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

# Create a past upload cycle with a combined workspace.
upload_cycle = factories.UploadCycleFactory.create(
    cycle=6,
    is_past=True,
    is_ready_for_compute=True,
)
workspace = factories.UploadWorkspaceFactory.create(
    upload_cycle=upload_cycle,
    research_center=rc,
    workspace__name="TEST_U06_RC1",
    date_qc_completed=timezone.now(),
)
factories.CombinedConsortiumDataWorkspaceFactory.create(
    upload_cycle=upload_cycle,
    date_completed=timezone.now(),
    workspace__name="TEST_U06_COMBINED",
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
