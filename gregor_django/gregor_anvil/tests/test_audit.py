"""Tests for the `py` module."""

from dataclasses import dataclass

import django_tables2 as tables
from anvil_consortium_manager.models import WorkspaceGroupSharing
from anvil_consortium_manager.tests.factories import ManagedGroupFactory, WorkspaceGroupSharingFactory
from django.test import TestCase
from django.utils import timezone
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
    """General tests of the `UploadWorkspaceAudit` class."""

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


class UploadWorkspaceAuditFutureCycleTest(TestCase):
    """Tests for the `UploadWorkspaceAudit` class for future cycle UploadWorkspaces.

    Expectations at this point in the upload cycle:
    - RC uploader group should be writers without compute.
    - DCC writer group should be writers with compute.
    """

    def setUp(self):
        super().setUp()
        self.rc_uploader_group = ManagedGroupFactory.create()
        self.dcc_writer_group = ManagedGroupFactory.create(name="GREGOR_DCC_WRITERS")
        self.research_center = factories.ResearchCenterFactory.create(uploader_group=self.rc_uploader_group)
        self.upload_workspace = factories.UploadWorkspaceFactory.create(
            research_center=self.research_center, upload_cycle__is_future=True
        )

    def test_uploaders_shared_as_writer_no_compute(self):
        # Share the workspace with the group.
        sharing = WorkspaceGroupSharingFactory.create(
            workspace=self.upload_workspace.workspace, group=self.rc_uploader_group, access=WorkspaceGroupSharing.WRITER
        )
        audit = upload_workspace_audit.UploadWorkspaceAudit()
        audit.audit_workspace_and_group(self.upload_workspace, self.rc_uploader_group)
        self.assertEqual(len(audit.verified), 1)
        self.assertEqual(len(audit.needs_action), 0)
        self.assertEqual(len(audit.errors), 0)
        record = audit.verified[0]
        self.assertIsInstance(record, upload_workspace_audit.VerifiedShared)
        self.assertEqual(record.workspace, self.upload_workspace)
        self.assertEqual(record.managed_group, self.rc_uploader_group)
        self.assertEqual(record.current_sharing_instance, sharing)
        self.assertEqual(record.note, upload_workspace_audit.UploadWorkspaceAudit.RC_UPLOADERS_FUTURE_CYCLE)

    def test_uploaders_not_shared(self):
        audit = upload_workspace_audit.UploadWorkspaceAudit()
        audit.audit_workspace_and_group(self.upload_workspace, self.rc_uploader_group)
        self.assertEqual(len(audit.verified), 0)
        self.assertEqual(len(audit.needs_action), 1)
        self.assertEqual(len(audit.errors), 0)
        record = audit.needs_action[0]
        self.assertIsInstance(record, upload_workspace_audit.ShareAsWriter)
        self.assertEqual(record.workspace, self.upload_workspace)
        self.assertEqual(record.managed_group, self.rc_uploader_group)
        self.assertEqual(record.current_sharing_instance, None)
        self.assertEqual(record.note, upload_workspace_audit.UploadWorkspaceAudit.RC_UPLOADERS_FUTURE_CYCLE)

    def test_uploaders_shared_as_writer_can_compute(self):
        sharing = WorkspaceGroupSharingFactory.create(
            workspace=self.upload_workspace.workspace,
            group=self.rc_uploader_group,
            access=WorkspaceGroupSharing.WRITER,
            can_compute=True,
        )
        audit = upload_workspace_audit.UploadWorkspaceAudit()
        audit.audit_workspace_and_group(self.upload_workspace, self.rc_uploader_group)
        self.assertEqual(len(audit.verified), 0)
        self.assertEqual(len(audit.needs_action), 1)
        self.assertEqual(len(audit.errors), 0)
        record = audit.needs_action[0]
        self.assertIsInstance(record, upload_workspace_audit.ShareAsWriter)
        self.assertEqual(record.workspace, self.upload_workspace)
        self.assertEqual(record.managed_group, self.rc_uploader_group)
        self.assertEqual(record.current_sharing_instance, sharing)
        self.assertEqual(record.note, upload_workspace_audit.UploadWorkspaceAudit.RC_UPLOADERS_FUTURE_CYCLE)

    def test_uploaders_shared_as_reader(self):
        sharing = WorkspaceGroupSharingFactory.create(
            workspace=self.upload_workspace.workspace, group=self.rc_uploader_group, access=WorkspaceGroupSharing.READER
        )
        audit = upload_workspace_audit.UploadWorkspaceAudit()
        audit.audit_workspace_and_group(self.upload_workspace, self.rc_uploader_group)
        self.assertEqual(len(audit.verified), 0)
        self.assertEqual(len(audit.needs_action), 1)
        self.assertEqual(len(audit.errors), 0)
        record = audit.needs_action[0]
        self.assertIsInstance(record, upload_workspace_audit.ShareAsWriter)
        self.assertEqual(record.workspace, self.upload_workspace)
        self.assertEqual(record.managed_group, self.rc_uploader_group)
        self.assertEqual(record.current_sharing_instance, sharing)
        self.assertEqual(record.note, upload_workspace_audit.UploadWorkspaceAudit.RC_UPLOADERS_FUTURE_CYCLE)

    def test_uploaders_shared_as_owner(self):
        sharing = WorkspaceGroupSharingFactory.create(
            workspace=self.upload_workspace.workspace, group=self.rc_uploader_group, access=WorkspaceGroupSharing.OWNER
        )
        audit = upload_workspace_audit.UploadWorkspaceAudit()
        audit.audit_workspace_and_group(self.upload_workspace, self.rc_uploader_group)
        self.assertEqual(len(audit.verified), 0)
        self.assertEqual(len(audit.needs_action), 1)
        self.assertEqual(len(audit.errors), 0)
        record = audit.needs_action[0]
        self.assertIsInstance(record, upload_workspace_audit.ShareAsWriter)
        self.assertEqual(record.workspace, self.upload_workspace)
        self.assertEqual(record.managed_group, self.rc_uploader_group)
        self.assertEqual(record.current_sharing_instance, sharing)
        self.assertEqual(record.note, upload_workspace_audit.UploadWorkspaceAudit.RC_UPLOADERS_FUTURE_CYCLE)

    def test_dcc_writers_shared_as_writer_no_compute(self):
        # Share the workspace with the group.
        sharing = WorkspaceGroupSharingFactory.create(
            workspace=self.upload_workspace.workspace, group=self.dcc_writer_group, access=WorkspaceGroupSharing.WRITER
        )
        audit = upload_workspace_audit.UploadWorkspaceAudit()
        audit.audit_workspace_and_group(self.upload_workspace, self.dcc_writer_group)
        self.assertEqual(len(audit.verified), 0)
        self.assertEqual(len(audit.needs_action), 1)
        self.assertEqual(len(audit.errors), 0)
        record = audit.needs_action[0]
        self.assertIsInstance(record, upload_workspace_audit.ShareWithCompute)
        self.assertEqual(record.workspace, self.upload_workspace)
        self.assertEqual(record.managed_group, self.dcc_writer_group)
        self.assertEqual(record.current_sharing_instance, sharing)
        self.assertEqual(record.note, upload_workspace_audit.UploadWorkspaceAudit.DCC_WRITERS_FUTURE_CYCLE)

    def test_dcc_writers_not_shared(self):
        audit = upload_workspace_audit.UploadWorkspaceAudit()
        audit.audit_workspace_and_group(self.upload_workspace, self.dcc_writer_group)
        self.assertEqual(len(audit.verified), 0)
        self.assertEqual(len(audit.needs_action), 1)
        self.assertEqual(len(audit.errors), 0)
        record = audit.needs_action[0]
        self.assertIsInstance(record, upload_workspace_audit.ShareWithCompute)
        self.assertEqual(record.workspace, self.upload_workspace)
        self.assertEqual(record.managed_group, self.dcc_writer_group)
        self.assertEqual(record.current_sharing_instance, None)
        self.assertEqual(record.note, upload_workspace_audit.UploadWorkspaceAudit.DCC_WRITERS_FUTURE_CYCLE)

    def test_dcc_writers_shared_as_writer_can_compute(self):
        sharing = WorkspaceGroupSharingFactory.create(
            workspace=self.upload_workspace.workspace,
            group=self.dcc_writer_group,
            access=WorkspaceGroupSharing.WRITER,
            can_compute=True,
        )
        audit = upload_workspace_audit.UploadWorkspaceAudit()
        audit.audit_workspace_and_group(self.upload_workspace, self.dcc_writer_group)
        self.assertEqual(len(audit.verified), 1)
        self.assertEqual(len(audit.needs_action), 0)
        self.assertEqual(len(audit.errors), 0)
        record = audit.verified[0]
        self.assertIsInstance(record, upload_workspace_audit.VerifiedShared)
        self.assertEqual(record.workspace, self.upload_workspace)
        self.assertEqual(record.managed_group, self.dcc_writer_group)
        self.assertEqual(record.current_sharing_instance, sharing)
        self.assertEqual(record.note, upload_workspace_audit.UploadWorkspaceAudit.DCC_WRITERS_FUTURE_CYCLE)

    def test_dcc_writers_shared_as_reader(self):
        sharing = WorkspaceGroupSharingFactory.create(
            workspace=self.upload_workspace.workspace, group=self.dcc_writer_group, access=WorkspaceGroupSharing.READER
        )
        audit = upload_workspace_audit.UploadWorkspaceAudit()
        audit.audit_workspace_and_group(self.upload_workspace, self.dcc_writer_group)
        self.assertEqual(len(audit.verified), 0)
        self.assertEqual(len(audit.needs_action), 1)
        self.assertEqual(len(audit.errors), 0)
        record = audit.needs_action[0]
        self.assertIsInstance(record, upload_workspace_audit.ShareWithCompute)
        self.assertEqual(record.workspace, self.upload_workspace)
        self.assertEqual(record.managed_group, self.dcc_writer_group)
        self.assertEqual(record.current_sharing_instance, sharing)
        self.assertEqual(record.note, upload_workspace_audit.UploadWorkspaceAudit.DCC_WRITERS_FUTURE_CYCLE)

    def test_dcc_writers_shared_as_owner(self):
        sharing = WorkspaceGroupSharingFactory.create(
            workspace=self.upload_workspace.workspace, group=self.dcc_writer_group, access=WorkspaceGroupSharing.OWNER
        )
        audit = upload_workspace_audit.UploadWorkspaceAudit()
        audit.audit_workspace_and_group(self.upload_workspace, self.dcc_writer_group)
        self.assertEqual(len(audit.verified), 0)
        self.assertEqual(len(audit.needs_action), 1)
        self.assertEqual(len(audit.errors), 0)
        record = audit.needs_action[0]
        self.assertIsInstance(record, upload_workspace_audit.ShareWithCompute)
        self.assertEqual(record.workspace, self.upload_workspace)
        self.assertEqual(record.managed_group, self.dcc_writer_group)
        self.assertEqual(record.current_sharing_instance, sharing)
        self.assertEqual(record.note, upload_workspace_audit.UploadWorkspaceAudit.DCC_WRITERS_FUTURE_CYCLE)

    def test_dcc_admin(self):
        pass

    def test_anvil_groups(self):
        pass

    def test_gregor_all(self):
        pass

    def test_unexpected_group(self):
        pass


