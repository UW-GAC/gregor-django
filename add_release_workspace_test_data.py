from anvil_consortium_manager.tests.factories import BillingProjectFactory

from gregor_django.gregor_anvil.tests import factories

# Dummy billing project
billing_project = BillingProjectFactory.create(name="TEST_BILLING_PROJECT")
# Create consent groups.
consent_group_gru = factories.ConsentGroupFactory.create(
    code="GRU",
    consent="General Research Use",
    data_use_limitations="GRU",
)
consent_group_hmb = factories.ConsentGroupFactory.create(
    code="HMB",
    consent="Health and Medical/Biomedical",
    data_use_limitations="HMB",
)

# Create upload cycles.
upload_cycle_1 = factories.UploadCycleFactory.create(cycle=1)
upload_cycle_2 = factories.UploadCycleFactory.create(cycle=2)
upload_cycle_3 = factories.UploadCycleFactory.create(cycle=3)
upload_cycle_4 = factories.UploadCycleFactory.create(cycle=4)
upload_cycle_5 = factories.UploadCycleFactory.create(cycle=5)

# Upload cycle 1 - not included in a release
## Create upload workspaces
upload_cycle = upload_cycle_1
factories.UploadWorkspaceFactory.create(
    upload_cycle=upload_cycle,
    consent_group=consent_group_gru,
    workspace__billing_project=billing_project,
    workspace__name="TEST_U01_RC1_GRU",
)
factories.UploadWorkspaceFactory.create(
    upload_cycle=upload_cycle,
    consent_group=consent_group_gru,
    workspace__billing_project=billing_project,
    workspace__name="TEST_U01_RC2_GRU",
)
factories.UploadWorkspaceFactory.create(
    upload_cycle=upload_cycle,
    consent_group=consent_group_hmb,
    workspace__billing_project=billing_project,
    workspace__name="TEST_U01_RC1_HMB",
)

# Upload cycle 2 - first included in a release R01
## Create upload workspaces
upload_cycle = upload_cycle_2
factories.UploadWorkspaceFactory.create(
    upload_cycle=upload_cycle,
    consent_group=consent_group_gru,
    workspace__billing_project=billing_project,
    workspace__name="TEST_U02_RC1_GRU",
)
factories.UploadWorkspaceFactory.create(
    upload_cycle=upload_cycle,
    consent_group=consent_group_gru,
    workspace__billing_project=billing_project,
    workspace__name="TEST_U02_RC2_GRU",
)
factories.UploadWorkspaceFactory.create(
    upload_cycle=upload_cycle,
    consent_group=consent_group_hmb,
    workspace__billing_project=billing_project,
    workspace__name="TEST_U02_RC1_HMB",
)
## Create release workspaces.
factories.ReleaseWorkspaceFactory.create(
    upload_cycle=upload_cycle,
    consent_group=consent_group_gru,
    dbgap_version=1,
    workspace__billing_project=billing_project,
    workspace__name="TEST_R01_GRU",
)
factories.ReleaseWorkspaceFactory.create(
    upload_cycle=upload_cycle,
    consent_group=consent_group_hmb,
    dbgap_version=1,
    workspace__billing_project=billing_project,
    workspace__name="TEST_R01_HMB",
)

# Upload cycle 3 - new workspace, not included in a release
## Create upload workspaces
upload_cycle = upload_cycle_3
factories.UploadWorkspaceFactory.create(
    upload_cycle=upload_cycle,
    consent_group=consent_group_gru,
    workspace__billing_project=billing_project,
    workspace__name="TEST_U03_RC1_GRU",
)
factories.UploadWorkspaceFactory.create(
    upload_cycle=upload_cycle,
    consent_group=consent_group_gru,
    workspace__billing_project=billing_project,
    workspace__name="TEST_U03_RC2_GRU",
)
factories.UploadWorkspaceFactory.create(
    upload_cycle=upload_cycle,
    consent_group=consent_group_hmb,
    workspace__billing_project=billing_project,
    workspace__name="TEST_U03_RC1_HMB",
)
factories.UploadWorkspaceFactory.create(
    upload_cycle=upload_cycle,
    consent_group=consent_group_hmb,
    workspace__billing_project=billing_project,
    workspace__name="TEST_U03_RC2_HMB",
)

