"""Tests for the `py` module."""

from dataclasses import dataclass

import django_tables2 as tables
from anvil_consortium_manager.models import GroupGroupMembership, WorkspaceGroupSharing
from anvil_consortium_manager.tests.factories import (
    GroupGroupMembershipFactory,
    ManagedGroupFactory,
    WorkspaceGroupSharingFactory,
)
from django.conf import settings
from django.test import TestCase, override_settings
from faker import Faker

from ..audit import upload_workspace_audit, upload_workspace_auth_domain_audit
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

    def test_one_upload_workspace_no_groups(self):
        upload_workspace = factories.UploadWorkspaceFactory.create()
        audit = upload_workspace_audit.UploadWorkspaceAudit()
        audit.run_audit()
        self.assertEqual(len(audit.verified), 0)
        self.assertEqual(len(audit.needs_action), 1)
        self.assertEqual(len(audit.errors), 0)
        record = audit.needs_action[0]
        self.assertIsInstance(record, upload_workspace_audit.ShareAsReader)
        self.assertEqual(record.workspace, upload_workspace)
        self.assertEqual(record.managed_group, upload_workspace.workspace.authorization_domains.first())
        self.assertEqual(record.current_sharing_instance, None)
        self.assertEqual(record.note, upload_workspace_audit.UploadWorkspaceAudit.AUTH_DOMAIN_AS_READER)

    def test_one_upload_workspace_rc_upload_group(self):
        group = ManagedGroupFactory.create()
        upload_workspace = factories.UploadWorkspaceFactory.create(
            research_center__uploader_group=group, upload_cycle__is_future=True
        )
        WorkspaceGroupSharingFactory.create(
            workspace=upload_workspace.workspace, group=group, access=WorkspaceGroupSharing.WRITER
        )
        audit = upload_workspace_audit.UploadWorkspaceAudit()
        audit.run_audit()
        self.assertEqual(len(audit.verified), 1)
        self.assertEqual(len(audit.needs_action), 1)  # auth domain is not shared
        self.assertEqual(len(audit.errors), 0)
        record = audit.verified[0]
        self.assertIsInstance(record, upload_workspace_audit.VerifiedShared)
        self.assertEqual(record.workspace, upload_workspace)
        self.assertEqual(record.managed_group, group)

    def test_one_upload_workspace_dcc_writer_group(self):
        group = ManagedGroupFactory.create(name="GREGOR_DCC_WRITERS")
        upload_workspace = factories.UploadWorkspaceFactory.create(upload_cycle__is_future=True)
        WorkspaceGroupSharingFactory.create(
            workspace=upload_workspace.workspace, group=group, access=WorkspaceGroupSharing.WRITER, can_compute=True
        )
        audit = upload_workspace_audit.UploadWorkspaceAudit()
        audit.run_audit()
        self.assertEqual(len(audit.verified), 1)
        self.assertEqual(len(audit.needs_action), 1)  # auth domain is not shared
        self.assertEqual(len(audit.errors), 0)
        record = audit.verified[0]
        self.assertIsInstance(record, upload_workspace_audit.VerifiedShared)
        self.assertEqual(record.workspace, upload_workspace)
        self.assertEqual(record.managed_group, group)

    def test_one_upload_workspace_auth_domain(self):
        upload_workspace = factories.UploadWorkspaceFactory.create(upload_cycle__is_future=True)
        group = upload_workspace.workspace.authorization_domains.first()
        WorkspaceGroupSharingFactory.create(
            workspace=upload_workspace.workspace, group=group, access=WorkspaceGroupSharing.READER
        )
        audit = upload_workspace_audit.UploadWorkspaceAudit()
        audit.run_audit()
        self.assertEqual(len(audit.verified), 1)
        self.assertEqual(len(audit.needs_action), 0)  # auth domain is shared
        self.assertEqual(len(audit.errors), 0)
        record = audit.verified[0]
        self.assertIsInstance(record, upload_workspace_audit.VerifiedShared)
        self.assertEqual(record.workspace, upload_workspace)
        self.assertEqual(record.managed_group, group)

    def test_one_upload_workspace_dcc_admin_group(self):
        group = ManagedGroupFactory.create(name=settings.ANVIL_DCC_ADMINS_GROUP_NAME)
        upload_workspace = factories.UploadWorkspaceFactory.create(upload_cycle__is_future=True)
        WorkspaceGroupSharingFactory.create(
            workspace=upload_workspace.workspace, group=group, access=WorkspaceGroupSharing.OWNER
        )
        audit = upload_workspace_audit.UploadWorkspaceAudit()
        audit.run_audit()
        self.assertEqual(len(audit.verified), 1)
        self.assertEqual(len(audit.needs_action), 1)  # auth domain is not shared
        self.assertEqual(len(audit.errors), 0)
        record = audit.verified[0]
        self.assertIsInstance(record, upload_workspace_audit.VerifiedShared)
        self.assertEqual(record.workspace, upload_workspace)
        self.assertEqual(record.managed_group, group)

    @override_settings(ANVIL_DCC_ADMINS_GROUP_NAME="foo")
    def test_one_upload_workspace_dcc_admin_group_different_name(self):
        group = ManagedGroupFactory.create(name="foo")
        upload_workspace = factories.UploadWorkspaceFactory.create(upload_cycle__is_future=True)
        WorkspaceGroupSharingFactory.create(
            workspace=upload_workspace.workspace, group=group, access=WorkspaceGroupSharing.OWNER
        )
        audit = upload_workspace_audit.UploadWorkspaceAudit()
        audit.run_audit()
        self.assertEqual(len(audit.verified), 1)
        self.assertEqual(len(audit.needs_action), 1)  # auth domain is not shared
        self.assertEqual(len(audit.errors), 0)
        record = audit.verified[0]
        self.assertIsInstance(record, upload_workspace_audit.VerifiedShared)
        self.assertEqual(record.workspace, upload_workspace)
        self.assertEqual(record.managed_group, group)

    def test_one_upload_workspace_anvil_admin_group(self):
        group = ManagedGroupFactory.create(name="anvil-admins")
        upload_workspace = factories.UploadWorkspaceFactory.create(upload_cycle__is_future=True)
        WorkspaceGroupSharingFactory.create(workspace=upload_workspace.workspace, group=group)
        audit = upload_workspace_audit.UploadWorkspaceAudit()
        audit.run_audit()
        self.assertEqual(len(audit.verified), 0)
        self.assertEqual(len(audit.needs_action), 1)  # auth domain is not shared
        self.assertEqual(len(audit.errors), 0)

    def test_one_upload_workspace_anvil_dev_group(self):
        group = ManagedGroupFactory.create(name="anvil_devs")
        upload_workspace = factories.UploadWorkspaceFactory.create(upload_cycle__is_future=True)
        WorkspaceGroupSharingFactory.create(workspace=upload_workspace.workspace, group=group)
        audit = upload_workspace_audit.UploadWorkspaceAudit()
        audit.run_audit()
        self.assertEqual(len(audit.verified), 0)
        self.assertEqual(len(audit.needs_action), 1)  # auth domain is not shared
        self.assertEqual(len(audit.errors), 0)

    def test_one_upload_workspace_other_group_shared(self):
        group = ManagedGroupFactory.create(name="foo")
        upload_workspace = factories.UploadWorkspaceFactory.create(upload_cycle__is_future=True)
        WorkspaceGroupSharingFactory.create(
            workspace=upload_workspace.workspace, group=group, access=WorkspaceGroupSharing.READER
        )
        audit = upload_workspace_audit.UploadWorkspaceAudit()
        audit.run_audit()
        self.assertEqual(len(audit.verified), 0)
        self.assertEqual(len(audit.needs_action), 1)  # auth domain is not shared
        self.assertEqual(len(audit.errors), 1)
        record = audit.errors[0]
        self.assertIsInstance(record, upload_workspace_audit.StopSharing)
        self.assertEqual(record.workspace, upload_workspace)
        self.assertEqual(record.managed_group, group)

    def test_one_upload_workspace_other_group_not_shared(self):
        ManagedGroupFactory.create(name="foo")
        factories.UploadWorkspaceFactory.create(upload_cycle__is_future=True)
        audit = upload_workspace_audit.UploadWorkspaceAudit()
        audit.run_audit()
        self.assertEqual(len(audit.verified), 0)
        self.assertEqual(len(audit.needs_action), 1)  # auth domain is not shared
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
        self.dcc_admin_group = ManagedGroupFactory.create(name=settings.ANVIL_DCC_ADMINS_GROUP_NAME)
        self.research_center = factories.ResearchCenterFactory.create(uploader_group=self.rc_uploader_group)
        self.upload_workspace = factories.UploadWorkspaceFactory.create(
            research_center=self.research_center, upload_cycle__is_future=True
        )
        self.auth_domain = self.upload_workspace.workspace.authorization_domains.get()
        self.other_group = ManagedGroupFactory.create()
        self.anvil_admins = ManagedGroupFactory.create(name="anvil-admins")
        self.anvil_devs = ManagedGroupFactory.create(name="anvil_devs")

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

    def test_auth_domain_shared_as_writer_no_compute(self):
        # Share the workspace with the group.
        sharing = WorkspaceGroupSharingFactory.create(
            workspace=self.upload_workspace.workspace, group=self.auth_domain, access=WorkspaceGroupSharing.WRITER
        )
        audit = upload_workspace_audit.UploadWorkspaceAudit()
        audit.audit_workspace_and_group(self.upload_workspace, self.auth_domain)
        self.assertEqual(len(audit.verified), 0)
        self.assertEqual(len(audit.needs_action), 1)
        self.assertEqual(len(audit.errors), 0)
        record = audit.needs_action[0]
        self.assertIsInstance(record, upload_workspace_audit.ShareAsReader)
        self.assertEqual(record.workspace, self.upload_workspace)
        self.assertEqual(record.managed_group, self.auth_domain)
        self.assertEqual(record.current_sharing_instance, sharing)
        self.assertEqual(record.note, upload_workspace_audit.UploadWorkspaceAudit.AUTH_DOMAIN_AS_READER)

    def test_auth_domain_not_shared(self):
        audit = upload_workspace_audit.UploadWorkspaceAudit()
        audit.audit_workspace_and_group(self.upload_workspace, self.auth_domain)
        self.assertEqual(len(audit.verified), 0)
        self.assertEqual(len(audit.needs_action), 1)
        self.assertEqual(len(audit.errors), 0)
        record = audit.needs_action[0]
        self.assertIsInstance(record, upload_workspace_audit.ShareAsReader)
        self.assertEqual(record.workspace, self.upload_workspace)
        self.assertEqual(record.managed_group, self.auth_domain)
        self.assertEqual(record.current_sharing_instance, None)
        self.assertEqual(record.note, upload_workspace_audit.UploadWorkspaceAudit.AUTH_DOMAIN_AS_READER)

    def test_auth_domain_shared_as_writer_can_compute(self):
        sharing = WorkspaceGroupSharingFactory.create(
            workspace=self.upload_workspace.workspace,
            group=self.auth_domain,
            access=WorkspaceGroupSharing.WRITER,
            can_compute=True,
        )
        audit = upload_workspace_audit.UploadWorkspaceAudit()
        audit.audit_workspace_and_group(self.upload_workspace, self.auth_domain)
        self.assertEqual(len(audit.verified), 0)
        self.assertEqual(len(audit.needs_action), 1)
        self.assertEqual(len(audit.errors), 0)
        record = audit.needs_action[0]
        self.assertIsInstance(record, upload_workspace_audit.ShareAsReader)
        self.assertEqual(record.workspace, self.upload_workspace)
        self.assertEqual(record.managed_group, self.auth_domain)
        self.assertEqual(record.current_sharing_instance, sharing)
        self.assertEqual(record.note, upload_workspace_audit.UploadWorkspaceAudit.AUTH_DOMAIN_AS_READER)

    def test_auth_domain_shared_as_reader(self):
        sharing = WorkspaceGroupSharingFactory.create(
            workspace=self.upload_workspace.workspace, group=self.auth_domain, access=WorkspaceGroupSharing.READER
        )
        audit = upload_workspace_audit.UploadWorkspaceAudit()
        audit.audit_workspace_and_group(self.upload_workspace, self.auth_domain)
        self.assertEqual(len(audit.verified), 1)
        self.assertEqual(len(audit.needs_action), 0)
        self.assertEqual(len(audit.errors), 0)
        record = audit.verified[0]
        self.assertIsInstance(record, upload_workspace_audit.VerifiedShared)
        self.assertEqual(record.workspace, self.upload_workspace)
        self.assertEqual(record.managed_group, self.auth_domain)
        self.assertEqual(record.current_sharing_instance, sharing)
        self.assertEqual(record.note, upload_workspace_audit.UploadWorkspaceAudit.AUTH_DOMAIN_AS_READER)

    def test_auth_domain_shared_as_owner(self):
        sharing = WorkspaceGroupSharingFactory.create(
            workspace=self.upload_workspace.workspace, group=self.auth_domain, access=WorkspaceGroupSharing.OWNER
        )
        audit = upload_workspace_audit.UploadWorkspaceAudit()
        audit.audit_workspace_and_group(self.upload_workspace, self.auth_domain)
        self.assertEqual(len(audit.verified), 0)
        self.assertEqual(len(audit.needs_action), 1)
        self.assertEqual(len(audit.errors), 0)
        record = audit.needs_action[0]
        self.assertIsInstance(record, upload_workspace_audit.ShareAsReader)
        self.assertEqual(record.workspace, self.upload_workspace)
        self.assertEqual(record.managed_group, self.auth_domain)
        self.assertEqual(record.current_sharing_instance, sharing)
        self.assertEqual(record.note, upload_workspace_audit.UploadWorkspaceAudit.AUTH_DOMAIN_AS_READER)

    def test_dcc_admin_shared_as_writer_no_compute(self):
        # Share the workspace with the group.
        sharing = WorkspaceGroupSharingFactory.create(
            workspace=self.upload_workspace.workspace, group=self.dcc_admin_group, access=WorkspaceGroupSharing.WRITER
        )
        audit = upload_workspace_audit.UploadWorkspaceAudit()
        audit.audit_workspace_and_group(self.upload_workspace, self.dcc_admin_group)
        self.assertEqual(len(audit.verified), 0)
        self.assertEqual(len(audit.needs_action), 1)
        self.assertEqual(len(audit.errors), 0)
        record = audit.needs_action[0]
        self.assertIsInstance(record, upload_workspace_audit.ShareAsOwner)
        self.assertEqual(record.workspace, self.upload_workspace)
        self.assertEqual(record.managed_group, self.dcc_admin_group)
        self.assertEqual(record.current_sharing_instance, sharing)
        self.assertEqual(record.note, upload_workspace_audit.UploadWorkspaceAudit.DCC_ADMIN_AS_OWNER)

    def test_dcc_admin_not_shared(self):
        audit = upload_workspace_audit.UploadWorkspaceAudit()
        audit.audit_workspace_and_group(self.upload_workspace, self.dcc_admin_group)
        self.assertEqual(len(audit.verified), 0)
        self.assertEqual(len(audit.needs_action), 1)
        self.assertEqual(len(audit.errors), 0)
        record = audit.needs_action[0]
        self.assertIsInstance(record, upload_workspace_audit.ShareAsOwner)
        self.assertEqual(record.workspace, self.upload_workspace)
        self.assertEqual(record.managed_group, self.dcc_admin_group)
        self.assertEqual(record.current_sharing_instance, None)
        self.assertEqual(record.note, upload_workspace_audit.UploadWorkspaceAudit.DCC_ADMIN_AS_OWNER)

    def test_dcc_admin_shared_as_writer_can_compute(self):
        sharing = WorkspaceGroupSharingFactory.create(
            workspace=self.upload_workspace.workspace,
            group=self.dcc_admin_group,
            access=WorkspaceGroupSharing.WRITER,
            can_compute=True,
        )
        audit = upload_workspace_audit.UploadWorkspaceAudit()
        audit.audit_workspace_and_group(self.upload_workspace, self.dcc_admin_group)
        self.assertEqual(len(audit.verified), 0)
        self.assertEqual(len(audit.needs_action), 1)
        self.assertEqual(len(audit.errors), 0)
        record = audit.needs_action[0]
        self.assertIsInstance(record, upload_workspace_audit.ShareAsOwner)
        self.assertEqual(record.workspace, self.upload_workspace)
        self.assertEqual(record.managed_group, self.dcc_admin_group)
        self.assertEqual(record.current_sharing_instance, sharing)
        self.assertEqual(record.note, upload_workspace_audit.UploadWorkspaceAudit.DCC_ADMIN_AS_OWNER)

    def test_dcc_admin_shared_as_reader(self):
        sharing = WorkspaceGroupSharingFactory.create(
            workspace=self.upload_workspace.workspace, group=self.dcc_admin_group, access=WorkspaceGroupSharing.READER
        )
        audit = upload_workspace_audit.UploadWorkspaceAudit()
        audit.audit_workspace_and_group(self.upload_workspace, self.dcc_admin_group)
        self.assertEqual(len(audit.verified), 0)
        self.assertEqual(len(audit.needs_action), 1)
        self.assertEqual(len(audit.errors), 0)
        record = audit.needs_action[0]
        self.assertIsInstance(record, upload_workspace_audit.ShareAsOwner)
        self.assertEqual(record.workspace, self.upload_workspace)
        self.assertEqual(record.managed_group, self.dcc_admin_group)
        self.assertEqual(record.current_sharing_instance, sharing)
        self.assertEqual(record.note, upload_workspace_audit.UploadWorkspaceAudit.DCC_ADMIN_AS_OWNER)

    def test_dcc_admin_shared_as_owner(self):
        sharing = WorkspaceGroupSharingFactory.create(
            workspace=self.upload_workspace.workspace, group=self.dcc_admin_group, access=WorkspaceGroupSharing.OWNER
        )
        audit = upload_workspace_audit.UploadWorkspaceAudit()
        audit.audit_workspace_and_group(self.upload_workspace, self.dcc_admin_group)
        self.assertEqual(len(audit.verified), 1)
        self.assertEqual(len(audit.needs_action), 0)
        self.assertEqual(len(audit.errors), 0)
        record = audit.verified[0]
        self.assertIsInstance(record, upload_workspace_audit.VerifiedShared)
        self.assertEqual(record.workspace, self.upload_workspace)
        self.assertEqual(record.managed_group, self.dcc_admin_group)
        self.assertEqual(record.current_sharing_instance, sharing)
        self.assertEqual(record.note, upload_workspace_audit.UploadWorkspaceAudit.DCC_ADMIN_AS_OWNER)

    @override_settings(ANVIL_DCC_ADMINS_GROUP_NAME="foo")
    def test_dcc_admin_different_setting(self):
        group = ManagedGroupFactory.create(name="foo")
        sharing = WorkspaceGroupSharingFactory.create(
            workspace=self.upload_workspace.workspace, group=group, access=WorkspaceGroupSharing.OWNER
        )
        audit = upload_workspace_audit.UploadWorkspaceAudit()
        audit.audit_workspace_and_group(self.upload_workspace, group)
        self.assertEqual(len(audit.verified), 1)
        self.assertEqual(len(audit.needs_action), 0)
        self.assertEqual(len(audit.errors), 0)
        record = audit.verified[0]
        self.assertIsInstance(record, upload_workspace_audit.VerifiedShared)
        self.assertEqual(record.workspace, self.upload_workspace)
        self.assertEqual(record.managed_group, group)
        self.assertEqual(record.current_sharing_instance, sharing)
        self.assertEqual(record.note, upload_workspace_audit.UploadWorkspaceAudit.DCC_ADMIN_AS_OWNER)

    def test_anvil_admins_shared_as_writer_no_compute(self):
        # Share the workspace with the group.
        WorkspaceGroupSharingFactory.create(
            workspace=self.upload_workspace.workspace, group=self.anvil_admins, access=WorkspaceGroupSharing.WRITER
        )
        audit = upload_workspace_audit.UploadWorkspaceAudit()
        audit.audit_workspace_and_group(self.upload_workspace, self.anvil_admins)
        self.assertEqual(len(audit.verified), 0)
        self.assertEqual(len(audit.needs_action), 0)
        self.assertEqual(len(audit.errors), 0)

    def test_anvil_admins_not_shared(self):
        audit = upload_workspace_audit.UploadWorkspaceAudit()
        audit.audit_workspace_and_group(self.upload_workspace, self.anvil_admins)
        self.assertEqual(len(audit.verified), 0)
        self.assertEqual(len(audit.needs_action), 0)
        self.assertEqual(len(audit.errors), 0)

    def test_anvil_admins_shared_as_writer_can_compute(self):
        WorkspaceGroupSharingFactory.create(
            workspace=self.upload_workspace.workspace,
            group=self.anvil_admins,
            access=WorkspaceGroupSharing.WRITER,
            can_compute=True,
        )
        audit = upload_workspace_audit.UploadWorkspaceAudit()
        audit.audit_workspace_and_group(self.upload_workspace, self.anvil_admins)
        self.assertEqual(len(audit.verified), 0)
        self.assertEqual(len(audit.needs_action), 0)
        self.assertEqual(len(audit.errors), 0)

    def test_anvil_admins_shared_as_reader(self):
        WorkspaceGroupSharingFactory.create(
            workspace=self.upload_workspace.workspace, group=self.anvil_admins, access=WorkspaceGroupSharing.READER
        )
        audit = upload_workspace_audit.UploadWorkspaceAudit()
        audit.audit_workspace_and_group(self.upload_workspace, self.anvil_admins)
        self.assertEqual(len(audit.verified), 0)
        self.assertEqual(len(audit.needs_action), 0)
        self.assertEqual(len(audit.errors), 0)

    def test_anvil_admins_shared_as_owner(self):
        WorkspaceGroupSharingFactory.create(
            workspace=self.upload_workspace.workspace, group=self.anvil_admins, access=WorkspaceGroupSharing.OWNER
        )
        audit = upload_workspace_audit.UploadWorkspaceAudit()
        audit.audit_workspace_and_group(self.upload_workspace, self.anvil_admins)
        self.assertEqual(len(audit.verified), 0)
        self.assertEqual(len(audit.needs_action), 0)
        self.assertEqual(len(audit.errors), 0)

    def test_anvil_devs_shared_as_writer_no_compute(self):
        # Share the workspace with the group.
        WorkspaceGroupSharingFactory.create(
            workspace=self.upload_workspace.workspace, group=self.anvil_devs, access=WorkspaceGroupSharing.WRITER
        )
        audit = upload_workspace_audit.UploadWorkspaceAudit()
        audit.audit_workspace_and_group(self.upload_workspace, self.anvil_devs)
        self.assertEqual(len(audit.verified), 0)
        self.assertEqual(len(audit.needs_action), 0)
        self.assertEqual(len(audit.errors), 0)

    def test_anvil_devs_not_shared(self):
        audit = upload_workspace_audit.UploadWorkspaceAudit()
        audit.audit_workspace_and_group(self.upload_workspace, self.anvil_devs)
        self.assertEqual(len(audit.verified), 0)
        self.assertEqual(len(audit.needs_action), 0)
        self.assertEqual(len(audit.errors), 0)

    def test_anvil_devs_shared_as_writer_can_compute(self):
        WorkspaceGroupSharingFactory.create(
            workspace=self.upload_workspace.workspace,
            group=self.anvil_devs,
            access=WorkspaceGroupSharing.WRITER,
            can_compute=True,
        )
        audit = upload_workspace_audit.UploadWorkspaceAudit()
        audit.audit_workspace_and_group(self.upload_workspace, self.anvil_devs)
        self.assertEqual(len(audit.verified), 0)
        self.assertEqual(len(audit.needs_action), 0)
        self.assertEqual(len(audit.errors), 0)

    def test_anvil_devs_shared_as_reader(self):
        WorkspaceGroupSharingFactory.create(
            workspace=self.upload_workspace.workspace, group=self.anvil_devs, access=WorkspaceGroupSharing.READER
        )
        audit = upload_workspace_audit.UploadWorkspaceAudit()
        audit.audit_workspace_and_group(self.upload_workspace, self.anvil_devs)
        self.assertEqual(len(audit.verified), 0)
        self.assertEqual(len(audit.needs_action), 0)
        self.assertEqual(len(audit.errors), 0)

    def test_anvil_devs_shared_as_owner(self):
        WorkspaceGroupSharingFactory.create(
            workspace=self.upload_workspace.workspace, group=self.anvil_devs, access=WorkspaceGroupSharing.OWNER
        )
        audit = upload_workspace_audit.UploadWorkspaceAudit()
        audit.audit_workspace_and_group(self.upload_workspace, self.anvil_devs)
        self.assertEqual(len(audit.verified), 0)
        self.assertEqual(len(audit.needs_action), 0)
        self.assertEqual(len(audit.errors), 0)

    def test_other_group_shared_as_writer_no_compute(self):
        # Share the workspace with the group.
        sharing = WorkspaceGroupSharingFactory.create(
            workspace=self.upload_workspace.workspace, group=self.other_group, access=WorkspaceGroupSharing.WRITER
        )
        audit = upload_workspace_audit.UploadWorkspaceAudit()
        audit.audit_workspace_and_group(self.upload_workspace, self.other_group)
        self.assertEqual(len(audit.verified), 0)
        self.assertEqual(len(audit.needs_action), 0)
        self.assertEqual(len(audit.errors), 1)
        record = audit.errors[0]
        self.assertIsInstance(record, upload_workspace_audit.StopSharing)
        self.assertEqual(record.workspace, self.upload_workspace)
        self.assertEqual(record.managed_group, self.other_group)
        self.assertEqual(record.current_sharing_instance, sharing)
        self.assertEqual(record.note, upload_workspace_audit.UploadWorkspaceAudit.OTHER_GROUP_NO_ACCESS)

    def test_other_group_not_shared(self):
        audit = upload_workspace_audit.UploadWorkspaceAudit()
        audit.audit_workspace_and_group(self.upload_workspace, self.other_group)
        self.assertEqual(len(audit.verified), 1)
        self.assertEqual(len(audit.needs_action), 0)
        self.assertEqual(len(audit.errors), 0)
        record = audit.verified[0]
        self.assertIsInstance(record, upload_workspace_audit.VerifiedNotShared)
        self.assertEqual(record.workspace, self.upload_workspace)
        self.assertEqual(record.managed_group, self.other_group)
        self.assertEqual(record.current_sharing_instance, None)
        self.assertEqual(record.note, upload_workspace_audit.UploadWorkspaceAudit.OTHER_GROUP_NO_ACCESS)

    def test_other_group_shared_as_writer_can_compute(self):
        sharing = WorkspaceGroupSharingFactory.create(
            workspace=self.upload_workspace.workspace,
            group=self.other_group,
            access=WorkspaceGroupSharing.WRITER,
            can_compute=True,
        )
        audit = upload_workspace_audit.UploadWorkspaceAudit()
        audit.audit_workspace_and_group(self.upload_workspace, self.other_group)
        self.assertEqual(len(audit.verified), 0)
        self.assertEqual(len(audit.needs_action), 0)
        self.assertEqual(len(audit.errors), 1)
        record = audit.errors[0]
        self.assertIsInstance(record, upload_workspace_audit.StopSharing)
        self.assertEqual(record.workspace, self.upload_workspace)
        self.assertEqual(record.managed_group, self.other_group)
        self.assertEqual(record.current_sharing_instance, sharing)
        self.assertEqual(record.note, upload_workspace_audit.UploadWorkspaceAudit.OTHER_GROUP_NO_ACCESS)

    def test_other_group_shared_as_reader(self):
        sharing = WorkspaceGroupSharingFactory.create(
            workspace=self.upload_workspace.workspace, group=self.other_group, access=WorkspaceGroupSharing.READER
        )
        audit = upload_workspace_audit.UploadWorkspaceAudit()
        audit.audit_workspace_and_group(self.upload_workspace, self.other_group)
        self.assertEqual(len(audit.verified), 0)
        self.assertEqual(len(audit.needs_action), 0)
        self.assertEqual(len(audit.errors), 1)
        record = audit.errors[0]
        self.assertIsInstance(record, upload_workspace_audit.StopSharing)
        self.assertEqual(record.workspace, self.upload_workspace)
        self.assertEqual(record.managed_group, self.other_group)
        self.assertEqual(record.current_sharing_instance, sharing)
        self.assertEqual(record.note, upload_workspace_audit.UploadWorkspaceAudit.OTHER_GROUP_NO_ACCESS)

    def test_other_group_shared_as_owner(self):
        sharing = WorkspaceGroupSharingFactory.create(
            workspace=self.upload_workspace.workspace, group=self.other_group, access=WorkspaceGroupSharing.OWNER
        )
        audit = upload_workspace_audit.UploadWorkspaceAudit()
        audit.audit_workspace_and_group(self.upload_workspace, self.other_group)
        self.assertEqual(len(audit.verified), 0)
        self.assertEqual(len(audit.needs_action), 0)
        self.assertEqual(len(audit.errors), 1)
        record = audit.errors[0]
        self.assertIsInstance(record, upload_workspace_audit.StopSharing)
        self.assertEqual(record.workspace, self.upload_workspace)
        self.assertEqual(record.managed_group, self.other_group)
        self.assertEqual(record.current_sharing_instance, sharing)
        self.assertEqual(record.note, upload_workspace_audit.UploadWorkspaceAudit.OTHER_GROUP_NO_ACCESS)


