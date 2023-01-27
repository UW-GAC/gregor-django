from anvil_consortium_manager import models as acm_models
from anvil_consortium_manager.tests.factories import (
    AccountFactory,
    GroupAccountMembershipFactory,
)
from django.test import TestCase

from .. import models, tables
from . import factories


class AccountTableTest(TestCase):
    """Tests for the AccountTable in this app."""

    model = acm_models.Account
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


class UploadWorkspaceTableTest(TestCase):
    model = acm_models.Workspace
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
    model = acm_models.Workspace
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
