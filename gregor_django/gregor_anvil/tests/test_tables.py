from anvil_consortium_manager.models import Account, Workspace
from anvil_consortium_manager.tests.factories import (
    AccountFactory,
    GroupAccountMembershipFactory,
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

    def test_number_workspaces(self):
        self.model_factory.create()
        workspace_1 = self.model_factory.create()
        workspace_1.upload_workspaces.add(factories.UploadWorkspaceFactory.create())
        workspace_2 = self.model_factory.create()
        workspace_2.upload_workspaces.add(factories.UploadWorkspaceFactory.create())
        workspace_2.upload_workspaces.add(factories.UploadWorkspaceFactory.create())
        table = self.table_class(
            self.model.objects.filter(workspace_type="combined_consortium")
        )
        self.assertEqual(table.rows[0].get_cell("number_workspaces"), 0)
        self.assertEqual(table.rows[1].get_cell("number_workspaces"), 1)
        self.assertEqual(table.rows[2].get_cell("number_workspaces"), 2)


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

    def test_number_workspaces(self):
        self.model_factory.create()
        release_workspace_1 = self.model_factory.create()
        release_workspace_1.upload_workspaces.add(
            factories.UploadWorkspaceFactory.create()
        )
        release_workspace_2 = self.model_factory.create()
        release_workspace_2.upload_workspaces.add(
            factories.UploadWorkspaceFactory.create()
        )
        release_workspace_2.upload_workspaces.add(
            factories.UploadWorkspaceFactory.create()
        )
        table = self.table_class(self.model.objects.filter(workspace_type="release"))
        self.assertEqual(table.rows[0].get_cell("number_workspaces"), 0)
        self.assertEqual(table.rows[1].get_cell("number_workspaces"), 1)
        self.assertEqual(table.rows[2].get_cell("number_workspaces"), 2)


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