class UploadWorkspaceAuditCurrentCycleBeforeComputeTest(TestCase):
    """Tests for the `UploadWorkspaceAudit` class for current cycle UploadWorkspaces before compute is enabled.

    Expectations at this point in the upload cycle:
    - RC uploader group should be writers without compute.
    - DCC writer group should be writers with compute.
    """

    def setUp(self):
        super().setUp()
        self.dcc_admin_group = ManagedGroupFactory.create(name=settings.ANVIL_DCC_ADMINS_GROUP_NAME)
        self.dcc_writer_group = ManagedGroupFactory.create(name="GREGOR_DCC_WRITERS")
        self.rc_uploader_group = ManagedGroupFactory.create()
        self.research_center = factories.ResearchCenterFactory.create(uploader_group=self.rc_uploader_group)
        self.upload_workspace = factories.UploadWorkspaceFactory.create(
            research_center=self.research_center,
            upload_cycle__is_current=True,
            upload_cycle__date_ready_for_compute=None,
        )
        self.auth_domain = self.upload_workspace.workspace.authorization_domains.get()
        self.other_group = ManagedGroupFactory.create()
        self.anvil_admins = ManagedGroupFactory.create(name="anvil-admins")
        self.anvil_devs = ManagedGroupFactory.create(name="anvil_devs")

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

    def test_auth_domain_shared_as_writer_no_compute(self):
        # Share the workspace with the group.
        sharing = WorkspaceGroupSharingFactory.create(
            workspace=self.upload_workspace.workspace, group=self.auth_domain, access=WorkspaceGroupSharing.WRITER
        )
        audit = upload_workspace_audit.UploadWorkspaceAudit()
        audit.audit_workspace_and_group(self.upload_workspace, self.auth_domain)
        self.assertEqual(len(audit.verified), 0)
        self.assertEqual(len(audit.needs_action), 1)
        self.assertEqual(len(audit.errors), 0)
        record = audit.needs_action[0]
        self.assertIsInstance(record, upload_workspace_audit.ShareAsReader)
        self.assertEqual(record.workspace, self.upload_workspace)
        self.assertEqual(record.managed_group, self.auth_domain)
        self.assertEqual(record.current_sharing_instance, sharing)
        self.assertEqual(record.note, upload_workspace_audit.UploadWorkspaceAudit.AUTH_DOMAIN_AS_READER)

    def test_auth_domain_not_shared(self):
        audit = upload_workspace_audit.UploadWorkspaceAudit()
        audit.audit_workspace_and_group(self.upload_workspace, self.auth_domain)
        self.assertEqual(len(audit.verified), 0)
        self.assertEqual(len(audit.needs_action), 1)
        self.assertEqual(len(audit.errors), 0)
        record = audit.needs_action[0]
        self.assertIsInstance(record, upload_workspace_audit.ShareAsReader)
        self.assertEqual(record.workspace, self.upload_workspace)
        self.assertEqual(record.managed_group, self.auth_domain)
        self.assertEqual(record.current_sharing_instance, None)
        self.assertEqual(record.note, upload_workspace_audit.UploadWorkspaceAudit.AUTH_DOMAIN_AS_READER)

    def test_auth_domain_shared_as_writer_can_compute(self):
        sharing = WorkspaceGroupSharingFactory.create(
            workspace=self.upload_workspace.workspace,
            group=self.auth_domain,
            access=WorkspaceGroupSharing.WRITER,
            can_compute=True,
        )
        audit = upload_workspace_audit.UploadWorkspaceAudit()
        audit.audit_workspace_and_group(self.upload_workspace, self.auth_domain)
        self.assertEqual(len(audit.verified), 0)
        self.assertEqual(len(audit.needs_action), 1)
        self.assertEqual(len(audit.errors), 0)
        record = audit.needs_action[0]
        self.assertIsInstance(record, upload_workspace_audit.ShareAsReader)
        self.assertEqual(record.workspace, self.upload_workspace)
        self.assertEqual(record.managed_group, self.auth_domain)
        self.assertEqual(record.current_sharing_instance, sharing)
        self.assertEqual(record.note, upload_workspace_audit.UploadWorkspaceAudit.AUTH_DOMAIN_AS_READER)

    def test_auth_domain_shared_as_reader(self):
        sharing = WorkspaceGroupSharingFactory.create(
            workspace=self.upload_workspace.workspace, group=self.auth_domain, access=WorkspaceGroupSharing.READER
        )
        audit = upload_workspace_audit.UploadWorkspaceAudit()
        audit.audit_workspace_and_group(self.upload_workspace, self.auth_domain)
        self.assertEqual(len(audit.verified), 1)
        self.assertEqual(len(audit.needs_action), 0)
        self.assertEqual(len(audit.errors), 0)
        record = audit.verified[0]
        self.assertIsInstance(record, upload_workspace_audit.VerifiedShared)
        self.assertEqual(record.workspace, self.upload_workspace)
        self.assertEqual(record.managed_group, self.auth_domain)
        self.assertEqual(record.current_sharing_instance, sharing)
        self.assertEqual(record.note, upload_workspace_audit.UploadWorkspaceAudit.AUTH_DOMAIN_AS_READER)

    def test_auth_domain_shared_as_owner(self):
        sharing = WorkspaceGroupSharingFactory.create(
            workspace=self.upload_workspace.workspace, group=self.auth_domain, access=WorkspaceGroupSharing.OWNER
        )
        audit = upload_workspace_audit.UploadWorkspaceAudit()
        audit.audit_workspace_and_group(self.upload_workspace, self.auth_domain)
        self.assertEqual(len(audit.verified), 0)
        self.assertEqual(len(audit.needs_action), 1)
        self.assertEqual(len(audit.errors), 0)
        record = audit.needs_action[0]
        self.assertIsInstance(record, upload_workspace_audit.ShareAsReader)
        self.assertEqual(record.workspace, self.upload_workspace)
        self.assertEqual(record.managed_group, self.auth_domain)
        self.assertEqual(record.current_sharing_instance, sharing)
        self.assertEqual(record.note, upload_workspace_audit.UploadWorkspaceAudit.AUTH_DOMAIN_AS_READER)

    def test_dcc_admin_shared_as_writer_no_compute(self):
        # Share the workspace with the group.
        sharing = WorkspaceGroupSharingFactory.create(
            workspace=self.upload_workspace.workspace, group=self.dcc_admin_group, access=WorkspaceGroupSharing.WRITER
        )
        audit = upload_workspace_audit.UploadWorkspaceAudit()
        audit.audit_workspace_and_group(self.upload_workspace, self.dcc_admin_group)
        self.assertEqual(len(audit.verified), 0)
        self.assertEqual(len(audit.needs_action), 1)
        self.assertEqual(len(audit.errors), 0)
        record = audit.needs_action[0]
        self.assertIsInstance(record, upload_workspace_audit.ShareAsOwner)
        self.assertEqual(record.workspace, self.upload_workspace)
        self.assertEqual(record.managed_group, self.dcc_admin_group)
        self.assertEqual(record.current_sharing_instance, sharing)
        self.assertEqual(record.note, upload_workspace_audit.UploadWorkspaceAudit.DCC_ADMIN_AS_OWNER)

    def test_dcc_admin_not_shared(self):
        audit = upload_workspace_audit.UploadWorkspaceAudit()
        audit.audit_workspace_and_group(self.upload_workspace, self.dcc_admin_group)
        self.assertEqual(len(audit.verified), 0)
        self.assertEqual(len(audit.needs_action), 1)
        self.assertEqual(len(audit.errors), 0)
        record = audit.needs_action[0]
        self.assertIsInstance(record, upload_workspace_audit.ShareAsOwner)
        self.assertEqual(record.workspace, self.upload_workspace)
        self.assertEqual(record.managed_group, self.dcc_admin_group)
        self.assertEqual(record.current_sharing_instance, None)
        self.assertEqual(record.note, upload_workspace_audit.UploadWorkspaceAudit.DCC_ADMIN_AS_OWNER)

    def test_dcc_admin_shared_as_writer_can_compute(self):
        sharing = WorkspaceGroupSharingFactory.create(
            workspace=self.upload_workspace.workspace,
            group=self.dcc_admin_group,
            access=WorkspaceGroupSharing.WRITER,
            can_compute=True,
        )
        audit = upload_workspace_audit.UploadWorkspaceAudit()
        audit.audit_workspace_and_group(self.upload_workspace, self.dcc_admin_group)
        self.assertEqual(len(audit.verified), 0)
        self.assertEqual(len(audit.needs_action), 1)
        self.assertEqual(len(audit.errors), 0)
        record = audit.needs_action[0]
        self.assertIsInstance(record, upload_workspace_audit.ShareAsOwner)
        self.assertEqual(record.workspace, self.upload_workspace)
        self.assertEqual(record.managed_group, self.dcc_admin_group)
        self.assertEqual(record.current_sharing_instance, sharing)
        self.assertEqual(record.note, upload_workspace_audit.UploadWorkspaceAudit.DCC_ADMIN_AS_OWNER)

    def test_dcc_admin_shared_as_reader(self):
        sharing = WorkspaceGroupSharingFactory.create(
            workspace=self.upload_workspace.workspace, group=self.dcc_admin_group, access=WorkspaceGroupSharing.READER
        )
        audit = upload_workspace_audit.UploadWorkspaceAudit()
        audit.audit_workspace_and_group(self.upload_workspace, self.dcc_admin_group)
        self.assertEqual(len(audit.verified), 0)
        self.assertEqual(len(audit.needs_action), 1)
        self.assertEqual(len(audit.errors), 0)
        record = audit.needs_action[0]
        self.assertIsInstance(record, upload_workspace_audit.ShareAsOwner)
        self.assertEqual(record.workspace, self.upload_workspace)
        self.assertEqual(record.managed_group, self.dcc_admin_group)
        self.assertEqual(record.current_sharing_instance, sharing)
        self.assertEqual(record.note, upload_workspace_audit.UploadWorkspaceAudit.DCC_ADMIN_AS_OWNER)

    def test_dcc_admin_shared_as_owner(self):
        sharing = WorkspaceGroupSharingFactory.create(
            workspace=self.upload_workspace.workspace, group=self.dcc_admin_group, access=WorkspaceGroupSharing.OWNER
        )
        audit = upload_workspace_audit.UploadWorkspaceAudit()
        audit.audit_workspace_and_group(self.upload_workspace, self.dcc_admin_group)
        self.assertEqual(len(audit.verified), 1)
        self.assertEqual(len(audit.needs_action), 0)
        self.assertEqual(len(audit.errors), 0)
        record = audit.verified[0]
        self.assertIsInstance(record, upload_workspace_audit.VerifiedShared)
        self.assertEqual(record.workspace, self.upload_workspace)
        self.assertEqual(record.managed_group, self.dcc_admin_group)
        self.assertEqual(record.current_sharing_instance, sharing)
        self.assertEqual(record.note, upload_workspace_audit.UploadWorkspaceAudit.DCC_ADMIN_AS_OWNER)

    @override_settings(ANVIL_DCC_ADMINS_GROUP_NAME="foo")
    def test_dcc_admin_different_setting(self):
        group = ManagedGroupFactory.create(name="foo")
        sharing = WorkspaceGroupSharingFactory.create(
            workspace=self.upload_workspace.workspace, group=group, access=WorkspaceGroupSharing.OWNER
        )
        audit = upload_workspace_audit.UploadWorkspaceAudit()
        audit.audit_workspace_and_group(self.upload_workspace, group)
        self.assertEqual(len(audit.verified), 1)
        self.assertEqual(len(audit.needs_action), 0)
        self.assertEqual(len(audit.errors), 0)
        record = audit.verified[0]
        self.assertIsInstance(record, upload_workspace_audit.VerifiedShared)
        self.assertEqual(record.workspace, self.upload_workspace)
        self.assertEqual(record.managed_group, group)
        self.assertEqual(record.current_sharing_instance, sharing)
        self.assertEqual(record.note, upload_workspace_audit.UploadWorkspaceAudit.DCC_ADMIN_AS_OWNER)

    def test_anvil_admins_shared_as_writer_no_compute(self):
        # Share the workspace with the group.
        WorkspaceGroupSharingFactory.create(
            workspace=self.upload_workspace.workspace, group=self.anvil_admins, access=WorkspaceGroupSharing.WRITER
        )
        audit = upload_workspace_audit.UploadWorkspaceAudit()
        audit.audit_workspace_and_group(self.upload_workspace, self.anvil_admins)
        self.assertEqual(len(audit.verified), 0)
        self.assertEqual(len(audit.needs_action), 0)
        self.assertEqual(len(audit.errors), 0)

    def test_anvil_admins_not_shared(self):
        audit = upload_workspace_audit.UploadWorkspaceAudit()
        audit.audit_workspace_and_group(self.upload_workspace, self.anvil_admins)
        self.assertEqual(len(audit.verified), 0)
        self.assertEqual(len(audit.needs_action), 0)
        self.assertEqual(len(audit.errors), 0)

    def test_anvil_admins_shared_as_writer_can_compute(self):
        WorkspaceGroupSharingFactory.create(
            workspace=self.upload_workspace.workspace,
            group=self.anvil_admins,
            access=WorkspaceGroupSharing.WRITER,
            can_compute=True,
        )
        audit = upload_workspace_audit.UploadWorkspaceAudit()
        audit.audit_workspace_and_group(self.upload_workspace, self.anvil_admins)
        self.assertEqual(len(audit.verified), 0)
        self.assertEqual(len(audit.needs_action), 0)
        self.assertEqual(len(audit.errors), 0)

    def test_anvil_admins_shared_as_reader(self):
        WorkspaceGroupSharingFactory.create(
            workspace=self.upload_workspace.workspace, group=self.anvil_admins, access=WorkspaceGroupSharing.READER
        )
        audit = upload_workspace_audit.UploadWorkspaceAudit()
        audit.audit_workspace_and_group(self.upload_workspace, self.anvil_admins)
        self.assertEqual(len(audit.verified), 0)
        self.assertEqual(len(audit.needs_action), 0)
        self.assertEqual(len(audit.errors), 0)

    def test_anvil_admins_shared_as_owner(self):
        WorkspaceGroupSharingFactory.create(
            workspace=self.upload_workspace.workspace, group=self.anvil_admins, access=WorkspaceGroupSharing.OWNER
        )
        audit = upload_workspace_audit.UploadWorkspaceAudit()
        audit.audit_workspace_and_group(self.upload_workspace, self.anvil_admins)
        self.assertEqual(len(audit.verified), 0)
        self.assertEqual(len(audit.needs_action), 0)
        self.assertEqual(len(audit.errors), 0)

    def test_anvil_devs_shared_as_writer_no_compute(self):
        # Share the workspace with the group.
        WorkspaceGroupSharingFactory.create(
            workspace=self.upload_workspace.workspace, group=self.anvil_devs, access=WorkspaceGroupSharing.WRITER
        )
        audit = upload_workspace_audit.UploadWorkspaceAudit()
        audit.audit_workspace_and_group(self.upload_workspace, self.anvil_devs)
        self.assertEqual(len(audit.verified), 0)
        self.assertEqual(len(audit.needs_action), 0)
        self.assertEqual(len(audit.errors), 0)

    def test_anvil_devs_not_shared(self):
        audit = upload_workspace_audit.UploadWorkspaceAudit()
        audit.audit_workspace_and_group(self.upload_workspace, self.anvil_devs)
        self.assertEqual(len(audit.verified), 0)
        self.assertEqual(len(audit.needs_action), 0)
        self.assertEqual(len(audit.errors), 0)

    def test_anvil_devs_shared_as_writer_can_compute(self):
        WorkspaceGroupSharingFactory.create(
            workspace=self.upload_workspace.workspace,
            group=self.anvil_devs,
            access=WorkspaceGroupSharing.WRITER,
            can_compute=True,
        )
        audit = upload_workspace_audit.UploadWorkspaceAudit()
        audit.audit_workspace_and_group(self.upload_workspace, self.anvil_devs)
        self.assertEqual(len(audit.verified), 0)
        self.assertEqual(len(audit.needs_action), 0)
        self.assertEqual(len(audit.errors), 0)

    def test_anvil_devs_shared_as_reader(self):
        WorkspaceGroupSharingFactory.create(
            workspace=self.upload_workspace.workspace, group=self.anvil_devs, access=WorkspaceGroupSharing.READER
        )
        audit = upload_workspace_audit.UploadWorkspaceAudit()
        audit.audit_workspace_and_group(self.upload_workspace, self.anvil_devs)
        self.assertEqual(len(audit.verified), 0)
        self.assertEqual(len(audit.needs_action), 0)
        self.assertEqual(len(audit.errors), 0)

    def test_anvil_devs_shared_as_owner(self):
        WorkspaceGroupSharingFactory.create(
            workspace=self.upload_workspace.workspace, group=self.anvil_devs, access=WorkspaceGroupSharing.OWNER
        )
        audit = upload_workspace_audit.UploadWorkspaceAudit()
        audit.audit_workspace_and_group(self.upload_workspace, self.anvil_devs)
        self.assertEqual(len(audit.verified), 0)
        self.assertEqual(len(audit.needs_action), 0)
        self.assertEqual(len(audit.errors), 0)

    def test_other_group_shared_as_writer_no_compute(self):
        # Share the workspace with the group.
        sharing = WorkspaceGroupSharingFactory.create(
            workspace=self.upload_workspace.workspace, group=self.other_group, access=WorkspaceGroupSharing.WRITER
        )
        audit = upload_workspace_audit.UploadWorkspaceAudit()
        audit.audit_workspace_and_group(self.upload_workspace, self.other_group)
        self.assertEqual(len(audit.verified), 0)
        self.assertEqual(len(audit.needs_action), 0)
        self.assertEqual(len(audit.errors), 1)
        record = audit.errors[0]
        self.assertIsInstance(record, upload_workspace_audit.StopSharing)
        self.assertEqual(record.workspace, self.upload_workspace)
        self.assertEqual(record.managed_group, self.other_group)
        self.assertEqual(record.current_sharing_instance, sharing)
        self.assertEqual(record.note, upload_workspace_audit.UploadWorkspaceAudit.OTHER_GROUP_NO_ACCESS)

    def test_other_group_not_shared(self):
        audit = upload_workspace_audit.UploadWorkspaceAudit()
        audit.audit_workspace_and_group(self.upload_workspace, self.other_group)
        self.assertEqual(len(audit.verified), 1)
        self.assertEqual(len(audit.needs_action), 0)
        self.assertEqual(len(audit.errors), 0)
        record = audit.verified[0]
        self.assertIsInstance(record, upload_workspace_audit.VerifiedNotShared)
        self.assertEqual(record.workspace, self.upload_workspace)
        self.assertEqual(record.managed_group, self.other_group)
        self.assertEqual(record.current_sharing_instance, None)
        self.assertEqual(record.note, upload_workspace_audit.UploadWorkspaceAudit.OTHER_GROUP_NO_ACCESS)

    def test_other_group_shared_as_writer_can_compute(self):
        sharing = WorkspaceGroupSharingFactory.create(
            workspace=self.upload_workspace.workspace,
            group=self.other_group,
            access=WorkspaceGroupSharing.WRITER,
            can_compute=True,
        )
        audit = upload_workspace_audit.UploadWorkspaceAudit()
        audit.audit_workspace_and_group(self.upload_workspace, self.other_group)
        self.assertEqual(len(audit.verified), 0)
        self.assertEqual(len(audit.needs_action), 0)
        self.assertEqual(len(audit.errors), 1)
        record = audit.errors[0]
        self.assertIsInstance(record, upload_workspace_audit.StopSharing)
        self.assertEqual(record.workspace, self.upload_workspace)
        self.assertEqual(record.managed_group, self.other_group)
        self.assertEqual(record.current_sharing_instance, sharing)
        self.assertEqual(record.note, upload_workspace_audit.UploadWorkspaceAudit.OTHER_GROUP_NO_ACCESS)

    def test_other_group_shared_as_reader(self):
        sharing = WorkspaceGroupSharingFactory.create(
            workspace=self.upload_workspace.workspace, group=self.other_group, access=WorkspaceGroupSharing.READER
        )
        audit = upload_workspace_audit.UploadWorkspaceAudit()
        audit.audit_workspace_and_group(self.upload_workspace, self.other_group)
        self.assertEqual(len(audit.verified), 0)
        self.assertEqual(len(audit.needs_action), 0)
        self.assertEqual(len(audit.errors), 1)
        record = audit.errors[0]
        self.assertIsInstance(record, upload_workspace_audit.StopSharing)
        self.assertEqual(record.workspace, self.upload_workspace)
        self.assertEqual(record.managed_group, self.other_group)
        self.assertEqual(record.current_sharing_instance, sharing)
        self.assertEqual(record.note, upload_workspace_audit.UploadWorkspaceAudit.OTHER_GROUP_NO_ACCESS)

    def test_other_group_shared_as_owner(self):
        sharing = WorkspaceGroupSharingFactory.create(
            workspace=self.upload_workspace.workspace, group=self.other_group, access=WorkspaceGroupSharing.OWNER
        )
        audit = upload_workspace_audit.UploadWorkspaceAudit()
        audit.audit_workspace_and_group(self.upload_workspace, self.other_group)
        self.assertEqual(len(audit.verified), 0)
        self.assertEqual(len(audit.needs_action), 0)
        self.assertEqual(len(audit.errors), 1)
        record = audit.errors[0]
        self.assertIsInstance(record, upload_workspace_audit.StopSharing)
        self.assertEqual(record.workspace, self.upload_workspace)
        self.assertEqual(record.managed_group, self.other_group)
        self.assertEqual(record.current_sharing_instance, sharing)
        self.assertEqual(record.note, upload_workspace_audit.UploadWorkspaceAudit.OTHER_GROUP_NO_ACCESS)


