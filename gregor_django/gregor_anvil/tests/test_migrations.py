"""Tests for data migrations in the app."""
from datetime import date

from anvil_consortium_manager.tests.factories import BillingProjectFactory, WorkspaceFactory
from django_test_migrations.contrib.unittest_case import MigratorTestCase
import factory

from . import factories

class PopulateUploadCycleTest(MigratorTestCase):
    """Tests for the populate_upload_cycle migration."""

    migrate_from = ("gregor_anvil", "0011_add_uploadcycle_fields")
    migrate_to = ("gregor_anvil", "0012_populate_upload_cycle")

    def prepare(self):
        """Prepare some data before the migration."""
        # Get model definition for the old state.
        Workspace = self.old_state.apps.get_model("anvil_consortium_manager", "Workspace")
        BillingProject = self.old_state.apps.get_model("anvil_consortium_manager", "BillingProject")
        ResearchCenter = self.old_state.apps.get_model("gregor_anvil", "ResearchCenter")
        ConsentGroup = self.old_state.apps.get_model("gregor_anvil", "ConsentGroup")
        UploadWorkspace = self.old_state.apps.get_model("gregor_anvil", "UploadWorkspace")
        UploadCycle = self.old_state.apps.get_model("gregor_anvil", "UploadCycle")
        CombinedConsortiumDataWorkspace = self.old_state.apps.get_model("gregor_anvil", "CombinedConsortiumDataWorkspace")
        ReleaseWorkspace = self.old_state.apps.get_model("gregor_anvil", "ReleaseWorkspace")
        upload_cycle = factory.create(UploadCycle)
        # Make FKs.
        consent_group = factory.create(ConsentGroup, FACTORY_CLASS=factories.ConsentGroupFactory)
        # First upload workspace - version 1
        workspace = factory.create(
            Workspace,
            FACTORY_CLASS=WorkspaceFactory,
            billing_project=factory.create(BillingProject, FACTORY_CLASS=BillingProjectFactory)
        )
        self.u_1 = UploadWorkspace.objects.create(
            version=1,
            research_center=factory.create(ResearchCenter, FACTORY_CLASS=factories.ResearchCenterFactory),
            consent_group=consent_group,
            workspace=workspace
        )
        # Second upload workspace - also version 1
        workspace = factory.create(
            Workspace,
            FACTORY_CLASS=WorkspaceFactory,
            billing_project=factory.create(BillingProject, FACTORY_CLASS=BillingProjectFactory)
        )
        self.u_2 = UploadWorkspace.objects.create(
            version=1,
            research_center=factory.create(ResearchCenter, FACTORY_CLASS=factories.ResearchCenterFactory),
            consent_group=consent_group,
            workspace=workspace
        )
        # Third upload workspace - version 2
        workspace = factory.create(
            Workspace,
            FACTORY_CLASS=WorkspaceFactory,
            billing_project=factory.create(BillingProject, FACTORY_CLASS=BillingProjectFactory)
        )
        self.u_3 = UploadWorkspace.objects.create(
            version=2,
            research_center=factory.create(ResearchCenter, FACTORY_CLASS=factories.ResearchCenterFactory),
            consent_group=consent_group,
            workspace=workspace
        )
        # Combined data workspace.
        workspace = factory.create(
            Workspace,
            FACTORY_CLASS=WorkspaceFactory,
            billing_project=factory.create(BillingProject, FACTORY_CLASS=BillingProjectFactory)
        )
        self.c_1 = CombinedConsortiumDataWorkspace.objects.create(workspace=workspace)
        self.c_1.upload_workspaces.add(self.u_1, self.u_2)
        workspace = factory.create(
            Workspace,
            FACTORY_CLASS=WorkspaceFactory,
            billing_project=factory.create(BillingProject, FACTORY_CLASS=BillingProjectFactory)
        )
        self.c_2 = CombinedConsortiumDataWorkspace.objects.create(workspace=workspace)
        self.c_2.upload_workspaces.add(self.u_1, self.u_2, self.u_3)
        # Release workspace.
        workspace = factory.create(
            Workspace,
            FACTORY_CLASS=WorkspaceFactory,
            billing_project=factory.create(BillingProject, FACTORY_CLASS=BillingProjectFactory)
        )
        self.r_1 = factory.create(
            ReleaseWorkspace,
            FACTORY_CLASS=factories.ReleaseWorkspaceFactory,
            workspace=workspace,
            dbgap_version=1,
            dbgap_participant_set=1,
            consent_group=consent_group
        )
        self.r_1.upload_workspaces.add(self.u_1, self.u_2)
        workspace = factory.create(
            Workspace,
            FACTORY_CLASS=WorkspaceFactory,
            billing_project=factory.create(BillingProject, FACTORY_CLASS=BillingProjectFactory)
        )
        self.r_2 = factory.create(
            ReleaseWorkspace,
            FACTORY_CLASS=factories.ReleaseWorkspaceFactory,
            workspace=workspace,
            dbgap_version=2,
            dbgap_participant_set=1,
            consent_group=consent_group
        )
        self.r_2.upload_workspaces.add(self.u_1, self.u_2, self.u_3)

    def test_migration_0012_upload_cycles(self):
        """Run the test."""
        UploadCycle = self.new_state.apps.get_model(
            "gregor_anvil", "UploadCycle"
        )
        self.assertEqual(UploadCycle.objects.count(), 2)
        upload_cycle = UploadCycle.objects.get(cycle=1)
        self.assertEqual(upload_cycle.cycle, 1)
        self.assertEqual(upload_cycle.start_date, date.fromtimestamp(0))
        self.assertEqual(upload_cycle.end_date, date.fromtimestamp(0))
        upload_cycle.full_clean()
        upload_cycle = UploadCycle.objects.get(cycle=2)
        self.assertEqual(upload_cycle.cycle, 2)
        self.assertEqual(upload_cycle.start_date, date.fromtimestamp(0))
        self.assertEqual(upload_cycle.end_date, date.fromtimestamp(0))
        upload_cycle.full_clean()

    def test_migration_0012_upload_workspaces(self):
        """Run the test for upload workspaces."""
        UploadWorkspace = self.new_state.apps.get_model(
            "gregor_anvil", "UploadWorkspace"
        )
        workspace = UploadWorkspace.objects.get(pk=self.u_1.pk)
        self.assertEqual(workspace.upload_cycle.cycle, 1)
        workspace.full_clean()
        workspace = UploadWorkspace.objects.get(pk=self.u_2.pk)
        self.assertEqual(workspace.upload_cycle.cycle, 1)
        workspace.full_clean()
        workspace = UploadWorkspace.objects.get(pk=self.u_3.pk)
        self.assertEqual(workspace.upload_cycle.cycle, 2)
        workspace.full_clean()

    def test_migration_0012_consortium_combined_data_workspaces(self):
        """Run the test for consortium combined data workspaces."""
        CombinedConsortiumDataWorkspace = self.new_state.apps.get_model(
            "gregor_anvil", "CombinedConsortiumDataWorkspace"
        )
        workspace = CombinedConsortiumDataWorkspace.objects.get(pk=self.c_1.pk)
        self.assertEqual(workspace.upload_cycle.cycle, 1)
        workspace.full_clean()
        workspace = CombinedConsortiumDataWorkspace.objects.get(pk=self.c_2.pk)
        self.assertEqual(workspace.upload_cycle.cycle, 2)
        workspace.full_clean()

    def test_migration_0012_release_workspaces(self):
        """Run the test for release workspaces."""
        ReleaseWorkspace = self.new_state.apps.get_model(
            "gregor_anvil", "ReleaseWorkspace"
        )
        workspace = ReleaseWorkspace.objects.get(pk=self.r_1.pk)
        self.assertEqual(workspace.upload_cycle.cycle, 1)
        workspace.full_clean()
        workspace = ReleaseWorkspace.objects.get(pk=self.r_2.pk)
        self.assertEqual(workspace.upload_cycle.cycle, 2)
        workspace.full_clean()
