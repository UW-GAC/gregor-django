from anvil_consortium_manager.models import Account, Workspace
from anvil_consortium_manager.tests.factories import (
    AccountFactory,
    GroupAccountMembershipFactory,
    GroupGroupMembershipFactory,
    ManagedGroupFactory,
    WorkspaceAuthorizationDomainFactory,
    WorkspaceFactory,
    WorkspaceGroupSharingFactory,
)
from django.db.models import Count, Q
from django.test import TestCase

from .. import models, tables
from . import factories


class AccountTableTest(TestCase):
    """Tests for the AccountTable in this app."""

    model = Account
    model_factory = AccountFactory
    table_class = tables.AccountTable

    def test_row_count_with_no_objects(self):
        table = self.table_class(self.model.objects.all())
        self.assertEqual(len(table.rows), 0)

    def test_row_count_with_one_object(self):
        self.model_factory.create()
        table = self.table_class(self.model.objects.all())
        self.assertEqual(len(table.rows), 1)

    def test_row_count_with_two_objects(self):
        self.model_factory.create_batch(2)
        table = self.table_class(self.model.objects.all())
        self.assertEqual(len(table.rows), 2)

    def test_number_of_groups(self):
        self.model_factory.create()
        account_1 = self.model_factory.create()
        account_2 = self.model_factory.create()
        GroupAccountMembershipFactory.create_batch(1, account=account_1)
        GroupAccountMembershipFactory.create_batch(2, account=account_2)
        table = self.table_class(self.model.objects.all())
        self.assertEqual(table.rows[0].get_cell("number_groups"), 0)
        self.assertEqual(table.rows[1].get_cell("number_groups"), 1)
        self.assertEqual(table.rows[2].get_cell("number_groups"), 2)

    def test_account_status(self):
        self.model_factory.create()
        account_1 = self.model_factory.create()
        account_1.deactivate()
        table = self.table_class(self.model.objects.all())
        self.assertEqual(table.rows[0].get_cell("status"), "Active")
        self.assertEqual(table.rows[1].get_cell("status"), "Inactive")


class ResearchCenterTableTest(TestCase):
    model = models.ResearchCenter
    model_factory = factories.ResearchCenterFactory
    table_class = tables.ResearchCenterTable

    def test_row_count_with_no_objects(self):
        table = self.table_class(self.model.objects.all())
        self.assertEqual(len(table.rows), 0)

    def test_row_count_with_one_object(self):
        self.model_factory.create()
        table = self.table_class(self.model.objects.all())
        self.assertEqual(len(table.rows), 1)

    def test_row_count_with_two_objects(self):
        self.model_factory.create_batch(2)
        table = self.table_class(self.model.objects.all())
        self.assertEqual(len(table.rows), 2)


class ConsentGroupTableTest(TestCase):
    model = models.ConsentGroup
    model_factory = factories.ConsentGroupFactory
    table_class = tables.ConsentGroupTable

    def test_row_count_with_no_objects(self):
        table = self.table_class(self.model.objects.all())
        self.assertEqual(len(table.rows), 0)

    def test_row_count_with_one_object(self):
        self.model_factory.create()
        table = self.table_class(self.model.objects.all())
        self.assertEqual(len(table.rows), 1)

    def test_row_count_with_two_objects(self):
        # These values are coded into the model, so need to create separately.
        self.model_factory.create_batch(2)
        table = self.table_class(self.model.objects.all())
        self.assertEqual(len(table.rows), 2)


class UploadCycleTableTest(TestCase):
    model = models.UploadCycle
    model_factory = factories.UploadCycleFactory
    table_class = tables.UploadCycleTable

    def test_row_count_with_no_objects(self):
        table = self.table_class(self.model.objects.all())
        self.assertEqual(len(table.rows), 0)

    def test_row_count_with_one_object(self):
        self.model_factory.create()
        table = self.table_class(self.model.objects.all())
        self.assertEqual(len(table.rows), 1)

    def test_row_count_with_two_objects(self):
        self.model_factory.create_batch(2)
        table = self.table_class(self.model.objects.all())
        self.assertEqual(len(table.rows), 2)