class UploadWorkspaceAuditCurrentCycleAfterComputeTest(TestCase):
    """Tests for the `UploadWorkspaceAudit` class for current cycle UploadWorkspaces after compute is enabled.

    Expectations at this point in the upload cycle:
    - RC uploader group should be writers with compute.
    - DCC writer group should be writers with compute.
    """

    def setUp(self):
        super().setUp()
        self.dcc_admin_group = ManagedGroupFactory.create(name=settings.ANVIL_DCC_ADMINS_GROUP_NAME)
        self.dcc_writer_group = ManagedGroupFactory.create(name="GREGOR_DCC_WRITERS")
        self.rc_uploader_group = ManagedGroupFactory.create()
        self.research_center = factories.ResearchCenterFactory.create(uploader_group=self.rc_uploader_group)
        self.upload_workspace = factories.UploadWorkspaceFactory.create(
            research_center=self.research_center,
            upload_cycle__is_current=True,
        )
        # Set date ready for compute to a non-null value.
        self.upload_workspace.upload_cycle.date_ready_for_compute = self.upload_workspace.upload_cycle.start_date
        self.upload_workspace.upload_cycle.save()
        self.auth_domain = self.upload_workspace.workspace.authorization_domains.get()
        self.other_group = ManagedGroupFactory.create()
        self.anvil_admins = ManagedGroupFactory.create(name="anvil-admins")
        self.anvil_devs = ManagedGroupFactory.create(name="anvil_devs")

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

    def test_auth_domain_shared_as_writer_no_compute(self):
        # Share the workspace with the group.
        sharing = WorkspaceGroupSharingFactory.create(
            workspace=self.upload_workspace.workspace, group=self.auth_domain, access=WorkspaceGroupSharing.WRITER
        )
        audit = upload_workspace_audit.UploadWorkspaceAudit()
        audit.audit_workspace_and_group(self.upload_workspace, self.auth_domain)
        self.assertEqual(len(audit.verified), 0)
        self.assertEqual(len(audit.needs_action), 1)
        self.assertEqual(len(audit.errors), 0)
        record = audit.needs_action[0]
        self.assertIsInstance(record, upload_workspace_audit.ShareAsReader)
        self.assertEqual(record.workspace, self.upload_workspace)
        self.assertEqual(record.managed_group, self.auth_domain)
        self.assertEqual(record.current_sharing_instance, sharing)
        self.assertEqual(record.note, upload_workspace_audit.UploadWorkspaceAudit.AUTH_DOMAIN_AS_READER)

    def test_auth_domain_not_shared(self):
        audit = upload_workspace_audit.UploadWorkspaceAudit()
        audit.audit_workspace_and_group(self.upload_workspace, self.auth_domain)
        self.assertEqual(len(audit.verified), 0)
        self.assertEqual(len(audit.needs_action), 1)
        self.assertEqual(len(audit.errors), 0)
        record = audit.needs_action[0]
        self.assertIsInstance(record, upload_workspace_audit.ShareAsReader)
        self.assertEqual(record.workspace, self.upload_workspace)
        self.assertEqual(record.managed_group, self.auth_domain)
        self.assertEqual(record.current_sharing_instance, None)
        self.assertEqual(record.note, upload_workspace_audit.UploadWorkspaceAudit.AUTH_DOMAIN_AS_READER)

    def test_auth_domain_shared_as_writer_can_compute(self):
        sharing = WorkspaceGroupSharingFactory.create(
            workspace=self.upload_workspace.workspace,
            group=self.auth_domain,
            access=WorkspaceGroupSharing.WRITER,
            can_compute=True,
        )
        audit = upload_workspace_audit.UploadWorkspaceAudit()
        audit.audit_workspace_and_group(self.upload_workspace, self.auth_domain)
        self.assertEqual(len(audit.verified), 0)
        self.assertEqual(len(audit.needs_action), 1)
        self.assertEqual(len(audit.errors), 0)
        record = audit.needs_action[0]
        self.assertIsInstance(record, upload_workspace_audit.ShareAsReader)
        self.assertEqual(record.workspace, self.upload_workspace)
        self.assertEqual(record.managed_group, self.auth_domain)
        self.assertEqual(record.current_sharing_instance, sharing)
        self.assertEqual(record.note, upload_workspace_audit.UploadWorkspaceAudit.AUTH_DOMAIN_AS_READER)

    def test_auth_domain_shared_as_reader(self):
        sharing = WorkspaceGroupSharingFactory.create(
            workspace=self.upload_workspace.workspace, group=self.auth_domain, access=WorkspaceGroupSharing.READER
        )
        audit = upload_workspace_audit.UploadWorkspaceAudit()
        audit.audit_workspace_and_group(self.upload_workspace, self.auth_domain)
        self.assertEqual(len(audit.verified), 1)
        self.assertEqual(len(audit.needs_action), 0)
        self.assertEqual(len(audit.errors), 0)
        record = audit.verified[0]
        self.assertIsInstance(record, upload_workspace_audit.VerifiedShared)
        self.assertEqual(record.workspace, self.upload_workspace)
        self.assertEqual(record.managed_group, self.auth_domain)
        self.assertEqual(record.current_sharing_instance, sharing)
        self.assertEqual(record.note, upload_workspace_audit.UploadWorkspaceAudit.AUTH_DOMAIN_AS_READER)

    def test_auth_domain_shared_as_owner(self):
        sharing = WorkspaceGroupSharingFactory.create(
            workspace=self.upload_workspace.workspace, group=self.auth_domain, access=WorkspaceGroupSharing.OWNER
        )
        audit = upload_workspace_audit.UploadWorkspaceAudit()
        audit.audit_workspace_and_group(self.upload_workspace, self.auth_domain)
        self.assertEqual(len(audit.verified), 0)
        self.assertEqual(len(audit.needs_action), 1)
        self.assertEqual(len(audit.errors), 0)
        record = audit.needs_action[0]
        self.assertIsInstance(record, upload_workspace_audit.ShareAsReader)
        self.assertEqual(record.workspace, self.upload_workspace)
        self.assertEqual(record.managed_group, self.auth_domain)
        self.assertEqual(record.current_sharing_instance, sharing)
        self.assertEqual(record.note, upload_workspace_audit.UploadWorkspaceAudit.AUTH_DOMAIN_AS_READER)

    def test_dcc_admin_shared_as_writer_no_compute(self):
        # Share the workspace with the group.
        sharing = WorkspaceGroupSharingFactory.create(
            workspace=self.upload_workspace.workspace, group=self.dcc_admin_group, access=WorkspaceGroupSharing.WRITER
        )
        audit = upload_workspace_audit.UploadWorkspaceAudit()
        audit.audit_workspace_and_group(self.upload_workspace, self.dcc_admin_group)
        self.assertEqual(len(audit.verified), 0)
        self.assertEqual(len(audit.needs_action), 1)
        self.assertEqual(len(audit.errors), 0)
        record = audit.needs_action[0]
        self.assertIsInstance(record, upload_workspace_audit.ShareAsOwner)
        self.assertEqual(record.workspace, self.upload_workspace)
        self.assertEqual(record.managed_group, self.dcc_admin_group)
        self.assertEqual(record.current_sharing_instance, sharing)
        self.assertEqual(record.note, upload_workspace_audit.UploadWorkspaceAudit.DCC_ADMIN_AS_OWNER)

    def test_dcc_admin_not_shared(self):
        audit = upload_workspace_audit.UploadWorkspaceAudit()
        audit.audit_workspace_and_group(self.upload_workspace, self.dcc_admin_group)
        self.assertEqual(len(audit.verified), 0)
        self.assertEqual(len(audit.needs_action), 1)
        self.assertEqual(len(audit.errors), 0)
        record = audit.needs_action[0]
        self.assertIsInstance(record, upload_workspace_audit.ShareAsOwner)
        self.assertEqual(record.workspace, self.upload_workspace)
        self.assertEqual(record.managed_group, self.dcc_admin_group)
        self.assertEqual(record.current_sharing_instance, None)
        self.assertEqual(record.note, upload_workspace_audit.UploadWorkspaceAudit.DCC_ADMIN_AS_OWNER)

    def test_dcc_admin_shared_as_writer_can_compute(self):
        sharing = WorkspaceGroupSharingFactory.create(
            workspace=self.upload_workspace.workspace,
            group=self.dcc_admin_group,
            access=WorkspaceGroupSharing.WRITER,
            can_compute=True,
        )
        audit = upload_workspace_audit.UploadWorkspaceAudit()
        audit.audit_workspace_and_group(self.upload_workspace, self.dcc_admin_group)
        self.assertEqual(len(audit.verified), 0)
        self.assertEqual(len(audit.needs_action), 1)
        self.assertEqual(len(audit.errors), 0)
        record = audit.needs_action[0]
        self.assertIsInstance(record, upload_workspace_audit.ShareAsOwner)
        self.assertEqual(record.workspace, self.upload_workspace)
        self.assertEqual(record.managed_group, self.dcc_admin_group)
        self.assertEqual(record.current_sharing_instance, sharing)
        self.assertEqual(record.note, upload_workspace_audit.UploadWorkspaceAudit.DCC_ADMIN_AS_OWNER)

    def test_dcc_admin_shared_as_reader(self):
        sharing = WorkspaceGroupSharingFactory.create(
            workspace=self.upload_workspace.workspace, group=self.dcc_admin_group, access=WorkspaceGroupSharing.READER
        )
        audit = upload_workspace_audit.UploadWorkspaceAudit()
        audit.audit_workspace_and_group(self.upload_workspace, self.dcc_admin_group)
        self.assertEqual(len(audit.verified), 0)
        self.assertEqual(len(audit.needs_action), 1)
        self.assertEqual(len(audit.errors), 0)
        record = audit.needs_action[0]
        self.assertIsInstance(record, upload_workspace_audit.ShareAsOwner)
        self.assertEqual(record.workspace, self.upload_workspace)
        self.assertEqual(record.managed_group, self.dcc_admin_group)
        self.assertEqual(record.current_sharing_instance, sharing)
        self.assertEqual(record.note, upload_workspace_audit.UploadWorkspaceAudit.DCC_ADMIN_AS_OWNER)

    def test_dcc_admin_shared_as_owner(self):
        sharing = WorkspaceGroupSharingFactory.create(
            workspace=self.upload_workspace.workspace, group=self.dcc_admin_group, access=WorkspaceGroupSharing.OWNER
        )
        audit = upload_workspace_audit.UploadWorkspaceAudit()
        audit.audit_workspace_and_group(self.upload_workspace, self.dcc_admin_group)
        self.assertEqual(len(audit.verified), 1)
        self.assertEqual(len(audit.needs_action), 0)
        self.assertEqual(len(audit.errors), 0)
        record = audit.verified[0]
        self.assertIsInstance(record, upload_workspace_audit.VerifiedShared)
        self.assertEqual(record.workspace, self.upload_workspace)
        self.assertEqual(record.managed_group, self.dcc_admin_group)
        self.assertEqual(record.current_sharing_instance, sharing)
        self.assertEqual(record.note, upload_workspace_audit.UploadWorkspaceAudit.DCC_ADMIN_AS_OWNER)

    @override_settings(ANVIL_DCC_ADMINS_GROUP_NAME="foo")
    def test_dcc_admin_different_setting(self):
        group = ManagedGroupFactory.create(name="foo")
        sharing = WorkspaceGroupSharingFactory.create(
            workspace=self.upload_workspace.workspace, group=group, access=WorkspaceGroupSharing.OWNER
        )
        audit = upload_workspace_audit.UploadWorkspaceAudit()
        audit.audit_workspace_and_group(self.upload_workspace, group)
        self.assertEqual(len(audit.verified), 1)
        self.assertEqual(len(audit.needs_action), 0)
        self.assertEqual(len(audit.errors), 0)
        record = audit.verified[0]
        self.assertIsInstance(record, upload_workspace_audit.VerifiedShared)
        self.assertEqual(record.workspace, self.upload_workspace)
        self.assertEqual(record.managed_group, group)
        self.assertEqual(record.current_sharing_instance, sharing)
        self.assertEqual(record.note, upload_workspace_audit.UploadWorkspaceAudit.DCC_ADMIN_AS_OWNER)

    def test_anvil_admins_shared_as_writer_no_compute(self):
        # Share the workspace with the group.
        WorkspaceGroupSharingFactory.create(
            workspace=self.upload_workspace.workspace, group=self.anvil_admins, access=WorkspaceGroupSharing.WRITER
        )
        audit = upload_workspace_audit.UploadWorkspaceAudit()
        audit.audit_workspace_and_group(self.upload_workspace, self.anvil_admins)
        self.assertEqual(len(audit.verified), 0)
        self.assertEqual(len(audit.needs_action), 0)
        self.assertEqual(len(audit.errors), 0)

    def test_anvil_admins_not_shared(self):
        audit = upload_workspace_audit.UploadWorkspaceAudit()
        audit.audit_workspace_and_group(self.upload_workspace, self.anvil_admins)
        self.assertEqual(len(audit.verified), 0)
        self.assertEqual(len(audit.needs_action), 0)
        self.assertEqual(len(audit.errors), 0)

    def test_anvil_admins_shared_as_writer_can_compute(self):
        WorkspaceGroupSharingFactory.create(
            workspace=self.upload_workspace.workspace,
            group=self.anvil_admins,
            access=WorkspaceGroupSharing.WRITER,
            can_compute=True,
        )
        audit = upload_workspace_audit.UploadWorkspaceAudit()
        audit.audit_workspace_and_group(self.upload_workspace, self.anvil_admins)
        self.assertEqual(len(audit.verified), 0)
        self.assertEqual(len(audit.needs_action), 0)
        self.assertEqual(len(audit.errors), 0)

    def test_anvil_admins_shared_as_reader(self):
        WorkspaceGroupSharingFactory.create(
            workspace=self.upload_workspace.workspace, group=self.anvil_admins, access=WorkspaceGroupSharing.READER
        )
        audit = upload_workspace_audit.UploadWorkspaceAudit()
        audit.audit_workspace_and_group(self.upload_workspace, self.anvil_admins)
        self.assertEqual(len(audit.verified), 0)
        self.assertEqual(len(audit.needs_action), 0)
        self.assertEqual(len(audit.errors), 0)

    def test_anvil_admins_shared_as_owner(self):
        WorkspaceGroupSharingFactory.create(
            workspace=self.upload_workspace.workspace, group=self.anvil_admins, access=WorkspaceGroupSharing.OWNER
        )
        audit = upload_workspace_audit.UploadWorkspaceAudit()
        audit.audit_workspace_and_group(self.upload_workspace, self.anvil_admins)
        self.assertEqual(len(audit.verified), 0)
        self.assertEqual(len(audit.needs_action), 0)
        self.assertEqual(len(audit.errors), 0)

    def test_anvil_devs_shared_as_writer_no_compute(self):
        # Share the workspace with the group.
        WorkspaceGroupSharingFactory.create(
            workspace=self.upload_workspace.workspace, group=self.anvil_devs, access=WorkspaceGroupSharing.WRITER
        )
        audit = upload_workspace_audit.UploadWorkspaceAudit()
        audit.audit_workspace_and_group(self.upload_workspace, self.anvil_devs)
        self.assertEqual(len(audit.verified), 0)
        self.assertEqual(len(audit.needs_action), 0)
        self.assertEqual(len(audit.errors), 0)

    def test_anvil_devs_not_shared(self):
        audit = upload_workspace_audit.UploadWorkspaceAudit()
        audit.audit_workspace_and_group(self.upload_workspace, self.anvil_devs)
        self.assertEqual(len(audit.verified), 0)
        self.assertEqual(len(audit.needs_action), 0)
        self.assertEqual(len(audit.errors), 0)

    def test_anvil_devs_shared_as_writer_can_compute(self):
        WorkspaceGroupSharingFactory.create(
            workspace=self.upload_workspace.workspace,
            group=self.anvil_devs,
            access=WorkspaceGroupSharing.WRITER,
            can_compute=True,
        )
        audit = upload_workspace_audit.UploadWorkspaceAudit()
        audit.audit_workspace_and_group(self.upload_workspace, self.anvil_devs)
        self.assertEqual(len(audit.verified), 0)
        self.assertEqual(len(audit.needs_action), 0)
        self.assertEqual(len(audit.errors), 0)

    def test_anvil_devs_shared_as_reader(self):
        WorkspaceGroupSharingFactory.create(
            workspace=self.upload_workspace.workspace, group=self.anvil_devs, access=WorkspaceGroupSharing.READER
        )
        audit = upload_workspace_audit.UploadWorkspaceAudit()
        audit.audit_workspace_and_group(self.upload_workspace, self.anvil_devs)
        self.assertEqual(len(audit.verified), 0)
        self.assertEqual(len(audit.needs_action), 0)
        self.assertEqual(len(audit.errors), 0)

    def test_anvil_devs_shared_as_owner(self):
        WorkspaceGroupSharingFactory.create(
            workspace=self.upload_workspace.workspace, group=self.anvil_devs, access=WorkspaceGroupSharing.OWNER
        )
        audit = upload_workspace_audit.UploadWorkspaceAudit()
        audit.audit_workspace_and_group(self.upload_workspace, self.anvil_devs)
        self.assertEqual(len(audit.verified), 0)
        self.assertEqual(len(audit.needs_action), 0)
        self.assertEqual(len(audit.errors), 0)

    def test_other_group_shared_as_writer_no_compute(self):
        # Share the workspace with the group.
        sharing = WorkspaceGroupSharingFactory.create(
            workspace=self.upload_workspace.workspace, group=self.other_group, access=WorkspaceGroupSharing.WRITER
        )
        audit = upload_workspace_audit.UploadWorkspaceAudit()
        audit.audit_workspace_and_group(self.upload_workspace, self.other_group)
        self.assertEqual(len(audit.verified), 0)
        self.assertEqual(len(audit.needs_action), 0)
        self.assertEqual(len(audit.errors), 1)
        record = audit.errors[0]
        self.assertIsInstance(record, upload_workspace_audit.StopSharing)
        self.assertEqual(record.workspace, self.upload_workspace)
        self.assertEqual(record.managed_group, self.other_group)
        self.assertEqual(record.current_sharing_instance, sharing)
        self.assertEqual(record.note, upload_workspace_audit.UploadWorkspaceAudit.OTHER_GROUP_NO_ACCESS)

    def test_other_group_not_shared(self):
        audit = upload_workspace_audit.UploadWorkspaceAudit()
        audit.audit_workspace_and_group(self.upload_workspace, self.other_group)
        self.assertEqual(len(audit.verified), 1)
        self.assertEqual(len(audit.needs_action), 0)
        self.assertEqual(len(audit.errors), 0)
        record = audit.verified[0]
        self.assertIsInstance(record, upload_workspace_audit.VerifiedNotShared)
        self.assertEqual(record.workspace, self.upload_workspace)
        self.assertEqual(record.managed_group, self.other_group)
        self.assertEqual(record.current_sharing_instance, None)
        self.assertEqual(record.note, upload_workspace_audit.UploadWorkspaceAudit.OTHER_GROUP_NO_ACCESS)

    def test_other_group_shared_as_writer_can_compute(self):
        sharing = WorkspaceGroupSharingFactory.create(
            workspace=self.upload_workspace.workspace,
            group=self.other_group,
            access=WorkspaceGroupSharing.WRITER,
            can_compute=True,
        )
        audit = upload_workspace_audit.UploadWorkspaceAudit()
        audit.audit_workspace_and_group(self.upload_workspace, self.other_group)
        self.assertEqual(len(audit.verified), 0)
        self.assertEqual(len(audit.needs_action), 0)
        self.assertEqual(len(audit.errors), 1)
        record = audit.errors[0]
        self.assertIsInstance(record, upload_workspace_audit.StopSharing)
        self.assertEqual(record.workspace, self.upload_workspace)
        self.assertEqual(record.managed_group, self.other_group)
        self.assertEqual(record.current_sharing_instance, sharing)
        self.assertEqual(record.note, upload_workspace_audit.UploadWorkspaceAudit.OTHER_GROUP_NO_ACCESS)

    def test_other_group_shared_as_reader(self):
        sharing = WorkspaceGroupSharingFactory.create(
            workspace=self.upload_workspace.workspace, group=self.other_group, access=WorkspaceGroupSharing.READER
        )
        audit = upload_workspace_audit.UploadWorkspaceAudit()
        audit.audit_workspace_and_group(self.upload_workspace, self.other_group)
        self.assertEqual(len(audit.verified), 0)
        self.assertEqual(len(audit.needs_action), 0)
        self.assertEqual(len(audit.errors), 1)
        record = audit.errors[0]
        self.assertIsInstance(record, upload_workspace_audit.StopSharing)
        self.assertEqual(record.workspace, self.upload_workspace)
        self.assertEqual(record.managed_group, self.other_group)
        self.assertEqual(record.current_sharing_instance, sharing)
        self.assertEqual(record.note, upload_workspace_audit.UploadWorkspaceAudit.OTHER_GROUP_NO_ACCESS)

    def test_other_group_shared_as_owner(self):
        sharing = WorkspaceGroupSharingFactory.create(
            workspace=self.upload_workspace.workspace, group=self.other_group, access=WorkspaceGroupSharing.OWNER
        )
        audit = upload_workspace_audit.UploadWorkspaceAudit()
        audit.audit_workspace_and_group(self.upload_workspace, self.other_group)
        self.assertEqual(len(audit.verified), 0)
        self.assertEqual(len(audit.needs_action), 0)
        self.assertEqual(len(audit.errors), 1)
        record = audit.errors[0]
        self.assertIsInstance(record, upload_workspace_audit.StopSharing)
        self.assertEqual(record.workspace, self.upload_workspace)
        self.assertEqual(record.managed_group, self.other_group)
        self.assertEqual(record.current_sharing_instance, sharing)
        self.assertEqual(record.note, upload_workspace_audit.UploadWorkspaceAudit.OTHER_GROUP_NO_ACCESS)


class UploadWorkspaceAuditPastCycleBeforeQCCompleteTest(TestCase):
    """Tests for the `UploadWorkspaceAudit` class for past cycles before QC is complete.

    Expectations at this point in the upload cycle:
    - RC uploader group should not have direct access.
    - DCC writer group should not have direct access.
    """

    def setUp(self):
        super().setUp()
        self.dcc_admin_group = ManagedGroupFactory.create(name=settings.ANVIL_DCC_ADMINS_GROUP_NAME)
        self.dcc_writer_group = ManagedGroupFactory.create(name="GREGOR_DCC_WRITERS")
        self.rc_uploader_group = ManagedGroupFactory.create()
        self.research_center = factories.ResearchCenterFactory.create(uploader_group=self.rc_uploader_group)
        self.upload_workspace = factories.UploadWorkspaceFactory.create(
            research_center=self.research_center,
            upload_cycle__is_past=True,
        )
        self.auth_domain = self.upload_workspace.workspace.authorization_domains.get()
        self.other_group = ManagedGroupFactory.create()
        self.anvil_admins = ManagedGroupFactory.create(name="anvil-admins")
        self.anvil_devs = ManagedGroupFactory.create(name="anvil_devs")

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
            record.note, upload_workspace_audit.UploadWorkspaceAudit.RC_UPLOADERS_PAST_CYCLE_BEFORE_QC_COMPLETE
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
        self.assertIsInstance(record, upload_workspace_audit.StopSharing)
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
        self.assertEqual(len(audit.verified), 0)
        self.assertEqual(len(audit.needs_action), 1)
        self.assertEqual(len(audit.errors), 0)
        record = audit.needs_action[0]
        self.assertIsInstance(record, upload_workspace_audit.StopSharing)
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
        self.assertIsInstance(record, upload_workspace_audit.StopSharing)
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

    def test_auth_domain_shared_as_writer_no_compute(self):
        # Share the workspace with the group.
        sharing = WorkspaceGroupSharingFactory.create(
            workspace=self.upload_workspace.workspace, group=self.auth_domain, access=WorkspaceGroupSharing.WRITER
        )
        audit = upload_workspace_audit.UploadWorkspaceAudit()
        audit.audit_workspace_and_group(self.upload_workspace, self.auth_domain)
        self.assertEqual(len(audit.verified), 0)
        self.assertEqual(len(audit.needs_action), 1)
        self.assertEqual(len(audit.errors), 0)
        record = audit.needs_action[0]
        self.assertIsInstance(record, upload_workspace_audit.ShareAsReader)
        self.assertEqual(record.workspace, self.upload_workspace)
        self.assertEqual(record.managed_group, self.auth_domain)
        self.assertEqual(record.current_sharing_instance, sharing)
        self.assertEqual(record.note, upload_workspace_audit.UploadWorkspaceAudit.AUTH_DOMAIN_AS_READER)

    def test_auth_domain_not_shared(self):
        audit = upload_workspace_audit.UploadWorkspaceAudit()
        audit.audit_workspace_and_group(self.upload_workspace, self.auth_domain)
        self.assertEqual(len(audit.verified), 0)
        self.assertEqual(len(audit.needs_action), 1)
        self.assertEqual(len(audit.errors), 0)
        record = audit.needs_action[0]
        self.assertIsInstance(record, upload_workspace_audit.ShareAsReader)
        self.assertEqual(record.workspace, self.upload_workspace)
        self.assertEqual(record.managed_group, self.auth_domain)
        self.assertEqual(record.current_sharing_instance, None)
        self.assertEqual(record.note, upload_workspace_audit.UploadWorkspaceAudit.AUTH_DOMAIN_AS_READER)

    def test_auth_domain_shared_as_writer_can_compute(self):
        sharing = WorkspaceGroupSharingFactory.create(
            workspace=self.upload_workspace.workspace,
            group=self.auth_domain,
            access=WorkspaceGroupSharing.WRITER,
            can_compute=True,
        )
        audit = upload_workspace_audit.UploadWorkspaceAudit()
        audit.audit_workspace_and_group(self.upload_workspace, self.auth_domain)
        self.assertEqual(len(audit.verified), 0)
        self.assertEqual(len(audit.needs_action), 1)
        self.assertEqual(len(audit.errors), 0)
        record = audit.needs_action[0]
        self.assertIsInstance(record, upload_workspace_audit.ShareAsReader)
        self.assertEqual(record.workspace, self.upload_workspace)
        self.assertEqual(record.managed_group, self.auth_domain)
        self.assertEqual(record.current_sharing_instance, sharing)
        self.assertEqual(record.note, upload_workspace_audit.UploadWorkspaceAudit.AUTH_DOMAIN_AS_READER)

    def test_auth_domain_shared_as_reader(self):
        sharing = WorkspaceGroupSharingFactory.create(
            workspace=self.upload_workspace.workspace, group=self.auth_domain, access=WorkspaceGroupSharing.READER
        )
        audit = upload_workspace_audit.UploadWorkspaceAudit()
        audit.audit_workspace_and_group(self.upload_workspace, self.auth_domain)
        self.assertEqual(len(audit.verified), 1)
        self.assertEqual(len(audit.needs_action), 0)
        self.assertEqual(len(audit.errors), 0)
        record = audit.verified[0]
        self.assertIsInstance(record, upload_workspace_audit.VerifiedShared)
        self.assertEqual(record.workspace, self.upload_workspace)
        self.assertEqual(record.managed_group, self.auth_domain)
        self.assertEqual(record.current_sharing_instance, sharing)
        self.assertEqual(record.note, upload_workspace_audit.UploadWorkspaceAudit.AUTH_DOMAIN_AS_READER)

    def test_auth_domain_shared_as_owner(self):
        sharing = WorkspaceGroupSharingFactory.create(
            workspace=self.upload_workspace.workspace, group=self.auth_domain, access=WorkspaceGroupSharing.OWNER
        )
        audit = upload_workspace_audit.UploadWorkspaceAudit()
        audit.audit_workspace_and_group(self.upload_workspace, self.auth_domain)
        self.assertEqual(len(audit.verified), 0)
        self.assertEqual(len(audit.needs_action), 1)
        self.assertEqual(len(audit.errors), 0)
        record = audit.needs_action[0]
        self.assertIsInstance(record, upload_workspace_audit.ShareAsReader)
        self.assertEqual(record.workspace, self.upload_workspace)
        self.assertEqual(record.managed_group, self.auth_domain)
        self.assertEqual(record.current_sharing_instance, sharing)
        self.assertEqual(record.note, upload_workspace_audit.UploadWorkspaceAudit.AUTH_DOMAIN_AS_READER)

    def test_dcc_admin_shared_as_writer_no_compute(self):
        # Share the workspace with the group.
        sharing = WorkspaceGroupSharingFactory.create(
            workspace=self.upload_workspace.workspace, group=self.dcc_admin_group, access=WorkspaceGroupSharing.WRITER
        )
        audit = upload_workspace_audit.UploadWorkspaceAudit()
        audit.audit_workspace_and_group(self.upload_workspace, self.dcc_admin_group)
        self.assertEqual(len(audit.verified), 0)
        self.assertEqual(len(audit.needs_action), 1)
        self.assertEqual(len(audit.errors), 0)
        record = audit.needs_action[0]
        self.assertIsInstance(record, upload_workspace_audit.ShareAsOwner)
        self.assertEqual(record.workspace, self.upload_workspace)
        self.assertEqual(record.managed_group, self.dcc_admin_group)
        self.assertEqual(record.current_sharing_instance, sharing)
        self.assertEqual(record.note, upload_workspace_audit.UploadWorkspaceAudit.DCC_ADMIN_AS_OWNER)

    def test_dcc_admin_not_shared(self):
        audit = upload_workspace_audit.UploadWorkspaceAudit()
        audit.audit_workspace_and_group(self.upload_workspace, self.dcc_admin_group)
        self.assertEqual(len(audit.verified), 0)
        self.assertEqual(len(audit.needs_action), 1)
        self.assertEqual(len(audit.errors), 0)
        record = audit.needs_action[0]
        self.assertIsInstance(record, upload_workspace_audit.ShareAsOwner)
        self.assertEqual(record.workspace, self.upload_workspace)
        self.assertEqual(record.managed_group, self.dcc_admin_group)
        self.assertEqual(record.current_sharing_instance, None)
        self.assertEqual(record.note, upload_workspace_audit.UploadWorkspaceAudit.DCC_ADMIN_AS_OWNER)

    def test_dcc_admin_shared_as_writer_can_compute(self):
        sharing = WorkspaceGroupSharingFactory.create(
            workspace=self.upload_workspace.workspace,
            group=self.dcc_admin_group,
            access=WorkspaceGroupSharing.WRITER,
            can_compute=True,
        )
        audit = upload_workspace_audit.UploadWorkspaceAudit()
        audit.audit_workspace_and_group(self.upload_workspace, self.dcc_admin_group)
        self.assertEqual(len(audit.verified), 0)
        self.assertEqual(len(audit.needs_action), 1)
        self.assertEqual(len(audit.errors), 0)
        record = audit.needs_action[0]
        self.assertIsInstance(record, upload_workspace_audit.ShareAsOwner)
        self.assertEqual(record.workspace, self.upload_workspace)
        self.assertEqual(record.managed_group, self.dcc_admin_group)
        self.assertEqual(record.current_sharing_instance, sharing)
        self.assertEqual(record.note, upload_workspace_audit.UploadWorkspaceAudit.DCC_ADMIN_AS_OWNER)

    def test_dcc_admin_shared_as_reader(self):
        sharing = WorkspaceGroupSharingFactory.create(
            workspace=self.upload_workspace.workspace, group=self.dcc_admin_group, access=WorkspaceGroupSharing.READER
        )
        audit = upload_workspace_audit.UploadWorkspaceAudit()
        audit.audit_workspace_and_group(self.upload_workspace, self.dcc_admin_group)
        self.assertEqual(len(audit.verified), 0)
        self.assertEqual(len(audit.needs_action), 1)
        self.assertEqual(len(audit.errors), 0)
        record = audit.needs_action[0]
        self.assertIsInstance(record, upload_workspace_audit.ShareAsOwner)
        self.assertEqual(record.workspace, self.upload_workspace)
        self.assertEqual(record.managed_group, self.dcc_admin_group)
        self.assertEqual(record.current_sharing_instance, sharing)
        self.assertEqual(record.note, upload_workspace_audit.UploadWorkspaceAudit.DCC_ADMIN_AS_OWNER)

    def test_dcc_admin_shared_as_owner(self):
        sharing = WorkspaceGroupSharingFactory.create(
            workspace=self.upload_workspace.workspace, group=self.dcc_admin_group, access=WorkspaceGroupSharing.OWNER
        )
        audit = upload_workspace_audit.UploadWorkspaceAudit()
        audit.audit_workspace_and_group(self.upload_workspace, self.dcc_admin_group)
        self.assertEqual(len(audit.verified), 1)
        self.assertEqual(len(audit.needs_action), 0)
        self.assertEqual(len(audit.errors), 0)
        record = audit.verified[0]
        self.assertIsInstance(record, upload_workspace_audit.VerifiedShared)
        self.assertEqual(record.workspace, self.upload_workspace)
        self.assertEqual(record.managed_group, self.dcc_admin_group)
        self.assertEqual(record.current_sharing_instance, sharing)
        self.assertEqual(record.note, upload_workspace_audit.UploadWorkspaceAudit.DCC_ADMIN_AS_OWNER)

    @override_settings(ANVIL_DCC_ADMINS_GROUP_NAME="foo")
    def test_dcc_admin_different_setting(self):
        group = ManagedGroupFactory.create(name="foo")
        sharing = WorkspaceGroupSharingFactory.create(
            workspace=self.upload_workspace.workspace, group=group, access=WorkspaceGroupSharing.OWNER
        )
        audit = upload_workspace_audit.UploadWorkspaceAudit()
        audit.audit_workspace_and_group(self.upload_workspace, group)
        self.assertEqual(len(audit.verified), 1)
        self.assertEqual(len(audit.needs_action), 0)
        self.assertEqual(len(audit.errors), 0)
        record = audit.verified[0]
        self.assertIsInstance(record, upload_workspace_audit.VerifiedShared)
        self.assertEqual(record.workspace, self.upload_workspace)
        self.assertEqual(record.managed_group, group)
        self.assertEqual(record.current_sharing_instance, sharing)
        self.assertEqual(record.note, upload_workspace_audit.UploadWorkspaceAudit.DCC_ADMIN_AS_OWNER)

    def test_anvil_admins_shared_as_writer_no_compute(self):
        # Share the workspace with the group.
        WorkspaceGroupSharingFactory.create(
            workspace=self.upload_workspace.workspace, group=self.anvil_admins, access=WorkspaceGroupSharing.WRITER
        )
        audit = upload_workspace_audit.UploadWorkspaceAudit()
        audit.audit_workspace_and_group(self.upload_workspace, self.anvil_admins)
        self.assertEqual(len(audit.verified), 0)
        self.assertEqual(len(audit.needs_action), 0)
        self.assertEqual(len(audit.errors), 0)

    def test_anvil_admins_not_shared(self):
        audit = upload_workspace_audit.UploadWorkspaceAudit()
        audit.audit_workspace_and_group(self.upload_workspace, self.anvil_admins)
        self.assertEqual(len(audit.verified), 0)
        self.assertEqual(len(audit.needs_action), 0)
        self.assertEqual(len(audit.errors), 0)

    def test_anvil_admins_shared_as_writer_can_compute(self):
        WorkspaceGroupSharingFactory.create(
            workspace=self.upload_workspace.workspace,
            group=self.anvil_admins,
            access=WorkspaceGroupSharing.WRITER,
            can_compute=True,
        )
        audit = upload_workspace_audit.UploadWorkspaceAudit()
        audit.audit_workspace_and_group(self.upload_workspace, self.anvil_admins)
        self.assertEqual(len(audit.verified), 0)
        self.assertEqual(len(audit.needs_action), 0)
        self.assertEqual(len(audit.errors), 0)

    def test_anvil_admins_shared_as_reader(self):
        WorkspaceGroupSharingFactory.create(
            workspace=self.upload_workspace.workspace, group=self.anvil_admins, access=WorkspaceGroupSharing.READER
        )
        audit = upload_workspace_audit.UploadWorkspaceAudit()
        audit.audit_workspace_and_group(self.upload_workspace, self.anvil_admins)
        self.assertEqual(len(audit.verified), 0)
        self.assertEqual(len(audit.needs_action), 0)
        self.assertEqual(len(audit.errors), 0)

    def test_anvil_admins_shared_as_owner(self):
        WorkspaceGroupSharingFactory.create(
            workspace=self.upload_workspace.workspace, group=self.anvil_admins, access=WorkspaceGroupSharing.OWNER
        )
        audit = upload_workspace_audit.UploadWorkspaceAudit()
        audit.audit_workspace_and_group(self.upload_workspace, self.anvil_admins)
        self.assertEqual(len(audit.verified), 0)
        self.assertEqual(len(audit.needs_action), 0)
        self.assertEqual(len(audit.errors), 0)

    def test_anvil_devs_shared_as_writer_no_compute(self):
        # Share the workspace with the group.
        WorkspaceGroupSharingFactory.create(
            workspace=self.upload_workspace.workspace, group=self.anvil_devs, access=WorkspaceGroupSharing.WRITER
        )
        audit = upload_workspace_audit.UploadWorkspaceAudit()
        audit.audit_workspace_and_group(self.upload_workspace, self.anvil_devs)
        self.assertEqual(len(audit.verified), 0)
        self.assertEqual(len(audit.needs_action), 0)
        self.assertEqual(len(audit.errors), 0)

    def test_anvil_devs_not_shared(self):
        audit = upload_workspace_audit.UploadWorkspaceAudit()
        audit.audit_workspace_and_group(self.upload_workspace, self.anvil_devs)
        self.assertEqual(len(audit.verified), 0)
        self.assertEqual(len(audit.needs_action), 0)
        self.assertEqual(len(audit.errors), 0)

    def test_anvil_devs_shared_as_writer_can_compute(self):
        WorkspaceGroupSharingFactory.create(
            workspace=self.upload_workspace.workspace,
            group=self.anvil_devs,
            access=WorkspaceGroupSharing.WRITER,
            can_compute=True,
        )
        audit = upload_workspace_audit.UploadWorkspaceAudit()
        audit.audit_workspace_and_group(self.upload_workspace, self.anvil_devs)
        self.assertEqual(len(audit.verified), 0)
        self.assertEqual(len(audit.needs_action), 0)
        self.assertEqual(len(audit.errors), 0)

    def test_anvil_devs_shared_as_reader(self):
        WorkspaceGroupSharingFactory.create(
            workspace=self.upload_workspace.workspace, group=self.anvil_devs, access=WorkspaceGroupSharing.READER
        )
        audit = upload_workspace_audit.UploadWorkspaceAudit()
        audit.audit_workspace_and_group(self.upload_workspace, self.anvil_devs)
        self.assertEqual(len(audit.verified), 0)
        self.assertEqual(len(audit.needs_action), 0)
        self.assertEqual(len(audit.errors), 0)

    def test_anvil_devs_shared_as_owner(self):
        WorkspaceGroupSharingFactory.create(
            workspace=self.upload_workspace.workspace, group=self.anvil_devs, access=WorkspaceGroupSharing.OWNER
        )
        audit = upload_workspace_audit.UploadWorkspaceAudit()
        audit.audit_workspace_and_group(self.upload_workspace, self.anvil_devs)
        self.assertEqual(len(audit.verified), 0)
        self.assertEqual(len(audit.needs_action), 0)
        self.assertEqual(len(audit.errors), 0)

    def test_other_group_shared_as_writer_no_compute(self):
        # Share the workspace with the group.
        sharing = WorkspaceGroupSharingFactory.create(
            workspace=self.upload_workspace.workspace, group=self.other_group, access=WorkspaceGroupSharing.WRITER
        )
        audit = upload_workspace_audit.UploadWorkspaceAudit()
        audit.audit_workspace_and_group(self.upload_workspace, self.other_group)
        self.assertEqual(len(audit.verified), 0)
        self.assertEqual(len(audit.needs_action), 0)
        self.assertEqual(len(audit.errors), 1)
        record = audit.errors[0]
        self.assertIsInstance(record, upload_workspace_audit.StopSharing)
        self.assertEqual(record.workspace, self.upload_workspace)
        self.assertEqual(record.managed_group, self.other_group)
        self.assertEqual(record.current_sharing_instance, sharing)
        self.assertEqual(record.note, upload_workspace_audit.UploadWorkspaceAudit.OTHER_GROUP_NO_ACCESS)

    def test_other_group_not_shared(self):
        audit = upload_workspace_audit.UploadWorkspaceAudit()
        audit.audit_workspace_and_group(self.upload_workspace, self.other_group)
        self.assertEqual(len(audit.verified), 1)
        self.assertEqual(len(audit.needs_action), 0)
        self.assertEqual(len(audit.errors), 0)
        record = audit.verified[0]
        self.assertIsInstance(record, upload_workspace_audit.VerifiedNotShared)
        self.assertEqual(record.workspace, self.upload_workspace)
        self.assertEqual(record.managed_group, self.other_group)
        self.assertEqual(record.current_sharing_instance, None)
        self.assertEqual(record.note, upload_workspace_audit.UploadWorkspaceAudit.OTHER_GROUP_NO_ACCESS)

    def test_other_group_shared_as_writer_can_compute(self):
        sharing = WorkspaceGroupSharingFactory.create(
            workspace=self.upload_workspace.workspace,
            group=self.other_group,
            access=WorkspaceGroupSharing.WRITER,
            can_compute=True,
        )
        audit = upload_workspace_audit.UploadWorkspaceAudit()
        audit.audit_workspace_and_group(self.upload_workspace, self.other_group)
        self.assertEqual(len(audit.verified), 0)
        self.assertEqual(len(audit.needs_action), 0)
        self.assertEqual(len(audit.errors), 1)
        record = audit.errors[0]
        self.assertIsInstance(record, upload_workspace_audit.StopSharing)
        self.assertEqual(record.workspace, self.upload_workspace)
        self.assertEqual(record.managed_group, self.other_group)
        self.assertEqual(record.current_sharing_instance, sharing)
        self.assertEqual(record.note, upload_workspace_audit.UploadWorkspaceAudit.OTHER_GROUP_NO_ACCESS)

    def test_other_group_shared_as_reader(self):
        sharing = WorkspaceGroupSharingFactory.create(
            workspace=self.upload_workspace.workspace, group=self.other_group, access=WorkspaceGroupSharing.READER
        )
        audit = upload_workspace_audit.UploadWorkspaceAudit()
        audit.audit_workspace_and_group(self.upload_workspace, self.other_group)
        self.assertEqual(len(audit.verified), 0)
        self.assertEqual(len(audit.needs_action), 0)
        self.assertEqual(len(audit.errors), 1)
        record = audit.errors[0]
        self.assertIsInstance(record, upload_workspace_audit.StopSharing)
        self.assertEqual(record.workspace, self.upload_workspace)
        self.assertEqual(record.managed_group, self.other_group)
        self.assertEqual(record.current_sharing_instance, sharing)
        self.assertEqual(record.note, upload_workspace_audit.UploadWorkspaceAudit.OTHER_GROUP_NO_ACCESS)

    def test_other_group_shared_as_owner(self):
        sharing = WorkspaceGroupSharingFactory.create(
            workspace=self.upload_workspace.workspace, group=self.other_group, access=WorkspaceGroupSharing.OWNER
        )
        audit = upload_workspace_audit.UploadWorkspaceAudit()
        audit.audit_workspace_and_group(self.upload_workspace, self.other_group)
        self.assertEqual(len(audit.verified), 0)
        self.assertEqual(len(audit.needs_action), 0)
        self.assertEqual(len(audit.errors), 1)
        record = audit.errors[0]
        self.assertIsInstance(record, upload_workspace_audit.StopSharing)
        self.assertEqual(record.workspace, self.upload_workspace)
        self.assertEqual(record.managed_group, self.other_group)
        self.assertEqual(record.current_sharing_instance, sharing)
        self.assertEqual(record.note, upload_workspace_audit.UploadWorkspaceAudit.OTHER_GROUP_NO_ACCESS)