# Upload cycle 4 - included in release R02
## Create upload workspaces
upload_cycle = upload_cycle_4
factories.UploadWorkspaceFactory.create(
    upload_cycle=upload_cycle,
    consent_group=consent_group_gru,
    workspace__billing_project=billing_project,
    workspace__name="TEST_U04_RC1_GRU",
)
factories.UploadWorkspaceFactory.create(
    upload_cycle=upload_cycle,
    consent_group=consent_group_gru,
    workspace__billing_project=billing_project,
    workspace__name="TEST_U04_RC2_GRU",
)
factories.UploadWorkspaceFactory.create(
    upload_cycle=upload_cycle,
    consent_group=consent_group_hmb,
    workspace__billing_project=billing_project,
    workspace__name="TEST_U04_RC1_HMB",
)
factories.UploadWorkspaceFactory.create(
    upload_cycle=upload_cycle,
    consent_group=consent_group_hmb,
    workspace__billing_project=billing_project,
    workspace__name="TEST_U04_RC2_HMB",
)
## Create release workspaces.
factories.ReleaseWorkspaceFactory.create(
    upload_cycle=upload_cycle,
    consent_group=consent_group_gru,
    dbgap_version=2,
    workspace__billing_project=billing_project,
    workspace__name="TEST_R02_GRU",
)
factories.ReleaseWorkspaceFactory.create(
    upload_cycle=upload_cycle,
    consent_group=consent_group_hmb,
    dbgap_version=2,
    workspace__billing_project=billing_project,
    workspace__name="TEST_R02_HMB",
)

# Upload cycle 5 - first DCC processed workspaces, included in release R03
## Create upload workspaces
upload_cycle = upload_cycle_5
factories.UploadWorkspaceFactory.create(
    upload_cycle=upload_cycle,
    consent_group=consent_group_gru,
    workspace__billing_project=billing_project,
    workspace__name="TEST_U05_RC1_GRU",
)
factories.UploadWorkspaceFactory.create(
    upload_cycle=upload_cycle,
    consent_group=consent_group_gru,
    workspace__billing_project=billing_project,
    workspace__name="TEST_U05_RC2_GRU",
)
factories.UploadWorkspaceFactory.create(
    upload_cycle=upload_cycle,
    consent_group=consent_group_hmb,
    workspace__billing_project=billing_project,
    workspace__name="TEST_U05_RC1_HMB",
)
factories.UploadWorkspaceFactory.create(
    upload_cycle=upload_cycle,
    consent_group=consent_group_hmb,
    workspace__billing_project=billing_project,
    workspace__name="TEST_U05_RC2_HMB",
)
## DCC processed data workspaces
factories.DCCProcessedDataWorkspaceFactory.create(
    upload_cycle=upload_cycle,
    consent_group=consent_group_gru,
    workspace__billing_project=billing_project,
    workspace__name="TEST_U05_DCC_GRU",
)
factories.DCCProcessedDataWorkspaceFactory.create(
    upload_cycle=upload_cycle,
    consent_group=consent_group_hmb,
    workspace__billing_project=billing_project,
    workspace__name="TEST_U05_DCC_HMB",
)
## Create release workspaces.
factories.ReleaseWorkspaceFactory.create(
    upload_cycle=upload_cycle,
    consent_group=consent_group_gru,
    dbgap_version=3,
    workspace__billing_project=billing_project,
    workspace__name="TEST_R03_GRU",
)
factories.ReleaseWorkspaceFactory.create(
    upload_cycle=upload_cycle,
    consent_group=consent_group_hmb,
    dbgap_version=3,
    workspace__billing_project=billing_project,
    workspace__name="TEST_R03_HMB",
)