class WorkspaceSharedWithConsortiumTableTest(TestCase):
    """Tests for the is_shared column."""

    def setUp(self):
        self.gregor_all = ManagedGroupFactory.create(name="GREGOR_ALL")

    def test_is_shared_no_auth_domain_not_shared(self):
        """Workspace has no auth domain and is not shared with GREGOR_ALL."""
        workspace = WorkspaceFactory.create()
        table = tables.WorkspaceSharedWithConsortiumTable(Workspace.objects.all())
        self.assertNotIn("check-circle-fill", table.render_is_shared(workspace))

    def test_is_shared_no_auth_domain_shared(self):
        """Workspace has no auth domain and is shared with GREGOR_ALL."""
        workspace = WorkspaceFactory.create()
        WorkspaceGroupSharingFactory.create(workspace=workspace, group=self.gregor_all)
        table = tables.WorkspaceSharedWithConsortiumTable(Workspace.objects.all())
        self.assertIn("check-circle-fill", table.render_is_shared(workspace))

    def test_is_shared_no_auth_domain_shared_other_group(self):
        """Workspace has no auth domain and is shared with a different group."""
        workspace = WorkspaceFactory.create()
        WorkspaceGroupSharingFactory.create(workspace=workspace)
        table = tables.WorkspaceSharedWithConsortiumTable(Workspace.objects.all())
        self.assertNotIn("check-circle-fill", table.render_is_shared(workspace))

    def test_is_shared_one_auth_domain_not_shared_not_in_auth_domain(self):
        """GREGOR_ALL is not in auth domain and workspace is not shared."""
        workspace = WorkspaceFactory.create()
        WorkspaceAuthorizationDomainFactory.create(workspace=workspace)
        table = tables.WorkspaceSharedWithConsortiumTable(Workspace.objects.all())
        self.assertNotIn("check-circle-fill", table.render_is_shared(workspace))

    def test_is_shared_one_auth_domain_not_shared_in_auth_domain(self):
        """GREGOR_ALL is in auth domain and workspace is not shared."""
        workspace = WorkspaceFactory.create()
        auth_domain = WorkspaceAuthorizationDomainFactory.create(workspace=workspace)
        GroupGroupMembershipFactory.create(
            parent_group=auth_domain.group, child_group=self.gregor_all
        )
        table = tables.WorkspaceSharedWithConsortiumTable(Workspace.objects.all())
        self.assertNotIn("check-circle-fill", table.render_is_shared(workspace))

    def test_is_shared_one_auth_domain_shared_different_group_in_auth_domain(self):
        """GREGOR_ALL is in auth domain and workspace is shared with a different group."""
        workspace = WorkspaceFactory.create()
        auth_domain = WorkspaceAuthorizationDomainFactory.create(workspace=workspace)
        GroupGroupMembershipFactory.create(
            parent_group=auth_domain.group, child_group=self.gregor_all
        )
        WorkspaceGroupSharingFactory.create(workspace=workspace)
        table = tables.WorkspaceSharedWithConsortiumTable(Workspace.objects.all())
        self.assertNotIn("check-circle-fill", table.render_is_shared(workspace))

    def test_is_shared_one_auth_domain_shared_with_gregor_all_not_in_auth_domain(self):
        """GREGOR_ALL is not in auth domain and workspace is shared with GREGOR_ALL."""
        workspace = WorkspaceFactory.create()
        WorkspaceAuthorizationDomainFactory.create(workspace=workspace)
        WorkspaceGroupSharingFactory.create(workspace=workspace, group=self.gregor_all)
        table = tables.WorkspaceSharedWithConsortiumTable(Workspace.objects.all())
        self.assertNotIn("check-circle-fill", table.render_is_shared(workspace))

    def test_is_shared_one_auth_domain_shared_with_auth_domain_not_in_auth_domain(self):
        """GREGOR_ALL is not in auth domain and workspace is shared with its auth domain."""
        workspace = WorkspaceFactory.create()
        auth_domain = WorkspaceAuthorizationDomainFactory.create(workspace=workspace)
        WorkspaceGroupSharingFactory.create(
            workspace=workspace, group=auth_domain.group
        )
        table = tables.WorkspaceSharedWithConsortiumTable(Workspace.objects.all())
        self.assertNotIn("check-circle-fill", table.render_is_shared(workspace))

    def test_is_shared_one_auth_domain_shared_with_gregor_all_in_auth_domain(self):
        """GREGOR_ALL is in auth domain and workspace is shared with GREGOR_ALL."""
        workspace = WorkspaceFactory.create()
        auth_domain = WorkspaceAuthorizationDomainFactory.create(workspace=workspace)
        GroupGroupMembershipFactory.create(
            parent_group=auth_domain.group, child_group=self.gregor_all
        )
        WorkspaceGroupSharingFactory.create(workspace=workspace, group=self.gregor_all)
        table = tables.WorkspaceSharedWithConsortiumTable(Workspace.objects.all())
        self.assertIn("check-circle-fill", table.render_is_shared(workspace))

    def test_is_shared_one_auth_domain_shared_with_auth_domain_in_auth_domain(self):
        """GREGOR_ALL is in auth domain and workspace is shared with its auth domain."""
        workspace = WorkspaceFactory.create()
        auth_domain = WorkspaceAuthorizationDomainFactory.create(workspace=workspace)
        GroupGroupMembershipFactory.create(
            parent_group=auth_domain.group, child_group=self.gregor_all
        )
        WorkspaceGroupSharingFactory.create(
            workspace=workspace, group=auth_domain.group
        )
        table = tables.WorkspaceSharedWithConsortiumTable(Workspace.objects.all())
        self.assertIn("check-circle-fill", table.render_is_shared(workspace))

    def test_is_shared_one_auth_domain_shared_with_different_group_in_auth_domain(self):
        """GREGOR_ALL is in auth domain and workspace is shared with a different group."""
        workspace = WorkspaceFactory.create()
        auth_domain = WorkspaceAuthorizationDomainFactory.create(workspace=workspace)
        GroupGroupMembershipFactory.create(
            parent_group=auth_domain.group, child_group=self.gregor_all
        )
        WorkspaceGroupSharingFactory.create(workspace=workspace)
        table = tables.WorkspaceSharedWithConsortiumTable(Workspace.objects.all())
        self.assertNotIn("check-circle-fill", table.render_is_shared(workspace))


