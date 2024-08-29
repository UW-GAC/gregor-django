"""Tests for data migrations in the app."""

from datetime import date, timedelta

import factory
from anvil_consortium_manager.tests.factories import (
    BillingProjectFactory,
    WorkspaceAuthorizationDomainFactory,
    WorkspaceFactory,
)
from django.utils import timezone
from django_test_migrations.contrib.unittest_case import MigratorTestCase
from freezegun import freeze_time

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
        CombinedConsortiumDataWorkspace = self.old_state.apps.get_model(
            "gregor_anvil", "CombinedConsortiumDataWorkspace"
        )
        ReleaseWorkspace = self.old_state.apps.get_model("gregor_anvil", "ReleaseWorkspace")
        # Make FKs.
        consent_group = factory.create(ConsentGroup, FACTORY_CLASS=factories.ConsentGroupFactory)
        # First upload workspace - version 1
        workspace = factory.create(
            Workspace,
            FACTORY_CLASS=WorkspaceFactory,
            billing_project=factory.create(BillingProject, FACTORY_CLASS=BillingProjectFactory),
        )
        research_center_1 = ResearchCenter.objects.create(short_name="rc1", full_name="Research Center 1")
        self.u_1 = UploadWorkspace.objects.create(
            version=1,
            research_center=research_center_1,
            consent_group=consent_group,
            workspace=workspace,
        )
        # Second upload workspace - also version 1
        workspace = factory.create(
            Workspace,
            FACTORY_CLASS=WorkspaceFactory,
            billing_project=factory.create(BillingProject, FACTORY_CLASS=BillingProjectFactory),
        )
        research_center_2 = ResearchCenter.objects.create(short_name="rc2", full_name="Research Center 2")
        self.u_2 = UploadWorkspace.objects.create(
            version=1,
            research_center=research_center_2,
            consent_group=consent_group,
            workspace=workspace,
        )
        # Third upload workspace - version 2
        workspace = factory.create(
            Workspace,
            FACTORY_CLASS=WorkspaceFactory,
            billing_project=factory.create(BillingProject, FACTORY_CLASS=BillingProjectFactory),
        )
        research_center_3 = ResearchCenter.objects.create(short_name="rc3", full_name="Research Center 3")
        self.u_3 = UploadWorkspace.objects.create(
            version=2,
            research_center=research_center_3,
            consent_group=consent_group,
            workspace=workspace,
        )
        # Combined data workspace.
        workspace = factory.create(
            Workspace,
            FACTORY_CLASS=WorkspaceFactory,
            billing_project=factory.create(BillingProject, FACTORY_CLASS=BillingProjectFactory),
        )
        self.c_1 = CombinedConsortiumDataWorkspace.objects.create(workspace=workspace)
        self.c_1.upload_workspaces.add(self.u_1, self.u_2)
        workspace = factory.create(
            Workspace,
            FACTORY_CLASS=WorkspaceFactory,
            billing_project=factory.create(BillingProject, FACTORY_CLASS=BillingProjectFactory),
        )
        self.c_2 = CombinedConsortiumDataWorkspace.objects.create(workspace=workspace)
        self.c_2.upload_workspaces.add(self.u_3)
        # Release workspace.
        workspace = factory.create(
            Workspace,
            FACTORY_CLASS=WorkspaceFactory,
            billing_project=factory.create(BillingProject, FACTORY_CLASS=BillingProjectFactory),
        )
        self.r_1 = ReleaseWorkspace.objects.create(
            consent_group=consent_group,
            workspace=workspace,
            full_data_use_limitations="foo",
            dbgap_version=1,
            dbgap_participant_set=1,
        )
        self.r_1.upload_workspaces.add(self.u_1, self.u_2)
        workspace = factory.create(
            Workspace,
            FACTORY_CLASS=WorkspaceFactory,
            billing_project=factory.create(BillingProject, FACTORY_CLASS=BillingProjectFactory),
        )
        self.r_2 = ReleaseWorkspace.objects.create(
            consent_group=consent_group,
            workspace=workspace,
            full_data_use_limitations="foo",
            dbgap_version=2,
            dbgap_participant_set=1,
        )
        self.r_2.upload_workspaces.add(self.u_3)

    def test_migration_0012_upload_cycles(self):
        """Run the test."""
        UploadCycle = self.new_state.apps.get_model("gregor_anvil", "UploadCycle")
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
        UploadWorkspace = self.new_state.apps.get_model("gregor_anvil", "UploadWorkspace")
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
        ReleaseWorkspace = self.new_state.apps.get_model("gregor_anvil", "ReleaseWorkspace")
        workspace = ReleaseWorkspace.objects.get(pk=self.r_1.pk)
        self.assertEqual(workspace.upload_cycle.cycle, 1)
        workspace.full_clean()
        workspace = ReleaseWorkspace.objects.get(pk=self.r_2.pk)
        self.assertEqual(workspace.upload_cycle.cycle, 2)
        workspace.full_clean()