class UploadWorkspaceAuditPastCycleAfterQCCompleteTest(TestCase):
    """Tests for the `UploadWorkspaceAudit` class for past cycles before QC is complete.

    Expectations at this point in the upload cycle:
    - RC uploader group should not have direct access.
    - DCC writer group should not have direct access.
    """

    def setUp(self):
        super().setUp()
        self.dcc_admin_group = ManagedGroupFactory.create(name=settings.ANVIL_DCC_ADMINS_GROUP_NAME)
        self.dcc_writer_group = ManagedGroupFactory.create(name="GREGOR_DCC_WRITERS")
        self.rc_uploader_group = ManagedGroupFactory.create()
        self.research_center = factories.ResearchCenterFactory.create(uploader_group=self.rc_uploader_group)
        self.upload_workspace = factories.UploadWorkspaceFactory.create(
            research_center=self.research_center,
            upload_cycle__is_past=True,
            date_qc_completed=fake.date_this_year(before_today=True, after_today=False),
        )
        self.auth_domain = self.upload_workspace.workspace.authorization_domains.get()
        self.other_group = ManagedGroupFactory.create()
        self.anvil_admins = ManagedGroupFactory.create(name="anvil-admins")
        self.anvil_devs = ManagedGroupFactory.create(name="anvil_devs")

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

    def test_auth_domain_shared_as_writer_no_compute(self):
        # Share the workspace with the group.
        sharing = WorkspaceGroupSharingFactory.create(
            workspace=self.upload_workspace.workspace, group=self.auth_domain, access=WorkspaceGroupSharing.WRITER
        )
        audit = upload_workspace_audit.UploadWorkspaceAudit()
        audit.audit_workspace_and_group(self.upload_workspace, self.auth_domain)
        self.assertEqual(len(audit.verified), 0)
        self.assertEqual(len(audit.needs_action), 1)
        self.assertEqual(len(audit.errors), 0)
        record = audit.needs_action[0]
        self.assertIsInstance(record, upload_workspace_audit.ShareAsReader)
        self.assertEqual(record.workspace, self.upload_workspace)
        self.assertEqual(record.managed_group, self.auth_domain)
        self.assertEqual(record.current_sharing_instance, sharing)
        self.assertEqual(record.note, upload_workspace_audit.UploadWorkspaceAudit.AUTH_DOMAIN_AS_READER)

    def test_auth_domain_not_shared(self):
        audit = upload_workspace_audit.UploadWorkspaceAudit()
        audit.audit_workspace_and_group(self.upload_workspace, self.auth_domain)
        self.assertEqual(len(audit.verified), 0)
        self.assertEqual(len(audit.needs_action), 1)
        self.assertEqual(len(audit.errors), 0)
        record = audit.needs_action[0]
        self.assertIsInstance(record, upload_workspace_audit.ShareAsReader)
        self.assertEqual(record.workspace, self.upload_workspace)
        self.assertEqual(record.managed_group, self.auth_domain)
        self.assertEqual(record.current_sharing_instance, None)
        self.assertEqual(record.note, upload_workspace_audit.UploadWorkspaceAudit.AUTH_DOMAIN_AS_READER)

    def test_auth_domain_shared_as_writer_can_compute(self):
        sharing = WorkspaceGroupSharingFactory.create(
            workspace=self.upload_workspace.workspace,
            group=self.auth_domain,
            access=WorkspaceGroupSharing.WRITER,
            can_compute=True,
        )
        audit = upload_workspace_audit.UploadWorkspaceAudit()
        audit.audit_workspace_and_group(self.upload_workspace, self.auth_domain)
        self.assertEqual(len(audit.verified), 0)
        self.assertEqual(len(audit.needs_action), 1)
        self.assertEqual(len(audit.errors), 0)
        record = audit.needs_action[0]
        self.assertIsInstance(record, upload_workspace_audit.ShareAsReader)
        self.assertEqual(record.workspace, self.upload_workspace)
        self.assertEqual(record.managed_group, self.auth_domain)
        self.assertEqual(record.current_sharing_instance, sharing)
        self.assertEqual(record.note, upload_workspace_audit.UploadWorkspaceAudit.AUTH_DOMAIN_AS_READER)

    def test_auth_domain_shared_as_reader(self):
        sharing = WorkspaceGroupSharingFactory.create(
            workspace=self.upload_workspace.workspace, group=self.auth_domain, access=WorkspaceGroupSharing.READER
        )
        audit = upload_workspace_audit.UploadWorkspaceAudit()
        audit.audit_workspace_and_group(self.upload_workspace, self.auth_domain)
        self.assertEqual(len(audit.verified), 1)
        self.assertEqual(len(audit.needs_action), 0)
        self.assertEqual(len(audit.errors), 0)
        record = audit.verified[0]
        self.assertIsInstance(record, upload_workspace_audit.VerifiedShared)
        self.assertEqual(record.workspace, self.upload_workspace)
        self.assertEqual(record.managed_group, self.auth_domain)
        self.assertEqual(record.current_sharing_instance, sharing)
        self.assertEqual(record.note, upload_workspace_audit.UploadWorkspaceAudit.AUTH_DOMAIN_AS_READER)

    def test_auth_domain_shared_as_owner(self):
        sharing = WorkspaceGroupSharingFactory.create(
            workspace=self.upload_workspace.workspace, group=self.auth_domain, access=WorkspaceGroupSharing.OWNER
        )
        audit = upload_workspace_audit.UploadWorkspaceAudit()
        audit.audit_workspace_and_group(self.upload_workspace, self.auth_domain)
        self.assertEqual(len(audit.verified), 0)
        self.assertEqual(len(audit.needs_action), 1)
        self.assertEqual(len(audit.errors), 0)
        record = audit.needs_action[0]
        self.assertIsInstance(record, upload_workspace_audit.ShareAsReader)
        self.assertEqual(record.workspace, self.upload_workspace)
        self.assertEqual(record.managed_group, self.auth_domain)
        self.assertEqual(record.current_sharing_instance, sharing)
        self.assertEqual(record.note, upload_workspace_audit.UploadWorkspaceAudit.AUTH_DOMAIN_AS_READER)

    def test_dcc_admin_shared_as_writer_no_compute(self):
        # Share the workspace with the group.
        sharing = WorkspaceGroupSharingFactory.create(
            workspace=self.upload_workspace.workspace, group=self.dcc_admin_group, access=WorkspaceGroupSharing.WRITER
        )
        audit = upload_workspace_audit.UploadWorkspaceAudit()
        audit.audit_workspace_and_group(self.upload_workspace, self.dcc_admin_group)
        self.assertEqual(len(audit.verified), 0)
        self.assertEqual(len(audit.needs_action), 1)
        self.assertEqual(len(audit.errors), 0)
        record = audit.needs_action[0]
        self.assertIsInstance(record, upload_workspace_audit.ShareAsOwner)
        self.assertEqual(record.workspace, self.upload_workspace)
        self.assertEqual(record.managed_group, self.dcc_admin_group)
        self.assertEqual(record.current_sharing_instance, sharing)
        self.assertEqual(record.note, upload_workspace_audit.UploadWorkspaceAudit.DCC_ADMIN_AS_OWNER)

    def test_dcc_admin_not_shared(self):
        audit = upload_workspace_audit.UploadWorkspaceAudit()
        audit.audit_workspace_and_group(self.upload_workspace, self.dcc_admin_group)
        self.assertEqual(len(audit.verified), 0)
        self.assertEqual(len(audit.needs_action), 1)
        self.assertEqual(len(audit.errors), 0)
        record = audit.needs_action[0]
        self.assertIsInstance(record, upload_workspace_audit.ShareAsOwner)
        self.assertEqual(record.workspace, self.upload_workspace)
        self.assertEqual(record.managed_group, self.dcc_admin_group)
        self.assertEqual(record.current_sharing_instance, None)
        self.assertEqual(record.note, upload_workspace_audit.UploadWorkspaceAudit.DCC_ADMIN_AS_OWNER)

    def test_dcc_admin_shared_as_writer_can_compute(self):
        sharing = WorkspaceGroupSharingFactory.create(
            workspace=self.upload_workspace.workspace,
            group=self.dcc_admin_group,
            access=WorkspaceGroupSharing.WRITER,
            can_compute=True,
        )
        audit = upload_workspace_audit.UploadWorkspaceAudit()
        audit.audit_workspace_and_group(self.upload_workspace, self.dcc_admin_group)
        self.assertEqual(len(audit.verified), 0)
        self.assertEqual(len(audit.needs_action), 1)
        self.assertEqual(len(audit.errors), 0)
        record = audit.needs_action[0]
        self.assertIsInstance(record, upload_workspace_audit.ShareAsOwner)
        self.assertEqual(record.workspace, self.upload_workspace)
        self.assertEqual(record.managed_group, self.dcc_admin_group)
        self.assertEqual(record.current_sharing_instance, sharing)
        self.assertEqual(record.note, upload_workspace_audit.UploadWorkspaceAudit.DCC_ADMIN_AS_OWNER)

    def test_dcc_admin_shared_as_reader(self):
        sharing = WorkspaceGroupSharingFactory.create(
            workspace=self.upload_workspace.workspace, group=self.dcc_admin_group, access=WorkspaceGroupSharing.READER
        )
        audit = upload_workspace_audit.UploadWorkspaceAudit()
        audit.audit_workspace_and_group(self.upload_workspace, self.dcc_admin_group)
        self.assertEqual(len(audit.verified), 0)
        self.assertEqual(len(audit.needs_action), 1)
        self.assertEqual(len(audit.errors), 0)
        record = audit.needs_action[0]
        self.assertIsInstance(record, upload_workspace_audit.ShareAsOwner)
        self.assertEqual(record.workspace, self.upload_workspace)
        self.assertEqual(record.managed_group, self.dcc_admin_group)
        self.assertEqual(record.current_sharing_instance, sharing)
        self.assertEqual(record.note, upload_workspace_audit.UploadWorkspaceAudit.DCC_ADMIN_AS_OWNER)

    def test_dcc_admin_shared_as_owner(self):
        sharing = WorkspaceGroupSharingFactory.create(
            workspace=self.upload_workspace.workspace, group=self.dcc_admin_group, access=WorkspaceGroupSharing.OWNER
        )
        audit = upload_workspace_audit.UploadWorkspaceAudit()
        audit.audit_workspace_and_group(self.upload_workspace, self.dcc_admin_group)
        self.assertEqual(len(audit.verified), 1)
        self.assertEqual(len(audit.needs_action), 0)
        self.assertEqual(len(audit.errors), 0)
        record = audit.verified[0]
        self.assertIsInstance(record, upload_workspace_audit.VerifiedShared)
        self.assertEqual(record.workspace, self.upload_workspace)
        self.assertEqual(record.managed_group, self.dcc_admin_group)
        self.assertEqual(record.current_sharing_instance, sharing)
        self.assertEqual(record.note, upload_workspace_audit.UploadWorkspaceAudit.DCC_ADMIN_AS_OWNER)

    @override_settings(ANVIL_DCC_ADMINS_GROUP_NAME="foo")
    def test_dcc_admin_different_setting(self):
        group = ManagedGroupFactory.create(name="foo")
        sharing = WorkspaceGroupSharingFactory.create(
            workspace=self.upload_workspace.workspace, group=group, access=WorkspaceGroupSharing.OWNER
        )
        audit = upload_workspace_audit.UploadWorkspaceAudit()
        audit.audit_workspace_and_group(self.upload_workspace, group)
        self.assertEqual(len(audit.verified), 1)
        self.assertEqual(len(audit.needs_action), 0)
        self.assertEqual(len(audit.errors), 0)
        record = audit.verified[0]
        self.assertIsInstance(record, upload_workspace_audit.VerifiedShared)
        self.assertEqual(record.workspace, self.upload_workspace)
        self.assertEqual(record.managed_group, group)
        self.assertEqual(record.current_sharing_instance, sharing)
        self.assertEqual(record.note, upload_workspace_audit.UploadWorkspaceAudit.DCC_ADMIN_AS_OWNER)

    def test_anvil_admins_shared_as_writer_no_compute(self):
        # Share the workspace with the group.
        WorkspaceGroupSharingFactory.create(
            workspace=self.upload_workspace.workspace, group=self.anvil_admins, access=WorkspaceGroupSharing.WRITER
        )
        audit = upload_workspace_audit.UploadWorkspaceAudit()
        audit.audit_workspace_and_group(self.upload_workspace, self.anvil_admins)
        self.assertEqual(len(audit.verified), 0)
        self.assertEqual(len(audit.needs_action), 0)
        self.assertEqual(len(audit.errors), 0)

    def test_anvil_admins_not_shared(self):
        audit = upload_workspace_audit.UploadWorkspaceAudit()
        audit.audit_workspace_and_group(self.upload_workspace, self.anvil_admins)
        self.assertEqual(len(audit.verified), 0)
        self.assertEqual(len(audit.needs_action), 0)
        self.assertEqual(len(audit.errors), 0)

    def test_anvil_admins_shared_as_writer_can_compute(self):
        WorkspaceGroupSharingFactory.create(
            workspace=self.upload_workspace.workspace,
            group=self.anvil_admins,
            access=WorkspaceGroupSharing.WRITER,
            can_compute=True,
        )
        audit = upload_workspace_audit.UploadWorkspaceAudit()
        audit.audit_workspace_and_group(self.upload_workspace, self.anvil_admins)
        self.assertEqual(len(audit.verified), 0)
        self.assertEqual(len(audit.needs_action), 0)
        self.assertEqual(len(audit.errors), 0)

    def test_anvil_admins_shared_as_reader(self):
        WorkspaceGroupSharingFactory.create(
            workspace=self.upload_workspace.workspace, group=self.anvil_admins, access=WorkspaceGroupSharing.READER
        )
        audit = upload_workspace_audit.UploadWorkspaceAudit()
        audit.audit_workspace_and_group(self.upload_workspace, self.anvil_admins)
        self.assertEqual(len(audit.verified), 0)
        self.assertEqual(len(audit.needs_action), 0)
        self.assertEqual(len(audit.errors), 0)

    def test_anvil_admins_shared_as_owner(self):
        WorkspaceGroupSharingFactory.create(
            workspace=self.upload_workspace.workspace, group=self.anvil_admins, access=WorkspaceGroupSharing.OWNER
        )
        audit = upload_workspace_audit.UploadWorkspaceAudit()
        audit.audit_workspace_and_group(self.upload_workspace, self.anvil_admins)
        self.assertEqual(len(audit.verified), 0)
        self.assertEqual(len(audit.needs_action), 0)
        self.assertEqual(len(audit.errors), 0)

    def test_anvil_devs_shared_as_writer_no_compute(self):
        # Share the workspace with the group.
        WorkspaceGroupSharingFactory.create(
            workspace=self.upload_workspace.workspace, group=self.anvil_devs, access=WorkspaceGroupSharing.WRITER
        )
        audit = upload_workspace_audit.UploadWorkspaceAudit()
        audit.audit_workspace_and_group(self.upload_workspace, self.anvil_devs)
        self.assertEqual(len(audit.verified), 0)
        self.assertEqual(len(audit.needs_action), 0)
        self.assertEqual(len(audit.errors), 0)

    def test_anvil_devs_not_shared(self):
        audit = upload_workspace_audit.UploadWorkspaceAudit()
        audit.audit_workspace_and_group(self.upload_workspace, self.anvil_devs)
        self.assertEqual(len(audit.verified), 0)
        self.assertEqual(len(audit.needs_action), 0)
        self.assertEqual(len(audit.errors), 0)

    def test_anvil_devs_shared_as_writer_can_compute(self):
        WorkspaceGroupSharingFactory.create(
            workspace=self.upload_workspace.workspace,
            group=self.anvil_devs,
            access=WorkspaceGroupSharing.WRITER,
            can_compute=True,
        )
        audit = upload_workspace_audit.UploadWorkspaceAudit()
        audit.audit_workspace_and_group(self.upload_workspace, self.anvil_devs)
        self.assertEqual(len(audit.verified), 0)
        self.assertEqual(len(audit.needs_action), 0)
        self.assertEqual(len(audit.errors), 0)

    def test_anvil_devs_shared_as_reader(self):
        WorkspaceGroupSharingFactory.create(
            workspace=self.upload_workspace.workspace, group=self.anvil_devs, access=WorkspaceGroupSharing.READER
        )
        audit = upload_workspace_audit.UploadWorkspaceAudit()
        audit.audit_workspace_and_group(self.upload_workspace, self.anvil_devs)
        self.assertEqual(len(audit.verified), 0)
        self.assertEqual(len(audit.needs_action), 0)
        self.assertEqual(len(audit.errors), 0)

    def test_anvil_devs_shared_as_owner(self):
        WorkspaceGroupSharingFactory.create(
            workspace=self.upload_workspace.workspace, group=self.anvil_devs, access=WorkspaceGroupSharing.OWNER
        )
        audit = upload_workspace_audit.UploadWorkspaceAudit()
        audit.audit_workspace_and_group(self.upload_workspace, self.anvil_devs)
        self.assertEqual(len(audit.verified), 0)
        self.assertEqual(len(audit.needs_action), 0)
        self.assertEqual(len(audit.errors), 0)

    def test_other_group_shared_as_writer_no_compute(self):
        # Share the workspace with the group.
        sharing = WorkspaceGroupSharingFactory.create(
            workspace=self.upload_workspace.workspace, group=self.other_group, access=WorkspaceGroupSharing.WRITER
        )
        audit = upload_workspace_audit.UploadWorkspaceAudit()
        audit.audit_workspace_and_group(self.upload_workspace, self.other_group)
        self.assertEqual(len(audit.verified), 0)
        self.assertEqual(len(audit.needs_action), 0)
        self.assertEqual(len(audit.errors), 1)
        record = audit.errors[0]
        self.assertIsInstance(record, upload_workspace_audit.StopSharing)
        self.assertEqual(record.workspace, self.upload_workspace)
        self.assertEqual(record.managed_group, self.other_group)
        self.assertEqual(record.current_sharing_instance, sharing)
        self.assertEqual(record.note, upload_workspace_audit.UploadWorkspaceAudit.OTHER_GROUP_NO_ACCESS)

    def test_other_group_not_shared(self):
        audit = upload_workspace_audit.UploadWorkspaceAudit()
        audit.audit_workspace_and_group(self.upload_workspace, self.other_group)
        self.assertEqual(len(audit.verified), 1)
        self.assertEqual(len(audit.needs_action), 0)
        self.assertEqual(len(audit.errors), 0)
        record = audit.verified[0]
        self.assertIsInstance(record, upload_workspace_audit.VerifiedNotShared)
        self.assertEqual(record.workspace, self.upload_workspace)
        self.assertEqual(record.managed_group, self.other_group)
        self.assertEqual(record.current_sharing_instance, None)
        self.assertEqual(record.note, upload_workspace_audit.UploadWorkspaceAudit.OTHER_GROUP_NO_ACCESS)

    def test_other_group_shared_as_writer_can_compute(self):
        sharing = WorkspaceGroupSharingFactory.create(
            workspace=self.upload_workspace.workspace,
            group=self.other_group,
            access=WorkspaceGroupSharing.WRITER,
            can_compute=True,
        )
        audit = upload_workspace_audit.UploadWorkspaceAudit()
        audit.audit_workspace_and_group(self.upload_workspace, self.other_group)
        self.assertEqual(len(audit.verified), 0)
        self.assertEqual(len(audit.needs_action), 0)
        self.assertEqual(len(audit.errors), 1)
        record = audit.errors[0]
        self.assertIsInstance(record, upload_workspace_audit.StopSharing)
        self.assertEqual(record.workspace, self.upload_workspace)
        self.assertEqual(record.managed_group, self.other_group)
        self.assertEqual(record.current_sharing_instance, sharing)
        self.assertEqual(record.note, upload_workspace_audit.UploadWorkspaceAudit.OTHER_GROUP_NO_ACCESS)

    def test_other_group_shared_as_reader(self):
        sharing = WorkspaceGroupSharingFactory.create(
            workspace=self.upload_workspace.workspace, group=self.other_group, access=WorkspaceGroupSharing.READER
        )
        audit = upload_workspace_audit.UploadWorkspaceAudit()
        audit.audit_workspace_and_group(self.upload_workspace, self.other_group)
        self.assertEqual(len(audit.verified), 0)
        self.assertEqual(len(audit.needs_action), 0)
        self.assertEqual(len(audit.errors), 1)
        record = audit.errors[0]
        self.assertIsInstance(record, upload_workspace_audit.StopSharing)
        self.assertEqual(record.workspace, self.upload_workspace)
        self.assertEqual(record.managed_group, self.other_group)
        self.assertEqual(record.current_sharing_instance, sharing)
        self.assertEqual(record.note, upload_workspace_audit.UploadWorkspaceAudit.OTHER_GROUP_NO_ACCESS)

    def test_other_group_shared_as_owner(self):
        sharing = WorkspaceGroupSharingFactory.create(
            workspace=self.upload_workspace.workspace, group=self.other_group, access=WorkspaceGroupSharing.OWNER
        )
        audit = upload_workspace_audit.UploadWorkspaceAudit()
        audit.audit_workspace_and_group(self.upload_workspace, self.other_group)
        self.assertEqual(len(audit.verified), 0)
        self.assertEqual(len(audit.needs_action), 0)
        self.assertEqual(len(audit.errors), 1)
        record = audit.errors[0]
        self.assertIsInstance(record, upload_workspace_audit.StopSharing)
        self.assertEqual(record.workspace, self.upload_workspace)
        self.assertEqual(record.managed_group, self.other_group)
        self.assertEqual(record.current_sharing_instance, sharing)
        self.assertEqual(record.note, upload_workspace_audit.UploadWorkspaceAudit.OTHER_GROUP_NO_ACCESS)


