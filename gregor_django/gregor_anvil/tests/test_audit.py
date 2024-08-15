"""Tests for the `py` module."""

from dataclasses import dataclass

import django_tables2 as tables
from anvil_consortium_manager.models import WorkspaceGroupSharing
from anvil_consortium_manager.tests.factories import ManagedGroupFactory, WorkspaceGroupSharingFactory
from django.test import TestCase
from faker import Faker

from ..audit import upload_workspace_audit
from ..audit.base import GREGoRAudit, GREGoRAuditResult
from ..tests import factories

fake = Faker()


@dataclass
class TempAuditResult(GREGoRAuditResult):
    value: str

    def get_table_dictionary(self):
        return {"value": self.value}


class TempResultsTable(tables.Table):
    """A dummy class to use as the results_table_class attribute of GREGoR"""

    # Columns.
    value = tables.Column()


class TempAudit(GREGoRAudit):
    """A dummy class to use for testing the GREGoRAudit class."""

    # Required abstract properties.
    results_table_class = TempResultsTable

    def _run_audit(self):
        # For this test, do nothing.
        pass


class GREGoRAuditResultTest(TestCase):
    """Tests for the `GREGoRAuditResult` class."""

    def test_abstract_base_class(self):
        """The abstract base class cannot be instantiated."""
        with self.assertRaises(TypeError):
            GREGoRAuditResult()

    def test_instantiation(self):
        """Subclass of abstract base class can be instantiated."""
        TempAuditResult(value="foo")

    def test_get_table_dictionary(self):
        audit_result = TempAuditResult(value="foo")
        self.assertEqual(audit_result.get_table_dictionary(), {"value": "foo"})


class GREGoRAuditTest(TestCase):
    """Tests for the `GREGoRAudit` class."""

    def test_abstract_base_class(self):
        """The abstract base class cannot be instantiated."""
        with self.assertRaises(TypeError):
            GREGoRAudit()

    def test_instantiation(self):
        """Subclass of abstract base class can be instantiated."""
        TempAudit()

    def test_results_lists(self):
        """The completed attribute is set appropriately."""
        # Instantiate the class.
        audit_results = TempAudit()
        self.assertEqual(audit_results.verified, [])
        self.assertEqual(audit_results.needs_action, [])
        self.assertEqual(audit_results.errors, [])

    def test_completed(self):
        """The completed attribute is set appropriately."""
        # Instantiate the class.
        audit_results = TempAudit()
        self.assertFalse(audit_results.completed)
        audit_results.run_audit()
        self.assertTrue(audit_results.completed)

    def test_get_all_results(self):
        audit_results = TempAudit()
        audit_results.run_audit()
        # Manually set some audit results to get the output we want.
        audit_results.verified = ["a"]
        audit_results.needs_action = ["b"]
        audit_results.errors = ["c"]
        self.assertEqual(audit_results.get_all_results(), ["a", "b", "c"])

    def test_get_all_results_incomplete(self):
        audit_results = TempAudit()
        with self.assertRaises(ValueError) as e:
            audit_results.get_all_results()
        self.assertEqual(
            str(e.exception),
            "Audit has not been completed. Use run_audit() to run the audit.",
        )

    def test_get_verified_table(self):
        audit_results = TempAudit()
        audit_results.run_audit()
        audit_results.verified = [
            TempAuditResult(value="a"),
        ]
        audit_results.needs_action = [
            TempAuditResult(value="b"),
        ]
        audit_results.errors = [
            TempAuditResult(value="c"),
        ]
        table = audit_results.get_verified_table()
        self.assertIsInstance(table, TempResultsTable)
        self.assertEqual(len(table.rows), 1)
        self.assertEqual(table.rows[0].get_cell("value"), "a")

    def test_get_needs_action_table(self):
        audit_results = TempAudit()
        audit_results.run_audit()
        audit_results.verified = [
            TempAuditResult(value="a"),
        ]
        audit_results.needs_action = [
            TempAuditResult(value="b"),
        ]
        audit_results.errors = [
            TempAuditResult(value="c"),
        ]
        table = audit_results.get_needs_action_table()
        self.assertIsInstance(table, TempResultsTable)
        self.assertEqual(len(table.rows), 1)
        self.assertEqual(table.rows[0].get_cell("value"), "b")

    def test_get_errors_table(self):
        audit_results = TempAudit()
        audit_results.run_audit()
        audit_results.verified = [
            TempAuditResult(value="a"),
        ]
        audit_results.needs_action = [
            TempAuditResult(value="b"),
        ]
        audit_results.errors = [
            TempAuditResult(value="c"),
        ]
        table = audit_results.get_errors_table()
        self.assertIsInstance(table, TempResultsTable)
        self.assertEqual(len(table.rows), 1)
        self.assertEqual(table.rows[0].get_cell("value"), "c")


class UploadWorkspaceAuditTest(TestCase):
    """Tests for the `UploadWorkspaceAudit` class."""

    def test_completed(self):
        """The completed attribute is set appropriately."""
        # Instantiate the class.
        audit = upload_workspace_audit.UploadWorkspaceAudit()
        self.assertFalse(audit.completed)
        audit.run_audit()
        self.assertTrue(audit.completed)

    def test_no_upload_workspaces(self):
        """The audit works if there are no UploadWorkspaces."""
        audit = upload_workspace_audit.UploadWorkspaceAudit()
        audit.run_audit()
        self.assertEqual(len(audit.verified), 0)
        self.assertEqual(len(audit.needs_action), 0)
        self.assertEqual(len(audit.errors), 0)

    def test_audit_workspace_and_group_current_cycle_members_group_shared(self):
        """audit method works with current upload cycle and members group."""
        upload_workspace = factories.UploadWorkspaceFactory.create(
            upload_cycle__end_date=fake.date_between(start_date="-30d", end_date="+30d")
        )
        group = ManagedGroupFactory.create(research_center_of_members=upload_workspace.research_center)
        # Share the workspace with the group.
        WorkspaceGroupSharingFactory.create(
            workspace=upload_workspace.workspace, group=group, access=WorkspaceGroupSharing.WRITER
        )
        audit = upload_workspace_audit.UploadWorkspaceAudit()
        audit.audit_workspace_and_group(upload_workspace, group)
        self.assertEqual(len(audit.verified), 1)
        self.assertEqual(len(audit.needs_action), 0)
        self.assertEqual(len(audit.errors), 0)
        record = audit.verified[0]
        self.assertIsInstance(record, upload_workspace_audit.VerifiedShared)
        self.assertEqual(record.workspace, upload_workspace)
        self.assertEqual(record.managed_group, group)
        self.assertEqual(record.note, upload_workspace_audit.UploadWorkspaceAudit.CURRENT_CYCLE_RC_MEMBER_GROUP)