class ExampleToResourceWorkspaceForwardMigrationTest(MigratorTestCase):
    """Tests for the migrations associated with renaming the ExampleWorkspace to ResourceWorkspace."""

    migrate_from = ("gregor_anvil", "0020_alter_exchangeworkspace_research_center")
    migrate_to = ("gregor_anvil", "0022_update_exampleworkspace_workspace_type_field")

    def prepare(self):
        """Prepare some example workspaces to be migrated."""
        # Get model definition from the old state.
        BillingProject = self.old_state.apps.get_model("anvil_consortium_manager", "BillingProject")
        Workspace = self.old_state.apps.get_model("anvil_consortium_manager", "Workspace")
        ExampleWorkspace = self.old_state.apps.get_model("gregor_anvil", "ExampleWorkspace")
        # Create required fks.
        # requester = User.objects.create()
        billing_project = BillingProject.objects.create(name="bp", has_app_as_user=True)
        # Create some example workspaces for testing.
        self.workspace_1 = Workspace.objects.create(
            billing_project=billing_project,
            name="example-workspace-1",
            workspace_type="example",
        )
        self.example_workspace_1 = ExampleWorkspace.objects.create(
            workspace=self.workspace_1,
        )
        self.workspace_2 = Workspace.objects.create(
            billing_project=billing_project,
            name="example-workspace-2",
            workspace_type="example",
        )
        self.example_workspace_2 = ExampleWorkspace.objects.create(
            workspace=self.workspace_2,
        )
        # Create a workspace with a different type.
        self.other_workspace = Workspace.objects.create(
            billing_project=billing_project,
            name="other-workspace",
            workspace_type="upload",
        )

    def test_workspace_updates(self):
        """Test updates to the workspace model."""
        Workspace = self.new_state.apps.get_model("anvil_consortium_manager", "Workspace")
        workspace = Workspace.objects.get(pk=self.workspace_1.pk)
        self.assertEqual(workspace.workspace_type, "resource")
        workspace.full_clean()
        workspace = Workspace.objects.get(pk=self.workspace_2.pk)
        self.assertEqual(workspace.workspace_type, "resource")
        workspace.full_clean()
        # Check the other workspace.
        other_workspace = Workspace.objects.get(pk=self.other_workspace.pk)
        self.assertEqual(other_workspace.workspace_type, "upload")

    def test_resource_workspace_updates(self):
        """Test updates to the ResourceWorkspace model."""
        ResourceWorkspace = self.new_state.apps.get_model("gregor_anvil", "ResourceWorkspace")
        resource_workspace = ResourceWorkspace.objects.get(pk=self.example_workspace_1.pk)
        resource_workspace.full_clean()
        resource_workspace = ResourceWorkspace.objects.get(pk=self.example_workspace_2.pk)
        resource_workspace.full_clean()

    def test_relationships(self):
        """relationships and reverse relationships are correct after migration."""
        Workspace = self.new_state.apps.get_model("anvil_consortium_manager", "Workspace")
        ResourceWorkspace = self.new_state.apps.get_model("gregor_anvil", "ResourceWorkspace")
        workspace = Workspace.objects.get(pk=self.workspace_1.pk)
        resource_workspace = ResourceWorkspace.objects.get(pk=self.example_workspace_1.pk)
        self.assertTrue(hasattr(workspace, "resourceworkspace"))
        self.assertIsInstance(workspace.resourceworkspace, ResourceWorkspace)
        self.assertEqual(workspace.resourceworkspace, resource_workspace)
        workspace = Workspace.objects.get(pk=self.workspace_2.pk)
        resource_workspace = ResourceWorkspace.objects.get(pk=self.example_workspace_2.pk)
        self.assertTrue(hasattr(workspace, "resourceworkspace"))
        self.assertIsInstance(workspace.resourceworkspace, ResourceWorkspace)
        self.assertEqual(workspace.resourceworkspace, resource_workspace)