class UploadWorkspaceAuditPastCycleAfterCombinedWorkspaceSharedTest(TestCase):
    """Tests for the `UploadWorkspaceAudit` class for past cycles after the combined workspace is ready to share.

    Expectations at this point in the upload cycle:
    - RC uploader group should not have direct access.
    - DCC writer group should not have direct access.
    """

    def setUp(self):
        super().setUp()
        self.dcc_admin_group = ManagedGroupFactory.create(name=settings.ANVIL_DCC_ADMINS_GROUP_NAME)
        self.dcc_writer_group = ManagedGroupFactory.create(name="GREGOR_DCC_WRITERS")
        self.rc_uploader_group = ManagedGroupFactory.create()
        self.research_center = factories.ResearchCenterFactory.create(uploader_group=self.rc_uploader_group)
        self.upload_workspace = factories.UploadWorkspaceFactory.create(
            research_center=self.research_center,
            upload_cycle__is_past=True,
            date_qc_completed=fake.date_this_year(before_today=True, after_today=False),
        )
        self.auth_domain = self.upload_workspace.workspace.authorization_domains.get()
        # Create a corresponding combined workspace.
        self.combined_workspace = factories.CombinedConsortiumDataWorkspaceFactory.create(
            upload_cycle=self.upload_workspace.upload_cycle,
            date_completed=fake.date_this_year(
                before_today=True,
                after_today=False,
            ),
        )
        self.other_group = ManagedGroupFactory.create()
        self.anvil_admins = ManagedGroupFactory.create(name="anvil-admins")
        self.anvil_devs = ManagedGroupFactory.create(name="anvil_devs")

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

    def test_auth_domain_shared_as_writer_no_compute(self):
        # Share the workspace with the group.
        sharing = WorkspaceGroupSharingFactory.create(
            workspace=self.upload_workspace.workspace, group=self.auth_domain, access=WorkspaceGroupSharing.WRITER
        )
        audit = upload_workspace_audit.UploadWorkspaceAudit()
        audit.audit_workspace_and_group(self.upload_workspace, self.auth_domain)
        self.assertEqual(len(audit.verified), 0)
        self.assertEqual(len(audit.needs_action), 1)
        self.assertEqual(len(audit.errors), 0)
        record = audit.needs_action[0]
        self.assertIsInstance(record, upload_workspace_audit.ShareAsReader)
        self.assertEqual(record.workspace, self.upload_workspace)
        self.assertEqual(record.managed_group, self.auth_domain)
        self.assertEqual(record.current_sharing_instance, sharing)
        self.assertEqual(record.note, upload_workspace_audit.UploadWorkspaceAudit.AUTH_DOMAIN_AS_READER)

    def test_auth_domain_not_shared(self):
        audit = upload_workspace_audit.UploadWorkspaceAudit()
        audit.audit_workspace_and_group(self.upload_workspace, self.auth_domain)
        self.assertEqual(len(audit.verified), 0)
        self.assertEqual(len(audit.needs_action), 1)
        self.assertEqual(len(audit.errors), 0)
        record = audit.needs_action[0]
        self.assertIsInstance(record, upload_workspace_audit.ShareAsReader)
        self.assertEqual(record.workspace, self.upload_workspace)
        self.assertEqual(record.managed_group, self.auth_domain)
        self.assertEqual(record.current_sharing_instance, None)
        self.assertEqual(record.note, upload_workspace_audit.UploadWorkspaceAudit.AUTH_DOMAIN_AS_READER)

    def test_auth_domain_shared_as_writer_can_compute(self):
        sharing = WorkspaceGroupSharingFactory.create(
            workspace=self.upload_workspace.workspace,
            group=self.auth_domain,
            access=WorkspaceGroupSharing.WRITER,
            can_compute=True,
        )
        audit = upload_workspace_audit.UploadWorkspaceAudit()
        audit.audit_workspace_and_group(self.upload_workspace, self.auth_domain)
        self.assertEqual(len(audit.verified), 0)
        self.assertEqual(len(audit.needs_action), 1)
        self.assertEqual(len(audit.errors), 0)
        record = audit.needs_action[0]
        self.assertIsInstance(record, upload_workspace_audit.ShareAsReader)
        self.assertEqual(record.workspace, self.upload_workspace)
        self.assertEqual(record.managed_group, self.auth_domain)
        self.assertEqual(record.current_sharing_instance, sharing)
        self.assertEqual(record.note, upload_workspace_audit.UploadWorkspaceAudit.AUTH_DOMAIN_AS_READER)

    def test_auth_domain_shared_as_reader(self):
        sharing = WorkspaceGroupSharingFactory.create(
            workspace=self.upload_workspace.workspace, group=self.auth_domain, access=WorkspaceGroupSharing.READER
        )
        audit = upload_workspace_audit.UploadWorkspaceAudit()
        audit.audit_workspace_and_group(self.upload_workspace, self.auth_domain)
        self.assertEqual(len(audit.verified), 1)
        self.assertEqual(len(audit.needs_action), 0)
        self.assertEqual(len(audit.errors), 0)
        record = audit.verified[0]
        self.assertIsInstance(record, upload_workspace_audit.VerifiedShared)
        self.assertEqual(record.workspace, self.upload_workspace)
        self.assertEqual(record.managed_group, self.auth_domain)
        self.assertEqual(record.current_sharing_instance, sharing)
        self.assertEqual(record.note, upload_workspace_audit.UploadWorkspaceAudit.AUTH_DOMAIN_AS_READER)

    def test_auth_domain_shared_as_owner(self):
        sharing = WorkspaceGroupSharingFactory.create(
            workspace=self.upload_workspace.workspace, group=self.auth_domain, access=WorkspaceGroupSharing.OWNER
        )
        audit = upload_workspace_audit.UploadWorkspaceAudit()
        audit.audit_workspace_and_group(self.upload_workspace, self.auth_domain)
        self.assertEqual(len(audit.verified), 0)
        self.assertEqual(len(audit.needs_action), 1)
        self.assertEqual(len(audit.errors), 0)
        record = audit.needs_action[0]
        self.assertIsInstance(record, upload_workspace_audit.ShareAsReader)
        self.assertEqual(record.workspace, self.upload_workspace)
        self.assertEqual(record.managed_group, self.auth_domain)
        self.assertEqual(record.current_sharing_instance, sharing)
        self.assertEqual(record.note, upload_workspace_audit.UploadWorkspaceAudit.AUTH_DOMAIN_AS_READER)

    def test_dcc_admin_shared_as_writer_no_compute(self):
        # Share the workspace with the group.
        sharing = WorkspaceGroupSharingFactory.create(
            workspace=self.upload_workspace.workspace, group=self.dcc_admin_group, access=WorkspaceGroupSharing.WRITER
        )
        audit = upload_workspace_audit.UploadWorkspaceAudit()
        audit.audit_workspace_and_group(self.upload_workspace, self.dcc_admin_group)
        self.assertEqual(len(audit.verified), 0)
        self.assertEqual(len(audit.needs_action), 1)
        self.assertEqual(len(audit.errors), 0)
        record = audit.needs_action[0]
        self.assertIsInstance(record, upload_workspace_audit.ShareAsOwner)
        self.assertEqual(record.workspace, self.upload_workspace)
        self.assertEqual(record.managed_group, self.dcc_admin_group)
        self.assertEqual(record.current_sharing_instance, sharing)
        self.assertEqual(record.note, upload_workspace_audit.UploadWorkspaceAudit.DCC_ADMIN_AS_OWNER)

    def test_dcc_admin_not_shared(self):
        audit = upload_workspace_audit.UploadWorkspaceAudit()
        audit.audit_workspace_and_group(self.upload_workspace, self.dcc_admin_group)
        self.assertEqual(len(audit.verified), 0)
        self.assertEqual(len(audit.needs_action), 1)
        self.assertEqual(len(audit.errors), 0)
        record = audit.needs_action[0]
        self.assertIsInstance(record, upload_workspace_audit.ShareAsOwner)
        self.assertEqual(record.workspace, self.upload_workspace)
        self.assertEqual(record.managed_group, self.dcc_admin_group)
        self.assertEqual(record.current_sharing_instance, None)
        self.assertEqual(record.note, upload_workspace_audit.UploadWorkspaceAudit.DCC_ADMIN_AS_OWNER)

    def test_dcc_admin_shared_as_writer_can_compute(self):
        sharing = WorkspaceGroupSharingFactory.create(
            workspace=self.upload_workspace.workspace,
            group=self.dcc_admin_group,
            access=WorkspaceGroupSharing.WRITER,
            can_compute=True,
        )
        audit = upload_workspace_audit.UploadWorkspaceAudit()
        audit.audit_workspace_and_group(self.upload_workspace, self.dcc_admin_group)
        self.assertEqual(len(audit.verified), 0)
        self.assertEqual(len(audit.needs_action), 1)
        self.assertEqual(len(audit.errors), 0)
        record = audit.needs_action[0]
        self.assertIsInstance(record, upload_workspace_audit.ShareAsOwner)
        self.assertEqual(record.workspace, self.upload_workspace)
        self.assertEqual(record.managed_group, self.dcc_admin_group)
        self.assertEqual(record.current_sharing_instance, sharing)
        self.assertEqual(record.note, upload_workspace_audit.UploadWorkspaceAudit.DCC_ADMIN_AS_OWNER)

    def test_dcc_admin_shared_as_reader(self):
        sharing = WorkspaceGroupSharingFactory.create(
            workspace=self.upload_workspace.workspace, group=self.dcc_admin_group, access=WorkspaceGroupSharing.READER
        )
        audit = upload_workspace_audit.UploadWorkspaceAudit()
        audit.audit_workspace_and_group(self.upload_workspace, self.dcc_admin_group)
        self.assertEqual(len(audit.verified), 0)
        self.assertEqual(len(audit.needs_action), 1)
        self.assertEqual(len(audit.errors), 0)
        record = audit.needs_action[0]
        self.assertIsInstance(record, upload_workspace_audit.ShareAsOwner)
        self.assertEqual(record.workspace, self.upload_workspace)
        self.assertEqual(record.managed_group, self.dcc_admin_group)
        self.assertEqual(record.current_sharing_instance, sharing)
        self.assertEqual(record.note, upload_workspace_audit.UploadWorkspaceAudit.DCC_ADMIN_AS_OWNER)

    def test_dcc_admin_shared_as_owner(self):
        sharing = WorkspaceGroupSharingFactory.create(
            workspace=self.upload_workspace.workspace, group=self.dcc_admin_group, access=WorkspaceGroupSharing.OWNER
        )
        audit = upload_workspace_audit.UploadWorkspaceAudit()
        audit.audit_workspace_and_group(self.upload_workspace, self.dcc_admin_group)
        self.assertEqual(len(audit.verified), 1)
        self.assertEqual(len(audit.needs_action), 0)
        self.assertEqual(len(audit.errors), 0)
        record = audit.verified[0]
        self.assertIsInstance(record, upload_workspace_audit.VerifiedShared)
        self.assertEqual(record.workspace, self.upload_workspace)
        self.assertEqual(record.managed_group, self.dcc_admin_group)
        self.assertEqual(record.current_sharing_instance, sharing)
        self.assertEqual(record.note, upload_workspace_audit.UploadWorkspaceAudit.DCC_ADMIN_AS_OWNER)

    @override_settings(ANVIL_DCC_ADMINS_GROUP_NAME="foo")
    def test_dcc_admin_different_setting(self):
        group = ManagedGroupFactory.create(name="foo")
        sharing = WorkspaceGroupSharingFactory.create(
            workspace=self.upload_workspace.workspace, group=group, access=WorkspaceGroupSharing.OWNER
        )
        audit = upload_workspace_audit.UploadWorkspaceAudit()
        audit.audit_workspace_and_group(self.upload_workspace, group)
        self.assertEqual(len(audit.verified), 1)
        self.assertEqual(len(audit.needs_action), 0)
        self.assertEqual(len(audit.errors), 0)
        record = audit.verified[0]
        self.assertIsInstance(record, upload_workspace_audit.VerifiedShared)
        self.assertEqual(record.workspace, self.upload_workspace)
        self.assertEqual(record.managed_group, group)
        self.assertEqual(record.current_sharing_instance, sharing)
        self.assertEqual(record.note, upload_workspace_audit.UploadWorkspaceAudit.DCC_ADMIN_AS_OWNER)

    def test_anvil_admins_shared_as_writer_no_compute(self):
        # Share the workspace with the group.
        WorkspaceGroupSharingFactory.create(
            workspace=self.upload_workspace.workspace, group=self.anvil_admins, access=WorkspaceGroupSharing.WRITER
        )
        audit = upload_workspace_audit.UploadWorkspaceAudit()
        audit.audit_workspace_and_group(self.upload_workspace, self.anvil_admins)
        self.assertEqual(len(audit.verified), 0)
        self.assertEqual(len(audit.needs_action), 0)
        self.assertEqual(len(audit.errors), 0)

    def test_anvil_admins_not_shared(self):
        audit = upload_workspace_audit.UploadWorkspaceAudit()
        audit.audit_workspace_and_group(self.upload_workspace, self.anvil_admins)
        self.assertEqual(len(audit.verified), 0)
        self.assertEqual(len(audit.needs_action), 0)
        self.assertEqual(len(audit.errors), 0)

    def test_anvil_admins_shared_as_writer_can_compute(self):
        WorkspaceGroupSharingFactory.create(
            workspace=self.upload_workspace.workspace,
            group=self.anvil_admins,
            access=WorkspaceGroupSharing.WRITER,
            can_compute=True,
        )
        audit = upload_workspace_audit.UploadWorkspaceAudit()
        audit.audit_workspace_and_group(self.upload_workspace, self.anvil_admins)
        self.assertEqual(len(audit.verified), 0)
        self.assertEqual(len(audit.needs_action), 0)
        self.assertEqual(len(audit.errors), 0)

    def test_anvil_admins_shared_as_reader(self):
        WorkspaceGroupSharingFactory.create(
            workspace=self.upload_workspace.workspace, group=self.anvil_admins, access=WorkspaceGroupSharing.READER
        )
        audit = upload_workspace_audit.UploadWorkspaceAudit()
        audit.audit_workspace_and_group(self.upload_workspace, self.anvil_admins)
        self.assertEqual(len(audit.verified), 0)
        self.assertEqual(len(audit.needs_action), 0)
        self.assertEqual(len(audit.errors), 0)

    def test_anvil_admins_shared_as_owner(self):
        WorkspaceGroupSharingFactory.create(
            workspace=self.upload_workspace.workspace, group=self.anvil_admins, access=WorkspaceGroupSharing.OWNER
        )
        audit = upload_workspace_audit.UploadWorkspaceAudit()
        audit.audit_workspace_and_group(self.upload_workspace, self.anvil_admins)
        self.assertEqual(len(audit.verified), 0)
        self.assertEqual(len(audit.needs_action), 0)
        self.assertEqual(len(audit.errors), 0)

    def test_anvil_devs_shared_as_writer_no_compute(self):
        # Share the workspace with the group.
        WorkspaceGroupSharingFactory.create(
            workspace=self.upload_workspace.workspace, group=self.anvil_devs, access=WorkspaceGroupSharing.WRITER
        )
        audit = upload_workspace_audit.UploadWorkspaceAudit()
        audit.audit_workspace_and_group(self.upload_workspace, self.anvil_devs)
        self.assertEqual(len(audit.verified), 0)
        self.assertEqual(len(audit.needs_action), 0)
        self.assertEqual(len(audit.errors), 0)

    def test_anvil_devs_not_shared(self):
        audit = upload_workspace_audit.UploadWorkspaceAudit()
        audit.audit_workspace_and_group(self.upload_workspace, self.anvil_devs)
        self.assertEqual(len(audit.verified), 0)
        self.assertEqual(len(audit.needs_action), 0)
        self.assertEqual(len(audit.errors), 0)

    def test_anvil_devs_shared_as_writer_can_compute(self):
        WorkspaceGroupSharingFactory.create(
            workspace=self.upload_workspace.workspace,
            group=self.anvil_devs,
            access=WorkspaceGroupSharing.WRITER,
            can_compute=True,
        )
        audit = upload_workspace_audit.UploadWorkspaceAudit()
        audit.audit_workspace_and_group(self.upload_workspace, self.anvil_devs)
        self.assertEqual(len(audit.verified), 0)
        self.assertEqual(len(audit.needs_action), 0)
        self.assertEqual(len(audit.errors), 0)

    def test_anvil_devs_shared_as_reader(self):
        WorkspaceGroupSharingFactory.create(
            workspace=self.upload_workspace.workspace, group=self.anvil_devs, access=WorkspaceGroupSharing.READER
        )
        audit = upload_workspace_audit.UploadWorkspaceAudit()
        audit.audit_workspace_and_group(self.upload_workspace, self.anvil_devs)
        self.assertEqual(len(audit.verified), 0)
        self.assertEqual(len(audit.needs_action), 0)
        self.assertEqual(len(audit.errors), 0)

    def test_anvil_devs_shared_as_owner(self):
        WorkspaceGroupSharingFactory.create(
            workspace=self.upload_workspace.workspace, group=self.anvil_devs, access=WorkspaceGroupSharing.OWNER
        )
        audit = upload_workspace_audit.UploadWorkspaceAudit()
        audit.audit_workspace_and_group(self.upload_workspace, self.anvil_devs)
        self.assertEqual(len(audit.verified), 0)
        self.assertEqual(len(audit.needs_action), 0)
        self.assertEqual(len(audit.errors), 0)

    def test_other_group_shared_as_writer_no_compute(self):
        # Share the workspace with the group.
        sharing = WorkspaceGroupSharingFactory.create(
            workspace=self.upload_workspace.workspace, group=self.other_group, access=WorkspaceGroupSharing.WRITER
        )
        audit = upload_workspace_audit.UploadWorkspaceAudit()
        audit.audit_workspace_and_group(self.upload_workspace, self.other_group)
        self.assertEqual(len(audit.verified), 0)
        self.assertEqual(len(audit.needs_action), 0)
        self.assertEqual(len(audit.errors), 1)
        record = audit.errors[0]
        self.assertIsInstance(record, upload_workspace_audit.StopSharing)
        self.assertEqual(record.workspace, self.upload_workspace)
        self.assertEqual(record.managed_group, self.other_group)
        self.assertEqual(record.current_sharing_instance, sharing)
        self.assertEqual(record.note, upload_workspace_audit.UploadWorkspaceAudit.OTHER_GROUP_NO_ACCESS)

    def test_other_group_not_shared(self):
        audit = upload_workspace_audit.UploadWorkspaceAudit()
        audit.audit_workspace_and_group(self.upload_workspace, self.other_group)
        self.assertEqual(len(audit.verified), 1)
        self.assertEqual(len(audit.needs_action), 0)
        self.assertEqual(len(audit.errors), 0)
        record = audit.verified[0]
        self.assertIsInstance(record, upload_workspace_audit.VerifiedNotShared)
        self.assertEqual(record.workspace, self.upload_workspace)
        self.assertEqual(record.managed_group, self.other_group)
        self.assertEqual(record.current_sharing_instance, None)
        self.assertEqual(record.note, upload_workspace_audit.UploadWorkspaceAudit.OTHER_GROUP_NO_ACCESS)

    def test_other_group_shared_as_writer_can_compute(self):
        sharing = WorkspaceGroupSharingFactory.create(
            workspace=self.upload_workspace.workspace,
            group=self.other_group,
            access=WorkspaceGroupSharing.WRITER,
            can_compute=True,
        )
        audit = upload_workspace_audit.UploadWorkspaceAudit()
        audit.audit_workspace_and_group(self.upload_workspace, self.other_group)
        self.assertEqual(len(audit.verified), 0)
        self.assertEqual(len(audit.needs_action), 0)
        self.assertEqual(len(audit.errors), 1)
        record = audit.errors[0]
        self.assertIsInstance(record, upload_workspace_audit.StopSharing)
        self.assertEqual(record.workspace, self.upload_workspace)
        self.assertEqual(record.managed_group, self.other_group)
        self.assertEqual(record.current_sharing_instance, sharing)
        self.assertEqual(record.note, upload_workspace_audit.UploadWorkspaceAudit.OTHER_GROUP_NO_ACCESS)

    def test_other_group_shared_as_reader(self):
        sharing = WorkspaceGroupSharingFactory.create(
            workspace=self.upload_workspace.workspace, group=self.other_group, access=WorkspaceGroupSharing.READER
        )
        audit = upload_workspace_audit.UploadWorkspaceAudit()
        audit.audit_workspace_and_group(self.upload_workspace, self.other_group)
        self.assertEqual(len(audit.verified), 0)
        self.assertEqual(len(audit.needs_action), 0)
        self.assertEqual(len(audit.errors), 1)
        record = audit.errors[0]
        self.assertIsInstance(record, upload_workspace_audit.StopSharing)
        self.assertEqual(record.workspace, self.upload_workspace)
        self.assertEqual(record.managed_group, self.other_group)
        self.assertEqual(record.current_sharing_instance, sharing)
        self.assertEqual(record.note, upload_workspace_audit.UploadWorkspaceAudit.OTHER_GROUP_NO_ACCESS)

    def test_other_group_shared_as_owner(self):
        sharing = WorkspaceGroupSharingFactory.create(
            workspace=self.upload_workspace.workspace, group=self.other_group, access=WorkspaceGroupSharing.OWNER
        )
        audit = upload_workspace_audit.UploadWorkspaceAudit()
        audit.audit_workspace_and_group(self.upload_workspace, self.other_group)
        self.assertEqual(len(audit.verified), 0)
        self.assertEqual(len(audit.needs_action), 0)
        self.assertEqual(len(audit.errors), 1)
        record = audit.errors[0]
        self.assertIsInstance(record, upload_workspace_audit.StopSharing)
        self.assertEqual(record.workspace, self.upload_workspace)
        self.assertEqual(record.managed_group, self.other_group)
        self.assertEqual(record.current_sharing_instance, sharing)
        self.assertEqual(record.note, upload_workspace_audit.UploadWorkspaceAudit.OTHER_GROUP_NO_ACCESS)


class UploadWorkspaceAuthDomainAuditTest(TestCase):
    """General tests of the `UploadWorkspaceAuthDomainAudit` class."""

    def test_completed(self):
        """The completed attribute is set appropriately."""
        # Instantiate the class.
        audit = upload_workspace_auth_domain_audit.UploadWorkspaceAuthDomainAudit()
        self.assertFalse(audit.completed)
        audit.run_audit()
        self.assertTrue(audit.completed)

    def test_no_upload_workspaces(self):
        """The audit works if there are no UploadWorkspaces."""
        audit = upload_workspace_auth_domain_audit.UploadWorkspaceAuthDomainAudit()
        audit.run_audit()
        self.assertEqual(len(audit.verified), 0)
        self.assertEqual(len(audit.needs_action), 0)
        self.assertEqual(len(audit.errors), 0)

    def test_one_upload_workspace_no_groups(self):
        upload_workspace = factories.UploadWorkspaceFactory.create()
        audit = upload_workspace_auth_domain_audit.UploadWorkspaceAuthDomainAudit()
        audit.run_audit()
        self.assertEqual(len(audit.verified), 0)
        self.assertEqual(len(audit.needs_action), 0)
        self.assertEqual(len(audit.errors), 0)
        self.assertEqual(len(audit.queryset), 1)
        self.assertIn(upload_workspace, audit.queryset)

    def test_two_upload_workspace_no_groups(self):
        upload_workspace_1 = factories.UploadWorkspaceFactory.create()
        upload_workspace_2 = factories.UploadWorkspaceFactory.create()
        audit = upload_workspace_auth_domain_audit.UploadWorkspaceAuthDomainAudit()
        audit.run_audit()
        self.assertEqual(len(audit.verified), 0)
        self.assertEqual(len(audit.needs_action), 0)
        self.assertEqual(len(audit.errors), 0)
        self.assertEqual(len(audit.queryset), 2)
        self.assertIn(upload_workspace_1, audit.queryset)
        self.assertIn(upload_workspace_2, audit.queryset)

    def test_finish_tests(self):
        self.fail()