class UploadWorkspaceAuditCurrentCycleBeforeComputeTest(TestCase):
    """Tests for the `UploadWorkspaceAudit` class for current cycle UploadWorkspaces before compute is enabled.

    Expectations at this point in the upload cycle:
    - RC uploader group should be writers without compute.
    - DCC writer group should be writers with compute.
    """

    def setUp(self):
        super().setUp()
        self.dcc_writer_group = ManagedGroupFactory.create(name="GREGOR_DCC_WRITERS")
        self.rc_uploader_group = ManagedGroupFactory.create()
        self.research_center = factories.ResearchCenterFactory.create(uploader_group=self.rc_uploader_group)
        self.upload_workspace = factories.UploadWorkspaceFactory.create(
            research_center=self.research_center,
            upload_cycle__is_current=True,
            upload_cycle__is_ready_for_compute=False,
        )

    def test_uploaders_shared_as_writer_no_compute(self):
        # Share the workspace with the group.
        sharing = WorkspaceGroupSharingFactory.create(
            workspace=self.upload_workspace.workspace, group=self.rc_uploader_group, access=WorkspaceGroupSharing.WRITER
        )
        audit = upload_workspace_audit.UploadWorkspaceAudit()
        audit.audit_workspace_and_group(self.upload_workspace, self.rc_uploader_group)
        self.assertEqual(len(audit.verified), 1)
        self.assertEqual(len(audit.needs_action), 0)
        self.assertEqual(len(audit.errors), 0)
        record = audit.verified[0]
        self.assertIsInstance(record, upload_workspace_audit.VerifiedShared)
        self.assertEqual(record.workspace, self.upload_workspace)
        self.assertEqual(record.managed_group, self.rc_uploader_group)
        self.assertEqual(record.current_sharing_instance, sharing)
        self.assertEqual(
            record.note, upload_workspace_audit.UploadWorkspaceAudit.RC_UPLOADERS_CURRENT_CYCLE_BEFORE_COMPUTE
        )

    def test_uploaders_not_shared(self):
        audit = upload_workspace_audit.UploadWorkspaceAudit()
        audit.audit_workspace_and_group(self.upload_workspace, self.rc_uploader_group)
        self.assertEqual(len(audit.verified), 0)
        self.assertEqual(len(audit.needs_action), 1)
        self.assertEqual(len(audit.errors), 0)
        record = audit.needs_action[0]
        self.assertIsInstance(record, upload_workspace_audit.ShareAsWriter)
        self.assertEqual(record.workspace, self.upload_workspace)
        self.assertEqual(record.managed_group, self.rc_uploader_group)
        self.assertEqual(record.current_sharing_instance, None)
        self.assertEqual(
            record.note, upload_workspace_audit.UploadWorkspaceAudit.RC_UPLOADERS_CURRENT_CYCLE_BEFORE_COMPUTE
        )

    def test_uploaders_shared_as_writer_can_compute(self):
        sharing = WorkspaceGroupSharingFactory.create(
            workspace=self.upload_workspace.workspace,
            group=self.rc_uploader_group,
            access=WorkspaceGroupSharing.WRITER,
            can_compute=True,
        )
        audit = upload_workspace_audit.UploadWorkspaceAudit()
        audit.audit_workspace_and_group(self.upload_workspace, self.rc_uploader_group)
        self.assertEqual(len(audit.verified), 0)
        self.assertEqual(len(audit.needs_action), 1)
        self.assertEqual(len(audit.errors), 0)
        record = audit.needs_action[0]
        self.assertIsInstance(record, upload_workspace_audit.ShareAsWriter)
        self.assertEqual(record.workspace, self.upload_workspace)
        self.assertEqual(record.managed_group, self.rc_uploader_group)
        self.assertEqual(record.current_sharing_instance, sharing)
        self.assertEqual(
            record.note, upload_workspace_audit.UploadWorkspaceAudit.RC_UPLOADERS_CURRENT_CYCLE_BEFORE_COMPUTE
        )

    def test_uploaders_shared_as_reader(self):
        sharing = WorkspaceGroupSharingFactory.create(
            workspace=self.upload_workspace.workspace, group=self.rc_uploader_group, access=WorkspaceGroupSharing.READER
        )
        audit = upload_workspace_audit.UploadWorkspaceAudit()
        audit.audit_workspace_and_group(self.upload_workspace, self.rc_uploader_group)
        self.assertEqual(len(audit.verified), 0)
        self.assertEqual(len(audit.needs_action), 1)
        self.assertEqual(len(audit.errors), 0)
        record = audit.needs_action[0]
        self.assertIsInstance(record, upload_workspace_audit.ShareAsWriter)
        self.assertEqual(record.workspace, self.upload_workspace)
        self.assertEqual(record.managed_group, self.rc_uploader_group)
        self.assertEqual(record.current_sharing_instance, sharing)
        self.assertEqual(
            record.note, upload_workspace_audit.UploadWorkspaceAudit.RC_UPLOADERS_CURRENT_CYCLE_BEFORE_COMPUTE
        )

    def test_uploaders_shared_as_owner(self):
        sharing = WorkspaceGroupSharingFactory.create(
            workspace=self.upload_workspace.workspace, group=self.rc_uploader_group, access=WorkspaceGroupSharing.OWNER
        )
        audit = upload_workspace_audit.UploadWorkspaceAudit()
        audit.audit_workspace_and_group(self.upload_workspace, self.rc_uploader_group)
        self.assertEqual(len(audit.verified), 0)
        self.assertEqual(len(audit.needs_action), 1)
        self.assertEqual(len(audit.errors), 0)
        record = audit.needs_action[0]
        self.assertIsInstance(record, upload_workspace_audit.ShareAsWriter)
        self.assertEqual(record.workspace, self.upload_workspace)
        self.assertEqual(record.managed_group, self.rc_uploader_group)
        self.assertEqual(record.current_sharing_instance, sharing)
        self.assertEqual(
            record.note, upload_workspace_audit.UploadWorkspaceAudit.RC_UPLOADERS_CURRENT_CYCLE_BEFORE_COMPUTE
        )

    def test_dcc_writers_shared_as_writer_no_compute(self):
        # Share the workspace with the group.
        sharing = WorkspaceGroupSharingFactory.create(
            workspace=self.upload_workspace.workspace, group=self.dcc_writer_group, access=WorkspaceGroupSharing.WRITER
        )
        audit = upload_workspace_audit.UploadWorkspaceAudit()
        audit.audit_workspace_and_group(self.upload_workspace, self.dcc_writer_group)
        self.assertEqual(len(audit.verified), 0)
        self.assertEqual(len(audit.needs_action), 1)
        self.assertEqual(len(audit.errors), 0)
        record = audit.needs_action[0]
        self.assertIsInstance(record, upload_workspace_audit.ShareWithCompute)
        self.assertEqual(record.workspace, self.upload_workspace)
        self.assertEqual(record.managed_group, self.dcc_writer_group)
        self.assertEqual(record.current_sharing_instance, sharing)
        self.assertEqual(record.note, upload_workspace_audit.UploadWorkspaceAudit.DCC_WRITERS_CURRENT_CYCLE)

    def test_dcc_writers_not_shared(self):
        audit = upload_workspace_audit.UploadWorkspaceAudit()
        audit.audit_workspace_and_group(self.upload_workspace, self.dcc_writer_group)
        self.assertEqual(len(audit.verified), 0)
        self.assertEqual(len(audit.needs_action), 1)
        self.assertEqual(len(audit.errors), 0)
        record = audit.needs_action[0]
        self.assertIsInstance(record, upload_workspace_audit.ShareWithCompute)
        self.assertEqual(record.workspace, self.upload_workspace)
        self.assertEqual(record.managed_group, self.dcc_writer_group)
        self.assertEqual(record.current_sharing_instance, None)
        self.assertEqual(record.note, upload_workspace_audit.UploadWorkspaceAudit.DCC_WRITERS_CURRENT_CYCLE)

    def test_dcc_writers_shared_as_writer_can_compute(self):
        sharing = WorkspaceGroupSharingFactory.create(
            workspace=self.upload_workspace.workspace,
            group=self.dcc_writer_group,
            access=WorkspaceGroupSharing.WRITER,
            can_compute=True,
        )
        audit = upload_workspace_audit.UploadWorkspaceAudit()
        audit.audit_workspace_and_group(self.upload_workspace, self.dcc_writer_group)
        self.assertEqual(len(audit.verified), 1)
        self.assertEqual(len(audit.needs_action), 0)
        self.assertEqual(len(audit.errors), 0)
        record = audit.verified[0]
        self.assertIsInstance(record, upload_workspace_audit.VerifiedShared)
        self.assertEqual(record.workspace, self.upload_workspace)
        self.assertEqual(record.managed_group, self.dcc_writer_group)
        self.assertEqual(record.current_sharing_instance, sharing)
        self.assertEqual(record.note, upload_workspace_audit.UploadWorkspaceAudit.DCC_WRITERS_CURRENT_CYCLE)

    def test_dcc_writers_shared_as_reader(self):
        sharing = WorkspaceGroupSharingFactory.create(
            workspace=self.upload_workspace.workspace, group=self.dcc_writer_group, access=WorkspaceGroupSharing.READER
        )
        audit = upload_workspace_audit.UploadWorkspaceAudit()
        audit.audit_workspace_and_group(self.upload_workspace, self.dcc_writer_group)
        self.assertEqual(len(audit.verified), 0)
        self.assertEqual(len(audit.needs_action), 1)
        self.assertEqual(len(audit.errors), 0)
        record = audit.needs_action[0]
        self.assertIsInstance(record, upload_workspace_audit.ShareWithCompute)
        self.assertEqual(record.workspace, self.upload_workspace)
        self.assertEqual(record.managed_group, self.dcc_writer_group)
        self.assertEqual(record.current_sharing_instance, sharing)
        self.assertEqual(record.note, upload_workspace_audit.UploadWorkspaceAudit.DCC_WRITERS_CURRENT_CYCLE)

    def test_dcc_writers_shared_as_owner(self):
        sharing = WorkspaceGroupSharingFactory.create(
            workspace=self.upload_workspace.workspace, group=self.dcc_writer_group, access=WorkspaceGroupSharing.OWNER
        )
        audit = upload_workspace_audit.UploadWorkspaceAudit()
        audit.audit_workspace_and_group(self.upload_workspace, self.dcc_writer_group)
        self.assertEqual(len(audit.verified), 0)
        self.assertEqual(len(audit.needs_action), 1)
        self.assertEqual(len(audit.errors), 0)
        record = audit.needs_action[0]
        self.assertIsInstance(record, upload_workspace_audit.ShareWithCompute)
        self.assertEqual(record.workspace, self.upload_workspace)
        self.assertEqual(record.managed_group, self.dcc_writer_group)
        self.assertEqual(record.current_sharing_instance, sharing)
        self.assertEqual(record.note, upload_workspace_audit.UploadWorkspaceAudit.DCC_WRITERS_CURRENT_CYCLE)