class ExampleToResourceWorkspaceReverseMigrationTest(MigratorTestCase):
    """Tests for the reverse migrations associated with renaming the ExampleWorkspace to ResourceWorkspace."""

    migrate_from = ("gregor_anvil", "0022_update_exampleworkspace_workspace_type_field")
    migrate_to = ("gregor_anvil", "0020_alter_exchangeworkspace_research_center")

    def prepare(self):
        """Prepare some example workspaces to be migrated."""
        # Get model definition from the old state.
        BillingProject = self.old_state.apps.get_model("anvil_consortium_manager", "BillingProject")
        Workspace = self.old_state.apps.get_model("anvil_consortium_manager", "Workspace")
        ResourceWorkspace = self.old_state.apps.get_model("gregor_anvil", "ResourceWorkspace")
        # Create required fks.
        # requester = User.objects.create()
        billing_project = BillingProject.objects.create(name="bp", has_app_as_user=True)
        # Create some example workspaces for testing.
        self.workspace_1 = Workspace.objects.create(
            billing_project=billing_project,
            name="resource-workspace-1",
            workspace_type="resource",
        )
        self.resource_workspace_1 = ResourceWorkspace.objects.create(
            workspace=self.workspace_1,
        )
        self.workspace_2 = Workspace.objects.create(
            billing_project=billing_project,
            name="resource-workspace-2",
            workspace_type="resource",
        )
        self.resource_workspace_2 = ResourceWorkspace.objects.create(
            workspace=self.workspace_2,
        )
        # Create a workspace with a different type.
        self.other_workspace = Workspace.objects.create(
            billing_project=billing_project,
            name="other-workspace",
            workspace_type="upload",
        )

    def test_workspace_updates(self):
        """Test updates to the workspace model."""
        Workspace = self.new_state.apps.get_model("anvil_consortium_manager", "Workspace")
        workspace = Workspace.objects.get(pk=self.workspace_1.pk)
        self.assertEqual(workspace.workspace_type, "example")
        workspace.full_clean()
        workspace = Workspace.objects.get(pk=self.workspace_2.pk)
        self.assertEqual(workspace.workspace_type, "example")
        workspace.full_clean()
        # Check the other workspace.
        other_workspace = Workspace.objects.get(pk=self.other_workspace.pk)
        self.assertEqual(other_workspace.workspace_type, "upload")

    def test_resource_workspace_updates(self):
        """Test updates to the ResourceWorkspace model."""
        ExampleWorkspace = self.new_state.apps.get_model("gregor_anvil", "ExampleWorkspace")
        example_workspace = ExampleWorkspace.objects.get(pk=self.resource_workspace_1.pk)
        example_workspace.full_clean()
        example_workspace = ExampleWorkspace.objects.get(pk=self.resource_workspace_2.pk)
        example_workspace.full_clean()

    def test_relationships(self):
        """relationships and reverse relationships are correct after migration."""
        Workspace = self.new_state.apps.get_model("anvil_consortium_manager", "Workspace")
        ExampleWorkspace = self.new_state.apps.get_model("gregor_anvil", "ExampleWorkspace")
        workspace = Workspace.objects.get(pk=self.workspace_1.pk)
        example_workspace = ExampleWorkspace.objects.get(pk=self.resource_workspace_1.pk)
        self.assertTrue(hasattr(workspace, "exampleworkspace"))
        self.assertIsInstance(workspace.exampleworkspace, ExampleWorkspace)
        self.assertEqual(workspace.exampleworkspace, example_workspace)
        workspace = Workspace.objects.get(pk=self.workspace_2.pk)
        example_workspace = ExampleWorkspace.objects.get(pk=self.resource_workspace_2.pk)
        self.assertTrue(hasattr(workspace, "exampleworkspace"))
        self.assertIsInstance(workspace.exampleworkspace, ExampleWorkspace)
        self.assertEqual(workspace.exampleworkspace, example_workspace)