class UploadWorkspaceTableTest(TestCase):
    model = Workspace
    model_factory = factories.UploadWorkspaceFactory
    table_class = tables.UploadWorkspaceTable

    def test_row_count_with_no_objects(self):
        table = self.table_class(self.model.objects.all())
        self.assertEqual(len(table.rows), 0)

    def test_row_count_with_one_object(self):
        self.model_factory.create()
        table = self.table_class(self.model.objects.all())
        self.assertEqual(len(table.rows), 1)

    def test_row_count_with_two_objects(self):
        # These values are coded into the model, so need to create separately.
        self.model_factory.create_batch(2)
        table = self.table_class(self.model.objects.all())
        self.assertEqual(len(table.rows), 2)


class TemplateWorkspaceTableTest(TestCase):
    model = Workspace
    model_factory = factories.TemplateWorkspaceFactory
    table_class = tables.TemplateWorkspaceTable

    def test_row_count_with_no_objects(self):
        table = self.table_class(self.model.objects.all())
        self.assertEqual(len(table.rows), 0)

    def test_row_count_with_one_object(self):
        self.model_factory.create()
        table = self.table_class(self.model.objects.all())
        self.assertEqual(len(table.rows), 1)

    def test_row_count_with_two_objects(self):
        # These values are coded into the model, so need to create separately.
        self.model_factory.create_batch(2)
        table = self.table_class(self.model.objects.all())
        self.assertEqual(len(table.rows), 2)


class CombinedConsortiumDataWorkspaceTableTest(TestCase):
    """Tests for the AccountTable in this app."""

    model = Workspace
    model_factory = factories.CombinedConsortiumDataWorkspaceFactory
    table_class = tables.CombinedConsortiumDataWorkspaceTable

    def test_row_count_with_no_objects(self):
        table = self.table_class(self.model.objects.all())
        self.assertEqual(len(table.rows), 0)

    def test_row_count_with_one_object(self):
        self.model_factory.create()
        table = self.table_class(self.model.objects.all())
        self.assertEqual(len(table.rows), 1)

    def test_row_count_with_two_objects(self):
        self.model_factory.create_batch(2)
        table = self.table_class(self.model.objects.all())
        self.assertEqual(len(table.rows), 2)