class UploadWorkspaceAuditCurrentCycleAfterComputeTest(TestCase):
    """Tests for the `UploadWorkspaceAudit` class for current cycle UploadWorkspaces after compute is enabled.

    Expectations at this point in the upload cycle:
    - RC uploader group should be writers with compute.
    - DCC writer group should be writers with compute.
    """

    def setUp(self):
        super().setUp()
        self.dcc_writer_group = ManagedGroupFactory.create(name="GREGOR_DCC_WRITERS")
        self.rc_uploader_group = ManagedGroupFactory.create()
        self.research_center = factories.ResearchCenterFactory.create(uploader_group=self.rc_uploader_group)
        self.upload_workspace = factories.UploadWorkspaceFactory.create(
            research_center=self.research_center, upload_cycle__is_current=True, upload_cycle__is_ready_for_compute=True
        )

    def test_uploaders_shared_as_writer_no_compute(self):
        # Share the workspace with the group.
        sharing = WorkspaceGroupSharingFactory.create(
            workspace=self.upload_workspace.workspace, group=self.rc_uploader_group, access=WorkspaceGroupSharing.WRITER
        )
        audit = upload_workspace_audit.UploadWorkspaceAudit()
        audit.audit_workspace_and_group(self.upload_workspace, self.rc_uploader_group)
        self.assertEqual(len(audit.verified), 0)
        self.assertEqual(len(audit.needs_action), 1)
        self.assertEqual(len(audit.errors), 0)
        record = audit.needs_action[0]
        self.assertIsInstance(record, upload_workspace_audit.ShareWithCompute)
        self.assertEqual(record.workspace, self.upload_workspace)
        self.assertEqual(record.managed_group, self.rc_uploader_group)
        self.assertEqual(record.current_sharing_instance, sharing)
        self.assertEqual(
            record.note, upload_workspace_audit.UploadWorkspaceAudit.RC_UPLOADERS_CURRENT_CYCLE_AFTER_COMPUTE
        )

    def test_uploaders_not_shared(self):
        audit = upload_workspace_audit.UploadWorkspaceAudit()
        audit.audit_workspace_and_group(self.upload_workspace, self.rc_uploader_group)
        self.assertEqual(len(audit.verified), 0)
        self.assertEqual(len(audit.needs_action), 1)
        self.assertEqual(len(audit.errors), 0)
        record = audit.needs_action[0]
        self.assertIsInstance(record, upload_workspace_audit.ShareWithCompute)
        self.assertEqual(record.workspace, self.upload_workspace)
        self.assertEqual(record.managed_group, self.rc_uploader_group)
        self.assertEqual(record.current_sharing_instance, None)
        self.assertEqual(
            record.note, upload_workspace_audit.UploadWorkspaceAudit.RC_UPLOADERS_CURRENT_CYCLE_AFTER_COMPUTE
        )

    def test_uploaders_shared_as_writer_can_compute(self):
        sharing = WorkspaceGroupSharingFactory.create(
            workspace=self.upload_workspace.workspace,
            group=self.rc_uploader_group,
            access=WorkspaceGroupSharing.WRITER,
            can_compute=True,
        )
        audit = upload_workspace_audit.UploadWorkspaceAudit()
        audit.audit_workspace_and_group(self.upload_workspace, self.rc_uploader_group)
        self.assertEqual(len(audit.verified), 1)
        self.assertEqual(len(audit.needs_action), 0)
        self.assertEqual(len(audit.errors), 0)
        record = audit.verified[0]
        self.assertIsInstance(record, upload_workspace_audit.VerifiedShared)
        self.assertEqual(record.workspace, self.upload_workspace)
        self.assertEqual(record.managed_group, self.rc_uploader_group)
        self.assertEqual(record.current_sharing_instance, sharing)
        self.assertEqual(
            record.note, upload_workspace_audit.UploadWorkspaceAudit.RC_UPLOADERS_CURRENT_CYCLE_AFTER_COMPUTE
        )

    def test_uploaders_shared_as_reader(self):
        sharing = WorkspaceGroupSharingFactory.create(
            workspace=self.upload_workspace.workspace, group=self.rc_uploader_group, access=WorkspaceGroupSharing.READER
        )
        audit = upload_workspace_audit.UploadWorkspaceAudit()
        audit.audit_workspace_and_group(self.upload_workspace, self.rc_uploader_group)
        self.assertEqual(len(audit.verified), 0)
        self.assertEqual(len(audit.needs_action), 1)
        self.assertEqual(len(audit.errors), 0)
        record = audit.needs_action[0]
        self.assertIsInstance(record, upload_workspace_audit.ShareWithCompute)
        self.assertEqual(record.workspace, self.upload_workspace)
        self.assertEqual(record.managed_group, self.rc_uploader_group)
        self.assertEqual(record.current_sharing_instance, sharing)
        self.assertEqual(
            record.note, upload_workspace_audit.UploadWorkspaceAudit.RC_UPLOADERS_CURRENT_CYCLE_AFTER_COMPUTE
        )

    def test_uploaders_shared_as_owner(self):
        sharing = WorkspaceGroupSharingFactory.create(
            workspace=self.upload_workspace.workspace, group=self.rc_uploader_group, access=WorkspaceGroupSharing.OWNER
        )
        audit = upload_workspace_audit.UploadWorkspaceAudit()
        audit.audit_workspace_and_group(self.upload_workspace, self.rc_uploader_group)
        self.assertEqual(len(audit.verified), 0)
        self.assertEqual(len(audit.needs_action), 1)
        self.assertEqual(len(audit.errors), 0)
        record = audit.needs_action[0]
        self.assertIsInstance(record, upload_workspace_audit.ShareWithCompute)
        self.assertEqual(record.workspace, self.upload_workspace)
        self.assertEqual(record.managed_group, self.rc_uploader_group)
        self.assertEqual(record.current_sharing_instance, sharing)
        self.assertEqual(
            record.note, upload_workspace_audit.UploadWorkspaceAudit.RC_UPLOADERS_CURRENT_CYCLE_AFTER_COMPUTE
        )

    def test_dcc_writers_shared_as_writer_no_compute(self):
        # Share the workspace with the group.
        sharing = WorkspaceGroupSharingFactory.create(
            workspace=self.upload_workspace.workspace, group=self.dcc_writer_group, access=WorkspaceGroupSharing.WRITER
        )
        audit = upload_workspace_audit.UploadWorkspaceAudit()
        audit.audit_workspace_and_group(self.upload_workspace, self.dcc_writer_group)
        self.assertEqual(len(audit.verified), 0)
        self.assertEqual(len(audit.needs_action), 1)
        self.assertEqual(len(audit.errors), 0)
        record = audit.needs_action[0]
        self.assertIsInstance(record, upload_workspace_audit.ShareWithCompute)
        self.assertEqual(record.workspace, self.upload_workspace)
        self.assertEqual(record.managed_group, self.dcc_writer_group)
        self.assertEqual(record.current_sharing_instance, sharing)
        self.assertEqual(record.note, upload_workspace_audit.UploadWorkspaceAudit.DCC_WRITERS_CURRENT_CYCLE)

    def test_dcc_writers_not_shared(self):
        audit = upload_workspace_audit.UploadWorkspaceAudit()
        audit.audit_workspace_and_group(self.upload_workspace, self.dcc_writer_group)
        self.assertEqual(len(audit.verified), 0)
        self.assertEqual(len(audit.needs_action), 1)
        self.assertEqual(len(audit.errors), 0)
        record = audit.needs_action[0]
        self.assertIsInstance(record, upload_workspace_audit.ShareWithCompute)
        self.assertEqual(record.workspace, self.upload_workspace)
        self.assertEqual(record.managed_group, self.dcc_writer_group)
        self.assertEqual(record.current_sharing_instance, None)
        self.assertEqual(record.note, upload_workspace_audit.UploadWorkspaceAudit.DCC_WRITERS_CURRENT_CYCLE)

    def test_dcc_writers_shared_as_writer_can_compute(self):
        sharing = WorkspaceGroupSharingFactory.create(
            workspace=self.upload_workspace.workspace,
            group=self.dcc_writer_group,
            access=WorkspaceGroupSharing.WRITER,
            can_compute=True,
        )
        audit = upload_workspace_audit.UploadWorkspaceAudit()
        audit.audit_workspace_and_group(self.upload_workspace, self.dcc_writer_group)
        self.assertEqual(len(audit.verified), 1)
        self.assertEqual(len(audit.needs_action), 0)
        self.assertEqual(len(audit.errors), 0)
        record = audit.verified[0]
        self.assertIsInstance(record, upload_workspace_audit.VerifiedShared)
        self.assertEqual(record.workspace, self.upload_workspace)
        self.assertEqual(record.managed_group, self.dcc_writer_group)
        self.assertEqual(record.current_sharing_instance, sharing)
        self.assertEqual(record.note, upload_workspace_audit.UploadWorkspaceAudit.DCC_WRITERS_CURRENT_CYCLE)

    def test_dcc_writers_shared_as_reader(self):
        sharing = WorkspaceGroupSharingFactory.create(
            workspace=self.upload_workspace.workspace, group=self.dcc_writer_group, access=WorkspaceGroupSharing.READER
        )
        audit = upload_workspace_audit.UploadWorkspaceAudit()
        audit.audit_workspace_and_group(self.upload_workspace, self.dcc_writer_group)
        self.assertEqual(len(audit.verified), 0)
        self.assertEqual(len(audit.needs_action), 1)
        self.assertEqual(len(audit.errors), 0)
        record = audit.needs_action[0]
        self.assertIsInstance(record, upload_workspace_audit.ShareWithCompute)
        self.assertEqual(record.workspace, self.upload_workspace)
        self.assertEqual(record.managed_group, self.dcc_writer_group)
        self.assertEqual(record.current_sharing_instance, sharing)
        self.assertEqual(record.note, upload_workspace_audit.UploadWorkspaceAudit.DCC_WRITERS_CURRENT_CYCLE)

    def test_dcc_writers_shared_as_owner(self):
        sharing = WorkspaceGroupSharingFactory.create(
            workspace=self.upload_workspace.workspace, group=self.dcc_writer_group, access=WorkspaceGroupSharing.OWNER
        )
        audit = upload_workspace_audit.UploadWorkspaceAudit()
        audit.audit_workspace_and_group(self.upload_workspace, self.dcc_writer_group)
        self.assertEqual(len(audit.verified), 0)
        self.assertEqual(len(audit.needs_action), 1)
        self.assertEqual(len(audit.errors), 0)
        record = audit.needs_action[0]
        self.assertIsInstance(record, upload_workspace_audit.ShareWithCompute)
        self.assertEqual(record.workspace, self.upload_workspace)
        self.assertEqual(record.managed_group, self.dcc_writer_group)
        self.assertEqual(record.current_sharing_instance, sharing)
        self.assertEqual(record.note, upload_workspace_audit.UploadWorkspaceAudit.DCC_WRITERS_CURRENT_CYCLE)

    def test_other_groups(self):
        pass