class PopulateUploadCycleIsReadyForComputeForwardMigrationTest(MigratorTestCase):
    """Tests for the 0028_populate_uploadcycle_is_ready_for_compute migration."""

    migrate_from = ("gregor_anvil", "0027_tracking_fields_for_custom_audits")
    migrate_to = ("gregor_anvil", "0028_populate_uploadcycle_date_ready_for_compute")

    def prepare(self):
        """Prepare some data before the migration."""
        # Get model definition for the old state.
        UploadCycle = self.old_state.apps.get_model("gregor_anvil", "UploadCycle")
        # Create a past upload cycle.
        self.upload_cycle_past = UploadCycle.objects.create(
            cycle=1,
            start_date=timezone.localdate() - timedelta(days=30),
            end_date=timezone.localdate() - timedelta(days=20),
        )
        # Create a current upload cycle - nothing should change for this one.
        self.upload_cycle_current = UploadCycle.objects.create(
            cycle=2,
            start_date=timezone.localdate() - timedelta(days=10),
            end_date=timezone.localdate() + timedelta(days=10),
        )
        # Create a future upload cycle - nothing should change for this one.
        self.upload_cycle_future = UploadCycle.objects.create(
            cycle=3,
            start_date=timezone.localdate() + timedelta(days=10),
            end_date=timezone.localdate() + timedelta(days=20),
        )

    def test_date_completed(self):
        UploadCycle = self.old_state.apps.get_model("gregor_anvil", "UploadCycle")
        upload_cycle = UploadCycle.objects.get(pk=self.upload_cycle_past.pk)
        self.assertEqual(upload_cycle.date_ready_for_compute, upload_cycle.start_date + timedelta(weeks=4))
        upload_cycle = UploadCycle.objects.get(pk=self.upload_cycle_current.pk)
        self.assertIsNone(upload_cycle.date_ready_for_compute)
        upload_cycle = UploadCycle.objects.get(pk=self.upload_cycle_future.pk)
        self.assertIsNone(upload_cycle.date_ready_for_compute)


class PopulateUploadWorkspaceDateQCComplete(MigratorTestCase):
    """Tests for the 0029_populate_uploadworkspace_date_qc_complete migration."""

    migrate_from = ("gregor_anvil", "0027_tracking_fields_for_custom_audits")
    migrate_to = ("gregor_anvil", "0029_populate_uploadworkspace_date_qc_completed")

    def prepare(self):
        """Prepare some data before the migration."""
        # Get model definition for the old state.
        BillingProject = self.old_state.apps.get_model("anvil_consortium_manager", "BillingProject")
        Workspace = self.old_state.apps.get_model("anvil_consortium_manager", "Workspace")
        ResearchCenter = self.old_state.apps.get_model("gregor_anvil", "ResearchCenter")
        ConsentGroup = self.old_state.apps.get_model("gregor_anvil", "ConsentGroup")
        UploadCycle = self.old_state.apps.get_model("gregor_anvil", "UploadCycle")
        UploadWorkspace = self.old_state.apps.get_model("gregor_anvil", "UploadWorkspace")
        # Make FKs.
        consent_group = factory.create(ConsentGroup, FACTORY_CLASS=factories.ConsentGroupFactory)
        research_center = ResearchCenter.objects.create(short_name="rc", full_name="Research Center")
        # Create an upload workspace from a past upload cycle.
        upload_cycle = UploadCycle.objects.create(
            cycle=1,
            start_date=timezone.localdate() - timedelta(days=30),
            end_date=timezone.localdate() - timedelta(days=20),
        )
        workspace = factory.create(
            Workspace,
            FACTORY_CLASS=WorkspaceFactory,
            billing_project=factory.create(BillingProject, FACTORY_CLASS=BillingProjectFactory),
        )
        self.upload_workspace_past = UploadWorkspace.objects.create(
            upload_cycle=upload_cycle,
            research_center=research_center,
            consent_group=consent_group,
            workspace=workspace,
        )
        # Create a current upload cycle - nothing should change for this one.
        upload_cycle = UploadCycle.objects.create(
            cycle=2,
            start_date=timezone.localdate() - timedelta(days=10),
            end_date=timezone.localdate() + timedelta(days=10),
        )
        workspace = factory.create(
            Workspace,
            FACTORY_CLASS=WorkspaceFactory,
            billing_project=factory.create(BillingProject, FACTORY_CLASS=BillingProjectFactory),
        )
        self.upload_workspace_current = UploadWorkspace.objects.create(
            upload_cycle=upload_cycle,
            research_center=research_center,
            consent_group=consent_group,
            workspace=workspace,
        )
        # Create a future upload cycle - nothing should change for this one.
        upload_cycle = UploadCycle.objects.create(
            cycle=3,
            start_date=timezone.localdate() + timedelta(days=10),
            end_date=timezone.localdate() + timedelta(days=20),
        )
        workspace = factory.create(
            Workspace,
            FACTORY_CLASS=WorkspaceFactory,
            billing_project=factory.create(BillingProject, FACTORY_CLASS=BillingProjectFactory),
        )
        self.upload_workspace_future = UploadWorkspace.objects.create(
            upload_cycle=upload_cycle,
            research_center=research_center,
            consent_group=consent_group,
            workspace=workspace,
        )

    def test_date_qc_completed(self):
        UploadWorkspace = self.old_state.apps.get_model("gregor_anvil", "UploadWorkspace")
        upload_workspace = UploadWorkspace.objects.get(pk=self.upload_workspace_past.pk)
        self.assertEqual(
            upload_workspace.date_qc_completed, upload_workspace.upload_cycle.end_date + timedelta(weeks=2)
        )
        upload_workspace = UploadWorkspace.objects.get(pk=self.upload_workspace_current.pk)
        self.assertIsNone(upload_workspace.date_qc_completed)
        upload_workspace = UploadWorkspace.objects.get(pk=self.upload_workspace_future.pk)
        self.assertIsNone(upload_workspace.date_qc_completed)