class UploadWorkspaceAuthDomainAuditFutureCycleTest(TestCase):
    """Tests for the `UploadWorkspaceAuthDomainAudit` class for future cycle UploadWorkspaces."""

    def setUp(self):
        super().setUp()
        self.rc_uploader_group = ManagedGroupFactory.create()
        self.rc_member_group = ManagedGroupFactory.create()
        self.rc_non_member_group = ManagedGroupFactory.create()
        self.dcc_member_group = ManagedGroupFactory.create(name="GREGOR_DCC_MEMBERS")
        self.dcc_writer_group = ManagedGroupFactory.create(name="GREGOR_DCC_WRITERS")
        self.dcc_admin_group = ManagedGroupFactory.create(name=settings.ANVIL_DCC_ADMINS_GROUP_NAME)
        self.gregor_all_group = ManagedGroupFactory.create(name="GREGOR_ALL")
        self.research_center = factories.ResearchCenterFactory.create(
            uploader_group=self.rc_uploader_group,
            member_group=self.rc_member_group,
            non_member_group=self.rc_non_member_group,
        )
        self.upload_workspace = factories.UploadWorkspaceFactory.create(
            research_center=self.research_center, upload_cycle__is_future=True
        )
        self.auth_domain = self.upload_workspace.workspace.authorization_domains.get()
        self.other_group = ManagedGroupFactory.create()
        self.anvil_admins = ManagedGroupFactory.create(name="anvil-admins")
        self.anvil_devs = ManagedGroupFactory.create(name="anvil_devs")

    def test_rc_uploaders_not_member(self):
        audit = upload_workspace_auth_domain_audit.UploadWorkspaceAuthDomainAudit()
        audit.audit_workspace_and_group(self.upload_workspace, self.rc_uploader_group)
        self.assertEqual(len(audit.verified), 0)
        self.assertEqual(len(audit.needs_action), 1)
        self.assertEqual(len(audit.errors), 0)
        record = audit.needs_action[0]
        self.assertIsInstance(record, upload_workspace_auth_domain_audit.AddMember)
        self.assertEqual(record.workspace, self.upload_workspace)
        self.assertEqual(record.managed_group, self.rc_uploader_group)
        self.assertIsNone(record.current_membership_instance)
        self.assertEqual(
            record.note, upload_workspace_auth_domain_audit.UploadWorkspaceAuthDomainAudit.RC_BEFORE_COMBINED
        )

    def test_rc_uploaders_member(self):
        membership = GroupGroupMembershipFactory.create(
            parent_group=self.upload_workspace.workspace.authorization_domains.first(),
            child_group=self.rc_uploader_group,
            role=GroupGroupMembership.MEMBER,
        )
        audit = upload_workspace_auth_domain_audit.UploadWorkspaceAuthDomainAudit()
        audit.audit_workspace_and_group(self.upload_workspace, self.rc_uploader_group)
        self.assertEqual(len(audit.verified), 1)
        self.assertEqual(len(audit.needs_action), 0)
        self.assertEqual(len(audit.errors), 0)
        record = audit.verified[0]
        self.assertIsInstance(record, upload_workspace_auth_domain_audit.VerifiedMember)
        self.assertEqual(record.workspace, self.upload_workspace)
        self.assertEqual(record.managed_group, self.rc_uploader_group)
        self.assertEqual(record.current_membership_instance, membership)
        self.assertEqual(
            record.note, upload_workspace_auth_domain_audit.UploadWorkspaceAuthDomainAudit.RC_BEFORE_COMBINED
        )

    def test_rc_uploaders_admin(self):
        membership = GroupGroupMembershipFactory.create(
            parent_group=self.upload_workspace.workspace.authorization_domains.first(),
            child_group=self.rc_uploader_group,
            role=GroupGroupMembership.ADMIN,
        )
        audit = upload_workspace_auth_domain_audit.UploadWorkspaceAuthDomainAudit()
        audit.audit_workspace_and_group(self.upload_workspace, self.rc_uploader_group)
        self.assertEqual(len(audit.verified), 0)
        self.assertEqual(len(audit.needs_action), 0)
        self.assertEqual(len(audit.errors), 1)
        record = audit.errors[0]
        self.assertIsInstance(record, upload_workspace_auth_domain_audit.ChangeToMember)
        self.assertEqual(record.workspace, self.upload_workspace)
        self.assertEqual(record.managed_group, self.rc_uploader_group)
        self.assertEqual(record.current_membership_instance, membership)
        self.assertEqual(
            record.note, upload_workspace_auth_domain_audit.UploadWorkspaceAuthDomainAudit.RC_BEFORE_COMBINED
        )

    def test_rc_members_not_member(self):
        audit = upload_workspace_auth_domain_audit.UploadWorkspaceAuthDomainAudit()
        audit.audit_workspace_and_group(self.upload_workspace, self.rc_member_group)
        self.assertEqual(len(audit.verified), 0)
        self.assertEqual(len(audit.needs_action), 1)
        self.assertEqual(len(audit.errors), 0)
        record = audit.needs_action[0]
        self.assertIsInstance(record, upload_workspace_auth_domain_audit.AddMember)
        self.assertEqual(record.workspace, self.upload_workspace)
        self.assertEqual(record.managed_group, self.rc_member_group)
        self.assertIsNone(record.current_membership_instance)
        self.assertEqual(
            record.note, upload_workspace_auth_domain_audit.UploadWorkspaceAuthDomainAudit.RC_BEFORE_COMBINED
        )

    def test_rc_members_member(self):
        membership = GroupGroupMembershipFactory.create(
            parent_group=self.upload_workspace.workspace.authorization_domains.first(),
            child_group=self.rc_member_group,
            role=GroupGroupMembership.MEMBER,
        )
        audit = upload_workspace_auth_domain_audit.UploadWorkspaceAuthDomainAudit()
        audit.audit_workspace_and_group(self.upload_workspace, self.rc_member_group)
        self.assertEqual(len(audit.verified), 1)
        self.assertEqual(len(audit.needs_action), 0)
        self.assertEqual(len(audit.errors), 0)
        record = audit.verified[0]
        self.assertIsInstance(record, upload_workspace_auth_domain_audit.VerifiedMember)
        self.assertEqual(record.workspace, self.upload_workspace)
        self.assertEqual(record.managed_group, self.rc_member_group)
        self.assertEqual(record.current_membership_instance, membership)
        self.assertEqual(
            record.note, upload_workspace_auth_domain_audit.UploadWorkspaceAuthDomainAudit.RC_BEFORE_COMBINED
        )

    def test_rc_members_admin(self):
        membership = GroupGroupMembershipFactory.create(
            parent_group=self.upload_workspace.workspace.authorization_domains.first(),
            child_group=self.rc_member_group,
            role=GroupGroupMembership.ADMIN,
        )
        audit = upload_workspace_auth_domain_audit.UploadWorkspaceAuthDomainAudit()
        audit.audit_workspace_and_group(self.upload_workspace, self.rc_member_group)
        self.assertEqual(len(audit.verified), 0)
        self.assertEqual(len(audit.needs_action), 0)
        self.assertEqual(len(audit.errors), 1)
        record = audit.errors[0]
        self.assertIsInstance(record, upload_workspace_auth_domain_audit.ChangeToMember)
        self.assertEqual(record.workspace, self.upload_workspace)
        self.assertEqual(record.managed_group, self.rc_member_group)
        self.assertEqual(record.current_membership_instance, membership)
        self.assertEqual(
            record.note, upload_workspace_auth_domain_audit.UploadWorkspaceAuthDomainAudit.RC_BEFORE_COMBINED
        )

    def test_rc_non_members_not_member(self):
        audit = upload_workspace_auth_domain_audit.UploadWorkspaceAuthDomainAudit()
        audit.audit_workspace_and_group(self.upload_workspace, self.rc_non_member_group)
        self.assertEqual(len(audit.verified), 0)
        self.assertEqual(len(audit.needs_action), 1)
        self.assertEqual(len(audit.errors), 0)
        record = audit.needs_action[0]
        self.assertIsInstance(record, upload_workspace_auth_domain_audit.AddMember)
        self.assertEqual(record.workspace, self.upload_workspace)
        self.assertEqual(record.managed_group, self.rc_non_member_group)
        self.assertIsNone(record.current_membership_instance)
        self.assertEqual(record.note, upload_workspace_auth_domain_audit.UploadWorkspaceAuthDomainAudit.RC_NON_MEMBERS)

    def test_rc_non_members_member(self):
        membership = GroupGroupMembershipFactory.create(
            parent_group=self.upload_workspace.workspace.authorization_domains.first(),
            child_group=self.rc_non_member_group,
            role=GroupGroupMembership.MEMBER,
        )
        audit = upload_workspace_auth_domain_audit.UploadWorkspaceAuthDomainAudit()
        audit.audit_workspace_and_group(self.upload_workspace, self.rc_non_member_group)
        self.assertEqual(len(audit.verified), 1)
        self.assertEqual(len(audit.needs_action), 0)
        self.assertEqual(len(audit.errors), 0)
        record = audit.verified[0]
        self.assertIsInstance(record, upload_workspace_auth_domain_audit.VerifiedMember)
        self.assertEqual(record.workspace, self.upload_workspace)
        self.assertEqual(record.managed_group, self.rc_non_member_group)
        self.assertEqual(record.current_membership_instance, membership)
        self.assertEqual(record.note, upload_workspace_auth_domain_audit.UploadWorkspaceAuthDomainAudit.RC_NON_MEMBERS)

    def test_rc_non_members_admin(self):
        membership = GroupGroupMembershipFactory.create(
            parent_group=self.upload_workspace.workspace.authorization_domains.first(),
            child_group=self.rc_non_member_group,
            role=GroupGroupMembership.ADMIN,
        )
        audit = upload_workspace_auth_domain_audit.UploadWorkspaceAuthDomainAudit()
        audit.audit_workspace_and_group(self.upload_workspace, self.rc_non_member_group)
        self.assertEqual(len(audit.verified), 0)
        self.assertEqual(len(audit.needs_action), 0)
        self.assertEqual(len(audit.errors), 1)
        record = audit.errors[0]
        self.assertIsInstance(record, upload_workspace_auth_domain_audit.ChangeToMember)
        self.assertEqual(record.workspace, self.upload_workspace)
        self.assertEqual(record.managed_group, self.rc_non_member_group)
        self.assertEqual(record.current_membership_instance, membership)
        self.assertEqual(record.note, upload_workspace_auth_domain_audit.UploadWorkspaceAuthDomainAudit.RC_NON_MEMBERS)

    def test_dcc_admins_not_member(self):
        audit = upload_workspace_auth_domain_audit.UploadWorkspaceAuthDomainAudit()
        audit.audit_workspace_and_group(self.upload_workspace, self.dcc_admin_group)
        self.assertEqual(len(audit.verified), 0)
        self.assertEqual(len(audit.needs_action), 1)
        self.assertEqual(len(audit.errors), 0)
        record = audit.needs_action[0]
        self.assertIsInstance(record, upload_workspace_auth_domain_audit.AddAdmin)
        self.assertEqual(record.workspace, self.upload_workspace)
        self.assertEqual(record.managed_group, self.dcc_admin_group)
        self.assertIsNone(record.current_membership_instance)
        self.assertEqual(record.note, upload_workspace_auth_domain_audit.UploadWorkspaceAuthDomainAudit.DCC_ADMINS)

    def test_dcc_admins_member(self):
        membership = GroupGroupMembershipFactory.create(
            parent_group=self.upload_workspace.workspace.authorization_domains.first(),
            child_group=self.dcc_admin_group,
            role=GroupGroupMembership.MEMBER,
        )
        audit = upload_workspace_auth_domain_audit.UploadWorkspaceAuthDomainAudit()
        audit.audit_workspace_and_group(self.upload_workspace, self.dcc_admin_group)
        self.assertEqual(len(audit.verified), 0)
        self.assertEqual(len(audit.needs_action), 1)
        self.assertEqual(len(audit.errors), 0)
        record = audit.needs_action[0]
        self.assertIsInstance(record, upload_workspace_auth_domain_audit.ChangeToAdmin)
        self.assertEqual(record.workspace, self.upload_workspace)
        self.assertEqual(record.managed_group, self.dcc_admin_group)
        self.assertEqual(record.current_membership_instance, membership)
        self.assertEqual(record.note, upload_workspace_auth_domain_audit.UploadWorkspaceAuthDomainAudit.DCC_ADMINS)

    def test_dcc_admins_admin(self):
        membership = GroupGroupMembershipFactory.create(
            parent_group=self.upload_workspace.workspace.authorization_domains.first(),
            child_group=self.dcc_admin_group,
            role=GroupGroupMembership.ADMIN,
        )
        audit = upload_workspace_auth_domain_audit.UploadWorkspaceAuthDomainAudit()
        audit.audit_workspace_and_group(self.upload_workspace, self.dcc_admin_group)
        self.assertEqual(len(audit.verified), 1)
        self.assertEqual(len(audit.needs_action), 0)
        self.assertEqual(len(audit.errors), 0)
        record = audit.verified[0]
        self.assertIsInstance(record, upload_workspace_auth_domain_audit.VerifiedAdmin)
        self.assertEqual(record.workspace, self.upload_workspace)
        self.assertEqual(record.managed_group, self.dcc_admin_group)
        self.assertEqual(record.current_membership_instance, membership)
        self.assertEqual(record.note, upload_workspace_auth_domain_audit.UploadWorkspaceAuthDomainAudit.DCC_ADMINS)

    @override_settings(ANVIL_DCC_ADMINS_GROUP_NAME="foobar")
    def test_dcc_admins_different_setting(self):
        group = ManagedGroupFactory.create(name="foobar")
        audit = upload_workspace_auth_domain_audit.UploadWorkspaceAuthDomainAudit()
        audit.audit_workspace_and_group(self.upload_workspace, group)
        self.assertEqual(len(audit.verified), 0)
        self.assertEqual(len(audit.needs_action), 1)
        self.assertEqual(len(audit.errors), 0)
        record = audit.needs_action[0]
        self.assertIsInstance(record, upload_workspace_auth_domain_audit.AddAdmin)
        self.assertEqual(record.workspace, self.upload_workspace)
        self.assertEqual(record.managed_group, group)
        self.assertIsNone(record.current_membership_instance)
        self.assertEqual(record.note, upload_workspace_auth_domain_audit.UploadWorkspaceAuthDomainAudit.DCC_ADMINS)


class UploadWorkspaceAuthDomainAuditCurrentCycleBeforeComputeTest(TestCase):
    """Tests for the `UploadWorkspaceAuthDomainAudit` class for current cycle UploadWorkspaces before compute."""

    def setUp(self):
        super().setUp()
        self.rc_uploader_group = ManagedGroupFactory.create()
        self.rc_member_group = ManagedGroupFactory.create()
        self.rc_non_member_group = ManagedGroupFactory.create()
        self.dcc_member_group = ManagedGroupFactory.create(name="GREGOR_DCC_MEMBERS")
        self.dcc_writer_group = ManagedGroupFactory.create(name="GREGOR_DCC_WRITERS")
        self.dcc_admin_group = ManagedGroupFactory.create(name=settings.ANVIL_DCC_ADMINS_GROUP_NAME)
        self.gregor_all_group = ManagedGroupFactory.create(name="GREGOR_ALL")
        self.research_center = factories.ResearchCenterFactory.create(
            uploader_group=self.rc_uploader_group,
            member_group=self.rc_member_group,
            non_member_group=self.rc_non_member_group,
        )
        self.upload_workspace = factories.UploadWorkspaceFactory.create(
            research_center=self.research_center,
            upload_cycle__is_current=True,
            upload_cycle__date_ready_for_compute=None,
        )
        self.auth_domain = self.upload_workspace.workspace.authorization_domains.get()
        self.other_group = ManagedGroupFactory.create()
        self.anvil_admins = ManagedGroupFactory.create(name="anvil-admins")
        self.anvil_devs = ManagedGroupFactory.create(name="anvil_devs")

    def test_rc_uploaders_not_member(self):
        audit = upload_workspace_auth_domain_audit.UploadWorkspaceAuthDomainAudit()
        audit.audit_workspace_and_group(self.upload_workspace, self.rc_uploader_group)
        self.assertEqual(len(audit.verified), 0)
        self.assertEqual(len(audit.needs_action), 1)
        self.assertEqual(len(audit.errors), 0)
        record = audit.needs_action[0]
        self.assertIsInstance(record, upload_workspace_auth_domain_audit.AddMember)
        self.assertEqual(record.workspace, self.upload_workspace)
        self.assertEqual(record.managed_group, self.rc_uploader_group)
        self.assertIsNone(record.current_membership_instance)
        self.assertEqual(
            record.note, upload_workspace_auth_domain_audit.UploadWorkspaceAuthDomainAudit.RC_BEFORE_COMBINED
        )

    def test_rc_uploaders_member(self):
        membership = GroupGroupMembershipFactory.create(
            parent_group=self.upload_workspace.workspace.authorization_domains.first(),
            child_group=self.rc_uploader_group,
            role=GroupGroupMembership.MEMBER,
        )
        audit = upload_workspace_auth_domain_audit.UploadWorkspaceAuthDomainAudit()
        audit.audit_workspace_and_group(self.upload_workspace, self.rc_uploader_group)
        self.assertEqual(len(audit.verified), 1)
        self.assertEqual(len(audit.needs_action), 0)
        self.assertEqual(len(audit.errors), 0)
        record = audit.verified[0]
        self.assertIsInstance(record, upload_workspace_auth_domain_audit.VerifiedMember)
        self.assertEqual(record.workspace, self.upload_workspace)
        self.assertEqual(record.managed_group, self.rc_uploader_group)
        self.assertEqual(record.current_membership_instance, membership)
        self.assertEqual(
            record.note, upload_workspace_auth_domain_audit.UploadWorkspaceAuthDomainAudit.RC_BEFORE_COMBINED
        )

    def test_rc_uploaders_admin(self):
        membership = GroupGroupMembershipFactory.create(
            parent_group=self.upload_workspace.workspace.authorization_domains.first(),
            child_group=self.rc_uploader_group,
            role=GroupGroupMembership.ADMIN,
        )
        audit = upload_workspace_auth_domain_audit.UploadWorkspaceAuthDomainAudit()
        audit.audit_workspace_and_group(self.upload_workspace, self.rc_uploader_group)
        self.assertEqual(len(audit.verified), 0)
        self.assertEqual(len(audit.needs_action), 0)
        self.assertEqual(len(audit.errors), 1)
        record = audit.errors[0]
        self.assertIsInstance(record, upload_workspace_auth_domain_audit.ChangeToMember)
        self.assertEqual(record.workspace, self.upload_workspace)
        self.assertEqual(record.managed_group, self.rc_uploader_group)
        self.assertEqual(record.current_membership_instance, membership)
        self.assertEqual(
            record.note, upload_workspace_auth_domain_audit.UploadWorkspaceAuthDomainAudit.RC_BEFORE_COMBINED
        )

    def test_rc_members_not_member(self):
        audit = upload_workspace_auth_domain_audit.UploadWorkspaceAuthDomainAudit()
        audit.audit_workspace_and_group(self.upload_workspace, self.rc_member_group)
        self.assertEqual(len(audit.verified), 0)
        self.assertEqual(len(audit.needs_action), 1)
        self.assertEqual(len(audit.errors), 0)
        record = audit.needs_action[0]
        self.assertIsInstance(record, upload_workspace_auth_domain_audit.AddMember)
        self.assertEqual(record.workspace, self.upload_workspace)
        self.assertEqual(record.managed_group, self.rc_member_group)
        self.assertIsNone(record.current_membership_instance)
        self.assertEqual(
            record.note, upload_workspace_auth_domain_audit.UploadWorkspaceAuthDomainAudit.RC_BEFORE_COMBINED
        )

    def test_rc_members_member(self):
        membership = GroupGroupMembershipFactory.create(
            parent_group=self.upload_workspace.workspace.authorization_domains.first(),
            child_group=self.rc_member_group,
            role=GroupGroupMembership.MEMBER,
        )
        audit = upload_workspace_auth_domain_audit.UploadWorkspaceAuthDomainAudit()
        audit.audit_workspace_and_group(self.upload_workspace, self.rc_member_group)
        self.assertEqual(len(audit.verified), 1)
        self.assertEqual(len(audit.needs_action), 0)
        self.assertEqual(len(audit.errors), 0)
        record = audit.verified[0]
        self.assertIsInstance(record, upload_workspace_auth_domain_audit.VerifiedMember)
        self.assertEqual(record.workspace, self.upload_workspace)
        self.assertEqual(record.managed_group, self.rc_member_group)
        self.assertEqual(record.current_membership_instance, membership)
        self.assertEqual(
            record.note, upload_workspace_auth_domain_audit.UploadWorkspaceAuthDomainAudit.RC_BEFORE_COMBINED
        )

    def test_rc_members_admin(self):
        membership = GroupGroupMembershipFactory.create(
            parent_group=self.upload_workspace.workspace.authorization_domains.first(),
            child_group=self.rc_member_group,
            role=GroupGroupMembership.ADMIN,
        )
        audit = upload_workspace_auth_domain_audit.UploadWorkspaceAuthDomainAudit()
        audit.audit_workspace_and_group(self.upload_workspace, self.rc_member_group)
        self.assertEqual(len(audit.verified), 0)
        self.assertEqual(len(audit.needs_action), 0)
        self.assertEqual(len(audit.errors), 1)
        record = audit.errors[0]
        self.assertIsInstance(record, upload_workspace_auth_domain_audit.ChangeToMember)
        self.assertEqual(record.workspace, self.upload_workspace)
        self.assertEqual(record.managed_group, self.rc_member_group)
        self.assertEqual(record.current_membership_instance, membership)
        self.assertEqual(
            record.note, upload_workspace_auth_domain_audit.UploadWorkspaceAuthDomainAudit.RC_BEFORE_COMBINED
        )

    def test_rc_non_members_not_member(self):
        audit = upload_workspace_auth_domain_audit.UploadWorkspaceAuthDomainAudit()
        audit.audit_workspace_and_group(self.upload_workspace, self.rc_non_member_group)
        self.assertEqual(len(audit.verified), 0)
        self.assertEqual(len(audit.needs_action), 1)
        self.assertEqual(len(audit.errors), 0)
        record = audit.needs_action[0]
        self.assertIsInstance(record, upload_workspace_auth_domain_audit.AddMember)
        self.assertEqual(record.workspace, self.upload_workspace)
        self.assertEqual(record.managed_group, self.rc_non_member_group)
        self.assertIsNone(record.current_membership_instance)
        self.assertEqual(record.note, upload_workspace_auth_domain_audit.UploadWorkspaceAuthDomainAudit.RC_NON_MEMBERS)

    def test_rc_non_members_member(self):
        membership = GroupGroupMembershipFactory.create(
            parent_group=self.upload_workspace.workspace.authorization_domains.first(),
            child_group=self.rc_non_member_group,
            role=GroupGroupMembership.MEMBER,
        )
        audit = upload_workspace_auth_domain_audit.UploadWorkspaceAuthDomainAudit()
        audit.audit_workspace_and_group(self.upload_workspace, self.rc_non_member_group)
        self.assertEqual(len(audit.verified), 1)
        self.assertEqual(len(audit.needs_action), 0)
        self.assertEqual(len(audit.errors), 0)
        record = audit.verified[0]
        self.assertIsInstance(record, upload_workspace_auth_domain_audit.VerifiedMember)
        self.assertEqual(record.workspace, self.upload_workspace)
        self.assertEqual(record.managed_group, self.rc_non_member_group)
        self.assertEqual(record.current_membership_instance, membership)
        self.assertEqual(record.note, upload_workspace_auth_domain_audit.UploadWorkspaceAuthDomainAudit.RC_NON_MEMBERS)

    def test_rc_non_members_admin(self):
        membership = GroupGroupMembershipFactory.create(
            parent_group=self.upload_workspace.workspace.authorization_domains.first(),
            child_group=self.rc_non_member_group,
            role=GroupGroupMembership.ADMIN,
        )
        audit = upload_workspace_auth_domain_audit.UploadWorkspaceAuthDomainAudit()
        audit.audit_workspace_and_group(self.upload_workspace, self.rc_non_member_group)
        self.assertEqual(len(audit.verified), 0)
        self.assertEqual(len(audit.needs_action), 0)
        self.assertEqual(len(audit.errors), 1)
        record = audit.errors[0]
        self.assertIsInstance(record, upload_workspace_auth_domain_audit.ChangeToMember)
        self.assertEqual(record.workspace, self.upload_workspace)
        self.assertEqual(record.managed_group, self.rc_non_member_group)
        self.assertEqual(record.current_membership_instance, membership)
        self.assertEqual(record.note, upload_workspace_auth_domain_audit.UploadWorkspaceAuthDomainAudit.RC_NON_MEMBERS)

    def test_dcc_admins_not_member(self):
        audit = upload_workspace_auth_domain_audit.UploadWorkspaceAuthDomainAudit()
        audit.audit_workspace_and_group(self.upload_workspace, self.dcc_admin_group)
        self.assertEqual(len(audit.verified), 0)
        self.assertEqual(len(audit.needs_action), 1)
        self.assertEqual(len(audit.errors), 0)
        record = audit.needs_action[0]
        self.assertIsInstance(record, upload_workspace_auth_domain_audit.AddAdmin)
        self.assertEqual(record.workspace, self.upload_workspace)
        self.assertEqual(record.managed_group, self.dcc_admin_group)
        self.assertIsNone(record.current_membership_instance)
        self.assertEqual(record.note, upload_workspace_auth_domain_audit.UploadWorkspaceAuthDomainAudit.DCC_ADMINS)

    def test_dcc_admins_member(self):
        membership = GroupGroupMembershipFactory.create(
            parent_group=self.upload_workspace.workspace.authorization_domains.first(),
            child_group=self.dcc_admin_group,
            role=GroupGroupMembership.MEMBER,
        )
        audit = upload_workspace_auth_domain_audit.UploadWorkspaceAuthDomainAudit()
        audit.audit_workspace_and_group(self.upload_workspace, self.dcc_admin_group)
        self.assertEqual(len(audit.verified), 0)
        self.assertEqual(len(audit.needs_action), 1)
        self.assertEqual(len(audit.errors), 0)
        record = audit.needs_action[0]
        self.assertIsInstance(record, upload_workspace_auth_domain_audit.ChangeToAdmin)
        self.assertEqual(record.workspace, self.upload_workspace)
        self.assertEqual(record.managed_group, self.dcc_admin_group)
        self.assertEqual(record.current_membership_instance, membership)
        self.assertEqual(record.note, upload_workspace_auth_domain_audit.UploadWorkspaceAuthDomainAudit.DCC_ADMINS)

    def test_dcc_admins_admin(self):
        membership = GroupGroupMembershipFactory.create(
            parent_group=self.upload_workspace.workspace.authorization_domains.first(),
            child_group=self.dcc_admin_group,
            role=GroupGroupMembership.ADMIN,
        )
        audit = upload_workspace_auth_domain_audit.UploadWorkspaceAuthDomainAudit()
        audit.audit_workspace_and_group(self.upload_workspace, self.dcc_admin_group)
        self.assertEqual(len(audit.verified), 1)
        self.assertEqual(len(audit.needs_action), 0)
        self.assertEqual(len(audit.errors), 0)
        record = audit.verified[0]
        self.assertIsInstance(record, upload_workspace_auth_domain_audit.VerifiedAdmin)
        self.assertEqual(record.workspace, self.upload_workspace)
        self.assertEqual(record.managed_group, self.dcc_admin_group)
        self.assertEqual(record.current_membership_instance, membership)
        self.assertEqual(record.note, upload_workspace_auth_domain_audit.UploadWorkspaceAuthDomainAudit.DCC_ADMINS)

    @override_settings(ANVIL_DCC_ADMINS_GROUP_NAME="foobar")
    def test_dcc_admins_different_setting(self):
        group = ManagedGroupFactory.create(name="foobar")
        audit = upload_workspace_auth_domain_audit.UploadWorkspaceAuthDomainAudit()
        audit.audit_workspace_and_group(self.upload_workspace, group)
        self.assertEqual(len(audit.verified), 0)
        self.assertEqual(len(audit.needs_action), 1)
        self.assertEqual(len(audit.errors), 0)
        record = audit.needs_action[0]
        self.assertIsInstance(record, upload_workspace_auth_domain_audit.AddAdmin)
        self.assertEqual(record.workspace, self.upload_workspace)
        self.assertEqual(record.managed_group, group)
        self.assertIsNone(record.current_membership_instance)
        self.assertEqual(record.note, upload_workspace_auth_domain_audit.UploadWorkspaceAuthDomainAudit.DCC_ADMINS)