class UploadWorkspaceAuditPastCycleBeforeQCCompleteTest(TestCase):
    """Tests for the `UploadWorkspaceAudit` class for past cycles before QC is complete.

    Expectations at this point in the upload cycle:
    - RC uploader group should be readers.
    - DCC writer group should not have direct access.
    """

    def setUp(self):
        super().setUp()
        self.dcc_writer_group = ManagedGroupFactory.create(name="GREGOR_DCC_WRITERS")
        self.rc_uploader_group = ManagedGroupFactory.create()
        self.research_center = factories.ResearchCenterFactory.create(uploader_group=self.rc_uploader_group)
        self.upload_workspace = factories.UploadWorkspaceFactory.create(
            research_center=self.research_center,
            upload_cycle__is_past=True,
        )

    def test_uploaders_shared_as_writer_no_compute(self):
        # Share the workspace with the group.
        sharing = WorkspaceGroupSharingFactory.create(
            workspace=self.upload_workspace.workspace, group=self.rc_uploader_group, access=WorkspaceGroupSharing.WRITER
        )
        audit = upload_workspace_audit.UploadWorkspaceAudit()
        audit.audit_workspace_and_group(self.upload_workspace, self.rc_uploader_group)
        self.assertEqual(len(audit.verified), 0)
        self.assertEqual(len(audit.needs_action), 1)
        self.assertEqual(len(audit.errors), 0)
        record = audit.needs_action[0]
        self.assertIsInstance(record, upload_workspace_audit.ShareAsReader)
        self.assertEqual(record.workspace, self.upload_workspace)
        self.assertEqual(record.managed_group, self.rc_uploader_group)
        self.assertEqual(record.current_sharing_instance, sharing)
        self.assertEqual(
            record.note, upload_workspace_audit.UploadWorkspaceAudit.RC_UPLOADERS_PAST_CYCLE_BEFORE_QC_COMPLETE
        )

    def test_uploaders_not_shared(self):
        audit = upload_workspace_audit.UploadWorkspaceAudit()
        audit.audit_workspace_and_group(self.upload_workspace, self.rc_uploader_group)
        self.assertEqual(len(audit.verified), 0)
        self.assertEqual(len(audit.needs_action), 1)
        self.assertEqual(len(audit.errors), 0)
        record = audit.needs_action[0]
        self.assertIsInstance(record, upload_workspace_audit.ShareAsReader)
        self.assertEqual(record.workspace, self.upload_workspace)
        self.assertEqual(record.managed_group, self.rc_uploader_group)
        self.assertEqual(record.current_sharing_instance, None)
        self.assertEqual(
            record.note, upload_workspace_audit.UploadWorkspaceAudit.RC_UPLOADERS_PAST_CYCLE_BEFORE_QC_COMPLETE
        )

    def test_uploaders_shared_as_writer_can_compute(self):
        sharing = WorkspaceGroupSharingFactory.create(
            workspace=self.upload_workspace.workspace,
            group=self.rc_uploader_group,
            access=WorkspaceGroupSharing.WRITER,
            can_compute=True,
        )
        audit = upload_workspace_audit.UploadWorkspaceAudit()
        audit.audit_workspace_and_group(self.upload_workspace, self.rc_uploader_group)
        self.assertEqual(len(audit.verified), 0)
        self.assertEqual(len(audit.needs_action), 1)
        self.assertEqual(len(audit.errors), 0)
        record = audit.needs_action[0]
        self.assertIsInstance(record, upload_workspace_audit.ShareAsReader)
        self.assertEqual(record.workspace, self.upload_workspace)
        self.assertEqual(record.managed_group, self.rc_uploader_group)
        self.assertEqual(record.current_sharing_instance, sharing)
        self.assertEqual(
            record.note, upload_workspace_audit.UploadWorkspaceAudit.RC_UPLOADERS_PAST_CYCLE_BEFORE_QC_COMPLETE
        )

    def test_uploaders_shared_as_reader(self):
        sharing = WorkspaceGroupSharingFactory.create(
            workspace=self.upload_workspace.workspace, group=self.rc_uploader_group, access=WorkspaceGroupSharing.READER
        )
        audit = upload_workspace_audit.UploadWorkspaceAudit()
        audit.audit_workspace_and_group(self.upload_workspace, self.rc_uploader_group)
        self.assertEqual(len(audit.verified), 1)
        self.assertEqual(len(audit.needs_action), 0)
        self.assertEqual(len(audit.errors), 0)
        record = audit.verified[0]
        self.assertIsInstance(record, upload_workspace_audit.VerifiedShared)
        self.assertEqual(record.workspace, self.upload_workspace)
        self.assertEqual(record.managed_group, self.rc_uploader_group)
        self.assertEqual(record.current_sharing_instance, sharing)
        self.assertEqual(
            record.note, upload_workspace_audit.UploadWorkspaceAudit.RC_UPLOADERS_PAST_CYCLE_BEFORE_QC_COMPLETE
        )

    def test_uploaders_shared_as_owner(self):
        sharing = WorkspaceGroupSharingFactory.create(
            workspace=self.upload_workspace.workspace, group=self.rc_uploader_group, access=WorkspaceGroupSharing.OWNER
        )
        audit = upload_workspace_audit.UploadWorkspaceAudit()
        audit.audit_workspace_and_group(self.upload_workspace, self.rc_uploader_group)
        self.assertEqual(len(audit.verified), 0)
        self.assertEqual(len(audit.needs_action), 1)
        self.assertEqual(len(audit.errors), 0)
        record = audit.needs_action[0]
        self.assertIsInstance(record, upload_workspace_audit.ShareAsReader)
        self.assertEqual(record.workspace, self.upload_workspace)
        self.assertEqual(record.managed_group, self.rc_uploader_group)
        self.assertEqual(record.current_sharing_instance, sharing)
        self.assertEqual(
            record.note, upload_workspace_audit.UploadWorkspaceAudit.RC_UPLOADERS_PAST_CYCLE_BEFORE_QC_COMPLETE
        )

    def test_dcc_writers_shared_as_writer_no_compute(self):
        # Share the workspace with the group.
        sharing = WorkspaceGroupSharingFactory.create(
            workspace=self.upload_workspace.workspace, group=self.dcc_writer_group, access=WorkspaceGroupSharing.WRITER
        )
        audit = upload_workspace_audit.UploadWorkspaceAudit()
        audit.audit_workspace_and_group(self.upload_workspace, self.dcc_writer_group)
        self.assertEqual(len(audit.verified), 0)
        self.assertEqual(len(audit.needs_action), 1)
        self.assertEqual(len(audit.errors), 0)
        record = audit.needs_action[0]
        self.assertIsInstance(record, upload_workspace_audit.ShareWithCompute)
        self.assertEqual(record.workspace, self.upload_workspace)
        self.assertEqual(record.managed_group, self.dcc_writer_group)
        self.assertEqual(record.current_sharing_instance, sharing)
        self.assertEqual(
            record.note, upload_workspace_audit.UploadWorkspaceAudit.DCC_WRITERS_PAST_CYCLE_BEFORE_QC_COMPLETE
        )

    def test_dcc_writers_not_shared(self):
        audit = upload_workspace_audit.UploadWorkspaceAudit()
        audit.audit_workspace_and_group(self.upload_workspace, self.dcc_writer_group)
        self.assertEqual(len(audit.verified), 0)
        self.assertEqual(len(audit.needs_action), 1)
        self.assertEqual(len(audit.errors), 0)
        record = audit.needs_action[0]
        self.assertIsInstance(record, upload_workspace_audit.ShareWithCompute)
        self.assertEqual(record.workspace, self.upload_workspace)
        self.assertEqual(record.managed_group, self.dcc_writer_group)
        self.assertEqual(record.current_sharing_instance, None)
        self.assertEqual(
            record.note, upload_workspace_audit.UploadWorkspaceAudit.DCC_WRITERS_PAST_CYCLE_BEFORE_QC_COMPLETE
        )

    def test_dcc_writers_shared_as_writer_can_compute(self):
        sharing = WorkspaceGroupSharingFactory.create(
            workspace=self.upload_workspace.workspace,
            group=self.dcc_writer_group,
            access=WorkspaceGroupSharing.WRITER,
            can_compute=True,
        )
        audit = upload_workspace_audit.UploadWorkspaceAudit()
        audit.audit_workspace_and_group(self.upload_workspace, self.dcc_writer_group)
        self.assertEqual(len(audit.verified), 1)
        self.assertEqual(len(audit.needs_action), 0)
        self.assertEqual(len(audit.errors), 0)
        record = audit.verified[0]
        self.assertIsInstance(record, upload_workspace_audit.VerifiedShared)
        self.assertEqual(record.workspace, self.upload_workspace)
        self.assertEqual(record.managed_group, self.dcc_writer_group)
        self.assertEqual(record.current_sharing_instance, sharing)
        self.assertEqual(
            record.note, upload_workspace_audit.UploadWorkspaceAudit.DCC_WRITERS_PAST_CYCLE_BEFORE_QC_COMPLETE
        )

    def test_dcc_writers_shared_as_reader(self):
        sharing = WorkspaceGroupSharingFactory.create(
            workspace=self.upload_workspace.workspace, group=self.dcc_writer_group, access=WorkspaceGroupSharing.READER
        )
        audit = upload_workspace_audit.UploadWorkspaceAudit()
        audit.audit_workspace_and_group(self.upload_workspace, self.dcc_writer_group)
        self.assertEqual(len(audit.verified), 0)
        self.assertEqual(len(audit.needs_action), 1)
        self.assertEqual(len(audit.errors), 0)
        record = audit.needs_action[0]
        self.assertIsInstance(record, upload_workspace_audit.ShareWithCompute)
        self.assertEqual(record.workspace, self.upload_workspace)
        self.assertEqual(record.managed_group, self.dcc_writer_group)
        self.assertEqual(record.current_sharing_instance, sharing)
        self.assertEqual(
            record.note, upload_workspace_audit.UploadWorkspaceAudit.DCC_WRITERS_PAST_CYCLE_BEFORE_QC_COMPLETE
        )

    def test_dcc_writers_shared_as_owner(self):
        sharing = WorkspaceGroupSharingFactory.create(
            workspace=self.upload_workspace.workspace, group=self.dcc_writer_group, access=WorkspaceGroupSharing.OWNER
        )
        audit = upload_workspace_audit.UploadWorkspaceAudit()
        audit.audit_workspace_and_group(self.upload_workspace, self.dcc_writer_group)
        self.assertEqual(len(audit.verified), 0)
        self.assertEqual(len(audit.needs_action), 1)
        self.assertEqual(len(audit.errors), 0)
        record = audit.needs_action[0]
        self.assertIsInstance(record, upload_workspace_audit.ShareWithCompute)
        self.assertEqual(record.workspace, self.upload_workspace)
        self.assertEqual(record.managed_group, self.dcc_writer_group)
        self.assertEqual(record.current_sharing_instance, sharing)
        self.assertEqual(
            record.note, upload_workspace_audit.UploadWorkspaceAudit.DCC_WRITERS_PAST_CYCLE_BEFORE_QC_COMPLETE
        )

    def test_other_groups(self):
        pass