class PopulateConsortiumCombinedDataWorkspaceIsComplete(MigratorTestCase):
    """Tests for the 0030_populate_consortiumcombineddataworkspace_date_complete migration."""

    migrate_from = ("gregor_anvil", "0027_tracking_fields_for_custom_audits")
    migrate_to = ("gregor_anvil", "0030_populate_consortiumcombineddataworkspace_date_completed")

    def prepare(self):
        """Prepare some data before the migration."""
        # Get model definition for the old state.
        ManagedGroup = self.old_state.apps.get_model("anvil_consortium_manager", "ManagedGroup")
        BillingProject = self.old_state.apps.get_model("anvil_consortium_manager", "BillingProject")
        Workspace = self.old_state.apps.get_model("anvil_consortium_manager", "Workspace")
        WorkspaceAuthorizationDomain = self.old_state.apps.get_model(
            "anvil_consortium_manager", "WorkspaceAuthorizationDomain"
        )
        WorkspaceGroupSharing = self.old_state.apps.get_model("anvil_consortium_manager", "WorkspaceGroupSharing")
        UploadCycle = self.old_state.apps.get_model("gregor_anvil", "UploadCycle")
        CombinedConsortiumDataWorkspace = self.old_state.apps.get_model("gregor_anvil", "CombinedConsortiumDataWorkspace")
        # Create an auth domain for the combined workspaces.
        auth_domain_group = ManagedGroup.objects.create(
            name="auth_domain",
            email="auth_domain@firecloud.org",
        )
        # Create a shared combined workspace.
        upload_cycle = UploadCycle.objects.create(
            cycle=1,
            start_date=timezone.localdate() - timedelta(days=50),
            end_date=timezone.localdate() - timedelta(days=40),
        )
        workspace = factory.create(
            Workspace,
            FACTORY_CLASS=WorkspaceFactory,
            billing_project=factory.create(BillingProject, FACTORY_CLASS=BillingProjectFactory),
        )
        factory.create(
            WorkspaceAuthorizationDomain,
            FACTORY_CLASS=WorkspaceAuthorizationDomainFactory,
            workspace=workspace,
            group=auth_domain_group,
        )
        self.combined_workspace_shared = CombinedConsortiumDataWorkspace.objects.create(
            upload_cycle=upload_cycle,
            workspace=workspace,
        )
        # Shared with its auth domain.
        self.date_shared = timezone.localdate() - timedelta(days=35)
        with freeze_time(self.date_shared):
            WorkspaceGroupSharing.objects.create(
                workspace=workspace,
                group=auth_domain_group,
                access="READER",
                can_compute=False,
            )
        # Create a combined workspace that has not been shared.
        upload_cycle = UploadCycle.objects.create(
            cycle=2,
            start_date=timezone.localdate() - timedelta(days=30),
            end_date=timezone.localdate() - timedelta(days=20),
        )
        workspace = factory.create(
            Workspace,
            FACTORY_CLASS=WorkspaceFactory,
            billing_project=factory.create(BillingProject, FACTORY_CLASS=BillingProjectFactory),
        )
        factory.create(
            WorkspaceAuthorizationDomain,
            FACTORY_CLASS=WorkspaceAuthorizationDomainFactory,
            workspace=workspace,
            group=auth_domain_group,
        )
        self.combined_workspace_not_shared = CombinedConsortiumDataWorkspace.objects.create(
            upload_cycle=upload_cycle,
            workspace=workspace,
        )

    def test_date_completed(self):
        CombinedConsortiumDataWorkspace = self.new_state.apps.get_model("gregor_anvil", "CombinedConsortiumDataWorkspace")
        workspace = CombinedConsortiumDataWorkspace.objects.get(pk=self.combined_workspace_shared.pk)
        self.assertEqual(workspace.date_completed, self.date_shared)
        workspace = CombinedConsortiumDataWorkspace.objects.get(pk=self.combined_workspace_not_shared.pk)
        self.assertIsNone(workspace.date_completed)