class ReleaseWorkspaceTableTest(TestCase):
    """Tests for the AccountTable in this app."""

    model = Workspace
    model_factory = factories.ReleaseWorkspaceFactory
    table_class = tables.ReleaseWorkspaceTable

    def test_row_count_with_no_objects(self):
        table = self.table_class(self.model.objects.all())
        self.assertEqual(len(table.rows), 0)

    def test_row_count_with_one_object(self):
        self.model_factory.create()
        table = self.table_class(self.model.objects.all())
        self.assertEqual(len(table.rows), 1)

    def test_row_count_with_two_objects(self):
        self.model_factory.create_batch(2)
        table = self.table_class(self.model.objects.all())
        self.assertEqual(len(table.rows), 2)


class WorkspaceReportTableTest(TestCase):
    model = Workspace
    model_factory = factories.TemplateWorkspaceFactory
    table_class = tables.TemplateWorkspaceTable

    def get_qs(self):
        qs = Workspace.objects.values("workspace_type").annotate(
            n_total=Count("workspace_type"),
            n_shared=Count(
                "workspacegroupsharing",
                filter=Q(workspacegroupsharing__group__name="GREGOR_ALL"),
            ),
        )
        return qs

    def test_row_count_with_no_objects(self):
        table = self.table_class(self.get_qs())
        self.assertEqual(len(table.rows), 0)

    def test_row_count_with_one_workspace_type_one_workspace(self):
        factories.UploadWorkspaceFactory.create()
        table = self.table_class(self.get_qs())
        self.assertEqual(len(table.rows), 1)

    def test_row_count_with_one_workspace_type_two_workspaces(self):
        factories.UploadWorkspaceFactory.create_batch(2)
        table = self.table_class(self.get_qs())
        self.assertEqual(len(table.rows), 1)

    def test_row_count_with_two_workspace_types(self):
        factories.UploadWorkspaceFactory.create()
        factories.ExampleWorkspaceFactory.create_batch(2)
        table = self.table_class(self.get_qs())
        self.assertEqual(len(table.rows), 2)


class DCCProcessingWorkspaceTableTest(TestCase):
    model = Workspace
    model_factory = factories.DCCProcessingWorkspaceFactory
    table_class = tables.DCCProcessingWorkspaceTable

    def test_row_count_with_no_objects(self):
        table = self.table_class(
            self.model.objects.filter(workspace_type="dcc_processing")
        )
        self.assertEqual(len(table.rows), 0)

    def test_row_count_with_one_object(self):
        self.model_factory.create()
        table = self.table_class(
            self.model.objects.filter(workspace_type="dcc_processing")
        )
        self.assertEqual(len(table.rows), 1)

    def test_row_count_with_two_objects(self):
        # These values are coded into the model, so need to create separately.
        self.model_factory.create_batch(2)
        table = self.table_class(
            self.model.objects.filter(workspace_type="dcc_processing")
        )
        self.assertEqual(len(table.rows), 2)


class DCCProcessedDataWorkspaceTableTest(TestCase):
    model = Workspace
    model_factory = factories.DCCProcessedDataWorkspaceFactory
    table_class = tables.DCCProcessedDataWorkspaceTable

    def test_row_count_with_no_objects(self):
        table = self.table_class(
            self.model.objects.filter(workspace_type="dcc_processed_data")
        )
        self.assertEqual(len(table.rows), 0)

    def test_row_count_with_one_object(self):
        self.model_factory.create()
        table = self.table_class(
            self.model.objects.filter(workspace_type="dcc_processed_data")
        )
        self.assertEqual(len(table.rows), 1)

    def test_row_count_with_two_objects(self):
        # These values are coded into the model, so need to create separately.
        self.model_factory.create_batch(2)
        table = self.table_class(
            self.model.objects.filter(workspace_type="dcc_processed_data")
        )
        self.assertEqual(len(table.rows), 2)