class UploadWorkspaceAuditPastCycleAfterQCCompleteTest(TestCase):
    """Tests for the `UploadWorkspaceAudit` class for past cycles before QC is complete.

    Expectations at this point in the upload cycle:
    - RC uploader group should not have direct access.
    - DCC writer group should not have direct access.
    """

    def setUp(self):
        super().setUp()
        self.dcc_writer_group = ManagedGroupFactory.create(name="GREGOR_DCC_WRITERS")
        self.rc_uploader_group = ManagedGroupFactory.create()
        self.research_center = factories.ResearchCenterFactory.create(uploader_group=self.rc_uploader_group)
        self.upload_workspace = factories.UploadWorkspaceFactory.create(
            research_center=self.research_center,
            upload_cycle__is_past=True,
            date_qc_completed=fake.date_time_this_year(
                before_now=True, after_now=False, tzinfo=timezone.get_current_timezone()
            ),
        )

    def test_uploaders_shared_as_writer_no_compute(self):
        # Share the workspace with the group.
        sharing = WorkspaceGroupSharingFactory.create(
            workspace=self.upload_workspace.workspace, group=self.rc_uploader_group, access=WorkspaceGroupSharing.WRITER
        )
        audit = upload_workspace_audit.UploadWorkspaceAudit()
        audit.audit_workspace_and_group(self.upload_workspace, self.rc_uploader_group)
        self.assertEqual(len(audit.verified), 0)
        self.assertEqual(len(audit.needs_action), 1)
        self.assertEqual(len(audit.errors), 0)
        record = audit.needs_action[0]
        self.assertIsInstance(record, upload_workspace_audit.StopSharing)
        self.assertEqual(record.workspace, self.upload_workspace)
        self.assertEqual(record.managed_group, self.rc_uploader_group)
        self.assertEqual(record.current_sharing_instance, sharing)
        self.assertEqual(
            record.note, upload_workspace_audit.UploadWorkspaceAudit.RC_UPLOADERS_PAST_CYCLE_AFTER_QC_COMPLETE
        )

    def test_uploaders_not_shared(self):
        audit = upload_workspace_audit.UploadWorkspaceAudit()
        audit.audit_workspace_and_group(self.upload_workspace, self.rc_uploader_group)
        self.assertEqual(len(audit.verified), 1)
        self.assertEqual(len(audit.needs_action), 0)
        self.assertEqual(len(audit.errors), 0)
        record = audit.verified[0]
        self.assertIsInstance(record, upload_workspace_audit.VerifiedNotShared)
        self.assertEqual(record.workspace, self.upload_workspace)
        self.assertEqual(record.managed_group, self.rc_uploader_group)
        self.assertEqual(record.current_sharing_instance, None)
        self.assertEqual(
            record.note, upload_workspace_audit.UploadWorkspaceAudit.RC_UPLOADERS_PAST_CYCLE_AFTER_QC_COMPLETE
        )

    def test_uploaders_shared_as_writer_can_compute(self):
        sharing = WorkspaceGroupSharingFactory.create(
            workspace=self.upload_workspace.workspace,
            group=self.rc_uploader_group,
            access=WorkspaceGroupSharing.WRITER,
            can_compute=True,
        )
        audit = upload_workspace_audit.UploadWorkspaceAudit()
        audit.audit_workspace_and_group(self.upload_workspace, self.rc_uploader_group)
        self.assertEqual(len(audit.verified), 0)
        self.assertEqual(len(audit.needs_action), 1)
        self.assertEqual(len(audit.errors), 0)
        record = audit.needs_action[0]
        self.assertIsInstance(record, upload_workspace_audit.StopSharing)
        self.assertEqual(record.workspace, self.upload_workspace)
        self.assertEqual(record.managed_group, self.rc_uploader_group)
        self.assertEqual(record.current_sharing_instance, sharing)
        self.assertEqual(
            record.note, upload_workspace_audit.UploadWorkspaceAudit.RC_UPLOADERS_PAST_CYCLE_AFTER_QC_COMPLETE
        )

    def test_uploaders_shared_as_reader(self):
        sharing = WorkspaceGroupSharingFactory.create(
            workspace=self.upload_workspace.workspace, group=self.rc_uploader_group, access=WorkspaceGroupSharing.READER
        )
        audit = upload_workspace_audit.UploadWorkspaceAudit()
        audit.audit_workspace_and_group(self.upload_workspace, self.rc_uploader_group)
        self.assertEqual(len(audit.verified), 0)
        self.assertEqual(len(audit.needs_action), 1)
        self.assertEqual(len(audit.errors), 0)
        record = audit.needs_action[0]
        self.assertIsInstance(record, upload_workspace_audit.StopSharing)
        self.assertEqual(record.workspace, self.upload_workspace)
        self.assertEqual(record.managed_group, self.rc_uploader_group)
        self.assertEqual(record.current_sharing_instance, sharing)
        self.assertEqual(
            record.note, upload_workspace_audit.UploadWorkspaceAudit.RC_UPLOADERS_PAST_CYCLE_AFTER_QC_COMPLETE
        )

    def test_uploaders_shared_as_owner(self):
        sharing = WorkspaceGroupSharingFactory.create(
            workspace=self.upload_workspace.workspace, group=self.rc_uploader_group, access=WorkspaceGroupSharing.OWNER
        )
        audit = upload_workspace_audit.UploadWorkspaceAudit()
        audit.audit_workspace_and_group(self.upload_workspace, self.rc_uploader_group)
        self.assertEqual(len(audit.verified), 0)
        self.assertEqual(len(audit.needs_action), 1)
        self.assertEqual(len(audit.errors), 0)
        record = audit.needs_action[0]
        self.assertIsInstance(record, upload_workspace_audit.StopSharing)
        self.assertEqual(record.workspace, self.upload_workspace)
        self.assertEqual(record.managed_group, self.rc_uploader_group)
        self.assertEqual(record.current_sharing_instance, sharing)
        self.assertEqual(
            record.note, upload_workspace_audit.UploadWorkspaceAudit.RC_UPLOADERS_PAST_CYCLE_AFTER_QC_COMPLETE
        )

    def test_dcc_writers_shared_as_writer_no_compute(self):
        # Share the workspace with the group.
        sharing = WorkspaceGroupSharingFactory.create(
            workspace=self.upload_workspace.workspace, group=self.dcc_writer_group, access=WorkspaceGroupSharing.WRITER
        )
        audit = upload_workspace_audit.UploadWorkspaceAudit()
        audit.audit_workspace_and_group(self.upload_workspace, self.dcc_writer_group)
        self.assertEqual(len(audit.verified), 0)
        self.assertEqual(len(audit.needs_action), 1)
        self.assertEqual(len(audit.errors), 0)
        record = audit.needs_action[0]
        self.assertIsInstance(record, upload_workspace_audit.StopSharing)
        self.assertEqual(record.workspace, self.upload_workspace)
        self.assertEqual(record.managed_group, self.dcc_writer_group)
        self.assertEqual(record.current_sharing_instance, sharing)
        self.assertEqual(
            record.note, upload_workspace_audit.UploadWorkspaceAudit.DCC_WRITERS_PAST_CYCLE_AFTER_QC_COMPLETE
        )

    def test_dcc_writers_not_shared(self):
        audit = upload_workspace_audit.UploadWorkspaceAudit()
        audit.audit_workspace_and_group(self.upload_workspace, self.dcc_writer_group)
        self.assertEqual(len(audit.verified), 1)
        self.assertEqual(len(audit.needs_action), 0)
        self.assertEqual(len(audit.errors), 0)
        record = audit.verified[0]
        self.assertIsInstance(record, upload_workspace_audit.VerifiedNotShared)
        self.assertEqual(record.workspace, self.upload_workspace)
        self.assertEqual(record.managed_group, self.dcc_writer_group)
        self.assertEqual(record.current_sharing_instance, None)
        self.assertEqual(
            record.note, upload_workspace_audit.UploadWorkspaceAudit.DCC_WRITERS_PAST_CYCLE_AFTER_QC_COMPLETE
        )

    def test_dcc_writers_shared_as_writer_can_compute(self):
        sharing = WorkspaceGroupSharingFactory.create(
            workspace=self.upload_workspace.workspace,
            group=self.dcc_writer_group,
            access=WorkspaceGroupSharing.WRITER,
            can_compute=True,
        )
        audit = upload_workspace_audit.UploadWorkspaceAudit()
        audit.audit_workspace_and_group(self.upload_workspace, self.dcc_writer_group)
        self.assertEqual(len(audit.verified), 0)
        self.assertEqual(len(audit.needs_action), 1)
        self.assertEqual(len(audit.errors), 0)
        record = audit.needs_action[0]
        self.assertIsInstance(record, upload_workspace_audit.StopSharing)
        self.assertEqual(record.workspace, self.upload_workspace)
        self.assertEqual(record.managed_group, self.dcc_writer_group)
        self.assertEqual(record.current_sharing_instance, sharing)
        self.assertEqual(
            record.note, upload_workspace_audit.UploadWorkspaceAudit.DCC_WRITERS_PAST_CYCLE_AFTER_QC_COMPLETE
        )

    def test_dcc_writers_shared_as_reader(self):
        sharing = WorkspaceGroupSharingFactory.create(
            workspace=self.upload_workspace.workspace, group=self.dcc_writer_group, access=WorkspaceGroupSharing.READER
        )
        audit = upload_workspace_audit.UploadWorkspaceAudit()
        audit.audit_workspace_and_group(self.upload_workspace, self.dcc_writer_group)
        self.assertEqual(len(audit.verified), 0)
        self.assertEqual(len(audit.needs_action), 1)
        self.assertEqual(len(audit.errors), 0)
        record = audit.needs_action[0]
        self.assertIsInstance(record, upload_workspace_audit.StopSharing)
        self.assertEqual(record.workspace, self.upload_workspace)
        self.assertEqual(record.managed_group, self.dcc_writer_group)
        self.assertEqual(record.current_sharing_instance, sharing)
        self.assertEqual(
            record.note, upload_workspace_audit.UploadWorkspaceAudit.DCC_WRITERS_PAST_CYCLE_AFTER_QC_COMPLETE
        )

    def test_dcc_writers_shared_as_owner(self):
        sharing = WorkspaceGroupSharingFactory.create(
            workspace=self.upload_workspace.workspace, group=self.dcc_writer_group, access=WorkspaceGroupSharing.OWNER
        )
        audit = upload_workspace_audit.UploadWorkspaceAudit()
        audit.audit_workspace_and_group(self.upload_workspace, self.dcc_writer_group)
        self.assertEqual(len(audit.verified), 0)
        self.assertEqual(len(audit.needs_action), 1)
        self.assertEqual(len(audit.errors), 0)
        record = audit.needs_action[0]
        self.assertIsInstance(record, upload_workspace_audit.StopSharing)
        self.assertEqual(record.workspace, self.upload_workspace)
        self.assertEqual(record.managed_group, self.dcc_writer_group)
        self.assertEqual(record.current_sharing_instance, sharing)
        self.assertEqual(
            record.note, upload_workspace_audit.UploadWorkspaceAudit.DCC_WRITERS_PAST_CYCLE_AFTER_QC_COMPLETE
        )

    def test_other_groups(self):
        pass