class UploadWorkspaceAuthDomainAuditCurrentCycleAfterComputeTest(TestCase):
    """Tests for the `UploadWorkspaceAuthDomainAudit` class for current cycle UploadWorkspaces after compute."""

    def setUp(self):
        super().setUp()
        self.rc_uploader_group = ManagedGroupFactory.create()
        self.rc_member_group = ManagedGroupFactory.create()
        self.rc_non_member_group = ManagedGroupFactory.create()
        self.dcc_member_group = ManagedGroupFactory.create(name="GREGOR_DCC_MEMBERS")
        self.dcc_writer_group = ManagedGroupFactory.create(name="GREGOR_DCC_WRITERS")
        self.dcc_admin_group = ManagedGroupFactory.create(name=settings.ANVIL_DCC_ADMINS_GROUP_NAME)
        self.gregor_all_group = ManagedGroupFactory.create(name="GREGOR_ALL")
        self.research_center = factories.ResearchCenterFactory.create(
            uploader_group=self.rc_uploader_group,
            member_group=self.rc_member_group,
            non_member_group=self.rc_non_member_group,
        )
        self.upload_workspace = factories.UploadWorkspaceFactory.create(
            research_center=self.research_center,
            upload_cycle__is_current=True,
        )
        # Set date ready for compute to a non-null value.
        self.upload_workspace.upload_cycle.date_ready_for_compute = self.upload_workspace.upload_cycle.start_date
        self.upload_workspace.upload_cycle.save()
        self.auth_domain = self.upload_workspace.workspace.authorization_domains.get()
        self.other_group = ManagedGroupFactory.create()
        self.anvil_admins = ManagedGroupFactory.create(name="anvil-admins")
        self.anvil_devs = ManagedGroupFactory.create(name="anvil_devs")

    def test_rc_uploaders_not_member(self):
        audit = upload_workspace_auth_domain_audit.UploadWorkspaceAuthDomainAudit()
        audit.audit_workspace_and_group(self.upload_workspace, self.rc_uploader_group)
        self.assertEqual(len(audit.verified), 0)
        self.assertEqual(len(audit.needs_action), 1)
        self.assertEqual(len(audit.errors), 0)
        record = audit.needs_action[0]
        self.assertIsInstance(record, upload_workspace_auth_domain_audit.AddMember)
        self.assertEqual(record.workspace, self.upload_workspace)
        self.assertEqual(record.managed_group, self.rc_uploader_group)
        self.assertIsNone(record.current_membership_instance)
        self.assertEqual(
            record.note, upload_workspace_auth_domain_audit.UploadWorkspaceAuthDomainAudit.RC_BEFORE_COMBINED
        )

    def test_rc_uploaders_member(self):
        membership = GroupGroupMembershipFactory.create(
            parent_group=self.upload_workspace.workspace.authorization_domains.first(),
            child_group=self.rc_uploader_group,
            role=GroupGroupMembership.MEMBER,
        )
        audit = upload_workspace_auth_domain_audit.UploadWorkspaceAuthDomainAudit()
        audit.audit_workspace_and_group(self.upload_workspace, self.rc_uploader_group)
        self.assertEqual(len(audit.verified), 1)
        self.assertEqual(len(audit.needs_action), 0)
        self.assertEqual(len(audit.errors), 0)
        record = audit.verified[0]
        self.assertIsInstance(record, upload_workspace_auth_domain_audit.VerifiedMember)
        self.assertEqual(record.workspace, self.upload_workspace)
        self.assertEqual(record.managed_group, self.rc_uploader_group)
        self.assertEqual(record.current_membership_instance, membership)
        self.assertEqual(
            record.note, upload_workspace_auth_domain_audit.UploadWorkspaceAuthDomainAudit.RC_BEFORE_COMBINED
        )

    def test_rc_uploaders_admin(self):
        membership = GroupGroupMembershipFactory.create(
            parent_group=self.upload_workspace.workspace.authorization_domains.first(),
            child_group=self.rc_uploader_group,
            role=GroupGroupMembership.ADMIN,
        )
        audit = upload_workspace_auth_domain_audit.UploadWorkspaceAuthDomainAudit()
        audit.audit_workspace_and_group(self.upload_workspace, self.rc_uploader_group)
        self.assertEqual(len(audit.verified), 0)
        self.assertEqual(len(audit.needs_action), 0)
        self.assertEqual(len(audit.errors), 1)
        record = audit.errors[0]
        self.assertIsInstance(record, upload_workspace_auth_domain_audit.ChangeToMember)
        self.assertEqual(record.workspace, self.upload_workspace)
        self.assertEqual(record.managed_group, self.rc_uploader_group)
        self.assertEqual(record.current_membership_instance, membership)
        self.assertEqual(
            record.note, upload_workspace_auth_domain_audit.UploadWorkspaceAuthDomainAudit.RC_BEFORE_COMBINED
        )

    def test_rc_members_not_member(self):
        audit = upload_workspace_auth_domain_audit.UploadWorkspaceAuthDomainAudit()
        audit.audit_workspace_and_group(self.upload_workspace, self.rc_member_group)
        self.assertEqual(len(audit.verified), 0)
        self.assertEqual(len(audit.needs_action), 1)
        self.assertEqual(len(audit.errors), 0)
        record = audit.needs_action[0]
        self.assertIsInstance(record, upload_workspace_auth_domain_audit.AddMember)
        self.assertEqual(record.workspace, self.upload_workspace)
        self.assertEqual(record.managed_group, self.rc_member_group)
        self.assertIsNone(record.current_membership_instance)
        self.assertEqual(
            record.note, upload_workspace_auth_domain_audit.UploadWorkspaceAuthDomainAudit.RC_BEFORE_COMBINED
        )

    def test_rc_members_member(self):
        membership = GroupGroupMembershipFactory.create(
            parent_group=self.upload_workspace.workspace.authorization_domains.first(),
            child_group=self.rc_member_group,
            role=GroupGroupMembership.MEMBER,
        )
        audit = upload_workspace_auth_domain_audit.UploadWorkspaceAuthDomainAudit()
        audit.audit_workspace_and_group(self.upload_workspace, self.rc_member_group)
        self.assertEqual(len(audit.verified), 1)
        self.assertEqual(len(audit.needs_action), 0)
        self.assertEqual(len(audit.errors), 0)
        record = audit.verified[0]
        self.assertIsInstance(record, upload_workspace_auth_domain_audit.VerifiedMember)
        self.assertEqual(record.workspace, self.upload_workspace)
        self.assertEqual(record.managed_group, self.rc_member_group)
        self.assertEqual(record.current_membership_instance, membership)
        self.assertEqual(
            record.note, upload_workspace_auth_domain_audit.UploadWorkspaceAuthDomainAudit.RC_BEFORE_COMBINED
        )

    def test_rc_members_admin(self):
        membership = GroupGroupMembershipFactory.create(
            parent_group=self.upload_workspace.workspace.authorization_domains.first(),
            child_group=self.rc_member_group,
            role=GroupGroupMembership.ADMIN,
        )
        audit = upload_workspace_auth_domain_audit.UploadWorkspaceAuthDomainAudit()
        audit.audit_workspace_and_group(self.upload_workspace, self.rc_member_group)
        self.assertEqual(len(audit.verified), 0)
        self.assertEqual(len(audit.needs_action), 0)
        self.assertEqual(len(audit.errors), 1)
        record = audit.errors[0]
        self.assertIsInstance(record, upload_workspace_auth_domain_audit.ChangeToMember)
        self.assertEqual(record.workspace, self.upload_workspace)
        self.assertEqual(record.managed_group, self.rc_member_group)
        self.assertEqual(record.current_membership_instance, membership)
        self.assertEqual(
            record.note, upload_workspace_auth_domain_audit.UploadWorkspaceAuthDomainAudit.RC_BEFORE_COMBINED
        )

    def test_dcc_admins_not_member(self):
        audit = upload_workspace_auth_domain_audit.UploadWorkspaceAuthDomainAudit()
        audit.audit_workspace_and_group(self.upload_workspace, self.dcc_admin_group)
        self.assertEqual(len(audit.verified), 0)
        self.assertEqual(len(audit.needs_action), 1)
        self.assertEqual(len(audit.errors), 0)
        record = audit.needs_action[0]
        self.assertIsInstance(record, upload_workspace_auth_domain_audit.AddAdmin)
        self.assertEqual(record.workspace, self.upload_workspace)
        self.assertEqual(record.managed_group, self.dcc_admin_group)
        self.assertIsNone(record.current_membership_instance)
        self.assertEqual(record.note, upload_workspace_auth_domain_audit.UploadWorkspaceAuthDomainAudit.DCC_ADMINS)

    def test_dcc_admins_member(self):
        membership = GroupGroupMembershipFactory.create(
            parent_group=self.upload_workspace.workspace.authorization_domains.first(),
            child_group=self.dcc_admin_group,
            role=GroupGroupMembership.MEMBER,
        )
        audit = upload_workspace_auth_domain_audit.UploadWorkspaceAuthDomainAudit()
        audit.audit_workspace_and_group(self.upload_workspace, self.dcc_admin_group)
        self.assertEqual(len(audit.verified), 0)
        self.assertEqual(len(audit.needs_action), 1)
        self.assertEqual(len(audit.errors), 0)
        record = audit.needs_action[0]
        self.assertIsInstance(record, upload_workspace_auth_domain_audit.ChangeToAdmin)
        self.assertEqual(record.workspace, self.upload_workspace)
        self.assertEqual(record.managed_group, self.dcc_admin_group)
        self.assertEqual(record.current_membership_instance, membership)
        self.assertEqual(record.note, upload_workspace_auth_domain_audit.UploadWorkspaceAuthDomainAudit.DCC_ADMINS)

    def test_dcc_admins_admin(self):
        membership = GroupGroupMembershipFactory.create(
            parent_group=self.upload_workspace.workspace.authorization_domains.first(),
            child_group=self.dcc_admin_group,
            role=GroupGroupMembership.ADMIN,
        )
        audit = upload_workspace_auth_domain_audit.UploadWorkspaceAuthDomainAudit()
        audit.audit_workspace_and_group(self.upload_workspace, self.dcc_admin_group)
        self.assertEqual(len(audit.verified), 1)
        self.assertEqual(len(audit.needs_action), 0)
        self.assertEqual(len(audit.errors), 0)
        record = audit.verified[0]
        self.assertIsInstance(record, upload_workspace_auth_domain_audit.VerifiedAdmin)
        self.assertEqual(record.workspace, self.upload_workspace)
        self.assertEqual(record.managed_group, self.dcc_admin_group)
        self.assertEqual(record.current_membership_instance, membership)
        self.assertEqual(record.note, upload_workspace_auth_domain_audit.UploadWorkspaceAuthDomainAudit.DCC_ADMINS)

    @override_settings(ANVIL_DCC_ADMINS_GROUP_NAME="foobar")
    def test_dcc_admins_different_setting(self):
        group = ManagedGroupFactory.create(name="foobar")
        audit = upload_workspace_auth_domain_audit.UploadWorkspaceAuthDomainAudit()
        audit.audit_workspace_and_group(self.upload_workspace, group)
        self.assertEqual(len(audit.verified), 0)
        self.assertEqual(len(audit.needs_action), 1)
        self.assertEqual(len(audit.errors), 0)
        record = audit.needs_action[0]
        self.assertIsInstance(record, upload_workspace_auth_domain_audit.AddAdmin)
        self.assertEqual(record.workspace, self.upload_workspace)
        self.assertEqual(record.managed_group, group)
        self.assertIsNone(record.current_membership_instance)
        self.assertEqual(record.note, upload_workspace_auth_domain_audit.UploadWorkspaceAuthDomainAudit.DCC_ADMINS)


class UploadWorkspaceAuthDomainAuditPastCycleBeforeQCCompleteTest(TestCase):
    """Tests for the `UploadWorkspaceAuthDomainAudit` class for past cycles before QC is complete.

    Expectations at this point in the upload cycle:
    - RC uploader group should not have direct access.
    - DCC writer group should not have direct access.
    """

    def setUp(self):
        super().setUp()
        self.rc_uploader_group = ManagedGroupFactory.create()
        self.rc_member_group = ManagedGroupFactory.create()
        self.rc_non_member_group = ManagedGroupFactory.create()
        self.dcc_member_group = ManagedGroupFactory.create(name="GREGOR_DCC_MEMBERS")
        self.dcc_writer_group = ManagedGroupFactory.create(name="GREGOR_DCC_WRITERS")
        self.dcc_admin_group = ManagedGroupFactory.create(name=settings.ANVIL_DCC_ADMINS_GROUP_NAME)
        self.gregor_all_group = ManagedGroupFactory.create(name="GREGOR_ALL")
        self.research_center = factories.ResearchCenterFactory.create(
            uploader_group=self.rc_uploader_group,
            member_group=self.rc_member_group,
            non_member_group=self.rc_non_member_group,
        )
        self.upload_workspace = factories.UploadWorkspaceFactory.create(
            research_center=self.research_center,
            upload_cycle__is_past=True,
        )
        self.auth_domain = self.upload_workspace.workspace.authorization_domains.get()
        self.other_group = ManagedGroupFactory.create()
        self.anvil_admins = ManagedGroupFactory.create(name="anvil-admins")
        self.anvil_devs = ManagedGroupFactory.create(name="anvil_devs")

    def test_rc_uploaders_not_member(self):
        audit = upload_workspace_auth_domain_audit.UploadWorkspaceAuthDomainAudit()
        audit.audit_workspace_and_group(self.upload_workspace, self.rc_uploader_group)
        self.assertEqual(len(audit.verified), 0)
        self.assertEqual(len(audit.needs_action), 1)
        self.assertEqual(len(audit.errors), 0)
        record = audit.needs_action[0]
        self.assertIsInstance(record, upload_workspace_auth_domain_audit.AddMember)
        self.assertEqual(record.workspace, self.upload_workspace)
        self.assertEqual(record.managed_group, self.rc_uploader_group)
        self.assertIsNone(record.current_membership_instance)
        self.assertEqual(
            record.note, upload_workspace_auth_domain_audit.UploadWorkspaceAuthDomainAudit.RC_BEFORE_COMBINED
        )

    def test_rc_uploaders_member(self):
        membership = GroupGroupMembershipFactory.create(
            parent_group=self.upload_workspace.workspace.authorization_domains.first(),
            child_group=self.rc_uploader_group,
            role=GroupGroupMembership.MEMBER,
        )
        audit = upload_workspace_auth_domain_audit.UploadWorkspaceAuthDomainAudit()
        audit.audit_workspace_and_group(self.upload_workspace, self.rc_uploader_group)
        self.assertEqual(len(audit.verified), 1)
        self.assertEqual(len(audit.needs_action), 0)
        self.assertEqual(len(audit.errors), 0)
        record = audit.verified[0]
        self.assertIsInstance(record, upload_workspace_auth_domain_audit.VerifiedMember)
        self.assertEqual(record.workspace, self.upload_workspace)
        self.assertEqual(record.managed_group, self.rc_uploader_group)
        self.assertEqual(record.current_membership_instance, membership)
        self.assertEqual(
            record.note, upload_workspace_auth_domain_audit.UploadWorkspaceAuthDomainAudit.RC_BEFORE_COMBINED
        )

    def test_rc_uploaders_admin(self):
        membership = GroupGroupMembershipFactory.create(
            parent_group=self.upload_workspace.workspace.authorization_domains.first(),
            child_group=self.rc_uploader_group,
            role=GroupGroupMembership.ADMIN,
        )
        audit = upload_workspace_auth_domain_audit.UploadWorkspaceAuthDomainAudit()
        audit.audit_workspace_and_group(self.upload_workspace, self.rc_uploader_group)
        self.assertEqual(len(audit.verified), 0)
        self.assertEqual(len(audit.needs_action), 0)
        self.assertEqual(len(audit.errors), 1)
        record = audit.errors[0]
        self.assertIsInstance(record, upload_workspace_auth_domain_audit.ChangeToMember)
        self.assertEqual(record.workspace, self.upload_workspace)
        self.assertEqual(record.managed_group, self.rc_uploader_group)
        self.assertEqual(record.current_membership_instance, membership)
        self.assertEqual(
            record.note, upload_workspace_auth_domain_audit.UploadWorkspaceAuthDomainAudit.RC_BEFORE_COMBINED
        )

    def test_rc_members_not_member(self):
        audit = upload_workspace_auth_domain_audit.UploadWorkspaceAuthDomainAudit()
        audit.audit_workspace_and_group(self.upload_workspace, self.rc_member_group)
        self.assertEqual(len(audit.verified), 0)
        self.assertEqual(len(audit.needs_action), 1)
        self.assertEqual(len(audit.errors), 0)
        record = audit.needs_action[0]
        self.assertIsInstance(record, upload_workspace_auth_domain_audit.AddMember)
        self.assertEqual(record.workspace, self.upload_workspace)
        self.assertEqual(record.managed_group, self.rc_member_group)
        self.assertIsNone(record.current_membership_instance)
        self.assertEqual(
            record.note, upload_workspace_auth_domain_audit.UploadWorkspaceAuthDomainAudit.RC_BEFORE_COMBINED
        )

    def test_rc_members_member(self):
        membership = GroupGroupMembershipFactory.create(
            parent_group=self.upload_workspace.workspace.authorization_domains.first(),
            child_group=self.rc_member_group,
            role=GroupGroupMembership.MEMBER,
        )
        audit = upload_workspace_auth_domain_audit.UploadWorkspaceAuthDomainAudit()
        audit.audit_workspace_and_group(self.upload_workspace, self.rc_member_group)
        self.assertEqual(len(audit.verified), 1)
        self.assertEqual(len(audit.needs_action), 0)
        self.assertEqual(len(audit.errors), 0)
        record = audit.verified[0]
        self.assertIsInstance(record, upload_workspace_auth_domain_audit.VerifiedMember)
        self.assertEqual(record.workspace, self.upload_workspace)
        self.assertEqual(record.managed_group, self.rc_member_group)
        self.assertEqual(record.current_membership_instance, membership)
        self.assertEqual(
            record.note, upload_workspace_auth_domain_audit.UploadWorkspaceAuthDomainAudit.RC_BEFORE_COMBINED
        )

    def test_rc_members_admin(self):
        membership = GroupGroupMembershipFactory.create(
            parent_group=self.upload_workspace.workspace.authorization_domains.first(),
            child_group=self.rc_member_group,
            role=GroupGroupMembership.ADMIN,
        )
        audit = upload_workspace_auth_domain_audit.UploadWorkspaceAuthDomainAudit()
        audit.audit_workspace_and_group(self.upload_workspace, self.rc_member_group)
        self.assertEqual(len(audit.verified), 0)
        self.assertEqual(len(audit.needs_action), 0)
        self.assertEqual(len(audit.errors), 1)
        record = audit.errors[0]
        self.assertIsInstance(record, upload_workspace_auth_domain_audit.ChangeToMember)
        self.assertEqual(record.workspace, self.upload_workspace)
        self.assertEqual(record.managed_group, self.rc_member_group)
        self.assertEqual(record.current_membership_instance, membership)
        self.assertEqual(
            record.note, upload_workspace_auth_domain_audit.UploadWorkspaceAuthDomainAudit.RC_BEFORE_COMBINED
        )

    def test_rc_non_members_not_member(self):
        audit = upload_workspace_auth_domain_audit.UploadWorkspaceAuthDomainAudit()
        audit.audit_workspace_and_group(self.upload_workspace, self.rc_non_member_group)
        self.assertEqual(len(audit.verified), 0)
        self.assertEqual(len(audit.needs_action), 1)
        self.assertEqual(len(audit.errors), 0)
        record = audit.needs_action[0]
        self.assertIsInstance(record, upload_workspace_auth_domain_audit.AddMember)
        self.assertEqual(record.workspace, self.upload_workspace)
        self.assertEqual(record.managed_group, self.rc_non_member_group)
        self.assertIsNone(record.current_membership_instance)
        self.assertEqual(record.note, upload_workspace_auth_domain_audit.UploadWorkspaceAuthDomainAudit.RC_NON_MEMBERS)

    def test_rc_non_members_member(self):
        membership = GroupGroupMembershipFactory.create(
            parent_group=self.upload_workspace.workspace.authorization_domains.first(),
            child_group=self.rc_non_member_group,
            role=GroupGroupMembership.MEMBER,
        )
        audit = upload_workspace_auth_domain_audit.UploadWorkspaceAuthDomainAudit()
        audit.audit_workspace_and_group(self.upload_workspace, self.rc_non_member_group)
        self.assertEqual(len(audit.verified), 1)
        self.assertEqual(len(audit.needs_action), 0)
        self.assertEqual(len(audit.errors), 0)
        record = audit.verified[0]
        self.assertIsInstance(record, upload_workspace_auth_domain_audit.VerifiedMember)
        self.assertEqual(record.workspace, self.upload_workspace)
        self.assertEqual(record.managed_group, self.rc_non_member_group)
        self.assertEqual(record.current_membership_instance, membership)
        self.assertEqual(record.note, upload_workspace_auth_domain_audit.UploadWorkspaceAuthDomainAudit.RC_NON_MEMBERS)

    def test_rc_non_members_admin(self):
        membership = GroupGroupMembershipFactory.create(
            parent_group=self.upload_workspace.workspace.authorization_domains.first(),
            child_group=self.rc_non_member_group,
            role=GroupGroupMembership.ADMIN,
        )
        audit = upload_workspace_auth_domain_audit.UploadWorkspaceAuthDomainAudit()
        audit.audit_workspace_and_group(self.upload_workspace, self.rc_non_member_group)
        self.assertEqual(len(audit.verified), 0)
        self.assertEqual(len(audit.needs_action), 0)
        self.assertEqual(len(audit.errors), 1)
        record = audit.errors[0]
        self.assertIsInstance(record, upload_workspace_auth_domain_audit.ChangeToMember)
        self.assertEqual(record.workspace, self.upload_workspace)
        self.assertEqual(record.managed_group, self.rc_non_member_group)
        self.assertEqual(record.current_membership_instance, membership)
        self.assertEqual(record.note, upload_workspace_auth_domain_audit.UploadWorkspaceAuthDomainAudit.RC_NON_MEMBERS)

    def test_dcc_admins_not_member(self):
        audit = upload_workspace_auth_domain_audit.UploadWorkspaceAuthDomainAudit()
        audit.audit_workspace_and_group(self.upload_workspace, self.dcc_admin_group)
        self.assertEqual(len(audit.verified), 0)
        self.assertEqual(len(audit.needs_action), 1)
        self.assertEqual(len(audit.errors), 0)
        record = audit.needs_action[0]
        self.assertIsInstance(record, upload_workspace_auth_domain_audit.AddAdmin)
        self.assertEqual(record.workspace, self.upload_workspace)
        self.assertEqual(record.managed_group, self.dcc_admin_group)
        self.assertIsNone(record.current_membership_instance)
        self.assertEqual(record.note, upload_workspace_auth_domain_audit.UploadWorkspaceAuthDomainAudit.DCC_ADMINS)

    def test_dcc_admins_member(self):
        membership = GroupGroupMembershipFactory.create(
            parent_group=self.upload_workspace.workspace.authorization_domains.first(),
            child_group=self.dcc_admin_group,
            role=GroupGroupMembership.MEMBER,
        )
        audit = upload_workspace_auth_domain_audit.UploadWorkspaceAuthDomainAudit()
        audit.audit_workspace_and_group(self.upload_workspace, self.dcc_admin_group)
        self.assertEqual(len(audit.verified), 0)
        self.assertEqual(len(audit.needs_action), 1)
        self.assertEqual(len(audit.errors), 0)
        record = audit.needs_action[0]
        self.assertIsInstance(record, upload_workspace_auth_domain_audit.ChangeToAdmin)
        self.assertEqual(record.workspace, self.upload_workspace)
        self.assertEqual(record.managed_group, self.dcc_admin_group)
        self.assertEqual(record.current_membership_instance, membership)
        self.assertEqual(record.note, upload_workspace_auth_domain_audit.UploadWorkspaceAuthDomainAudit.DCC_ADMINS)

    def test_dcc_admins_admin(self):
        membership = GroupGroupMembershipFactory.create(
            parent_group=self.upload_workspace.workspace.authorization_domains.first(),
            child_group=self.dcc_admin_group,
            role=GroupGroupMembership.ADMIN,
        )
        audit = upload_workspace_auth_domain_audit.UploadWorkspaceAuthDomainAudit()
        audit.audit_workspace_and_group(self.upload_workspace, self.dcc_admin_group)
        self.assertEqual(len(audit.verified), 1)
        self.assertEqual(len(audit.needs_action), 0)
        self.assertEqual(len(audit.errors), 0)
        record = audit.verified[0]
        self.assertIsInstance(record, upload_workspace_auth_domain_audit.VerifiedAdmin)
        self.assertEqual(record.workspace, self.upload_workspace)
        self.assertEqual(record.managed_group, self.dcc_admin_group)
        self.assertEqual(record.current_membership_instance, membership)
        self.assertEqual(record.note, upload_workspace_auth_domain_audit.UploadWorkspaceAuthDomainAudit.DCC_ADMINS)

    @override_settings(ANVIL_DCC_ADMINS_GROUP_NAME="foobar")
    def test_dcc_admins_different_setting(self):
        group = ManagedGroupFactory.create(name="foobar")
        audit = upload_workspace_auth_domain_audit.UploadWorkspaceAuthDomainAudit()
        audit.audit_workspace_and_group(self.upload_workspace, group)
        self.assertEqual(len(audit.verified), 0)
        self.assertEqual(len(audit.needs_action), 1)
        self.assertEqual(len(audit.errors), 0)
        record = audit.needs_action[0]
        self.assertIsInstance(record, upload_workspace_auth_domain_audit.AddAdmin)
        self.assertEqual(record.workspace, self.upload_workspace)
        self.assertEqual(record.managed_group, group)
        self.assertIsNone(record.current_membership_instance)
        self.assertEqual(record.note, upload_workspace_auth_domain_audit.UploadWorkspaceAuthDomainAudit.DCC_ADMINS)