class UploadWorkspaceAuditPastCycleAfterCombinedWorkspaceSharedTest(TestCase):
    """Tests for the `UploadWorkspaceAudit` class for past cycles after the combined workspace is ready to share.

    Expectations at this point in the upload cycle:
    - RC uploader group should not have direct access.
    - DCC writer group should not have direct access.
    """

    def setUp(self):
        super().setUp()
        self.dcc_writer_group = ManagedGroupFactory.create(name="GREGOR_DCC_WRITERS")
        self.rc_uploader_group = ManagedGroupFactory.create()
        self.research_center = factories.ResearchCenterFactory.create(uploader_group=self.rc_uploader_group)
        self.upload_workspace = factories.UploadWorkspaceFactory.create(
            research_center=self.research_center,
            upload_cycle__is_past=True,
            date_qc_completed=fake.date_time_this_year(
                before_now=True, after_now=False, tzinfo=timezone.get_current_timezone()
            ),
        )
        # Create a corresponding combined workspace.
        self.combined_workspace = factories.CombinedConsortiumDataWorkspaceFactory.create(
            upload_cycle=self.upload_workspace.upload_cycle,
            date_completed=fake.date_time_this_year(
                before_now=True, after_now=False, tzinfo=timezone.get_current_timezone()
            ),
        )

    def test_uploaders_shared_as_writer_no_compute(self):
        # Share the workspace with the group.
        sharing = WorkspaceGroupSharingFactory.create(
            workspace=self.upload_workspace.workspace, group=self.rc_uploader_group, access=WorkspaceGroupSharing.WRITER
        )
        audit = upload_workspace_audit.UploadWorkspaceAudit()
        audit.audit_workspace_and_group(self.upload_workspace, self.rc_uploader_group)
        self.assertEqual(len(audit.verified), 0)
        self.assertEqual(len(audit.needs_action), 1)
        self.assertEqual(len(audit.errors), 0)
        record = audit.needs_action[0]
        self.assertIsInstance(record, upload_workspace_audit.StopSharing)
        self.assertEqual(record.workspace, self.upload_workspace)
        self.assertEqual(record.managed_group, self.rc_uploader_group)
        self.assertEqual(record.current_sharing_instance, sharing)
        self.assertEqual(
            record.note, upload_workspace_audit.UploadWorkspaceAudit.RC_UPLOADERS_PAST_CYCLE_COMBINED_WORKSPACE_READY
        )

    def test_uploaders_not_shared(self):
        audit = upload_workspace_audit.UploadWorkspaceAudit()
        audit.audit_workspace_and_group(self.upload_workspace, self.rc_uploader_group)
        self.assertEqual(len(audit.verified), 1)
        self.assertEqual(len(audit.needs_action), 0)
        self.assertEqual(len(audit.errors), 0)
        record = audit.verified[0]
        self.assertIsInstance(record, upload_workspace_audit.VerifiedNotShared)
        self.assertEqual(record.workspace, self.upload_workspace)
        self.assertEqual(record.managed_group, self.rc_uploader_group)
        self.assertEqual(record.current_sharing_instance, None)
        self.assertEqual(
            record.note, upload_workspace_audit.UploadWorkspaceAudit.RC_UPLOADERS_PAST_CYCLE_COMBINED_WORKSPACE_READY
        )

    def test_uploaders_shared_as_writer_can_compute(self):
        sharing = WorkspaceGroupSharingFactory.create(
            workspace=self.upload_workspace.workspace,
            group=self.rc_uploader_group,
            access=WorkspaceGroupSharing.WRITER,
            can_compute=True,
        )
        audit = upload_workspace_audit.UploadWorkspaceAudit()
        audit.audit_workspace_and_group(self.upload_workspace, self.rc_uploader_group)
        self.assertEqual(len(audit.verified), 0)
        self.assertEqual(len(audit.needs_action), 1)
        self.assertEqual(len(audit.errors), 0)
        record = audit.needs_action[0]
        self.assertIsInstance(record, upload_workspace_audit.StopSharing)
        self.assertEqual(record.workspace, self.upload_workspace)
        self.assertEqual(record.managed_group, self.rc_uploader_group)
        self.assertEqual(record.current_sharing_instance, sharing)
        self.assertEqual(
            record.note, upload_workspace_audit.UploadWorkspaceAudit.RC_UPLOADERS_PAST_CYCLE_COMBINED_WORKSPACE_READY
        )

    def test_uploaders_shared_as_reader(self):
        sharing = WorkspaceGroupSharingFactory.create(
            workspace=self.upload_workspace.workspace, group=self.rc_uploader_group, access=WorkspaceGroupSharing.READER
        )
        audit = upload_workspace_audit.UploadWorkspaceAudit()
        audit.audit_workspace_and_group(self.upload_workspace, self.rc_uploader_group)
        self.assertEqual(len(audit.verified), 0)
        self.assertEqual(len(audit.needs_action), 1)
        self.assertEqual(len(audit.errors), 0)
        record = audit.needs_action[0]
        self.assertIsInstance(record, upload_workspace_audit.StopSharing)
        self.assertEqual(record.workspace, self.upload_workspace)
        self.assertEqual(record.managed_group, self.rc_uploader_group)
        self.assertEqual(record.current_sharing_instance, sharing)
        self.assertEqual(
            record.note, upload_workspace_audit.UploadWorkspaceAudit.RC_UPLOADERS_PAST_CYCLE_COMBINED_WORKSPACE_READY
        )

    def test_uploaders_shared_as_owner(self):
        sharing = WorkspaceGroupSharingFactory.create(
            workspace=self.upload_workspace.workspace, group=self.rc_uploader_group, access=WorkspaceGroupSharing.OWNER
        )
        audit = upload_workspace_audit.UploadWorkspaceAudit()
        audit.audit_workspace_and_group(self.upload_workspace, self.rc_uploader_group)
        self.assertEqual(len(audit.verified), 0)
        self.assertEqual(len(audit.needs_action), 1)
        self.assertEqual(len(audit.errors), 0)
        record = audit.needs_action[0]
        self.assertIsInstance(record, upload_workspace_audit.StopSharing)
        self.assertEqual(record.workspace, self.upload_workspace)
        self.assertEqual(record.managed_group, self.rc_uploader_group)
        self.assertEqual(record.current_sharing_instance, sharing)
        self.assertEqual(
            record.note, upload_workspace_audit.UploadWorkspaceAudit.RC_UPLOADERS_PAST_CYCLE_COMBINED_WORKSPACE_READY
        )

    def test_dcc_writers_shared_as_writer_no_compute(self):
        # Share the workspace with the group.
        sharing = WorkspaceGroupSharingFactory.create(
            workspace=self.upload_workspace.workspace, group=self.dcc_writer_group, access=WorkspaceGroupSharing.WRITER
        )
        audit = upload_workspace_audit.UploadWorkspaceAudit()
        audit.audit_workspace_and_group(self.upload_workspace, self.dcc_writer_group)
        self.assertEqual(len(audit.verified), 0)
        self.assertEqual(len(audit.needs_action), 1)
        self.assertEqual(len(audit.errors), 0)
        record = audit.needs_action[0]
        self.assertIsInstance(record, upload_workspace_audit.StopSharing)
        self.assertEqual(record.workspace, self.upload_workspace)
        self.assertEqual(record.managed_group, self.dcc_writer_group)
        self.assertEqual(record.current_sharing_instance, sharing)
        self.assertEqual(
            record.note, upload_workspace_audit.UploadWorkspaceAudit.DCC_WRITERS_PAST_CYCLE_COMBINED_WORKSPACE_READY
        )

    def test_dcc_writers_not_shared(self):
        audit = upload_workspace_audit.UploadWorkspaceAudit()
        audit.audit_workspace_and_group(self.upload_workspace, self.dcc_writer_group)
        self.assertEqual(len(audit.verified), 1)
        self.assertEqual(len(audit.needs_action), 0)
        self.assertEqual(len(audit.errors), 0)
        record = audit.verified[0]
        self.assertIsInstance(record, upload_workspace_audit.VerifiedNotShared)
        self.assertEqual(record.workspace, self.upload_workspace)
        self.assertEqual(record.managed_group, self.dcc_writer_group)
        self.assertEqual(record.current_sharing_instance, None)
        self.assertEqual(
            record.note, upload_workspace_audit.UploadWorkspaceAudit.DCC_WRITERS_PAST_CYCLE_COMBINED_WORKSPACE_READY
        )

    def test_dcc_writers_shared_as_writer_can_compute(self):
        sharing = WorkspaceGroupSharingFactory.create(
            workspace=self.upload_workspace.workspace,
            group=self.dcc_writer_group,
            access=WorkspaceGroupSharing.WRITER,
            can_compute=True,
        )
        audit = upload_workspace_audit.UploadWorkspaceAudit()
        audit.audit_workspace_and_group(self.upload_workspace, self.dcc_writer_group)
        self.assertEqual(len(audit.verified), 0)
        self.assertEqual(len(audit.needs_action), 1)
        self.assertEqual(len(audit.errors), 0)
        record = audit.needs_action[0]
        self.assertIsInstance(record, upload_workspace_audit.StopSharing)
        self.assertEqual(record.workspace, self.upload_workspace)
        self.assertEqual(record.managed_group, self.dcc_writer_group)
        self.assertEqual(record.current_sharing_instance, sharing)
        self.assertEqual(
            record.note, upload_workspace_audit.UploadWorkspaceAudit.DCC_WRITERS_PAST_CYCLE_COMBINED_WORKSPACE_READY
        )

    def test_dcc_writers_shared_as_reader(self):
        sharing = WorkspaceGroupSharingFactory.create(
            workspace=self.upload_workspace.workspace, group=self.dcc_writer_group, access=WorkspaceGroupSharing.READER
        )
        audit = upload_workspace_audit.UploadWorkspaceAudit()
        audit.audit_workspace_and_group(self.upload_workspace, self.dcc_writer_group)
        self.assertEqual(len(audit.verified), 0)
        self.assertEqual(len(audit.needs_action), 1)
        self.assertEqual(len(audit.errors), 0)
        record = audit.needs_action[0]
        self.assertIsInstance(record, upload_workspace_audit.StopSharing)
        self.assertEqual(record.workspace, self.upload_workspace)
        self.assertEqual(record.managed_group, self.dcc_writer_group)
        self.assertEqual(record.current_sharing_instance, sharing)
        self.assertEqual(
            record.note, upload_workspace_audit.UploadWorkspaceAudit.DCC_WRITERS_PAST_CYCLE_COMBINED_WORKSPACE_READY
        )

    def test_dcc_writers_shared_as_owner(self):
        sharing = WorkspaceGroupSharingFactory.create(
            workspace=self.upload_workspace.workspace, group=self.dcc_writer_group, access=WorkspaceGroupSharing.OWNER
        )
        audit = upload_workspace_audit.UploadWorkspaceAudit()
        audit.audit_workspace_and_group(self.upload_workspace, self.dcc_writer_group)
        self.assertEqual(len(audit.verified), 0)
        self.assertEqual(len(audit.needs_action), 1)
        self.assertEqual(len(audit.errors), 0)
        record = audit.needs_action[0]
        self.assertIsInstance(record, upload_workspace_audit.StopSharing)
        self.assertEqual(record.workspace, self.upload_workspace)
        self.assertEqual(record.managed_group, self.dcc_writer_group)
        self.assertEqual(record.current_sharing_instance, sharing)
        self.assertEqual(
            record.note, upload_workspace_audit.UploadWorkspaceAudit.DCC_WRITERS_PAST_CYCLE_COMBINED_WORKSPACE_READY
        )

    def test_other_groups(self):
        pass