class UploadWorkspaceAuthDomainAuditPastCycleAfterQCCompleteTest(TestCase):
    """Tests for the `UploadWorkspaceAuthDomainAudit` class for past cycles before QC is complete.

    Expectations at this point in the upload cycle:
    - RC uploader group should not have direct access.
    - DCC writer group should not have direct access.
    """

    def setUp(self):
        super().setUp()
        self.rc_uploader_group = ManagedGroupFactory.create()
        self.rc_member_group = ManagedGroupFactory.create()
        self.rc_non_member_group = ManagedGroupFactory.create()
        self.dcc_member_group = ManagedGroupFactory.create(name="GREGOR_DCC_MEMBERS")
        self.dcc_writer_group = ManagedGroupFactory.create(name="GREGOR_DCC_WRITERS")
        self.dcc_admin_group = ManagedGroupFactory.create(name=settings.ANVIL_DCC_ADMINS_GROUP_NAME)
        self.gregor_all_group = ManagedGroupFactory.create(name="GREGOR_ALL")
        self.research_center = factories.ResearchCenterFactory.create(
            uploader_group=self.rc_uploader_group,
            member_group=self.rc_member_group,
            non_member_group=self.rc_non_member_group,
        )
        self.upload_workspace = factories.UploadWorkspaceFactory.create(
            research_center=self.research_center,
            upload_cycle__is_past=True,
            date_qc_completed=fake.date_this_year(before_today=True, after_today=False),
        )
        self.auth_domain = self.upload_workspace.workspace.authorization_domains.get()
        self.other_group = ManagedGroupFactory.create()
        self.anvil_admins = ManagedGroupFactory.create(name="anvil-admins")
        self.anvil_devs = ManagedGroupFactory.create(name="anvil_devs")

    def test_rc_uploaders_not_member(self):
        audit = upload_workspace_auth_domain_audit.UploadWorkspaceAuthDomainAudit()
        audit.audit_workspace_and_group(self.upload_workspace, self.rc_uploader_group)
        self.assertEqual(len(audit.verified), 0)
        self.assertEqual(len(audit.needs_action), 1)
        self.assertEqual(len(audit.errors), 0)
        record = audit.needs_action[0]
        self.assertIsInstance(record, upload_workspace_auth_domain_audit.AddMember)
        self.assertEqual(record.workspace, self.upload_workspace)
        self.assertEqual(record.managed_group, self.rc_uploader_group)
        self.assertIsNone(record.current_membership_instance)
        self.assertEqual(
            record.note, upload_workspace_auth_domain_audit.UploadWorkspaceAuthDomainAudit.RC_BEFORE_COMBINED
        )

    def test_rc_uploaders_member(self):
        membership = GroupGroupMembershipFactory.create(
            parent_group=self.upload_workspace.workspace.authorization_domains.first(),
            child_group=self.rc_uploader_group,
            role=GroupGroupMembership.MEMBER,
        )
        audit = upload_workspace_auth_domain_audit.UploadWorkspaceAuthDomainAudit()
        audit.audit_workspace_and_group(self.upload_workspace, self.rc_uploader_group)
        self.assertEqual(len(audit.verified), 1)
        self.assertEqual(len(audit.needs_action), 0)
        self.assertEqual(len(audit.errors), 0)
        record = audit.verified[0]
        self.assertIsInstance(record, upload_workspace_auth_domain_audit.VerifiedMember)
        self.assertEqual(record.workspace, self.upload_workspace)
        self.assertEqual(record.managed_group, self.rc_uploader_group)
        self.assertEqual(record.current_membership_instance, membership)
        self.assertEqual(
            record.note, upload_workspace_auth_domain_audit.UploadWorkspaceAuthDomainAudit.RC_BEFORE_COMBINED
        )

    def test_rc_uploaders_admin(self):
        membership = GroupGroupMembershipFactory.create(
            parent_group=self.upload_workspace.workspace.authorization_domains.first(),
            child_group=self.rc_uploader_group,
            role=GroupGroupMembership.ADMIN,
        )
        audit = upload_workspace_auth_domain_audit.UploadWorkspaceAuthDomainAudit()
        audit.audit_workspace_and_group(self.upload_workspace, self.rc_uploader_group)
        self.assertEqual(len(audit.verified), 0)
        self.assertEqual(len(audit.needs_action), 0)
        self.assertEqual(len(audit.errors), 1)
        record = audit.errors[0]
        self.assertIsInstance(record, upload_workspace_auth_domain_audit.ChangeToMember)
        self.assertEqual(record.workspace, self.upload_workspace)
        self.assertEqual(record.managed_group, self.rc_uploader_group)
        self.assertEqual(record.current_membership_instance, membership)
        self.assertEqual(
            record.note, upload_workspace_auth_domain_audit.UploadWorkspaceAuthDomainAudit.RC_BEFORE_COMBINED
        )

    def test_rc_members_not_member(self):
        audit = upload_workspace_auth_domain_audit.UploadWorkspaceAuthDomainAudit()
        audit.audit_workspace_and_group(self.upload_workspace, self.rc_member_group)
        self.assertEqual(len(audit.verified), 0)
        self.assertEqual(len(audit.needs_action), 1)
        self.assertEqual(len(audit.errors), 0)
        record = audit.needs_action[0]
        self.assertIsInstance(record, upload_workspace_auth_domain_audit.AddMember)
        self.assertEqual(record.workspace, self.upload_workspace)
        self.assertEqual(record.managed_group, self.rc_member_group)
        self.assertIsNone(record.current_membership_instance)
        self.assertEqual(
            record.note, upload_workspace_auth_domain_audit.UploadWorkspaceAuthDomainAudit.RC_BEFORE_COMBINED
        )

    def test_rc_members_member(self):
        membership = GroupGroupMembershipFactory.create(
            parent_group=self.upload_workspace.workspace.authorization_domains.first(),
            child_group=self.rc_member_group,
            role=GroupGroupMembership.MEMBER,
        )
        audit = upload_workspace_auth_domain_audit.UploadWorkspaceAuthDomainAudit()
        audit.audit_workspace_and_group(self.upload_workspace, self.rc_member_group)
        self.assertEqual(len(audit.verified), 1)
        self.assertEqual(len(audit.needs_action), 0)
        self.assertEqual(len(audit.errors), 0)
        record = audit.verified[0]
        self.assertIsInstance(record, upload_workspace_auth_domain_audit.VerifiedMember)
        self.assertEqual(record.workspace, self.upload_workspace)
        self.assertEqual(record.managed_group, self.rc_member_group)
        self.assertEqual(record.current_membership_instance, membership)
        self.assertEqual(
            record.note, upload_workspace_auth_domain_audit.UploadWorkspaceAuthDomainAudit.RC_BEFORE_COMBINED
        )

    def test_rc_members_admin(self):
        membership = GroupGroupMembershipFactory.create(
            parent_group=self.upload_workspace.workspace.authorization_domains.first(),
            child_group=self.rc_member_group,
            role=GroupGroupMembership.ADMIN,
        )
        audit = upload_workspace_auth_domain_audit.UploadWorkspaceAuthDomainAudit()
        audit.audit_workspace_and_group(self.upload_workspace, self.rc_member_group)
        self.assertEqual(len(audit.verified), 0)
        self.assertEqual(len(audit.needs_action), 0)
        self.assertEqual(len(audit.errors), 1)
        record = audit.errors[0]
        self.assertIsInstance(record, upload_workspace_auth_domain_audit.ChangeToMember)
        self.assertEqual(record.workspace, self.upload_workspace)
        self.assertEqual(record.managed_group, self.rc_member_group)
        self.assertEqual(record.current_membership_instance, membership)
        self.assertEqual(
            record.note, upload_workspace_auth_domain_audit.UploadWorkspaceAuthDomainAudit.RC_BEFORE_COMBINED
        )

    def test_rc_non_members_not_member(self):
        audit = upload_workspace_auth_domain_audit.UploadWorkspaceAuthDomainAudit()
        audit.audit_workspace_and_group(self.upload_workspace, self.rc_non_member_group)
        self.assertEqual(len(audit.verified), 0)
        self.assertEqual(len(audit.needs_action), 1)
        self.assertEqual(len(audit.errors), 0)
        record = audit.needs_action[0]
        self.assertIsInstance(record, upload_workspace_auth_domain_audit.AddMember)
        self.assertEqual(record.workspace, self.upload_workspace)
        self.assertEqual(record.managed_group, self.rc_non_member_group)
        self.assertIsNone(record.current_membership_instance)
        self.assertEqual(record.note, upload_workspace_auth_domain_audit.UploadWorkspaceAuthDomainAudit.RC_NON_MEMBERS)

    def test_rc_non_members_member(self):
        membership = GroupGroupMembershipFactory.create(
            parent_group=self.upload_workspace.workspace.authorization_domains.first(),
            child_group=self.rc_non_member_group,
            role=GroupGroupMembership.MEMBER,
        )
        audit = upload_workspace_auth_domain_audit.UploadWorkspaceAuthDomainAudit()
        audit.audit_workspace_and_group(self.upload_workspace, self.rc_non_member_group)
        self.assertEqual(len(audit.verified), 1)
        self.assertEqual(len(audit.needs_action), 0)
        self.assertEqual(len(audit.errors), 0)
        record = audit.verified[0]
        self.assertIsInstance(record, upload_workspace_auth_domain_audit.VerifiedMember)
        self.assertEqual(record.workspace, self.upload_workspace)
        self.assertEqual(record.managed_group, self.rc_non_member_group)
        self.assertEqual(record.current_membership_instance, membership)
        self.assertEqual(record.note, upload_workspace_auth_domain_audit.UploadWorkspaceAuthDomainAudit.RC_NON_MEMBERS)

    def test_rc_non_members_admin(self):
        membership = GroupGroupMembershipFactory.create(
            parent_group=self.upload_workspace.workspace.authorization_domains.first(),
            child_group=self.rc_non_member_group,
            role=GroupGroupMembership.ADMIN,
        )
        audit = upload_workspace_auth_domain_audit.UploadWorkspaceAuthDomainAudit()
        audit.audit_workspace_and_group(self.upload_workspace, self.rc_non_member_group)
        self.assertEqual(len(audit.verified), 0)
        self.assertEqual(len(audit.needs_action), 0)
        self.assertEqual(len(audit.errors), 1)
        record = audit.errors[0]
        self.assertIsInstance(record, upload_workspace_auth_domain_audit.ChangeToMember)
        self.assertEqual(record.workspace, self.upload_workspace)
        self.assertEqual(record.managed_group, self.rc_non_member_group)
        self.assertEqual(record.current_membership_instance, membership)
        self.assertEqual(record.note, upload_workspace_auth_domain_audit.UploadWorkspaceAuthDomainAudit.RC_NON_MEMBERS)

    def test_dcc_admins_not_member(self):
        audit = upload_workspace_auth_domain_audit.UploadWorkspaceAuthDomainAudit()
        audit.audit_workspace_and_group(self.upload_workspace, self.dcc_admin_group)
        self.assertEqual(len(audit.verified), 0)
        self.assertEqual(len(audit.needs_action), 1)
        self.assertEqual(len(audit.errors), 0)
        record = audit.needs_action[0]
        self.assertIsInstance(record, upload_workspace_auth_domain_audit.AddAdmin)
        self.assertEqual(record.workspace, self.upload_workspace)
        self.assertEqual(record.managed_group, self.dcc_admin_group)
        self.assertIsNone(record.current_membership_instance)
        self.assertEqual(record.note, upload_workspace_auth_domain_audit.UploadWorkspaceAuthDomainAudit.DCC_ADMINS)

    def test_dcc_admins_member(self):
        membership = GroupGroupMembershipFactory.create(
            parent_group=self.upload_workspace.workspace.authorization_domains.first(),
            child_group=self.dcc_admin_group,
            role=GroupGroupMembership.MEMBER,
        )
        audit = upload_workspace_auth_domain_audit.UploadWorkspaceAuthDomainAudit()
        audit.audit_workspace_and_group(self.upload_workspace, self.dcc_admin_group)
        self.assertEqual(len(audit.verified), 0)
        self.assertEqual(len(audit.needs_action), 1)
        self.assertEqual(len(audit.errors), 0)
        record = audit.needs_action[0]
        self.assertIsInstance(record, upload_workspace_auth_domain_audit.ChangeToAdmin)
        self.assertEqual(record.workspace, self.upload_workspace)
        self.assertEqual(record.managed_group, self.dcc_admin_group)
        self.assertEqual(record.current_membership_instance, membership)
        self.assertEqual(record.note, upload_workspace_auth_domain_audit.UploadWorkspaceAuthDomainAudit.DCC_ADMINS)

    def test_dcc_admins_admin(self):
        membership = GroupGroupMembershipFactory.create(
            parent_group=self.upload_workspace.workspace.authorization_domains.first(),
            child_group=self.dcc_admin_group,
            role=GroupGroupMembership.ADMIN,
        )
        audit = upload_workspace_auth_domain_audit.UploadWorkspaceAuthDomainAudit()
        audit.audit_workspace_and_group(self.upload_workspace, self.dcc_admin_group)
        self.assertEqual(len(audit.verified), 1)
        self.assertEqual(len(audit.needs_action), 0)
        self.assertEqual(len(audit.errors), 0)
        record = audit.verified[0]
        self.assertIsInstance(record, upload_workspace_auth_domain_audit.VerifiedAdmin)
        self.assertEqual(record.workspace, self.upload_workspace)
        self.assertEqual(record.managed_group, self.dcc_admin_group)
        self.assertEqual(record.current_membership_instance, membership)
        self.assertEqual(record.note, upload_workspace_auth_domain_audit.UploadWorkspaceAuthDomainAudit.DCC_ADMINS)

    @override_settings(ANVIL_DCC_ADMINS_GROUP_NAME="foobar")
    def test_dcc_admins_different_setting(self):
        group = ManagedGroupFactory.create(name="foobar")
        audit = upload_workspace_auth_domain_audit.UploadWorkspaceAuthDomainAudit()
        audit.audit_workspace_and_group(self.upload_workspace, group)
        self.assertEqual(len(audit.verified), 0)
        self.assertEqual(len(audit.needs_action), 1)
        self.assertEqual(len(audit.errors), 0)
        record = audit.needs_action[0]
        self.assertIsInstance(record, upload_workspace_auth_domain_audit.AddAdmin)
        self.assertEqual(record.workspace, self.upload_workspace)
        self.assertEqual(record.managed_group, group)
        self.assertIsNone(record.current_membership_instance)
        self.assertEqual(record.note, upload_workspace_auth_domain_audit.UploadWorkspaceAuthDomainAudit.DCC_ADMINS)


class UploadWorkspaceAuthDomainAuditPastCycleAfterCombinedWorkspaceSharedTest(TestCase):
    """Tests for the `UploadWorkspaceAuthDomainAudit` class for past cycles after the combined workspace is complete."""

    def setUp(self):
        super().setUp()
        self.rc_uploader_group = ManagedGroupFactory.create()
        self.rc_member_group = ManagedGroupFactory.create()
        self.rc_non_member_group = ManagedGroupFactory.create()
        self.dcc_member_group = ManagedGroupFactory.create(name="GREGOR_DCC_MEMBERS")
        self.dcc_writer_group = ManagedGroupFactory.create(name="GREGOR_DCC_WRITERS")
        self.dcc_admin_group = ManagedGroupFactory.create(name=settings.ANVIL_DCC_ADMINS_GROUP_NAME)
        self.gregor_all_group = ManagedGroupFactory.create(name="GREGOR_ALL")
        self.research_center = factories.ResearchCenterFactory.create(
            uploader_group=self.rc_uploader_group,
            member_group=self.rc_member_group,
            non_member_group=self.rc_non_member_group,
        )
        self.upload_workspace = factories.UploadWorkspaceFactory.create(
            research_center=self.research_center,
            upload_cycle__is_past=True,
            date_qc_completed=fake.date_this_year(before_today=True, after_today=False),
        )
        self.auth_domain = self.upload_workspace.workspace.authorization_domains.get()
        # Create a corresponding combined workspace.
        self.combined_workspace = factories.CombinedConsortiumDataWorkspaceFactory.create(
            upload_cycle=self.upload_workspace.upload_cycle,
            date_completed=fake.date_this_year(
                before_today=True,
                after_today=False,
            ),
        )
        self.other_group = ManagedGroupFactory.create()
        self.anvil_admins = ManagedGroupFactory.create(name="anvil-admins")
        self.anvil_devs = ManagedGroupFactory.create(name="anvil_devs")

    def test_rc_uploaders_not_member(self):
        audit = upload_workspace_auth_domain_audit.UploadWorkspaceAuthDomainAudit()
        audit.audit_workspace_and_group(self.upload_workspace, self.rc_uploader_group)
        self.assertEqual(len(audit.verified), 1)
        self.assertEqual(len(audit.needs_action), 0)
        self.assertEqual(len(audit.errors), 0)
        record = audit.verified[0]
        self.assertIsInstance(record, upload_workspace_auth_domain_audit.VerifiedNotMember)
        self.assertEqual(record.workspace, self.upload_workspace)
        self.assertEqual(record.managed_group, self.rc_uploader_group)
        self.assertIsNone(record.current_membership_instance)
        self.assertEqual(
            record.note, upload_workspace_auth_domain_audit.UploadWorkspaceAuthDomainAudit.RC_AFTER_COMBINED
        )

    def test_rc_uploaders_member(self):
        membership = GroupGroupMembershipFactory.create(
            parent_group=self.upload_workspace.workspace.authorization_domains.first(),
            child_group=self.rc_uploader_group,
            role=GroupGroupMembership.MEMBER,
        )
        audit = upload_workspace_auth_domain_audit.UploadWorkspaceAuthDomainAudit()
        audit.audit_workspace_and_group(self.upload_workspace, self.rc_uploader_group)
        self.assertEqual(len(audit.verified), 0)
        self.assertEqual(len(audit.needs_action), 1)
        self.assertEqual(len(audit.errors), 0)
        record = audit.needs_action[0]
        self.assertIsInstance(record, upload_workspace_auth_domain_audit.Remove)
        self.assertEqual(record.workspace, self.upload_workspace)
        self.assertEqual(record.managed_group, self.rc_uploader_group)
        self.assertEqual(record.current_membership_instance, membership)
        self.assertEqual(
            record.note, upload_workspace_auth_domain_audit.UploadWorkspaceAuthDomainAudit.RC_AFTER_COMBINED
        )

    def test_rc_uploaders_admin(self):
        membership = GroupGroupMembershipFactory.create(
            parent_group=self.upload_workspace.workspace.authorization_domains.first(),
            child_group=self.rc_uploader_group,
            role=GroupGroupMembership.ADMIN,
        )
        audit = upload_workspace_auth_domain_audit.UploadWorkspaceAuthDomainAudit()
        audit.audit_workspace_and_group(self.upload_workspace, self.rc_uploader_group)
        self.assertEqual(len(audit.verified), 0)
        self.assertEqual(len(audit.needs_action), 0)
        self.assertEqual(len(audit.errors), 1)
        record = audit.errors[0]
        self.assertIsInstance(record, upload_workspace_auth_domain_audit.Remove)
        self.assertEqual(record.workspace, self.upload_workspace)
        self.assertEqual(record.managed_group, self.rc_uploader_group)
        self.assertEqual(record.current_membership_instance, membership)
        self.assertEqual(
            record.note, upload_workspace_auth_domain_audit.UploadWorkspaceAuthDomainAudit.RC_AFTER_COMBINED
        )

    def test_rc_members_not_member(self):
        audit = upload_workspace_auth_domain_audit.UploadWorkspaceAuthDomainAudit()
        audit.audit_workspace_and_group(self.upload_workspace, self.rc_member_group)
        self.assertEqual(len(audit.verified), 1)
        self.assertEqual(len(audit.needs_action), 0)
        self.assertEqual(len(audit.errors), 0)
        record = audit.verified[0]
        self.assertIsInstance(record, upload_workspace_auth_domain_audit.VerifiedNotMember)
        self.assertEqual(record.workspace, self.upload_workspace)
        self.assertEqual(record.managed_group, self.rc_member_group)
        self.assertIsNone(record.current_membership_instance)
        self.assertEqual(
            record.note, upload_workspace_auth_domain_audit.UploadWorkspaceAuthDomainAudit.RC_AFTER_COMBINED
        )

    def test_rc_members_member(self):
        membership = GroupGroupMembershipFactory.create(
            parent_group=self.upload_workspace.workspace.authorization_domains.first(),
            child_group=self.rc_member_group,
            role=GroupGroupMembership.MEMBER,
        )
        audit = upload_workspace_auth_domain_audit.UploadWorkspaceAuthDomainAudit()
        audit.audit_workspace_and_group(self.upload_workspace, self.rc_member_group)
        self.assertEqual(len(audit.verified), 0)
        self.assertEqual(len(audit.needs_action), 1)
        self.assertEqual(len(audit.errors), 0)
        record = audit.needs_action[0]
        self.assertIsInstance(record, upload_workspace_auth_domain_audit.Remove)
        self.assertEqual(record.workspace, self.upload_workspace)
        self.assertEqual(record.managed_group, self.rc_member_group)
        self.assertEqual(record.current_membership_instance, membership)
        self.assertEqual(
            record.note, upload_workspace_auth_domain_audit.UploadWorkspaceAuthDomainAudit.RC_AFTER_COMBINED
        )

    def test_rc_members_admin(self):
        membership = GroupGroupMembershipFactory.create(
            parent_group=self.upload_workspace.workspace.authorization_domains.first(),
            child_group=self.rc_member_group,
            role=GroupGroupMembership.ADMIN,
        )
        audit = upload_workspace_auth_domain_audit.UploadWorkspaceAuthDomainAudit()
        audit.audit_workspace_and_group(self.upload_workspace, self.rc_member_group)
        self.assertEqual(len(audit.verified), 0)
        self.assertEqual(len(audit.needs_action), 0)
        self.assertEqual(len(audit.errors), 1)
        record = audit.errors[0]
        self.assertIsInstance(record, upload_workspace_auth_domain_audit.Remove)
        self.assertEqual(record.workspace, self.upload_workspace)
        self.assertEqual(record.managed_group, self.rc_member_group)
        self.assertEqual(record.current_membership_instance, membership)
        self.assertEqual(
            record.note, upload_workspace_auth_domain_audit.UploadWorkspaceAuthDomainAudit.RC_AFTER_COMBINED
        )

    def test_rc_non_members_not_member(self):
        audit = upload_workspace_auth_domain_audit.UploadWorkspaceAuthDomainAudit()
        audit.audit_workspace_and_group(self.upload_workspace, self.rc_non_member_group)
        self.assertEqual(len(audit.verified), 0)
        self.assertEqual(len(audit.needs_action), 1)
        self.assertEqual(len(audit.errors), 0)
        record = audit.needs_action[0]
        self.assertIsInstance(record, upload_workspace_auth_domain_audit.AddMember)
        self.assertEqual(record.workspace, self.upload_workspace)
        self.assertEqual(record.managed_group, self.rc_non_member_group)
        self.assertIsNone(record.current_membership_instance)
        self.assertEqual(record.note, upload_workspace_auth_domain_audit.UploadWorkspaceAuthDomainAudit.RC_NON_MEMBERS)

    def test_rc_non_members_member(self):
        membership = GroupGroupMembershipFactory.create(
            parent_group=self.upload_workspace.workspace.authorization_domains.first(),
            child_group=self.rc_non_member_group,
            role=GroupGroupMembership.MEMBER,
        )
        audit = upload_workspace_auth_domain_audit.UploadWorkspaceAuthDomainAudit()
        audit.audit_workspace_and_group(self.upload_workspace, self.rc_non_member_group)
        self.assertEqual(len(audit.verified), 1)
        self.assertEqual(len(audit.needs_action), 0)
        self.assertEqual(len(audit.errors), 0)
        record = audit.verified[0]
        self.assertIsInstance(record, upload_workspace_auth_domain_audit.VerifiedMember)
        self.assertEqual(record.workspace, self.upload_workspace)
        self.assertEqual(record.managed_group, self.rc_non_member_group)
        self.assertEqual(record.current_membership_instance, membership)
        self.assertEqual(record.note, upload_workspace_auth_domain_audit.UploadWorkspaceAuthDomainAudit.RC_NON_MEMBERS)

    def test_rc_non_members_admin(self):
        membership = GroupGroupMembershipFactory.create(
            parent_group=self.upload_workspace.workspace.authorization_domains.first(),
            child_group=self.rc_non_member_group,
            role=GroupGroupMembership.ADMIN,
        )
        audit = upload_workspace_auth_domain_audit.UploadWorkspaceAuthDomainAudit()
        audit.audit_workspace_and_group(self.upload_workspace, self.rc_non_member_group)
        self.assertEqual(len(audit.verified), 0)
        self.assertEqual(len(audit.needs_action), 0)
        self.assertEqual(len(audit.errors), 1)
        record = audit.errors[0]
        self.assertIsInstance(record, upload_workspace_auth_domain_audit.ChangeToMember)
        self.assertEqual(record.workspace, self.upload_workspace)
        self.assertEqual(record.managed_group, self.rc_non_member_group)
        self.assertEqual(record.current_membership_instance, membership)
        self.assertEqual(record.note, upload_workspace_auth_domain_audit.UploadWorkspaceAuthDomainAudit.RC_NON_MEMBERS)

    def test_dcc_admins_not_member(self):
        audit = upload_workspace_auth_domain_audit.UploadWorkspaceAuthDomainAudit()
        audit.audit_workspace_and_group(self.upload_workspace, self.dcc_admin_group)
        self.assertEqual(len(audit.verified), 0)
        self.assertEqual(len(audit.needs_action), 1)
        self.assertEqual(len(audit.errors), 0)
        record = audit.needs_action[0]
        self.assertIsInstance(record, upload_workspace_auth_domain_audit.AddAdmin)
        self.assertEqual(record.workspace, self.upload_workspace)
        self.assertEqual(record.managed_group, self.dcc_admin_group)
        self.assertIsNone(record.current_membership_instance)
        self.assertEqual(record.note, upload_workspace_auth_domain_audit.UploadWorkspaceAuthDomainAudit.DCC_ADMINS)

    def test_dcc_admins_member(self):
        membership = GroupGroupMembershipFactory.create(
            parent_group=self.upload_workspace.workspace.authorization_domains.first(),
            child_group=self.dcc_admin_group,
            role=GroupGroupMembership.MEMBER,
        )
        audit = upload_workspace_auth_domain_audit.UploadWorkspaceAuthDomainAudit()
        audit.audit_workspace_and_group(self.upload_workspace, self.dcc_admin_group)
        self.assertEqual(len(audit.verified), 0)
        self.assertEqual(len(audit.needs_action), 1)
        self.assertEqual(len(audit.errors), 0)
        record = audit.needs_action[0]
        self.assertIsInstance(record, upload_workspace_auth_domain_audit.ChangeToAdmin)
        self.assertEqual(record.workspace, self.upload_workspace)
        self.assertEqual(record.managed_group, self.dcc_admin_group)
        self.assertEqual(record.current_membership_instance, membership)
        self.assertEqual(record.note, upload_workspace_auth_domain_audit.UploadWorkspaceAuthDomainAudit.DCC_ADMINS)

    def test_dcc_admins_admin(self):
        membership = GroupGroupMembershipFactory.create(
            parent_group=self.upload_workspace.workspace.authorization_domains.first(),
            child_group=self.dcc_admin_group,
            role=GroupGroupMembership.ADMIN,
        )
        audit = upload_workspace_auth_domain_audit.UploadWorkspaceAuthDomainAudit()
        audit.audit_workspace_and_group(self.upload_workspace, self.dcc_admin_group)
        self.assertEqual(len(audit.verified), 1)
        self.assertEqual(len(audit.needs_action), 0)
        self.assertEqual(len(audit.errors), 0)
        record = audit.verified[0]
        self.assertIsInstance(record, upload_workspace_auth_domain_audit.VerifiedAdmin)
        self.assertEqual(record.workspace, self.upload_workspace)
        self.assertEqual(record.managed_group, self.dcc_admin_group)
        self.assertEqual(record.current_membership_instance, membership)
        self.assertEqual(record.note, upload_workspace_auth_domain_audit.UploadWorkspaceAuthDomainAudit.DCC_ADMINS)

    @override_settings(ANVIL_DCC_ADMINS_GROUP_NAME="foobar")
    def test_dcc_admins_different_setting(self):
        group = ManagedGroupFactory.create(name="foobar")
        audit = upload_workspace_auth_domain_audit.UploadWorkspaceAuthDomainAudit()
        audit.audit_workspace_and_group(self.upload_workspace, group)
        self.assertEqual(len(audit.verified), 0)
        self.assertEqual(len(audit.needs_action), 1)
        self.assertEqual(len(audit.errors), 0)
        record = audit.needs_action[0]
        self.assertIsInstance(record, upload_workspace_auth_domain_audit.AddAdmin)
        self.assertEqual(record.workspace, self.upload_workspace)
        self.assertEqual(record.managed_group, group)
        self.assertIsNone(record.current_membership_instance)
        self.assertEqual(record.note, upload_workspace_auth_domain_audit.UploadWorkspaceAuthDomainAudit.DCC_ADMINS)
