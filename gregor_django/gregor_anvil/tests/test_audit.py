"""Tests for the `py` module."""

from dataclasses import dataclass
from datetime import timedelta

import django_tables2 as tables
import responses
from anvil_consortium_manager.models import GroupGroupMembership, WorkspaceGroupSharing
from anvil_consortium_manager.tests.factories import (
    GroupGroupMembershipFactory,
    ManagedGroupFactory,
    WorkspaceAuthorizationDomainFactory,
    WorkspaceFactory,
    WorkspaceGroupSharingFactory,
)
from anvil_consortium_manager.tests.utils import AnVILAPIMockTestMixin
from django.conf import settings
from django.test import TestCase, override_settings
from django.utils import timezone
from faker import Faker
from freezegun import freeze_time

from .. import models
from ..audit import (
    combined_workspace_audit,
    dcc_processed_data_workspace_audit,
    upload_workspace_audit,
    workspace_auth_domain_audit_results,
    workspace_sharing_audit_results,
)
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


class WorkspaceSharingAuditResultTest(AnVILAPIMockTestMixin, TestCase):
    """General tests of the UploadWorkspaceSharingAuditResult dataclasses."""

    def test_shared_as_owner(self):
        workspace = WorkspaceFactory.create()
        group = ManagedGroupFactory.create()
        sharing = WorkspaceGroupSharingFactory.create(
            workspace=workspace, group=group, access=WorkspaceGroupSharing.OWNER, can_compute=True
        )
        instance = workspace_sharing_audit_results.WorkspaceSharingAuditResult(
            workspace=workspace,
            managed_group=group,
            current_sharing_instance=sharing,
            note="foo",
        )
        table_dictionary = instance.get_table_dictionary()
        self.assertEqual(table_dictionary["access"], sharing.OWNER)
        self.assertEqual(table_dictionary["can_compute"], True)

    def test_shared_as_writer_with_compute(self):
        workspace = WorkspaceFactory.create()
        group = ManagedGroupFactory.create()
        sharing = WorkspaceGroupSharingFactory.create(
            workspace=workspace, group=group, access=WorkspaceGroupSharing.WRITER, can_compute=True
        )
        instance = workspace_sharing_audit_results.WorkspaceSharingAuditResult(
            workspace=workspace,
            managed_group=group,
            current_sharing_instance=sharing,
            note="foo",
        )
        table_dictionary = instance.get_table_dictionary()
        self.assertEqual(table_dictionary["access"], sharing.WRITER)
        self.assertEqual(table_dictionary["can_compute"], True)

    def test_shared_as_writer_without_compute(self):
        workspace = WorkspaceFactory.create()
        group = ManagedGroupFactory.create()
        sharing = WorkspaceGroupSharingFactory.create(
            workspace=workspace, group=group, access=WorkspaceGroupSharing.WRITER, can_compute=False
        )
        instance = workspace_sharing_audit_results.WorkspaceSharingAuditResult(
            workspace=workspace,
            managed_group=group,
            current_sharing_instance=sharing,
            note="foo",
        )
        table_dictionary = instance.get_table_dictionary()
        self.assertEqual(table_dictionary["access"], sharing.WRITER)
        self.assertEqual(table_dictionary["can_compute"], False)

    def test_shared_as_reader(self):
        workspace = WorkspaceFactory.create()
        group = ManagedGroupFactory.create()
        sharing = WorkspaceGroupSharingFactory.create(
            workspace=workspace, group=group, access=WorkspaceGroupSharing.READER
        )
        instance = workspace_sharing_audit_results.WorkspaceSharingAuditResult(
            workspace=workspace,
            managed_group=group,
            current_sharing_instance=sharing,
            note="foo",
        )
        table_dictionary = instance.get_table_dictionary()
        self.assertEqual(table_dictionary["access"], sharing.READER)
        self.assertIsNone(table_dictionary["can_compute"])

    def test_not_shared(self):
        workspace = WorkspaceFactory.create()
        group = ManagedGroupFactory.create()
        instance = workspace_sharing_audit_results.WorkspaceSharingAuditResult(
            workspace=workspace,
            managed_group=group,
            current_sharing_instance=None,
            note="foo",
        )
        table_dictionary = instance.get_table_dictionary()
        self.assertIsNone(table_dictionary["access"])
        self.assertIsNone(table_dictionary["can_compute"])

    def test_handle_verified_shared(self):
        workspace = WorkspaceFactory.create(name="test-ws")
        group = ManagedGroupFactory.create()
        date_created = timezone.now() - timedelta(days=1)
        with freeze_time(date_created):
            sharing = WorkspaceGroupSharingFactory.create(
                workspace=workspace,
                group=group,
                access=WorkspaceGroupSharing.READER,
            )
        instance = workspace_sharing_audit_results.VerifiedShared(
            workspace=workspace,
            managed_group=group,
            current_sharing_instance=sharing,
            note="foo",
        )
        self.assertFalse(instance.handled)
        instance.handle()
        self.assertTrue(instance.handled)
        self.assertEqual(WorkspaceGroupSharing.objects.count(), 1)
        sharing.refresh_from_db()
        self.assertEqual(sharing.workspace, workspace)
        self.assertEqual(sharing.group, group)
        self.assertEqual(sharing.access, WorkspaceGroupSharing.READER)
        self.assertEqual(sharing.created, date_created)
        self.assertEqual(sharing.modified, date_created)

    def test_handle_verified_not_shared(self):
        workspace = WorkspaceFactory.create(name="test-ws")
        group = ManagedGroupFactory.create()
        instance = workspace_sharing_audit_results.VerifiedNotShared(
            workspace=workspace,
            managed_group=group,
            current_sharing_instance=None,
            note="foo",
        )
        self.assertFalse(instance.handled)
        instance.handle()
        self.assertTrue(instance.handled)
        self.assertEqual(WorkspaceGroupSharing.objects.count(), 0)

    def test_handle_share_as_reader_new(self):
        workspace = WorkspaceFactory.create(billing_project__name="test-bp", name="test-ws")
        group = ManagedGroupFactory.create()
        instance = workspace_sharing_audit_results.ShareAsReader(
            workspace=workspace,
            managed_group=group,
            current_sharing_instance=None,
            note="foo",
        )
        # Add the mocked API response.
        acls = [
            {
                "email": group.email,
                "accessLevel": "READER",
                "canShare": False,
                "canCompute": False,
            }
        ]
        self.anvil_response_mock.add(
            responses.PATCH,
            self.api_client.rawls_entry_point + "/api/workspaces/test-bp/test-ws/acl?inviteUsersNotFound=false",
            status=200,
            match=[responses.matchers.json_params_matcher(acls)],
            json={"invitesSent": {}, "usersNotFound": {}, "usersUpdated": acls},
        )
        self.assertFalse(instance.handled)
        instance.handle()
        self.assertTrue(instance.handled)
        self.assertEqual(WorkspaceGroupSharing.objects.count(), 1)
        sharing = WorkspaceGroupSharing.objects.first()
        self.assertEqual(sharing.workspace, workspace)
        self.assertEqual(sharing.group, group)
        self.assertEqual(sharing.access, WorkspaceGroupSharing.READER)
        self.assertFalse(sharing.can_compute)

    def test_handle_share_as_reader_update(self):
        workspace = WorkspaceFactory.create(billing_project__name="test-bp", name="test-ws")
        group = ManagedGroupFactory.create()
        date_created = timezone.now() - timedelta(days=1)
        with freeze_time(date_created):
            sharing = WorkspaceGroupSharingFactory.create(
                workspace=workspace,
                group=group,
                access=WorkspaceGroupSharing.WRITER,
                can_compute=True,
            )
        instance = workspace_sharing_audit_results.ShareAsReader(
            workspace=workspace,
            managed_group=group,
            current_sharing_instance=sharing,
            note="foo",
        )
        # Add the mocked API response.
        acls = [
            {
                "email": group.email,
                "accessLevel": "READER",
                "canShare": False,
                "canCompute": False,
            }
        ]
        self.anvil_response_mock.add(
            responses.PATCH,
            self.api_client.rawls_entry_point + "/api/workspaces/test-bp/test-ws/acl?inviteUsersNotFound=false",
            status=200,
            match=[responses.matchers.json_params_matcher(acls)],
            json={"invitesSent": {}, "usersNotFound": {}, "usersUpdated": acls},
        )
        self.assertFalse(instance.handled)
        instance.handle()
        self.assertTrue(instance.handled)
        self.assertEqual(WorkspaceGroupSharing.objects.count(), 1)
        sharing.refresh_from_db()
        self.assertEqual(sharing.workspace, workspace)
        self.assertEqual(sharing.group, group)
        self.assertEqual(sharing.access, WorkspaceGroupSharing.READER)
        self.assertFalse(sharing.can_compute)
        self.assertEqual(sharing.created, date_created)
        self.assertGreater(sharing.modified, date_created)

    def test_handle_share_as_writer_new(self):
        workspace = WorkspaceFactory.create(billing_project__name="test-bp", name="test-ws")
        group = ManagedGroupFactory.create()
        instance = workspace_sharing_audit_results.ShareAsWriter(
            workspace=workspace,
            managed_group=group,
            current_sharing_instance=None,
            note="foo",
        )
        # Add the mocked API response.
        acls = [
            {
                "email": group.email,
                "accessLevel": "WRITER",
                "canShare": False,
                "canCompute": False,
            }
        ]
        self.anvil_response_mock.add(
            responses.PATCH,
            self.api_client.rawls_entry_point + "/api/workspaces/test-bp/test-ws/acl?inviteUsersNotFound=false",
            status=200,
            match=[responses.matchers.json_params_matcher(acls)],
            json={"invitesSent": {}, "usersNotFound": {}, "usersUpdated": acls},
        )
        self.assertFalse(instance.handled)
        instance.handle()
        self.assertTrue(instance.handled)
        self.assertEqual(WorkspaceGroupSharing.objects.count(), 1)
        sharing = WorkspaceGroupSharing.objects.first()
        self.assertEqual(sharing.workspace, workspace)
        self.assertEqual(sharing.group, group)
        self.assertEqual(sharing.access, WorkspaceGroupSharing.WRITER)
        self.assertFalse(sharing.can_compute)

    def test_handle_share_as_writer_update(self):
        workspace = WorkspaceFactory.create(billing_project__name="test-bp", name="test-ws")
        group = ManagedGroupFactory.create()
        date_created = timezone.now() - timedelta(days=1)
        with freeze_time(date_created):
            sharing = WorkspaceGroupSharingFactory.create(
                workspace=workspace,
                group=group,
                access=WorkspaceGroupSharing.OWNER,
                can_compute=True,
            )
        instance = workspace_sharing_audit_results.ShareAsWriter(
            workspace=workspace,
            managed_group=group,
            current_sharing_instance=sharing,
            note="foo",
        )
        # Add the mocked API response.
        acls = [
            {
                "email": group.email,
                "accessLevel": "WRITER",
                "canShare": False,
                "canCompute": False,
            }
        ]
        self.anvil_response_mock.add(
            responses.PATCH,
            self.api_client.rawls_entry_point + "/api/workspaces/test-bp/test-ws/acl?inviteUsersNotFound=false",
            status=200,
            match=[responses.matchers.json_params_matcher(acls)],
            json={"invitesSent": {}, "usersNotFound": {}, "usersUpdated": acls},
        )
        self.assertFalse(instance.handled)
        instance.handle()
        self.assertTrue(instance.handled)
        self.assertEqual(WorkspaceGroupSharing.objects.count(), 1)
        sharing.refresh_from_db()
        self.assertEqual(sharing.workspace, workspace)
        self.assertEqual(sharing.group, group)
        self.assertEqual(sharing.access, WorkspaceGroupSharing.WRITER)
        self.assertFalse(sharing.can_compute)
        self.assertEqual(sharing.created, date_created)
        self.assertGreater(sharing.modified, date_created)

    def test_handle_share_with_compute_new(self):
        workspace = WorkspaceFactory.create(billing_project__name="test-bp", name="test-ws")
        group = ManagedGroupFactory.create()
        instance = workspace_sharing_audit_results.ShareWithCompute(
            workspace=workspace,
            managed_group=group,
            current_sharing_instance=None,
            note="foo",
        )
        # Add the mocked API response.
        acls = [
            {
                "email": group.email,
                "accessLevel": "WRITER",
                "canShare": False,
                "canCompute": True,
            }
        ]
        self.anvil_response_mock.add(
            responses.PATCH,
            self.api_client.rawls_entry_point + "/api/workspaces/test-bp/test-ws/acl?inviteUsersNotFound=false",
            status=200,
            match=[responses.matchers.json_params_matcher(acls)],
            json={"invitesSent": {}, "usersNotFound": {}, "usersUpdated": acls},
        )
        self.assertFalse(instance.handled)
        instance.handle()
        self.assertTrue(instance.handled)
        self.assertEqual(WorkspaceGroupSharing.objects.count(), 1)
        sharing = WorkspaceGroupSharing.objects.first()
        self.assertEqual(sharing.workspace, workspace)
        self.assertEqual(sharing.group, group)
        self.assertEqual(sharing.access, WorkspaceGroupSharing.WRITER)
        self.assertTrue(sharing.can_compute)

    def test_handle_share_with_compute_update(self):
        workspace = WorkspaceFactory.create(billing_project__name="test-bp", name="test-ws")
        group = ManagedGroupFactory.create()
        date_created = timezone.now() - timedelta(days=1)
        with freeze_time(date_created):
            sharing = WorkspaceGroupSharingFactory.create(
                workspace=workspace,
                group=group,
                access=WorkspaceGroupSharing.READER,
                can_compute=False,
            )
        instance = workspace_sharing_audit_results.ShareWithCompute(
            workspace=workspace,
            managed_group=group,
            current_sharing_instance=sharing,
            note="foo",
        )
        # Add the mocked API response.
        acls = [
            {
                "email": group.email,
                "accessLevel": "WRITER",
                "canShare": False,
                "canCompute": True,
            }
        ]
        self.anvil_response_mock.add(
            responses.PATCH,
            self.api_client.rawls_entry_point + "/api/workspaces/test-bp/test-ws/acl?inviteUsersNotFound=false",
            status=200,
            match=[responses.matchers.json_params_matcher(acls)],
            json={"invitesSent": {}, "usersNotFound": {}, "usersUpdated": acls},
        )
        self.assertFalse(instance.handled)
        instance.handle()
        self.assertTrue(instance.handled)
        self.assertEqual(WorkspaceGroupSharing.objects.count(), 1)
        sharing.refresh_from_db()
        self.assertEqual(sharing.workspace, workspace)
        self.assertEqual(sharing.group, group)
        self.assertEqual(sharing.access, WorkspaceGroupSharing.WRITER)
        self.assertTrue(sharing.can_compute)
        self.assertEqual(sharing.created, date_created)
        self.assertGreater(sharing.modified, date_created)

    def test_handle_share_as_owner_new(self):
        workspace = WorkspaceFactory.create(billing_project__name="test-bp", name="test-ws")
        group = ManagedGroupFactory.create()
        instance = workspace_sharing_audit_results.ShareAsOwner(
            workspace=workspace,
            managed_group=group,
            current_sharing_instance=None,
            note="foo",
        )
        # Add the mocked API response.
        acls = [
            {
                "email": group.email,
                "accessLevel": "OWNER",
                "canShare": False,  # We're not tracking this in ACM so we always send False.
                "canCompute": True,
            }
        ]
        self.anvil_response_mock.add(
            responses.PATCH,
            self.api_client.rawls_entry_point + "/api/workspaces/test-bp/test-ws/acl?inviteUsersNotFound=false",
            status=200,
            match=[responses.matchers.json_params_matcher(acls)],
            json={"invitesSent": {}, "usersNotFound": {}, "usersUpdated": acls},
        )
        self.assertFalse(instance.handled)
        instance.handle()
        self.assertTrue(instance.handled)
        self.assertEqual(WorkspaceGroupSharing.objects.count(), 1)
        sharing = WorkspaceGroupSharing.objects.first()
        self.assertEqual(sharing.workspace, workspace)
        self.assertEqual(sharing.group, group)
        self.assertEqual(sharing.access, WorkspaceGroupSharing.OWNER)
        self.assertTrue(sharing.can_compute)

    def test_handle_share_as_owner_update(self):
        workspace = WorkspaceFactory.create(billing_project__name="test-bp", name="test-ws")
        group = ManagedGroupFactory.create()
        date_created = timezone.now() - timedelta(days=1)
        with freeze_time(date_created):
            sharing = WorkspaceGroupSharingFactory.create(
                workspace=workspace,
                group=group,
                access=WorkspaceGroupSharing.READER,
                can_compute=False,
            )
        instance = workspace_sharing_audit_results.ShareAsOwner(
            workspace=workspace,
            managed_group=group,
            current_sharing_instance=sharing,
            note="foo",
        )
        # Add the mocked API response.
        acls = [
            {
                "email": group.email,
                "accessLevel": "OWNER",
                "canShare": False,  # We're not tracking this in ACM so we always send False.
                "canCompute": True,
            }
        ]
        self.anvil_response_mock.add(
            responses.PATCH,
            self.api_client.rawls_entry_point + "/api/workspaces/test-bp/test-ws/acl?inviteUsersNotFound=false",
            status=200,
            match=[responses.matchers.json_params_matcher(acls)],
            json={"invitesSent": {}, "usersNotFound": {}, "usersUpdated": acls},
        )
        self.assertFalse(instance.handled)
        instance.handle()
        self.assertTrue(instance.handled)
        self.assertEqual(WorkspaceGroupSharing.objects.count(), 1)
        sharing.refresh_from_db()
        self.assertEqual(sharing.workspace, workspace)
        self.assertEqual(sharing.group, group)
        self.assertEqual(sharing.access, WorkspaceGroupSharing.OWNER)
        self.assertTrue(sharing.can_compute)
        self.assertEqual(sharing.created, date_created)
        self.assertGreater(sharing.modified, date_created)

    def test_handle_stop_sharing(self):
        workspace = WorkspaceFactory.create(billing_project__name="test-bp", name="test-ws")
        group = ManagedGroupFactory.create()
        date_created = timezone.now() - timedelta(days=1)
        with freeze_time(date_created):
            sharing = WorkspaceGroupSharingFactory.create(
                workspace=workspace,
                group=group,
                access=WorkspaceGroupSharing.READER,
                can_compute=False,
            )
        instance = workspace_sharing_audit_results.StopSharing(
            workspace=workspace,
            managed_group=group,
            current_sharing_instance=sharing,
            note="foo",
        )
        # Add the mocked API response.
        acls = [
            {
                "email": group.email,
                "accessLevel": "NO ACCESS",
                "canShare": False,
                "canCompute": False,
            }
        ]
        self.anvil_response_mock.add(
            responses.PATCH,
            self.api_client.rawls_entry_point + "/api/workspaces/test-bp/test-ws/acl?inviteUsersNotFound=false",
            status=200,
            match=[responses.matchers.json_params_matcher(acls)],
            json={"invitesSent": {}, "usersNotFound": {}, "usersUpdated": acls},
        )
        self.assertFalse(instance.handled)
        instance.handle()
        self.assertTrue(instance.handled)
        self.assertEqual(WorkspaceGroupSharing.objects.count(), 0)


class WorkspaceAuthDomainAuditResultTest(AnVILAPIMockTestMixin, TestCase):
    """General tests of the WorkspaceAuthDomainAuditResult dataclasses."""

    def test_handle_verified_member(self):
        workspace = WorkspaceFactory.create(name="test-ws")
        WorkspaceAuthorizationDomainFactory.create(workspace=workspace, group__name="auth-test-ws")
        group = ManagedGroupFactory.create()
        date_created = timezone.now() - timedelta(days=1)
        with freeze_time(date_created):
            membership = GroupGroupMembershipFactory.create(
                parent_group=workspace.authorization_domains.first(),
                child_group=group,
                role=GroupGroupMembership.MEMBER,
            )
        instance = workspace_auth_domain_audit_results.VerifiedMember(
            workspace=workspace,
            managed_group=group,
            current_membership_instance=membership,
            note="foo",
        )
        self.assertFalse(instance.handled)
        instance.handle()
        self.assertTrue(instance.handled)
        self.assertEqual(GroupGroupMembership.objects.count(), 1)
        membership.refresh_from_db()
        self.assertEqual(membership.parent_group, workspace.authorization_domains.first())
        self.assertEqual(membership.child_group, group)
        self.assertEqual(membership.role, GroupGroupMembership.MEMBER)
        self.assertEqual(membership.created, date_created)
        self.assertEqual(membership.modified, date_created)

    def test_handle_verified_admin(self):
        workspace = WorkspaceFactory.create(name="test-ws")
        WorkspaceAuthorizationDomainFactory.create(workspace=workspace, group__name="auth-test-ws")
        group = ManagedGroupFactory.create()
        date_created = timezone.now() - timedelta(days=1)
        with freeze_time(date_created):
            membership = GroupGroupMembershipFactory.create(
                parent_group=workspace.authorization_domains.first(), child_group=group, role=GroupGroupMembership.ADMIN
            )
        instance = workspace_auth_domain_audit_results.VerifiedAdmin(
            workspace=workspace,
            managed_group=group,
            current_membership_instance=membership,
            note="foo",
        )
        self.assertFalse(instance.handled)
        instance.handle()
        self.assertTrue(instance.handled)
        self.assertEqual(GroupGroupMembership.objects.count(), 1)
        membership.refresh_from_db()
        self.assertEqual(membership.parent_group, workspace.authorization_domains.first())
        self.assertEqual(membership.child_group, group)
        self.assertEqual(membership.role, GroupGroupMembership.ADMIN)
        self.assertEqual(membership.created, date_created)
        self.assertEqual(membership.modified, date_created)

    def test_handle_verified_not_member(self):
        workspace = WorkspaceFactory.create(name="test-ws")
        WorkspaceAuthorizationDomainFactory.create(workspace=workspace, group__name="auth-test-ws")
        group = ManagedGroupFactory.create()
        instance = workspace_auth_domain_audit_results.VerifiedMember(
            workspace=workspace,
            managed_group=group,
            current_membership_instance=None,
            note="foo",
        )
        self.assertFalse(instance.handled)
        instance.handle()
        self.assertTrue(instance.handled)
        self.assertEqual(GroupGroupMembership.objects.count(), 0)

    def test_handle_add_member(self):
        workspace = WorkspaceFactory.create(name="test-ws")
        WorkspaceAuthorizationDomainFactory.create(workspace=workspace, group__name="auth-test-ws")
        group = ManagedGroupFactory.create()
        instance = workspace_auth_domain_audit_results.AddMember(
            workspace=workspace,
            managed_group=group,
            current_membership_instance=None,
            note="foo",
        )
        # Add the mocked API response.
        # Note that the auth domain group is created automatically by the factory using the workspace name.
        self.anvil_response_mock.add(
            responses.PUT,
            self.api_client.sam_entry_point + f"/api/groups/v1/auth-test-ws/member/{group.email}",
            status=204,
        )
        self.assertFalse(instance.handled)
        instance.handle()
        self.assertTrue(instance.handled)
        self.assertEqual(GroupGroupMembership.objects.count(), 1)
        membership = GroupGroupMembership.objects.first()
        self.assertEqual(membership.parent_group, workspace.authorization_domains.first())
        self.assertEqual(membership.child_group, group)
        self.assertEqual(membership.role, GroupGroupMembership.MEMBER)

    def test_handle_add_admin(self):
        workspace = WorkspaceFactory.create(name="test-ws")
        WorkspaceAuthorizationDomainFactory.create(workspace=workspace, group__name="auth-test-ws")
        group = ManagedGroupFactory.create()
        instance = workspace_auth_domain_audit_results.AddAdmin(
            workspace=workspace,
            managed_group=group,
            current_membership_instance=None,
            note="foo",
        )
        # Add the mocked API response.
        # Note that the auth domain group is created automatically by the factory using the workspace name.
        self.anvil_response_mock.add(
            responses.PUT,
            self.api_client.sam_entry_point + f"/api/groups/v1/auth-test-ws/admin/{group.email}",
            status=204,
        )
        self.assertFalse(instance.handled)
        instance.handle()
        self.assertTrue(instance.handled)
        self.assertEqual(GroupGroupMembership.objects.count(), 1)
        membership = GroupGroupMembership.objects.first()
        self.assertEqual(membership.parent_group, workspace.authorization_domains.first())
        self.assertEqual(membership.child_group, group)
        self.assertEqual(membership.role, GroupGroupMembership.ADMIN)

    def test_handle_change_to_member(self):
        workspace = WorkspaceFactory.create(name="test-ws")
        WorkspaceAuthorizationDomainFactory.create(workspace=workspace, group__name="auth-test-ws")
        group = ManagedGroupFactory.create()
        date_created = timezone.now() - timedelta(days=1)
        with freeze_time(date_created):
            membership = GroupGroupMembershipFactory.create(
                parent_group=workspace.authorization_domains.first(),
                child_group=group,
                role=GroupGroupMembership.ADMIN,
            )
        instance = workspace_auth_domain_audit_results.ChangeToMember(
            workspace=workspace,
            managed_group=group,
            current_membership_instance=membership,
            note="foo",
        )
        # Add the mocked API response.
        # Note that the auth domain group is created automatically by the factory using the workspace name.
        self.anvil_response_mock.add(
            responses.DELETE,
            self.api_client.sam_entry_point + f"/api/groups/v1/auth-test-ws/admin/{group.name}@firecloud.org",
            status=204,
        )
        self.anvil_response_mock.add(
            responses.PUT,
            self.api_client.sam_entry_point + f"/api/groups/v1/auth-test-ws/member/{group.name}@firecloud.org",
            status=204,
        )
        self.assertFalse(instance.handled)
        instance.handle()
        self.assertTrue(instance.handled)
        self.assertEqual(GroupGroupMembership.objects.count(), 1)
        membership = GroupGroupMembership.objects.first()
        self.assertEqual(membership.parent_group, workspace.authorization_domains.first())
        self.assertEqual(membership.child_group, group)
        self.assertEqual(membership.role, GroupGroupMembership.MEMBER)
        self.assertGreater(membership.modified, date_created)

    def test_handle_change_to_admin(self):
        workspace = WorkspaceFactory.create(name="test-ws")
        WorkspaceAuthorizationDomainFactory.create(workspace=workspace, group__name="auth-test-ws")
        group = ManagedGroupFactory.create()
        date_created = timezone.now() - timedelta(days=1)
        with freeze_time(date_created):
            membership = GroupGroupMembershipFactory.create(
                parent_group=workspace.authorization_domains.first(),
                child_group=group,
                role=GroupGroupMembership.MEMBER,
            )
        instance = workspace_auth_domain_audit_results.ChangeToAdmin(
            workspace=workspace,
            managed_group=group,
            current_membership_instance=membership,
            note="foo",
        )
        # Add the mocked API response.
        # Note that the auth domain group is created automatically by the factory using the workspace name.
        self.anvil_response_mock.add(
            responses.DELETE,
            self.api_client.sam_entry_point + f"/api/groups/v1/auth-test-ws/member/{group.name}@firecloud.org",
            status=204,
        )
        self.anvil_response_mock.add(
            responses.PUT,
            self.api_client.sam_entry_point + f"/api/groups/v1/auth-test-ws/admin/{group.name}@firecloud.org",
            status=204,
        )
        self.assertFalse(instance.handled)
        instance.handle()
        self.assertTrue(instance.handled)
        self.assertEqual(GroupGroupMembership.objects.count(), 1)
        membership = GroupGroupMembership.objects.first()
        self.assertEqual(membership.parent_group, workspace.authorization_domains.first())
        self.assertEqual(membership.child_group, group)
        self.assertEqual(membership.role, GroupGroupMembership.ADMIN)
        self.assertGreater(membership.modified, date_created)

    def test_handle_remove(self):
        workspace = WorkspaceFactory.create(name="test-ws")
        WorkspaceAuthorizationDomainFactory.create(workspace=workspace, group__name="auth-test-ws")
        group = ManagedGroupFactory.create()
        membership = GroupGroupMembershipFactory.create(
            parent_group=workspace.authorization_domains.first(),
            child_group=group,
            role=GroupGroupMembership.MEMBER,
        )
        instance = workspace_auth_domain_audit_results.Remove(
            workspace=workspace,
            managed_group=group,
            current_membership_instance=membership,
            note="foo",
        )
        # Add the mocked API response.
        # Note that the auth domain group is created automatically by the factory using the workspace name.
        self.anvil_response_mock.add(
            responses.DELETE,
            self.api_client.sam_entry_point + f"/api/groups/v1/auth-test-ws/member/{group.name}@firecloud.org",
            status=204,
        )
        self.assertFalse(instance.handled)
        instance.handle()
        self.assertTrue(instance.handled)
        self.assertEqual(GroupGroupMembership.objects.count(), 0)

    def test_member_as_admin(self):
        upload_workspace = factories.UploadWorkspaceFactory.create(upload_cycle__is_future=True)
        group = ManagedGroupFactory.create()
        membership = GroupGroupMembershipFactory.create(
            parent_group=upload_workspace.workspace.authorization_domains.first(),
            child_group=group,
            role=GroupGroupMembership.ADMIN,
        )
        instance = workspace_auth_domain_audit_results.WorkspaceAuthDomainAuditResult(
            workspace=upload_workspace.workspace,
            managed_group=group,
            current_membership_instance=membership,
            note="foo",
        )
        table_dictionary = instance.get_table_dictionary()
        self.assertEqual(table_dictionary["role"], membership.ADMIN)

    def test_member_as_member(self):
        upload_workspace = factories.UploadWorkspaceFactory.create(upload_cycle__is_future=True)
        group = ManagedGroupFactory.create()
        membership = GroupGroupMembershipFactory.create(
            parent_group=upload_workspace.workspace.authorization_domains.first(),
            child_group=group,
            role=GroupGroupMembership.MEMBER,
        )
        instance = workspace_auth_domain_audit_results.WorkspaceAuthDomainAuditResult(
            workspace=upload_workspace.workspace,
            managed_group=group,
            current_membership_instance=membership,
            note="foo",
        )
        table_dictionary = instance.get_table_dictionary()
        self.assertEqual(table_dictionary["role"], membership.MEMBER)

    def test_not_member(self):
        upload_workspace = factories.UploadWorkspaceFactory.create(upload_cycle__is_future=True)
        group = ManagedGroupFactory.create()
        instance = workspace_auth_domain_audit_results.WorkspaceAuthDomainAuditResult(
            workspace=upload_workspace.workspace,
            managed_group=group,
            current_membership_instance=None,
            note="foo",
        )
        table_dictionary = instance.get_table_dictionary()
        self.assertIsNone(table_dictionary["role"])


class UploadWorkspaceSharingAuditTableTest(TestCase):
    """General tests of the UploadWorkspaceSharingAuditTable class."""

    def test_no_rows(self):
        """Table works with no rows."""
        table = upload_workspace_audit.UploadWorkspaceSharingAuditTable([])
        self.assertIsInstance(table, upload_workspace_audit.UploadWorkspaceSharingAuditTable)
        self.assertEqual(len(table.rows), 0)

    def test_one_row(self):
        """Table works with one row."""
        upload_workspace = factories.UploadWorkspaceFactory.create()
        group = ManagedGroupFactory.create()
        WorkspaceGroupSharingFactory.create(
            workspace=upload_workspace.workspace, group=group, access=WorkspaceGroupSharing.READER
        )
        data = [
            {
                "workspace": upload_workspace.workspace,
                "managed_group": group,
                "access": WorkspaceGroupSharing.READER,
                "can_compute": None,
                "note": "a note",
                "action": "",
            },
        ]
        table = upload_workspace_audit.UploadWorkspaceSharingAuditTable(data)
        self.assertIsInstance(table, upload_workspace_audit.UploadWorkspaceSharingAuditTable)
        self.assertEqual(len(table.rows), 1)

    def test_two_rows(self):
        """Table works with two rows."""
        upload_workspace = factories.UploadWorkspaceFactory.create()
        group_1 = ManagedGroupFactory.create()
        group_2 = ManagedGroupFactory.create()
        WorkspaceGroupSharingFactory.create(
            workspace=upload_workspace.workspace, group=group_1, access=WorkspaceGroupSharing.READER
        )
        data = [
            {
                "workspace": upload_workspace.workspace,
                "managed_group": group_1,
                "access": WorkspaceGroupSharing.READER,
                "can_compute": None,
                "note": "a note",
                "action": "",
            },
            {
                "workspace": upload_workspace.workspace,
                "managed_group": group_2,
                "access": None,
                "can_compute": None,
                "note": "a note",
                "action": "",
            },
        ]
        table = upload_workspace_audit.UploadWorkspaceSharingAuditTable(data)
        self.assertIsInstance(table, upload_workspace_audit.UploadWorkspaceSharingAuditTable)
        self.assertEqual(len(table.rows), 2)


class UploadWorkspaceSharingAuditTest(TestCase):
    """General tests of the `UploadWorkspaceSharingAudit` class."""

    def test_completed(self):
        """The completed attribute is set appropriately."""
        # Instantiate the class.
        audit = upload_workspace_audit.UploadWorkspaceSharingAudit()
        self.assertFalse(audit.completed)
        audit.run_audit()
        self.assertTrue(audit.completed)

    def test_no_upload_workspaces(self):
        """The audit works if there are no UploadWorkspaces."""
        audit = upload_workspace_audit.UploadWorkspaceSharingAudit()
        audit.run_audit()
        self.assertEqual(len(audit.verified), 0)
        self.assertEqual(len(audit.needs_action), 0)
        self.assertEqual(len(audit.errors), 0)

    def test_one_upload_workspace_no_groups(self):
        upload_workspace = factories.UploadWorkspaceFactory.create()
        audit = upload_workspace_audit.UploadWorkspaceSharingAudit()
        audit.run_audit()
        self.assertEqual(len(audit.verified), 0)
        self.assertEqual(len(audit.needs_action), 1)
        self.assertEqual(len(audit.errors), 0)
        record = audit.needs_action[0]
        self.assertIsInstance(record, workspace_sharing_audit_results.ShareAsReader)
        self.assertEqual(record.workspace, upload_workspace.workspace)
        self.assertEqual(record.managed_group, upload_workspace.workspace.authorization_domains.first())
        self.assertEqual(record.current_sharing_instance, None)
        self.assertEqual(record.note, upload_workspace_audit.UploadWorkspaceSharingAudit.AUTH_DOMAIN_AS_READER)

    def test_one_upload_workspace_rc_upload_group(self):
        group = ManagedGroupFactory.create()
        upload_workspace = factories.UploadWorkspaceFactory.create(
            research_center__uploader_group=group, upload_cycle__is_future=True
        )
        audit = upload_workspace_audit.UploadWorkspaceSharingAudit()
        audit.run_audit()
        self.assertEqual(len(audit.verified), 1)
        self.assertEqual(len(audit.needs_action), 1)  # auth domain is not shared
        self.assertEqual(len(audit.errors), 0)
        record = audit.verified[0]
        self.assertIsInstance(record, workspace_sharing_audit_results.VerifiedNotShared)
        self.assertEqual(record.workspace, upload_workspace.workspace)
        self.assertEqual(record.managed_group, group)

    def test_one_upload_workspace_dcc_writer_group(self):
        group = ManagedGroupFactory.create(name="GREGOR_DCC_WRITERS")
        upload_workspace = factories.UploadWorkspaceFactory.create(upload_cycle__is_future=True)
        WorkspaceGroupSharingFactory.create(
            workspace=upload_workspace.workspace, group=group, access=WorkspaceGroupSharing.WRITER, can_compute=True
        )
        audit = upload_workspace_audit.UploadWorkspaceSharingAudit()
        audit.run_audit()
        self.assertEqual(len(audit.verified), 1)
        self.assertEqual(len(audit.needs_action), 1)  # auth domain is not shared
        self.assertEqual(len(audit.errors), 0)
        record = audit.verified[0]
        self.assertIsInstance(record, workspace_sharing_audit_results.VerifiedShared)
        self.assertEqual(record.workspace, upload_workspace.workspace)
        self.assertEqual(record.managed_group, group)

    def test_one_upload_workspace_auth_domain(self):
        upload_workspace = factories.UploadWorkspaceFactory.create(upload_cycle__is_future=True)
        group = upload_workspace.workspace.authorization_domains.first()
        WorkspaceGroupSharingFactory.create(
            workspace=upload_workspace.workspace, group=group, access=WorkspaceGroupSharing.READER
        )
        audit = upload_workspace_audit.UploadWorkspaceSharingAudit()
        audit.run_audit()
        self.assertEqual(len(audit.verified), 1)
        self.assertEqual(len(audit.needs_action), 0)  # auth domain is shared
        self.assertEqual(len(audit.errors), 0)
        record = audit.verified[0]
        self.assertIsInstance(record, workspace_sharing_audit_results.VerifiedShared)
        self.assertEqual(record.workspace, upload_workspace.workspace)
        self.assertEqual(record.managed_group, group)

    def test_one_upload_workspace_dcc_admin_group(self):
        group = ManagedGroupFactory.create(name=settings.ANVIL_DCC_ADMINS_GROUP_NAME)
        upload_workspace = factories.UploadWorkspaceFactory.create(upload_cycle__is_future=True)
        WorkspaceGroupSharingFactory.create(
            workspace=upload_workspace.workspace, group=group, access=WorkspaceGroupSharing.OWNER
        )
        audit = upload_workspace_audit.UploadWorkspaceSharingAudit()
        audit.run_audit()
        self.assertEqual(len(audit.verified), 1)
        self.assertEqual(len(audit.needs_action), 1)  # auth domain is not shared
        self.assertEqual(len(audit.errors), 0)
        record = audit.verified[0]
        self.assertIsInstance(record, workspace_sharing_audit_results.VerifiedShared)
        self.assertEqual(record.workspace, upload_workspace.workspace)
        self.assertEqual(record.managed_group, group)

    @override_settings(ANVIL_DCC_ADMINS_GROUP_NAME="foo")
    def test_one_upload_workspace_dcc_admin_group_different_name(self):
        group = ManagedGroupFactory.create(name="foo")
        upload_workspace = factories.UploadWorkspaceFactory.create(upload_cycle__is_future=True)
        WorkspaceGroupSharingFactory.create(
            workspace=upload_workspace.workspace, group=group, access=WorkspaceGroupSharing.OWNER
        )
        audit = upload_workspace_audit.UploadWorkspaceSharingAudit()
        audit.run_audit()
        self.assertEqual(len(audit.verified), 1)
        self.assertEqual(len(audit.needs_action), 1)  # auth domain is not shared
        self.assertEqual(len(audit.errors), 0)
        record = audit.verified[0]
        self.assertIsInstance(record, workspace_sharing_audit_results.VerifiedShared)
        self.assertEqual(record.workspace, upload_workspace.workspace)
        self.assertEqual(record.managed_group, group)

    def test_one_upload_workspace_anvil_admin_group(self):
        group = ManagedGroupFactory.create(name="anvil-admins")
        upload_workspace = factories.UploadWorkspaceFactory.create(upload_cycle__is_future=True)
        WorkspaceGroupSharingFactory.create(workspace=upload_workspace.workspace, group=group)
        audit = upload_workspace_audit.UploadWorkspaceSharingAudit()
        audit.run_audit()
        self.assertEqual(len(audit.verified), 0)
        self.assertEqual(len(audit.needs_action), 1)  # auth domain is not shared
        self.assertEqual(len(audit.errors), 0)

    def test_one_upload_workspace_anvil_dev_group(self):
        group = ManagedGroupFactory.create(name="anvil_devs")
        upload_workspace = factories.UploadWorkspaceFactory.create(upload_cycle__is_future=True)
        WorkspaceGroupSharingFactory.create(workspace=upload_workspace.workspace, group=group)
        audit = upload_workspace_audit.UploadWorkspaceSharingAudit()
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
        audit = upload_workspace_audit.UploadWorkspaceSharingAudit()
        audit.run_audit()
        self.assertEqual(len(audit.verified), 0)
        self.assertEqual(len(audit.needs_action), 1)  # auth domain is not shared
        self.assertEqual(len(audit.errors), 1)
        record = audit.errors[0]
        self.assertIsInstance(record, workspace_sharing_audit_results.StopSharing)
        self.assertEqual(record.workspace, upload_workspace.workspace)
        self.assertEqual(record.managed_group, group)

    def test_one_upload_workspace_other_group_not_shared(self):
        ManagedGroupFactory.create(name="foo")
        factories.UploadWorkspaceFactory.create(upload_cycle__is_future=True)
        audit = upload_workspace_audit.UploadWorkspaceSharingAudit()
        audit.run_audit()
        self.assertEqual(len(audit.verified), 0)
        self.assertEqual(len(audit.needs_action), 1)  # auth domain is not shared
        self.assertEqual(len(audit.errors), 0)

    def test_two_upload_workspaces(self):
        """Audit works with two UploadWorkspaces."""
        upload_workspace_1 = factories.UploadWorkspaceFactory.create()
        sharing = WorkspaceGroupSharingFactory.create(
            workspace=upload_workspace_1.workspace,
            group=upload_workspace_1.workspace.authorization_domains.first(),
        )
        upload_workspace_2 = factories.UploadWorkspaceFactory.create()
        audit = upload_workspace_audit.UploadWorkspaceSharingAudit()
        audit.run_audit()
        self.assertEqual(len(audit.verified), 1)
        self.assertEqual(len(audit.needs_action), 1)
        self.assertEqual(len(audit.errors), 0)
        record = audit.verified[0]
        self.assertIsInstance(record, workspace_sharing_audit_results.VerifiedShared)
        self.assertEqual(record.workspace, upload_workspace_1.workspace)
        self.assertEqual(record.managed_group, upload_workspace_1.workspace.authorization_domains.first())
        self.assertEqual(record.current_sharing_instance, sharing)
        self.assertEqual(record.note, upload_workspace_audit.UploadWorkspaceSharingAudit.AUTH_DOMAIN_AS_READER)
        record = audit.needs_action[0]
        self.assertIsInstance(record, workspace_sharing_audit_results.ShareAsReader)
        self.assertEqual(record.workspace, upload_workspace_2.workspace)
        self.assertEqual(record.managed_group, upload_workspace_2.workspace.authorization_domains.first())
        self.assertIsNone(record.current_sharing_instance)
        self.assertEqual(record.note, upload_workspace_audit.UploadWorkspaceSharingAudit.AUTH_DOMAIN_AS_READER)

    def test_queryset(self):
        """Audit only runs on the specified queryset of dbGaPApplications."""
        upload_workspace_1 = factories.UploadWorkspaceFactory.create()
        sharing = WorkspaceGroupSharingFactory.create(
            workspace=upload_workspace_1.workspace,
            group=upload_workspace_1.workspace.authorization_domains.first(),
        )
        upload_workspace_2 = factories.UploadWorkspaceFactory.create()
        # First application
        audit = upload_workspace_audit.UploadWorkspaceSharingAudit(
            queryset=models.UploadWorkspace.objects.filter(pk=upload_workspace_1.pk)
        )
        audit.run_audit()
        self.assertEqual(len(audit.verified), 1)
        self.assertEqual(len(audit.needs_action), 0)
        self.assertEqual(len(audit.errors), 0)
        record = audit.verified[0]
        self.assertIsInstance(record, workspace_sharing_audit_results.VerifiedShared)
        self.assertEqual(record.workspace, upload_workspace_1.workspace)
        self.assertEqual(record.managed_group, upload_workspace_1.workspace.authorization_domains.first())
        self.assertEqual(record.current_sharing_instance, sharing)
        self.assertEqual(record.note, upload_workspace_audit.UploadWorkspaceSharingAudit.AUTH_DOMAIN_AS_READER)
        # Second application
        audit = upload_workspace_audit.UploadWorkspaceSharingAudit(
            queryset=models.UploadWorkspace.objects.filter(pk=upload_workspace_2.pk)
        )
        audit.run_audit()
        self.assertEqual(len(audit.verified), 0)
        self.assertEqual(len(audit.needs_action), 1)
        self.assertEqual(len(audit.errors), 0)
        record = audit.needs_action[0]
        self.assertIsInstance(record, workspace_sharing_audit_results.ShareAsReader)
        self.assertEqual(record.workspace, upload_workspace_2.workspace)
        self.assertEqual(record.managed_group, upload_workspace_2.workspace.authorization_domains.first())
        self.assertIsNone(record.current_sharing_instance)
        self.assertEqual(record.note, upload_workspace_audit.UploadWorkspaceSharingAudit.AUTH_DOMAIN_AS_READER)

    def test_queryset_wrong_class(self):
        """Raises ValueError if queryset is not a QuerySet."""
        with self.assertRaises(ValueError):
            upload_workspace_audit.UploadWorkspaceSharingAudit(queryset="foo")
        with self.assertRaises(ValueError):
            upload_workspace_audit.UploadWorkspaceSharingAudit(
                queryset=models.CombinedConsortiumDataWorkspace.objects.all()
            )


class UploadWorkspaceSharingAuditFutureCycleTest(TestCase):
    """Tests for the `UploadWorkspaceSharingAudit` class for future cycle UploadWorkspaces.

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
        audit = upload_workspace_audit.UploadWorkspaceSharingAudit()
        audit.audit_workspace_and_group(self.upload_workspace, self.rc_uploader_group)
        self.assertEqual(len(audit.verified), 0)
        self.assertEqual(len(audit.needs_action), 1)
        self.assertEqual(len(audit.errors), 0)
        record = audit.needs_action[0]
        self.assertIsInstance(record, workspace_sharing_audit_results.StopSharing)
        self.assertEqual(record.workspace, self.upload_workspace.workspace)
        self.assertEqual(record.managed_group, self.rc_uploader_group)
        self.assertEqual(record.current_sharing_instance, sharing)
        self.assertEqual(record.note, upload_workspace_audit.UploadWorkspaceSharingAudit.RC_UPLOADERS_FUTURE_CYCLE)

    def test_uploaders_not_shared(self):
        audit = upload_workspace_audit.UploadWorkspaceSharingAudit()
        audit.audit_workspace_and_group(self.upload_workspace, self.rc_uploader_group)
        self.assertEqual(len(audit.verified), 1)
        self.assertEqual(len(audit.needs_action), 0)
        self.assertEqual(len(audit.errors), 0)
        record = audit.verified[0]
        self.assertIsInstance(record, workspace_sharing_audit_results.VerifiedNotShared)
        self.assertEqual(record.workspace, self.upload_workspace.workspace)
        self.assertEqual(record.managed_group, self.rc_uploader_group)
        self.assertEqual(record.current_sharing_instance, None)
        self.assertEqual(record.note, upload_workspace_audit.UploadWorkspaceSharingAudit.RC_UPLOADERS_FUTURE_CYCLE)

    def test_uploaders_shared_as_writer_can_compute(self):
        sharing = WorkspaceGroupSharingFactory.create(
            workspace=self.upload_workspace.workspace,
            group=self.rc_uploader_group,
            access=WorkspaceGroupSharing.WRITER,
            can_compute=True,
        )
        audit = upload_workspace_audit.UploadWorkspaceSharingAudit()
        audit.audit_workspace_and_group(self.upload_workspace, self.rc_uploader_group)
        self.assertEqual(len(audit.verified), 0)
        self.assertEqual(len(audit.needs_action), 1)
        self.assertEqual(len(audit.errors), 0)
        record = audit.needs_action[0]
        self.assertIsInstance(record, workspace_sharing_audit_results.StopSharing)
        self.assertEqual(record.workspace, self.upload_workspace.workspace)
        self.assertEqual(record.managed_group, self.rc_uploader_group)
        self.assertEqual(record.current_sharing_instance, sharing)
        self.assertEqual(record.note, upload_workspace_audit.UploadWorkspaceSharingAudit.RC_UPLOADERS_FUTURE_CYCLE)

    def test_uploaders_shared_as_reader(self):
        sharing = WorkspaceGroupSharingFactory.create(
            workspace=self.upload_workspace.workspace, group=self.rc_uploader_group, access=WorkspaceGroupSharing.READER
        )
        audit = upload_workspace_audit.UploadWorkspaceSharingAudit()
        audit.audit_workspace_and_group(self.upload_workspace, self.rc_uploader_group)
        self.assertEqual(len(audit.verified), 0)
        self.assertEqual(len(audit.needs_action), 1)
        self.assertEqual(len(audit.errors), 0)
        record = audit.needs_action[0]
        self.assertIsInstance(record, workspace_sharing_audit_results.StopSharing)
        self.assertEqual(record.workspace, self.upload_workspace.workspace)
        self.assertEqual(record.managed_group, self.rc_uploader_group)
        self.assertEqual(record.current_sharing_instance, sharing)
        self.assertEqual(record.note, upload_workspace_audit.UploadWorkspaceSharingAudit.RC_UPLOADERS_FUTURE_CYCLE)

    def test_uploaders_shared_as_owner(self):
        sharing = WorkspaceGroupSharingFactory.create(
            workspace=self.upload_workspace.workspace, group=self.rc_uploader_group, access=WorkspaceGroupSharing.OWNER
        )
        audit = upload_workspace_audit.UploadWorkspaceSharingAudit()
        audit.audit_workspace_and_group(self.upload_workspace, self.rc_uploader_group)
        self.assertEqual(len(audit.verified), 0)
        self.assertEqual(len(audit.needs_action), 0)
        self.assertEqual(len(audit.errors), 1)
        record = audit.errors[0]
        self.assertIsInstance(record, workspace_sharing_audit_results.StopSharing)
        self.assertEqual(record.workspace, self.upload_workspace.workspace)
        self.assertEqual(record.managed_group, self.rc_uploader_group)
        self.assertEqual(record.current_sharing_instance, sharing)
        self.assertEqual(record.note, upload_workspace_audit.UploadWorkspaceSharingAudit.RC_UPLOADERS_FUTURE_CYCLE)

    def test_dcc_writers_shared_as_writer_no_compute(self):
        # Share the workspace with the group.
        sharing = WorkspaceGroupSharingFactory.create(
            workspace=self.upload_workspace.workspace, group=self.dcc_writer_group, access=WorkspaceGroupSharing.WRITER
        )
        audit = upload_workspace_audit.UploadWorkspaceSharingAudit()
        audit.audit_workspace_and_group(self.upload_workspace, self.dcc_writer_group)
        self.assertEqual(len(audit.verified), 0)
        self.assertEqual(len(audit.needs_action), 1)
        self.assertEqual(len(audit.errors), 0)
        record = audit.needs_action[0]
        self.assertIsInstance(record, workspace_sharing_audit_results.ShareWithCompute)
        self.assertEqual(record.workspace, self.upload_workspace.workspace)
        self.assertEqual(record.managed_group, self.dcc_writer_group)
        self.assertEqual(record.current_sharing_instance, sharing)
        self.assertEqual(record.note, upload_workspace_audit.UploadWorkspaceSharingAudit.DCC_WRITERS_FUTURE_CYCLE)

    def test_dcc_writers_not_shared(self):
        audit = upload_workspace_audit.UploadWorkspaceSharingAudit()
        audit.audit_workspace_and_group(self.upload_workspace, self.dcc_writer_group)
        self.assertEqual(len(audit.verified), 0)
        self.assertEqual(len(audit.needs_action), 1)
        self.assertEqual(len(audit.errors), 0)
        record = audit.needs_action[0]
        self.assertIsInstance(record, workspace_sharing_audit_results.ShareWithCompute)
        self.assertEqual(record.workspace, self.upload_workspace.workspace)
        self.assertEqual(record.managed_group, self.dcc_writer_group)
        self.assertEqual(record.current_sharing_instance, None)
        self.assertEqual(record.note, upload_workspace_audit.UploadWorkspaceSharingAudit.DCC_WRITERS_FUTURE_CYCLE)

    def test_dcc_writers_shared_as_writer_can_compute(self):
        sharing = WorkspaceGroupSharingFactory.create(
            workspace=self.upload_workspace.workspace,
            group=self.dcc_writer_group,
            access=WorkspaceGroupSharing.WRITER,
            can_compute=True,
        )
        audit = upload_workspace_audit.UploadWorkspaceSharingAudit()
        audit.audit_workspace_and_group(self.upload_workspace, self.dcc_writer_group)
        self.assertEqual(len(audit.verified), 1)
        self.assertEqual(len(audit.needs_action), 0)
        self.assertEqual(len(audit.errors), 0)
        record = audit.verified[0]
        self.assertIsInstance(record, workspace_sharing_audit_results.VerifiedShared)
        self.assertEqual(record.workspace, self.upload_workspace.workspace)
        self.assertEqual(record.managed_group, self.dcc_writer_group)
        self.assertEqual(record.current_sharing_instance, sharing)
        self.assertEqual(record.note, upload_workspace_audit.UploadWorkspaceSharingAudit.DCC_WRITERS_FUTURE_CYCLE)

    def test_dcc_writers_shared_as_reader(self):
        sharing = WorkspaceGroupSharingFactory.create(
            workspace=self.upload_workspace.workspace, group=self.dcc_writer_group, access=WorkspaceGroupSharing.READER
        )
        audit = upload_workspace_audit.UploadWorkspaceSharingAudit()
        audit.audit_workspace_and_group(self.upload_workspace, self.dcc_writer_group)
        self.assertEqual(len(audit.verified), 0)
        self.assertEqual(len(audit.needs_action), 1)
        self.assertEqual(len(audit.errors), 0)
        record = audit.needs_action[0]
        self.assertIsInstance(record, workspace_sharing_audit_results.ShareWithCompute)
        self.assertEqual(record.workspace, self.upload_workspace.workspace)
        self.assertEqual(record.managed_group, self.dcc_writer_group)
        self.assertEqual(record.current_sharing_instance, sharing)
        self.assertEqual(record.note, upload_workspace_audit.UploadWorkspaceSharingAudit.DCC_WRITERS_FUTURE_CYCLE)

    def test_dcc_writers_shared_as_owner(self):
        sharing = WorkspaceGroupSharingFactory.create(
            workspace=self.upload_workspace.workspace, group=self.dcc_writer_group, access=WorkspaceGroupSharing.OWNER
        )
        audit = upload_workspace_audit.UploadWorkspaceSharingAudit()
        audit.audit_workspace_and_group(self.upload_workspace, self.dcc_writer_group)
        self.assertEqual(len(audit.verified), 0)
        self.assertEqual(len(audit.needs_action), 0)
        self.assertEqual(len(audit.errors), 1)
        record = audit.errors[0]
        self.assertIsInstance(record, workspace_sharing_audit_results.ShareWithCompute)
        self.assertEqual(record.workspace, self.upload_workspace.workspace)
        self.assertEqual(record.managed_group, self.dcc_writer_group)
        self.assertEqual(record.current_sharing_instance, sharing)
        self.assertEqual(record.note, upload_workspace_audit.UploadWorkspaceSharingAudit.DCC_WRITERS_FUTURE_CYCLE)

    def test_auth_domain_shared_as_writer_no_compute(self):
        # Share the workspace with the group.
        sharing = WorkspaceGroupSharingFactory.create(
            workspace=self.upload_workspace.workspace, group=self.auth_domain, access=WorkspaceGroupSharing.WRITER
        )
        audit = upload_workspace_audit.UploadWorkspaceSharingAudit()
        audit.audit_workspace_and_group(self.upload_workspace, self.auth_domain)
        self.assertEqual(len(audit.verified), 0)
        self.assertEqual(len(audit.needs_action), 1)
        self.assertEqual(len(audit.errors), 0)
        record = audit.needs_action[0]
        self.assertIsInstance(record, workspace_sharing_audit_results.ShareAsReader)
        self.assertEqual(record.workspace, self.upload_workspace.workspace)
        self.assertEqual(record.managed_group, self.auth_domain)
        self.assertEqual(record.current_sharing_instance, sharing)
        self.assertEqual(record.note, upload_workspace_audit.UploadWorkspaceSharingAudit.AUTH_DOMAIN_AS_READER)

    def test_auth_domain_not_shared(self):
        audit = upload_workspace_audit.UploadWorkspaceSharingAudit()
        audit.audit_workspace_and_group(self.upload_workspace, self.auth_domain)
        self.assertEqual(len(audit.verified), 0)
        self.assertEqual(len(audit.needs_action), 1)
        self.assertEqual(len(audit.errors), 0)
        record = audit.needs_action[0]
        self.assertIsInstance(record, workspace_sharing_audit_results.ShareAsReader)
        self.assertEqual(record.workspace, self.upload_workspace.workspace)
        self.assertEqual(record.managed_group, self.auth_domain)
        self.assertEqual(record.current_sharing_instance, None)
        self.assertEqual(record.note, upload_workspace_audit.UploadWorkspaceSharingAudit.AUTH_DOMAIN_AS_READER)

    def test_auth_domain_shared_as_writer_can_compute(self):
        sharing = WorkspaceGroupSharingFactory.create(
            workspace=self.upload_workspace.workspace,
            group=self.auth_domain,
            access=WorkspaceGroupSharing.WRITER,
            can_compute=True,
        )
        audit = upload_workspace_audit.UploadWorkspaceSharingAudit()
        audit.audit_workspace_and_group(self.upload_workspace, self.auth_domain)
        self.assertEqual(len(audit.verified), 0)
        self.assertEqual(len(audit.needs_action), 1)
        self.assertEqual(len(audit.errors), 0)
        record = audit.needs_action[0]
        self.assertIsInstance(record, workspace_sharing_audit_results.ShareAsReader)
        self.assertEqual(record.workspace, self.upload_workspace.workspace)
        self.assertEqual(record.managed_group, self.auth_domain)
        self.assertEqual(record.current_sharing_instance, sharing)
        self.assertEqual(record.note, upload_workspace_audit.UploadWorkspaceSharingAudit.AUTH_DOMAIN_AS_READER)

    def test_auth_domain_shared_as_reader(self):
        sharing = WorkspaceGroupSharingFactory.create(
            workspace=self.upload_workspace.workspace, group=self.auth_domain, access=WorkspaceGroupSharing.READER
        )
        audit = upload_workspace_audit.UploadWorkspaceSharingAudit()
        audit.audit_workspace_and_group(self.upload_workspace, self.auth_domain)
        self.assertEqual(len(audit.verified), 1)
        self.assertEqual(len(audit.needs_action), 0)
        self.assertEqual(len(audit.errors), 0)
        record = audit.verified[0]
        self.assertIsInstance(record, workspace_sharing_audit_results.VerifiedShared)
        self.assertEqual(record.workspace, self.upload_workspace.workspace)
        self.assertEqual(record.managed_group, self.auth_domain)
        self.assertEqual(record.current_sharing_instance, sharing)
        self.assertEqual(record.note, upload_workspace_audit.UploadWorkspaceSharingAudit.AUTH_DOMAIN_AS_READER)

    def test_auth_domain_shared_as_owner(self):
        sharing = WorkspaceGroupSharingFactory.create(
            workspace=self.upload_workspace.workspace, group=self.auth_domain, access=WorkspaceGroupSharing.OWNER
        )
        audit = upload_workspace_audit.UploadWorkspaceSharingAudit()
        audit.audit_workspace_and_group(self.upload_workspace, self.auth_domain)
        self.assertEqual(len(audit.verified), 0)
        self.assertEqual(len(audit.needs_action), 0)
        self.assertEqual(len(audit.errors), 1)
        record = audit.errors[0]
        self.assertIsInstance(record, workspace_sharing_audit_results.ShareAsReader)
        self.assertEqual(record.workspace, self.upload_workspace.workspace)
        self.assertEqual(record.managed_group, self.auth_domain)
        self.assertEqual(record.current_sharing_instance, sharing)
        self.assertEqual(record.note, upload_workspace_audit.UploadWorkspaceSharingAudit.AUTH_DOMAIN_AS_READER)

    def test_dcc_admin_shared_as_writer_no_compute(self):
        # Share the workspace with the group.
        sharing = WorkspaceGroupSharingFactory.create(
            workspace=self.upload_workspace.workspace, group=self.dcc_admin_group, access=WorkspaceGroupSharing.WRITER
        )
        audit = upload_workspace_audit.UploadWorkspaceSharingAudit()
        audit.audit_workspace_and_group(self.upload_workspace, self.dcc_admin_group)
        self.assertEqual(len(audit.verified), 0)
        self.assertEqual(len(audit.needs_action), 1)
        self.assertEqual(len(audit.errors), 0)
        record = audit.needs_action[0]
        self.assertIsInstance(record, workspace_sharing_audit_results.ShareAsOwner)
        self.assertEqual(record.workspace, self.upload_workspace.workspace)
        self.assertEqual(record.managed_group, self.dcc_admin_group)
        self.assertEqual(record.current_sharing_instance, sharing)
        self.assertEqual(record.note, upload_workspace_audit.UploadWorkspaceSharingAudit.DCC_ADMIN_AS_OWNER)

    def test_dcc_admin_not_shared(self):
        audit = upload_workspace_audit.UploadWorkspaceSharingAudit()
        audit.audit_workspace_and_group(self.upload_workspace, self.dcc_admin_group)
        self.assertEqual(len(audit.verified), 0)
        self.assertEqual(len(audit.needs_action), 1)
        self.assertEqual(len(audit.errors), 0)
        record = audit.needs_action[0]
        self.assertIsInstance(record, workspace_sharing_audit_results.ShareAsOwner)
        self.assertEqual(record.workspace, self.upload_workspace.workspace)
        self.assertEqual(record.managed_group, self.dcc_admin_group)
        self.assertEqual(record.current_sharing_instance, None)
        self.assertEqual(record.note, upload_workspace_audit.UploadWorkspaceSharingAudit.DCC_ADMIN_AS_OWNER)

    def test_dcc_admin_shared_as_writer_can_compute(self):
        sharing = WorkspaceGroupSharingFactory.create(
            workspace=self.upload_workspace.workspace,
            group=self.dcc_admin_group,
            access=WorkspaceGroupSharing.WRITER,
            can_compute=True,
        )
        audit = upload_workspace_audit.UploadWorkspaceSharingAudit()
        audit.audit_workspace_and_group(self.upload_workspace, self.dcc_admin_group)
        self.assertEqual(len(audit.verified), 0)
        self.assertEqual(len(audit.needs_action), 1)
        self.assertEqual(len(audit.errors), 0)
        record = audit.needs_action[0]
        self.assertIsInstance(record, workspace_sharing_audit_results.ShareAsOwner)
        self.assertEqual(record.workspace, self.upload_workspace.workspace)
        self.assertEqual(record.managed_group, self.dcc_admin_group)
        self.assertEqual(record.current_sharing_instance, sharing)
        self.assertEqual(record.note, upload_workspace_audit.UploadWorkspaceSharingAudit.DCC_ADMIN_AS_OWNER)

    def test_dcc_admin_shared_as_reader(self):
        sharing = WorkspaceGroupSharingFactory.create(
            workspace=self.upload_workspace.workspace, group=self.dcc_admin_group, access=WorkspaceGroupSharing.READER
        )
        audit = upload_workspace_audit.UploadWorkspaceSharingAudit()
        audit.audit_workspace_and_group(self.upload_workspace, self.dcc_admin_group)
        self.assertEqual(len(audit.verified), 0)
        self.assertEqual(len(audit.needs_action), 1)
        self.assertEqual(len(audit.errors), 0)
        record = audit.needs_action[0]
        self.assertIsInstance(record, workspace_sharing_audit_results.ShareAsOwner)
        self.assertEqual(record.workspace, self.upload_workspace.workspace)
        self.assertEqual(record.managed_group, self.dcc_admin_group)
        self.assertEqual(record.current_sharing_instance, sharing)
        self.assertEqual(record.note, upload_workspace_audit.UploadWorkspaceSharingAudit.DCC_ADMIN_AS_OWNER)

    def test_dcc_admin_shared_as_owner(self):
        sharing = WorkspaceGroupSharingFactory.create(
            workspace=self.upload_workspace.workspace, group=self.dcc_admin_group, access=WorkspaceGroupSharing.OWNER
        )
        audit = upload_workspace_audit.UploadWorkspaceSharingAudit()
        audit.audit_workspace_and_group(self.upload_workspace, self.dcc_admin_group)
        self.assertEqual(len(audit.verified), 1)
        self.assertEqual(len(audit.needs_action), 0)
        self.assertEqual(len(audit.errors), 0)
        record = audit.verified[0]
        self.assertIsInstance(record, workspace_sharing_audit_results.VerifiedShared)
        self.assertEqual(record.workspace, self.upload_workspace.workspace)
        self.assertEqual(record.managed_group, self.dcc_admin_group)
        self.assertEqual(record.current_sharing_instance, sharing)
        self.assertEqual(record.note, upload_workspace_audit.UploadWorkspaceSharingAudit.DCC_ADMIN_AS_OWNER)

    @override_settings(ANVIL_DCC_ADMINS_GROUP_NAME="foo")
    def test_dcc_admin_different_setting(self):
        group = ManagedGroupFactory.create(name="foo")
        sharing = WorkspaceGroupSharingFactory.create(
            workspace=self.upload_workspace.workspace, group=group, access=WorkspaceGroupSharing.OWNER
        )
        audit = upload_workspace_audit.UploadWorkspaceSharingAudit()
        audit.audit_workspace_and_group(self.upload_workspace, group)
        self.assertEqual(len(audit.verified), 1)
        self.assertEqual(len(audit.needs_action), 0)
        self.assertEqual(len(audit.errors), 0)
        record = audit.verified[0]
        self.assertIsInstance(record, workspace_sharing_audit_results.VerifiedShared)
        self.assertEqual(record.workspace, self.upload_workspace.workspace)
        self.assertEqual(record.managed_group, group)
        self.assertEqual(record.current_sharing_instance, sharing)
        self.assertEqual(record.note, upload_workspace_audit.UploadWorkspaceSharingAudit.DCC_ADMIN_AS_OWNER)

    def test_anvil_admins_shared_as_writer_no_compute(self):
        # Share the workspace with the group.
        WorkspaceGroupSharingFactory.create(
            workspace=self.upload_workspace.workspace, group=self.anvil_admins, access=WorkspaceGroupSharing.WRITER
        )
        audit = upload_workspace_audit.UploadWorkspaceSharingAudit()
        audit.audit_workspace_and_group(self.upload_workspace, self.anvil_admins)
        self.assertEqual(len(audit.verified), 0)
        self.assertEqual(len(audit.needs_action), 0)
        self.assertEqual(len(audit.errors), 0)

    def test_anvil_admins_not_shared(self):
        audit = upload_workspace_audit.UploadWorkspaceSharingAudit()
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
        audit = upload_workspace_audit.UploadWorkspaceSharingAudit()
        audit.audit_workspace_and_group(self.upload_workspace, self.anvil_admins)
        self.assertEqual(len(audit.verified), 0)
        self.assertEqual(len(audit.needs_action), 0)
        self.assertEqual(len(audit.errors), 0)

    def test_anvil_admins_shared_as_reader(self):
        WorkspaceGroupSharingFactory.create(
            workspace=self.upload_workspace.workspace, group=self.anvil_admins, access=WorkspaceGroupSharing.READER
        )
        audit = upload_workspace_audit.UploadWorkspaceSharingAudit()
        audit.audit_workspace_and_group(self.upload_workspace, self.anvil_admins)
        self.assertEqual(len(audit.verified), 0)
        self.assertEqual(len(audit.needs_action), 0)
        self.assertEqual(len(audit.errors), 0)

    def test_anvil_admins_shared_as_owner(self):
        WorkspaceGroupSharingFactory.create(
            workspace=self.upload_workspace.workspace, group=self.anvil_admins, access=WorkspaceGroupSharing.OWNER
        )
        audit = upload_workspace_audit.UploadWorkspaceSharingAudit()
        audit.audit_workspace_and_group(self.upload_workspace, self.anvil_admins)
        self.assertEqual(len(audit.verified), 0)
        self.assertEqual(len(audit.needs_action), 0)
        self.assertEqual(len(audit.errors), 0)

    def test_anvil_devs_shared_as_writer_no_compute(self):
        # Share the workspace with the group.
        WorkspaceGroupSharingFactory.create(
            workspace=self.upload_workspace.workspace, group=self.anvil_devs, access=WorkspaceGroupSharing.WRITER
        )
        audit = upload_workspace_audit.UploadWorkspaceSharingAudit()
        audit.audit_workspace_and_group(self.upload_workspace, self.anvil_devs)
        self.assertEqual(len(audit.verified), 0)
        self.assertEqual(len(audit.needs_action), 0)
        self.assertEqual(len(audit.errors), 0)

    def test_anvil_devs_not_shared(self):
        audit = upload_workspace_audit.UploadWorkspaceSharingAudit()
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
        audit = upload_workspace_audit.UploadWorkspaceSharingAudit()
        audit.audit_workspace_and_group(self.upload_workspace, self.anvil_devs)
        self.assertEqual(len(audit.verified), 0)
        self.assertEqual(len(audit.needs_action), 0)
        self.assertEqual(len(audit.errors), 0)

    def test_anvil_devs_shared_as_reader(self):
        WorkspaceGroupSharingFactory.create(
            workspace=self.upload_workspace.workspace, group=self.anvil_devs, access=WorkspaceGroupSharing.READER
        )
        audit = upload_workspace_audit.UploadWorkspaceSharingAudit()
        audit.audit_workspace_and_group(self.upload_workspace, self.anvil_devs)
        self.assertEqual(len(audit.verified), 0)
        self.assertEqual(len(audit.needs_action), 0)
        self.assertEqual(len(audit.errors), 0)

    def test_anvil_devs_shared_as_owner(self):
        WorkspaceGroupSharingFactory.create(
            workspace=self.upload_workspace.workspace, group=self.anvil_devs, access=WorkspaceGroupSharing.OWNER
        )
        audit = upload_workspace_audit.UploadWorkspaceSharingAudit()
        audit.audit_workspace_and_group(self.upload_workspace, self.anvil_devs)
        self.assertEqual(len(audit.verified), 0)
        self.assertEqual(len(audit.needs_action), 0)
        self.assertEqual(len(audit.errors), 0)

    def test_other_group_shared_as_writer_no_compute(self):
        # Share the workspace with the group.
        sharing = WorkspaceGroupSharingFactory.create(
            workspace=self.upload_workspace.workspace, group=self.other_group, access=WorkspaceGroupSharing.WRITER
        )
        audit = upload_workspace_audit.UploadWorkspaceSharingAudit()
        audit.audit_workspace_and_group(self.upload_workspace, self.other_group)
        self.assertEqual(len(audit.verified), 0)
        self.assertEqual(len(audit.needs_action), 0)
        self.assertEqual(len(audit.errors), 1)
        record = audit.errors[0]
        self.assertIsInstance(record, workspace_sharing_audit_results.StopSharing)
        self.assertEqual(record.workspace, self.upload_workspace.workspace)
        self.assertEqual(record.managed_group, self.other_group)
        self.assertEqual(record.current_sharing_instance, sharing)
        self.assertEqual(record.note, upload_workspace_audit.UploadWorkspaceSharingAudit.OTHER_GROUP_NO_ACCESS)

    def test_other_group_not_shared(self):
        audit = upload_workspace_audit.UploadWorkspaceSharingAudit()
        audit.audit_workspace_and_group(self.upload_workspace, self.other_group)
        self.assertEqual(len(audit.verified), 1)
        self.assertEqual(len(audit.needs_action), 0)
        self.assertEqual(len(audit.errors), 0)
        record = audit.verified[0]
        self.assertIsInstance(record, workspace_sharing_audit_results.VerifiedNotShared)
        self.assertEqual(record.workspace, self.upload_workspace.workspace)
        self.assertEqual(record.managed_group, self.other_group)
        self.assertEqual(record.current_sharing_instance, None)
        self.assertEqual(record.note, upload_workspace_audit.UploadWorkspaceSharingAudit.OTHER_GROUP_NO_ACCESS)

    def test_other_group_shared_as_writer_can_compute(self):
        sharing = WorkspaceGroupSharingFactory.create(
            workspace=self.upload_workspace.workspace,
            group=self.other_group,
            access=WorkspaceGroupSharing.WRITER,
            can_compute=True,
        )
        audit = upload_workspace_audit.UploadWorkspaceSharingAudit()
        audit.audit_workspace_and_group(self.upload_workspace, self.other_group)
        self.assertEqual(len(audit.verified), 0)
        self.assertEqual(len(audit.needs_action), 0)
        self.assertEqual(len(audit.errors), 1)
        record = audit.errors[0]
        self.assertIsInstance(record, workspace_sharing_audit_results.StopSharing)
        self.assertEqual(record.workspace, self.upload_workspace.workspace)
        self.assertEqual(record.managed_group, self.other_group)
        self.assertEqual(record.current_sharing_instance, sharing)
        self.assertEqual(record.note, upload_workspace_audit.UploadWorkspaceSharingAudit.OTHER_GROUP_NO_ACCESS)

    def test_other_group_shared_as_reader(self):
        sharing = WorkspaceGroupSharingFactory.create(
            workspace=self.upload_workspace.workspace, group=self.other_group, access=WorkspaceGroupSharing.READER
        )
        audit = upload_workspace_audit.UploadWorkspaceSharingAudit()
        audit.audit_workspace_and_group(self.upload_workspace, self.other_group)
        self.assertEqual(len(audit.verified), 0)
        self.assertEqual(len(audit.needs_action), 0)
        self.assertEqual(len(audit.errors), 1)
        record = audit.errors[0]
        self.assertIsInstance(record, workspace_sharing_audit_results.StopSharing)
        self.assertEqual(record.workspace, self.upload_workspace.workspace)
        self.assertEqual(record.managed_group, self.other_group)
        self.assertEqual(record.current_sharing_instance, sharing)
        self.assertEqual(record.note, upload_workspace_audit.UploadWorkspaceSharingAudit.OTHER_GROUP_NO_ACCESS)

    def test_other_group_shared_as_owner(self):
        sharing = WorkspaceGroupSharingFactory.create(
            workspace=self.upload_workspace.workspace, group=self.other_group, access=WorkspaceGroupSharing.OWNER
        )
        audit = upload_workspace_audit.UploadWorkspaceSharingAudit()
        audit.audit_workspace_and_group(self.upload_workspace, self.other_group)
        self.assertEqual(len(audit.verified), 0)
        self.assertEqual(len(audit.needs_action), 0)
        self.assertEqual(len(audit.errors), 1)
        record = audit.errors[0]
        self.assertIsInstance(record, workspace_sharing_audit_results.StopSharing)
        self.assertEqual(record.workspace, self.upload_workspace.workspace)
        self.assertEqual(record.managed_group, self.other_group)
        self.assertEqual(record.current_sharing_instance, sharing)
        self.assertEqual(record.note, upload_workspace_audit.UploadWorkspaceSharingAudit.OTHER_GROUP_NO_ACCESS)


class UploadWorkspaceSharingAuditCurrentCycleBeforeComputeTest(TestCase):
    """Tests for the `UploadWorkspaceSharingAudit` class for current cycle UploadWorkspaces before compute is enabled.

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
        audit = upload_workspace_audit.UploadWorkspaceSharingAudit()
        audit.audit_workspace_and_group(self.upload_workspace, self.rc_uploader_group)
        self.assertEqual(len(audit.verified), 1)
        self.assertEqual(len(audit.needs_action), 0)
        self.assertEqual(len(audit.errors), 0)
        record = audit.verified[0]
        self.assertIsInstance(record, workspace_sharing_audit_results.VerifiedShared)
        self.assertEqual(record.workspace, self.upload_workspace.workspace)
        self.assertEqual(record.managed_group, self.rc_uploader_group)
        self.assertEqual(record.current_sharing_instance, sharing)
        self.assertEqual(
            record.note,
            upload_workspace_audit.UploadWorkspaceSharingAudit.RC_UPLOADERS_CURRENT_CYCLE_BEFORE_COMPUTE,
        )

    def test_uploaders_not_shared(self):
        audit = upload_workspace_audit.UploadWorkspaceSharingAudit()
        audit.audit_workspace_and_group(self.upload_workspace, self.rc_uploader_group)
        self.assertEqual(len(audit.verified), 0)
        self.assertEqual(len(audit.needs_action), 1)
        self.assertEqual(len(audit.errors), 0)
        record = audit.needs_action[0]
        self.assertIsInstance(record, workspace_sharing_audit_results.ShareAsWriter)
        self.assertEqual(record.workspace, self.upload_workspace.workspace)
        self.assertEqual(record.managed_group, self.rc_uploader_group)
        self.assertEqual(record.current_sharing_instance, None)
        self.assertEqual(
            record.note,
            upload_workspace_audit.UploadWorkspaceSharingAudit.RC_UPLOADERS_CURRENT_CYCLE_BEFORE_COMPUTE,
        )

    def test_uploaders_shared_as_writer_can_compute(self):
        sharing = WorkspaceGroupSharingFactory.create(
            workspace=self.upload_workspace.workspace,
            group=self.rc_uploader_group,
            access=WorkspaceGroupSharing.WRITER,
            can_compute=True,
        )
        audit = upload_workspace_audit.UploadWorkspaceSharingAudit()
        audit.audit_workspace_and_group(self.upload_workspace, self.rc_uploader_group)
        self.assertEqual(len(audit.verified), 0)
        self.assertEqual(len(audit.needs_action), 1)
        self.assertEqual(len(audit.errors), 0)
        record = audit.needs_action[0]
        self.assertIsInstance(record, workspace_sharing_audit_results.ShareAsWriter)
        self.assertEqual(record.workspace, self.upload_workspace.workspace)
        self.assertEqual(record.managed_group, self.rc_uploader_group)
        self.assertEqual(record.current_sharing_instance, sharing)
        self.assertEqual(
            record.note,
            upload_workspace_audit.UploadWorkspaceSharingAudit.RC_UPLOADERS_CURRENT_CYCLE_BEFORE_COMPUTE,
        )

    def test_uploaders_shared_as_reader(self):
        sharing = WorkspaceGroupSharingFactory.create(
            workspace=self.upload_workspace.workspace, group=self.rc_uploader_group, access=WorkspaceGroupSharing.READER
        )
        audit = upload_workspace_audit.UploadWorkspaceSharingAudit()
        audit.audit_workspace_and_group(self.upload_workspace, self.rc_uploader_group)
        self.assertEqual(len(audit.verified), 0)
        self.assertEqual(len(audit.needs_action), 1)
        self.assertEqual(len(audit.errors), 0)
        record = audit.needs_action[0]
        self.assertIsInstance(record, workspace_sharing_audit_results.ShareAsWriter)
        self.assertEqual(record.workspace, self.upload_workspace.workspace)
        self.assertEqual(record.managed_group, self.rc_uploader_group)
        self.assertEqual(record.current_sharing_instance, sharing)
        self.assertEqual(
            record.note,
            upload_workspace_audit.UploadWorkspaceSharingAudit.RC_UPLOADERS_CURRENT_CYCLE_BEFORE_COMPUTE,
        )

    def test_uploaders_shared_as_owner(self):
        sharing = WorkspaceGroupSharingFactory.create(
            workspace=self.upload_workspace.workspace, group=self.rc_uploader_group, access=WorkspaceGroupSharing.OWNER
        )
        audit = upload_workspace_audit.UploadWorkspaceSharingAudit()
        audit.audit_workspace_and_group(self.upload_workspace, self.rc_uploader_group)
        self.assertEqual(len(audit.verified), 0)
        self.assertEqual(len(audit.needs_action), 0)
        self.assertEqual(len(audit.errors), 1)
        record = audit.errors[0]
        self.assertIsInstance(record, workspace_sharing_audit_results.ShareAsWriter)
        self.assertEqual(record.workspace, self.upload_workspace.workspace)
        self.assertEqual(record.managed_group, self.rc_uploader_group)
        self.assertEqual(record.current_sharing_instance, sharing)
        self.assertEqual(
            record.note,
            upload_workspace_audit.UploadWorkspaceSharingAudit.RC_UPLOADERS_CURRENT_CYCLE_BEFORE_COMPUTE,
        )

    def test_dcc_writers_shared_as_writer_no_compute(self):
        # Share the workspace with the group.
        sharing = WorkspaceGroupSharingFactory.create(
            workspace=self.upload_workspace.workspace, group=self.dcc_writer_group, access=WorkspaceGroupSharing.WRITER
        )
        audit = upload_workspace_audit.UploadWorkspaceSharingAudit()
        audit.audit_workspace_and_group(self.upload_workspace, self.dcc_writer_group)
        self.assertEqual(len(audit.verified), 0)
        self.assertEqual(len(audit.needs_action), 1)
        self.assertEqual(len(audit.errors), 0)
        record = audit.needs_action[0]
        self.assertIsInstance(record, workspace_sharing_audit_results.ShareWithCompute)
        self.assertEqual(record.workspace, self.upload_workspace.workspace)
        self.assertEqual(record.managed_group, self.dcc_writer_group)
        self.assertEqual(record.current_sharing_instance, sharing)
        self.assertEqual(record.note, upload_workspace_audit.UploadWorkspaceSharingAudit.DCC_WRITERS_CURRENT_CYCLE)

    def test_dcc_writers_not_shared(self):
        audit = upload_workspace_audit.UploadWorkspaceSharingAudit()
        audit.audit_workspace_and_group(self.upload_workspace, self.dcc_writer_group)
        self.assertEqual(len(audit.verified), 0)
        self.assertEqual(len(audit.needs_action), 1)
        self.assertEqual(len(audit.errors), 0)
        record = audit.needs_action[0]
        self.assertIsInstance(record, workspace_sharing_audit_results.ShareWithCompute)
        self.assertEqual(record.workspace, self.upload_workspace.workspace)
        self.assertEqual(record.managed_group, self.dcc_writer_group)
        self.assertEqual(record.current_sharing_instance, None)
        self.assertEqual(record.note, upload_workspace_audit.UploadWorkspaceSharingAudit.DCC_WRITERS_CURRENT_CYCLE)

    def test_dcc_writers_shared_as_writer_can_compute(self):
        sharing = WorkspaceGroupSharingFactory.create(
            workspace=self.upload_workspace.workspace,
            group=self.dcc_writer_group,
            access=WorkspaceGroupSharing.WRITER,
            can_compute=True,
        )
        audit = upload_workspace_audit.UploadWorkspaceSharingAudit()
        audit.audit_workspace_and_group(self.upload_workspace, self.dcc_writer_group)
        self.assertEqual(len(audit.verified), 1)
        self.assertEqual(len(audit.needs_action), 0)
        self.assertEqual(len(audit.errors), 0)
        record = audit.verified[0]
        self.assertIsInstance(record, workspace_sharing_audit_results.VerifiedShared)
        self.assertEqual(record.workspace, self.upload_workspace.workspace)
        self.assertEqual(record.managed_group, self.dcc_writer_group)
        self.assertEqual(record.current_sharing_instance, sharing)
        self.assertEqual(record.note, upload_workspace_audit.UploadWorkspaceSharingAudit.DCC_WRITERS_CURRENT_CYCLE)

    def test_dcc_writers_shared_as_reader(self):
        sharing = WorkspaceGroupSharingFactory.create(
            workspace=self.upload_workspace.workspace, group=self.dcc_writer_group, access=WorkspaceGroupSharing.READER
        )
        audit = upload_workspace_audit.UploadWorkspaceSharingAudit()
        audit.audit_workspace_and_group(self.upload_workspace, self.dcc_writer_group)
        self.assertEqual(len(audit.verified), 0)
        self.assertEqual(len(audit.needs_action), 1)
        self.assertEqual(len(audit.errors), 0)
        record = audit.needs_action[0]
        self.assertIsInstance(record, workspace_sharing_audit_results.ShareWithCompute)
        self.assertEqual(record.workspace, self.upload_workspace.workspace)
        self.assertEqual(record.managed_group, self.dcc_writer_group)
        self.assertEqual(record.current_sharing_instance, sharing)
        self.assertEqual(record.note, upload_workspace_audit.UploadWorkspaceSharingAudit.DCC_WRITERS_CURRENT_CYCLE)

    def test_dcc_writers_shared_as_owner(self):
        sharing = WorkspaceGroupSharingFactory.create(
            workspace=self.upload_workspace.workspace, group=self.dcc_writer_group, access=WorkspaceGroupSharing.OWNER
        )
        audit = upload_workspace_audit.UploadWorkspaceSharingAudit()
        audit.audit_workspace_and_group(self.upload_workspace, self.dcc_writer_group)
        self.assertEqual(len(audit.verified), 0)
        self.assertEqual(len(audit.needs_action), 0)
        self.assertEqual(len(audit.errors), 1)
        record = audit.errors[0]
        self.assertIsInstance(record, workspace_sharing_audit_results.ShareWithCompute)
        self.assertEqual(record.workspace, self.upload_workspace.workspace)
        self.assertEqual(record.managed_group, self.dcc_writer_group)
        self.assertEqual(record.current_sharing_instance, sharing)
        self.assertEqual(record.note, upload_workspace_audit.UploadWorkspaceSharingAudit.DCC_WRITERS_CURRENT_CYCLE)

    def test_auth_domain_shared_as_writer_no_compute(self):
        # Share the workspace with the group.
        sharing = WorkspaceGroupSharingFactory.create(
            workspace=self.upload_workspace.workspace, group=self.auth_domain, access=WorkspaceGroupSharing.WRITER
        )
        audit = upload_workspace_audit.UploadWorkspaceSharingAudit()
        audit.audit_workspace_and_group(self.upload_workspace, self.auth_domain)
        self.assertEqual(len(audit.verified), 0)
        self.assertEqual(len(audit.needs_action), 1)
        self.assertEqual(len(audit.errors), 0)
        record = audit.needs_action[0]
        self.assertIsInstance(record, workspace_sharing_audit_results.ShareAsReader)
        self.assertEqual(record.workspace, self.upload_workspace.workspace)
        self.assertEqual(record.managed_group, self.auth_domain)
        self.assertEqual(record.current_sharing_instance, sharing)
        self.assertEqual(record.note, upload_workspace_audit.UploadWorkspaceSharingAudit.AUTH_DOMAIN_AS_READER)

    def test_auth_domain_not_shared(self):
        audit = upload_workspace_audit.UploadWorkspaceSharingAudit()
        audit.audit_workspace_and_group(self.upload_workspace, self.auth_domain)
        self.assertEqual(len(audit.verified), 0)
        self.assertEqual(len(audit.needs_action), 1)
        self.assertEqual(len(audit.errors), 0)
        record = audit.needs_action[0]
        self.assertIsInstance(record, workspace_sharing_audit_results.ShareAsReader)
        self.assertEqual(record.workspace, self.upload_workspace.workspace)
        self.assertEqual(record.managed_group, self.auth_domain)
        self.assertEqual(record.current_sharing_instance, None)
        self.assertEqual(record.note, upload_workspace_audit.UploadWorkspaceSharingAudit.AUTH_DOMAIN_AS_READER)

    def test_auth_domain_shared_as_writer_can_compute(self):
        sharing = WorkspaceGroupSharingFactory.create(
            workspace=self.upload_workspace.workspace,
            group=self.auth_domain,
            access=WorkspaceGroupSharing.WRITER,
            can_compute=True,
        )
        audit = upload_workspace_audit.UploadWorkspaceSharingAudit()
        audit.audit_workspace_and_group(self.upload_workspace, self.auth_domain)
        self.assertEqual(len(audit.verified), 0)
        self.assertEqual(len(audit.needs_action), 1)
        self.assertEqual(len(audit.errors), 0)
        record = audit.needs_action[0]
        self.assertIsInstance(record, workspace_sharing_audit_results.ShareAsReader)
        self.assertEqual(record.workspace, self.upload_workspace.workspace)
        self.assertEqual(record.managed_group, self.auth_domain)
        self.assertEqual(record.current_sharing_instance, sharing)
        self.assertEqual(record.note, upload_workspace_audit.UploadWorkspaceSharingAudit.AUTH_DOMAIN_AS_READER)

    def test_auth_domain_shared_as_reader(self):
        sharing = WorkspaceGroupSharingFactory.create(
            workspace=self.upload_workspace.workspace, group=self.auth_domain, access=WorkspaceGroupSharing.READER
        )
        audit = upload_workspace_audit.UploadWorkspaceSharingAudit()
        audit.audit_workspace_and_group(self.upload_workspace, self.auth_domain)
        self.assertEqual(len(audit.verified), 1)
        self.assertEqual(len(audit.needs_action), 0)
        self.assertEqual(len(audit.errors), 0)
        record = audit.verified[0]
        self.assertIsInstance(record, workspace_sharing_audit_results.VerifiedShared)
        self.assertEqual(record.workspace, self.upload_workspace.workspace)
        self.assertEqual(record.managed_group, self.auth_domain)
        self.assertEqual(record.current_sharing_instance, sharing)
        self.assertEqual(record.note, upload_workspace_audit.UploadWorkspaceSharingAudit.AUTH_DOMAIN_AS_READER)

    def test_auth_domain_shared_as_owner(self):
        sharing = WorkspaceGroupSharingFactory.create(
            workspace=self.upload_workspace.workspace, group=self.auth_domain, access=WorkspaceGroupSharing.OWNER
        )
        audit = upload_workspace_audit.UploadWorkspaceSharingAudit()
        audit.audit_workspace_and_group(self.upload_workspace, self.auth_domain)
        self.assertEqual(len(audit.verified), 0)
        self.assertEqual(len(audit.needs_action), 0)
        self.assertEqual(len(audit.errors), 1)
        record = audit.errors[0]
        self.assertIsInstance(record, workspace_sharing_audit_results.ShareAsReader)
        self.assertEqual(record.workspace, self.upload_workspace.workspace)
        self.assertEqual(record.managed_group, self.auth_domain)
        self.assertEqual(record.current_sharing_instance, sharing)
        self.assertEqual(record.note, upload_workspace_audit.UploadWorkspaceSharingAudit.AUTH_DOMAIN_AS_READER)

    def test_dcc_admin_shared_as_writer_no_compute(self):
        # Share the workspace with the group.
        sharing = WorkspaceGroupSharingFactory.create(
            workspace=self.upload_workspace.workspace, group=self.dcc_admin_group, access=WorkspaceGroupSharing.WRITER
        )
        audit = upload_workspace_audit.UploadWorkspaceSharingAudit()
        audit.audit_workspace_and_group(self.upload_workspace, self.dcc_admin_group)
        self.assertEqual(len(audit.verified), 0)
        self.assertEqual(len(audit.needs_action), 1)
        self.assertEqual(len(audit.errors), 0)
        record = audit.needs_action[0]
        self.assertIsInstance(record, workspace_sharing_audit_results.ShareAsOwner)
        self.assertEqual(record.workspace, self.upload_workspace.workspace)
        self.assertEqual(record.managed_group, self.dcc_admin_group)
        self.assertEqual(record.current_sharing_instance, sharing)
        self.assertEqual(record.note, upload_workspace_audit.UploadWorkspaceSharingAudit.DCC_ADMIN_AS_OWNER)

    def test_dcc_admin_not_shared(self):
        audit = upload_workspace_audit.UploadWorkspaceSharingAudit()
        audit.audit_workspace_and_group(self.upload_workspace, self.dcc_admin_group)
        self.assertEqual(len(audit.verified), 0)
        self.assertEqual(len(audit.needs_action), 1)
        self.assertEqual(len(audit.errors), 0)
        record = audit.needs_action[0]
        self.assertIsInstance(record, workspace_sharing_audit_results.ShareAsOwner)
        self.assertEqual(record.workspace, self.upload_workspace.workspace)
        self.assertEqual(record.managed_group, self.dcc_admin_group)
        self.assertEqual(record.current_sharing_instance, None)
        self.assertEqual(record.note, upload_workspace_audit.UploadWorkspaceSharingAudit.DCC_ADMIN_AS_OWNER)

    def test_dcc_admin_shared_as_writer_can_compute(self):
        sharing = WorkspaceGroupSharingFactory.create(
            workspace=self.upload_workspace.workspace,
            group=self.dcc_admin_group,
            access=WorkspaceGroupSharing.WRITER,
            can_compute=True,
        )
        audit = upload_workspace_audit.UploadWorkspaceSharingAudit()
        audit.audit_workspace_and_group(self.upload_workspace, self.dcc_admin_group)
        self.assertEqual(len(audit.verified), 0)
        self.assertEqual(len(audit.needs_action), 1)
        self.assertEqual(len(audit.errors), 0)
        record = audit.needs_action[0]
        self.assertIsInstance(record, workspace_sharing_audit_results.ShareAsOwner)
        self.assertEqual(record.workspace, self.upload_workspace.workspace)
        self.assertEqual(record.managed_group, self.dcc_admin_group)
        self.assertEqual(record.current_sharing_instance, sharing)
        self.assertEqual(record.note, upload_workspace_audit.UploadWorkspaceSharingAudit.DCC_ADMIN_AS_OWNER)

    def test_dcc_admin_shared_as_reader(self):
        sharing = WorkspaceGroupSharingFactory.create(
            workspace=self.upload_workspace.workspace, group=self.dcc_admin_group, access=WorkspaceGroupSharing.READER
        )
        audit = upload_workspace_audit.UploadWorkspaceSharingAudit()
        audit.audit_workspace_and_group(self.upload_workspace, self.dcc_admin_group)
        self.assertEqual(len(audit.verified), 0)
        self.assertEqual(len(audit.needs_action), 1)
        self.assertEqual(len(audit.errors), 0)
        record = audit.needs_action[0]
        self.assertIsInstance(record, workspace_sharing_audit_results.ShareAsOwner)
        self.assertEqual(record.workspace, self.upload_workspace.workspace)
        self.assertEqual(record.managed_group, self.dcc_admin_group)
        self.assertEqual(record.current_sharing_instance, sharing)
        self.assertEqual(record.note, upload_workspace_audit.UploadWorkspaceSharingAudit.DCC_ADMIN_AS_OWNER)

    def test_dcc_admin_shared_as_owner(self):
        sharing = WorkspaceGroupSharingFactory.create(
            workspace=self.upload_workspace.workspace, group=self.dcc_admin_group, access=WorkspaceGroupSharing.OWNER
        )
        audit = upload_workspace_audit.UploadWorkspaceSharingAudit()
        audit.audit_workspace_and_group(self.upload_workspace, self.dcc_admin_group)
        self.assertEqual(len(audit.verified), 1)
        self.assertEqual(len(audit.needs_action), 0)
        self.assertEqual(len(audit.errors), 0)
        record = audit.verified[0]
        self.assertIsInstance(record, workspace_sharing_audit_results.VerifiedShared)
        self.assertEqual(record.workspace, self.upload_workspace.workspace)
        self.assertEqual(record.managed_group, self.dcc_admin_group)
        self.assertEqual(record.current_sharing_instance, sharing)
        self.assertEqual(record.note, upload_workspace_audit.UploadWorkspaceSharingAudit.DCC_ADMIN_AS_OWNER)

    @override_settings(ANVIL_DCC_ADMINS_GROUP_NAME="foo")
    def test_dcc_admin_different_setting(self):
        group = ManagedGroupFactory.create(name="foo")
        sharing = WorkspaceGroupSharingFactory.create(
            workspace=self.upload_workspace.workspace, group=group, access=WorkspaceGroupSharing.OWNER
        )
        audit = upload_workspace_audit.UploadWorkspaceSharingAudit()
        audit.audit_workspace_and_group(self.upload_workspace, group)
        self.assertEqual(len(audit.verified), 1)
        self.assertEqual(len(audit.needs_action), 0)
        self.assertEqual(len(audit.errors), 0)
        record = audit.verified[0]
        self.assertIsInstance(record, workspace_sharing_audit_results.VerifiedShared)
        self.assertEqual(record.workspace, self.upload_workspace.workspace)
        self.assertEqual(record.managed_group, group)
        self.assertEqual(record.current_sharing_instance, sharing)
        self.assertEqual(record.note, upload_workspace_audit.UploadWorkspaceSharingAudit.DCC_ADMIN_AS_OWNER)

    def test_anvil_admins_shared_as_writer_no_compute(self):
        # Share the workspace with the group.
        WorkspaceGroupSharingFactory.create(
            workspace=self.upload_workspace.workspace, group=self.anvil_admins, access=WorkspaceGroupSharing.WRITER
        )
        audit = upload_workspace_audit.UploadWorkspaceSharingAudit()
        audit.audit_workspace_and_group(self.upload_workspace, self.anvil_admins)
        self.assertEqual(len(audit.verified), 0)
        self.assertEqual(len(audit.needs_action), 0)
        self.assertEqual(len(audit.errors), 0)

    def test_anvil_admins_not_shared(self):
        audit = upload_workspace_audit.UploadWorkspaceSharingAudit()
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
        audit = upload_workspace_audit.UploadWorkspaceSharingAudit()
        audit.audit_workspace_and_group(self.upload_workspace, self.anvil_admins)
        self.assertEqual(len(audit.verified), 0)
        self.assertEqual(len(audit.needs_action), 0)
        self.assertEqual(len(audit.errors), 0)

    def test_anvil_admins_shared_as_reader(self):
        WorkspaceGroupSharingFactory.create(
            workspace=self.upload_workspace.workspace, group=self.anvil_admins, access=WorkspaceGroupSharing.READER
        )
        audit = upload_workspace_audit.UploadWorkspaceSharingAudit()
        audit.audit_workspace_and_group(self.upload_workspace, self.anvil_admins)
        self.assertEqual(len(audit.verified), 0)
        self.assertEqual(len(audit.needs_action), 0)
        self.assertEqual(len(audit.errors), 0)

    def test_anvil_admins_shared_as_owner(self):
        WorkspaceGroupSharingFactory.create(
            workspace=self.upload_workspace.workspace, group=self.anvil_admins, access=WorkspaceGroupSharing.OWNER
        )
        audit = upload_workspace_audit.UploadWorkspaceSharingAudit()
        audit.audit_workspace_and_group(self.upload_workspace, self.anvil_admins)
        self.assertEqual(len(audit.verified), 0)
        self.assertEqual(len(audit.needs_action), 0)
        self.assertEqual(len(audit.errors), 0)

    def test_anvil_devs_shared_as_writer_no_compute(self):
        # Share the workspace with the group.
        WorkspaceGroupSharingFactory.create(
            workspace=self.upload_workspace.workspace, group=self.anvil_devs, access=WorkspaceGroupSharing.WRITER
        )
        audit = upload_workspace_audit.UploadWorkspaceSharingAudit()
        audit.audit_workspace_and_group(self.upload_workspace, self.anvil_devs)
        self.assertEqual(len(audit.verified), 0)
        self.assertEqual(len(audit.needs_action), 0)
        self.assertEqual(len(audit.errors), 0)

    def test_anvil_devs_not_shared(self):
        audit = upload_workspace_audit.UploadWorkspaceSharingAudit()
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
        audit = upload_workspace_audit.UploadWorkspaceSharingAudit()
        audit.audit_workspace_and_group(self.upload_workspace, self.anvil_devs)
        self.assertEqual(len(audit.verified), 0)
        self.assertEqual(len(audit.needs_action), 0)
        self.assertEqual(len(audit.errors), 0)

    def test_anvil_devs_shared_as_reader(self):
        WorkspaceGroupSharingFactory.create(
            workspace=self.upload_workspace.workspace, group=self.anvil_devs, access=WorkspaceGroupSharing.READER
        )
        audit = upload_workspace_audit.UploadWorkspaceSharingAudit()
        audit.audit_workspace_and_group(self.upload_workspace, self.anvil_devs)
        self.assertEqual(len(audit.verified), 0)
        self.assertEqual(len(audit.needs_action), 0)
        self.assertEqual(len(audit.errors), 0)

    def test_anvil_devs_shared_as_owner(self):
        WorkspaceGroupSharingFactory.create(
            workspace=self.upload_workspace.workspace, group=self.anvil_devs, access=WorkspaceGroupSharing.OWNER
        )
        audit = upload_workspace_audit.UploadWorkspaceSharingAudit()
        audit.audit_workspace_and_group(self.upload_workspace, self.anvil_devs)
        self.assertEqual(len(audit.verified), 0)
        self.assertEqual(len(audit.needs_action), 0)
        self.assertEqual(len(audit.errors), 0)

    def test_other_group_shared_as_writer_no_compute(self):
        # Share the workspace with the group.
        sharing = WorkspaceGroupSharingFactory.create(
            workspace=self.upload_workspace.workspace, group=self.other_group, access=WorkspaceGroupSharing.WRITER
        )
        audit = upload_workspace_audit.UploadWorkspaceSharingAudit()
        audit.audit_workspace_and_group(self.upload_workspace, self.other_group)
        self.assertEqual(len(audit.verified), 0)
        self.assertEqual(len(audit.needs_action), 0)
        self.assertEqual(len(audit.errors), 1)
        record = audit.errors[0]
        self.assertIsInstance(record, workspace_sharing_audit_results.StopSharing)
        self.assertEqual(record.workspace, self.upload_workspace.workspace)
        self.assertEqual(record.managed_group, self.other_group)
        self.assertEqual(record.current_sharing_instance, sharing)
        self.assertEqual(record.note, upload_workspace_audit.UploadWorkspaceSharingAudit.OTHER_GROUP_NO_ACCESS)

    def test_other_group_not_shared(self):
        audit = upload_workspace_audit.UploadWorkspaceSharingAudit()
        audit.audit_workspace_and_group(self.upload_workspace, self.other_group)
        self.assertEqual(len(audit.verified), 1)
        self.assertEqual(len(audit.needs_action), 0)
        self.assertEqual(len(audit.errors), 0)
        record = audit.verified[0]
        self.assertIsInstance(record, workspace_sharing_audit_results.VerifiedNotShared)
        self.assertEqual(record.workspace, self.upload_workspace.workspace)
        self.assertEqual(record.managed_group, self.other_group)
        self.assertEqual(record.current_sharing_instance, None)
        self.assertEqual(record.note, upload_workspace_audit.UploadWorkspaceSharingAudit.OTHER_GROUP_NO_ACCESS)

    def test_other_group_shared_as_writer_can_compute(self):
        sharing = WorkspaceGroupSharingFactory.create(
            workspace=self.upload_workspace.workspace,
            group=self.other_group,
            access=WorkspaceGroupSharing.WRITER,
            can_compute=True,
        )
        audit = upload_workspace_audit.UploadWorkspaceSharingAudit()
        audit.audit_workspace_and_group(self.upload_workspace, self.other_group)
        self.assertEqual(len(audit.verified), 0)
        self.assertEqual(len(audit.needs_action), 0)
        self.assertEqual(len(audit.errors), 1)
        record = audit.errors[0]
        self.assertIsInstance(record, workspace_sharing_audit_results.StopSharing)
        self.assertEqual(record.workspace, self.upload_workspace.workspace)
        self.assertEqual(record.managed_group, self.other_group)
        self.assertEqual(record.current_sharing_instance, sharing)
        self.assertEqual(record.note, upload_workspace_audit.UploadWorkspaceSharingAudit.OTHER_GROUP_NO_ACCESS)

    def test_other_group_shared_as_reader(self):
        sharing = WorkspaceGroupSharingFactory.create(
            workspace=self.upload_workspace.workspace, group=self.other_group, access=WorkspaceGroupSharing.READER
        )
        audit = upload_workspace_audit.UploadWorkspaceSharingAudit()
        audit.audit_workspace_and_group(self.upload_workspace, self.other_group)
        self.assertEqual(len(audit.verified), 0)
        self.assertEqual(len(audit.needs_action), 0)
        self.assertEqual(len(audit.errors), 1)
        record = audit.errors[0]
        self.assertIsInstance(record, workspace_sharing_audit_results.StopSharing)
        self.assertEqual(record.workspace, self.upload_workspace.workspace)
        self.assertEqual(record.managed_group, self.other_group)
        self.assertEqual(record.current_sharing_instance, sharing)
        self.assertEqual(record.note, upload_workspace_audit.UploadWorkspaceSharingAudit.OTHER_GROUP_NO_ACCESS)

    def test_other_group_shared_as_owner(self):
        sharing = WorkspaceGroupSharingFactory.create(
            workspace=self.upload_workspace.workspace, group=self.other_group, access=WorkspaceGroupSharing.OWNER
        )
        audit = upload_workspace_audit.UploadWorkspaceSharingAudit()
        audit.audit_workspace_and_group(self.upload_workspace, self.other_group)
        self.assertEqual(len(audit.verified), 0)
        self.assertEqual(len(audit.needs_action), 0)
        self.assertEqual(len(audit.errors), 1)
        record = audit.errors[0]
        self.assertIsInstance(record, workspace_sharing_audit_results.StopSharing)
        self.assertEqual(record.workspace, self.upload_workspace.workspace)
        self.assertEqual(record.managed_group, self.other_group)
        self.assertEqual(record.current_sharing_instance, sharing)
        self.assertEqual(record.note, upload_workspace_audit.UploadWorkspaceSharingAudit.OTHER_GROUP_NO_ACCESS)


class UploadWorkspaceSharingAuditCurrentCycleAfterComputeTest(TestCase):
    """Tests for the `UploadWorkspaceSharingAudit` class for current cycle UploadWorkspaces after compute is enabled.

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
        audit = upload_workspace_audit.UploadWorkspaceSharingAudit()
        audit.audit_workspace_and_group(self.upload_workspace, self.rc_uploader_group)
        self.assertEqual(len(audit.verified), 0)
        self.assertEqual(len(audit.needs_action), 1)
        self.assertEqual(len(audit.errors), 0)
        record = audit.needs_action[0]
        self.assertIsInstance(record, workspace_sharing_audit_results.ShareWithCompute)
        self.assertEqual(record.workspace, self.upload_workspace.workspace)
        self.assertEqual(record.managed_group, self.rc_uploader_group)
        self.assertEqual(record.current_sharing_instance, sharing)
        self.assertEqual(
            record.note,
            upload_workspace_audit.UploadWorkspaceSharingAudit.RC_UPLOADERS_CURRENT_CYCLE_AFTER_COMPUTE,
        )

    def test_uploaders_not_shared(self):
        audit = upload_workspace_audit.UploadWorkspaceSharingAudit()
        audit.audit_workspace_and_group(self.upload_workspace, self.rc_uploader_group)
        self.assertEqual(len(audit.verified), 0)
        self.assertEqual(len(audit.needs_action), 1)
        self.assertEqual(len(audit.errors), 0)
        record = audit.needs_action[0]
        self.assertIsInstance(record, workspace_sharing_audit_results.ShareWithCompute)
        self.assertEqual(record.workspace, self.upload_workspace.workspace)
        self.assertEqual(record.managed_group, self.rc_uploader_group)
        self.assertEqual(record.current_sharing_instance, None)
        self.assertEqual(
            record.note,
            upload_workspace_audit.UploadWorkspaceSharingAudit.RC_UPLOADERS_CURRENT_CYCLE_AFTER_COMPUTE,
        )

    def test_uploaders_shared_as_writer_can_compute(self):
        sharing = WorkspaceGroupSharingFactory.create(
            workspace=self.upload_workspace.workspace,
            group=self.rc_uploader_group,
            access=WorkspaceGroupSharing.WRITER,
            can_compute=True,
        )
        audit = upload_workspace_audit.UploadWorkspaceSharingAudit()
        audit.audit_workspace_and_group(self.upload_workspace, self.rc_uploader_group)
        self.assertEqual(len(audit.verified), 1)
        self.assertEqual(len(audit.needs_action), 0)
        self.assertEqual(len(audit.errors), 0)
        record = audit.verified[0]
        self.assertIsInstance(record, workspace_sharing_audit_results.VerifiedShared)
        self.assertEqual(record.workspace, self.upload_workspace.workspace)
        self.assertEqual(record.managed_group, self.rc_uploader_group)
        self.assertEqual(record.current_sharing_instance, sharing)
        self.assertEqual(
            record.note,
            upload_workspace_audit.UploadWorkspaceSharingAudit.RC_UPLOADERS_CURRENT_CYCLE_AFTER_COMPUTE,
        )

    def test_uploaders_shared_as_reader(self):
        sharing = WorkspaceGroupSharingFactory.create(
            workspace=self.upload_workspace.workspace, group=self.rc_uploader_group, access=WorkspaceGroupSharing.READER
        )
        audit = upload_workspace_audit.UploadWorkspaceSharingAudit()
        audit.audit_workspace_and_group(self.upload_workspace, self.rc_uploader_group)
        self.assertEqual(len(audit.verified), 0)
        self.assertEqual(len(audit.needs_action), 1)
        self.assertEqual(len(audit.errors), 0)
        record = audit.needs_action[0]
        self.assertIsInstance(record, workspace_sharing_audit_results.ShareWithCompute)
        self.assertEqual(record.workspace, self.upload_workspace.workspace)
        self.assertEqual(record.managed_group, self.rc_uploader_group)
        self.assertEqual(record.current_sharing_instance, sharing)
        self.assertEqual(
            record.note,
            upload_workspace_audit.UploadWorkspaceSharingAudit.RC_UPLOADERS_CURRENT_CYCLE_AFTER_COMPUTE,
        )

    def test_uploaders_shared_as_owner(self):
        sharing = WorkspaceGroupSharingFactory.create(
            workspace=self.upload_workspace.workspace, group=self.rc_uploader_group, access=WorkspaceGroupSharing.OWNER
        )
        audit = upload_workspace_audit.UploadWorkspaceSharingAudit()
        audit.audit_workspace_and_group(self.upload_workspace, self.rc_uploader_group)
        self.assertEqual(len(audit.verified), 0)
        self.assertEqual(len(audit.needs_action), 0)
        self.assertEqual(len(audit.errors), 1)
        record = audit.errors[0]
        self.assertIsInstance(record, workspace_sharing_audit_results.ShareWithCompute)
        self.assertEqual(record.workspace, self.upload_workspace.workspace)
        self.assertEqual(record.managed_group, self.rc_uploader_group)
        self.assertEqual(record.current_sharing_instance, sharing)
        self.assertEqual(
            record.note,
            upload_workspace_audit.UploadWorkspaceSharingAudit.RC_UPLOADERS_CURRENT_CYCLE_AFTER_COMPUTE,
        )

    def test_dcc_writers_shared_as_writer_no_compute(self):
        # Share the workspace with the group.
        sharing = WorkspaceGroupSharingFactory.create(
            workspace=self.upload_workspace.workspace, group=self.dcc_writer_group, access=WorkspaceGroupSharing.WRITER
        )
        audit = upload_workspace_audit.UploadWorkspaceSharingAudit()
        audit.audit_workspace_and_group(self.upload_workspace, self.dcc_writer_group)
        self.assertEqual(len(audit.verified), 0)
        self.assertEqual(len(audit.needs_action), 1)
        self.assertEqual(len(audit.errors), 0)
        record = audit.needs_action[0]
        self.assertIsInstance(record, workspace_sharing_audit_results.ShareWithCompute)
        self.assertEqual(record.workspace, self.upload_workspace.workspace)
        self.assertEqual(record.managed_group, self.dcc_writer_group)
        self.assertEqual(record.current_sharing_instance, sharing)
        self.assertEqual(record.note, upload_workspace_audit.UploadWorkspaceSharingAudit.DCC_WRITERS_CURRENT_CYCLE)

    def test_dcc_writers_not_shared(self):
        audit = upload_workspace_audit.UploadWorkspaceSharingAudit()
        audit.audit_workspace_and_group(self.upload_workspace, self.dcc_writer_group)
        self.assertEqual(len(audit.verified), 0)
        self.assertEqual(len(audit.needs_action), 1)
        self.assertEqual(len(audit.errors), 0)
        record = audit.needs_action[0]
        self.assertIsInstance(record, workspace_sharing_audit_results.ShareWithCompute)
        self.assertEqual(record.workspace, self.upload_workspace.workspace)
        self.assertEqual(record.managed_group, self.dcc_writer_group)
        self.assertEqual(record.current_sharing_instance, None)
        self.assertEqual(record.note, upload_workspace_audit.UploadWorkspaceSharingAudit.DCC_WRITERS_CURRENT_CYCLE)

    def test_dcc_writers_shared_as_writer_can_compute(self):
        sharing = WorkspaceGroupSharingFactory.create(
            workspace=self.upload_workspace.workspace,
            group=self.dcc_writer_group,
            access=WorkspaceGroupSharing.WRITER,
            can_compute=True,
        )
        audit = upload_workspace_audit.UploadWorkspaceSharingAudit()
        audit.audit_workspace_and_group(self.upload_workspace, self.dcc_writer_group)
        self.assertEqual(len(audit.verified), 1)
        self.assertEqual(len(audit.needs_action), 0)
        self.assertEqual(len(audit.errors), 0)
        record = audit.verified[0]
        self.assertIsInstance(record, workspace_sharing_audit_results.VerifiedShared)
        self.assertEqual(record.workspace, self.upload_workspace.workspace)
        self.assertEqual(record.managed_group, self.dcc_writer_group)
        self.assertEqual(record.current_sharing_instance, sharing)
        self.assertEqual(record.note, upload_workspace_audit.UploadWorkspaceSharingAudit.DCC_WRITERS_CURRENT_CYCLE)

    def test_dcc_writers_shared_as_reader(self):
        sharing = WorkspaceGroupSharingFactory.create(
            workspace=self.upload_workspace.workspace, group=self.dcc_writer_group, access=WorkspaceGroupSharing.READER
        )
        audit = upload_workspace_audit.UploadWorkspaceSharingAudit()
        audit.audit_workspace_and_group(self.upload_workspace, self.dcc_writer_group)
        self.assertEqual(len(audit.verified), 0)
        self.assertEqual(len(audit.needs_action), 1)
        self.assertEqual(len(audit.errors), 0)
        record = audit.needs_action[0]
        self.assertIsInstance(record, workspace_sharing_audit_results.ShareWithCompute)
        self.assertEqual(record.workspace, self.upload_workspace.workspace)
        self.assertEqual(record.managed_group, self.dcc_writer_group)
        self.assertEqual(record.current_sharing_instance, sharing)
        self.assertEqual(record.note, upload_workspace_audit.UploadWorkspaceSharingAudit.DCC_WRITERS_CURRENT_CYCLE)

    def test_dcc_writers_shared_as_owner(self):
        sharing = WorkspaceGroupSharingFactory.create(
            workspace=self.upload_workspace.workspace, group=self.dcc_writer_group, access=WorkspaceGroupSharing.OWNER
        )
        audit = upload_workspace_audit.UploadWorkspaceSharingAudit()
        audit.audit_workspace_and_group(self.upload_workspace, self.dcc_writer_group)
        self.assertEqual(len(audit.verified), 0)
        self.assertEqual(len(audit.needs_action), 0)
        self.assertEqual(len(audit.errors), 1)
        record = audit.errors[0]
        self.assertIsInstance(record, workspace_sharing_audit_results.ShareWithCompute)
        self.assertEqual(record.workspace, self.upload_workspace.workspace)
        self.assertEqual(record.managed_group, self.dcc_writer_group)
        self.assertEqual(record.current_sharing_instance, sharing)
        self.assertEqual(record.note, upload_workspace_audit.UploadWorkspaceSharingAudit.DCC_WRITERS_CURRENT_CYCLE)

    def test_auth_domain_shared_as_writer_no_compute(self):
        # Share the workspace with the group.
        sharing = WorkspaceGroupSharingFactory.create(
            workspace=self.upload_workspace.workspace, group=self.auth_domain, access=WorkspaceGroupSharing.WRITER
        )
        audit = upload_workspace_audit.UploadWorkspaceSharingAudit()
        audit.audit_workspace_and_group(self.upload_workspace, self.auth_domain)
        self.assertEqual(len(audit.verified), 0)
        self.assertEqual(len(audit.needs_action), 1)
        self.assertEqual(len(audit.errors), 0)
        record = audit.needs_action[0]
        self.assertIsInstance(record, workspace_sharing_audit_results.ShareAsReader)
        self.assertEqual(record.workspace, self.upload_workspace.workspace)
        self.assertEqual(record.managed_group, self.auth_domain)
        self.assertEqual(record.current_sharing_instance, sharing)
        self.assertEqual(record.note, upload_workspace_audit.UploadWorkspaceSharingAudit.AUTH_DOMAIN_AS_READER)

    def test_auth_domain_not_shared(self):
        audit = upload_workspace_audit.UploadWorkspaceSharingAudit()
        audit.audit_workspace_and_group(self.upload_workspace, self.auth_domain)
        self.assertEqual(len(audit.verified), 0)
        self.assertEqual(len(audit.needs_action), 1)
        self.assertEqual(len(audit.errors), 0)
        record = audit.needs_action[0]
        self.assertIsInstance(record, workspace_sharing_audit_results.ShareAsReader)
        self.assertEqual(record.workspace, self.upload_workspace.workspace)
        self.assertEqual(record.managed_group, self.auth_domain)
        self.assertEqual(record.current_sharing_instance, None)
        self.assertEqual(record.note, upload_workspace_audit.UploadWorkspaceSharingAudit.AUTH_DOMAIN_AS_READER)

    def test_auth_domain_shared_as_writer_can_compute(self):
        sharing = WorkspaceGroupSharingFactory.create(
            workspace=self.upload_workspace.workspace,
            group=self.auth_domain,
            access=WorkspaceGroupSharing.WRITER,
            can_compute=True,
        )
        audit = upload_workspace_audit.UploadWorkspaceSharingAudit()
        audit.audit_workspace_and_group(self.upload_workspace, self.auth_domain)
        self.assertEqual(len(audit.verified), 0)
        self.assertEqual(len(audit.needs_action), 1)
        self.assertEqual(len(audit.errors), 0)
        record = audit.needs_action[0]
        self.assertIsInstance(record, workspace_sharing_audit_results.ShareAsReader)
        self.assertEqual(record.workspace, self.upload_workspace.workspace)
        self.assertEqual(record.managed_group, self.auth_domain)
        self.assertEqual(record.current_sharing_instance, sharing)
        self.assertEqual(record.note, upload_workspace_audit.UploadWorkspaceSharingAudit.AUTH_DOMAIN_AS_READER)

    def test_auth_domain_shared_as_reader(self):
        sharing = WorkspaceGroupSharingFactory.create(
            workspace=self.upload_workspace.workspace, group=self.auth_domain, access=WorkspaceGroupSharing.READER
        )
        audit = upload_workspace_audit.UploadWorkspaceSharingAudit()
        audit.audit_workspace_and_group(self.upload_workspace, self.auth_domain)
        self.assertEqual(len(audit.verified), 1)
        self.assertEqual(len(audit.needs_action), 0)
        self.assertEqual(len(audit.errors), 0)
        record = audit.verified[0]
        self.assertIsInstance(record, workspace_sharing_audit_results.VerifiedShared)
        self.assertEqual(record.workspace, self.upload_workspace.workspace)
        self.assertEqual(record.managed_group, self.auth_domain)
        self.assertEqual(record.current_sharing_instance, sharing)
        self.assertEqual(record.note, upload_workspace_audit.UploadWorkspaceSharingAudit.AUTH_DOMAIN_AS_READER)

    def test_auth_domain_shared_as_owner(self):
        sharing = WorkspaceGroupSharingFactory.create(
            workspace=self.upload_workspace.workspace, group=self.auth_domain, access=WorkspaceGroupSharing.OWNER
        )
        audit = upload_workspace_audit.UploadWorkspaceSharingAudit()
        audit.audit_workspace_and_group(self.upload_workspace, self.auth_domain)
        self.assertEqual(len(audit.verified), 0)
        self.assertEqual(len(audit.needs_action), 0)
        self.assertEqual(len(audit.errors), 1)
        record = audit.errors[0]
        self.assertIsInstance(record, workspace_sharing_audit_results.ShareAsReader)
        self.assertEqual(record.workspace, self.upload_workspace.workspace)
        self.assertEqual(record.managed_group, self.auth_domain)
        self.assertEqual(record.current_sharing_instance, sharing)
        self.assertEqual(record.note, upload_workspace_audit.UploadWorkspaceSharingAudit.AUTH_DOMAIN_AS_READER)

    def test_dcc_admin_shared_as_writer_no_compute(self):
        # Share the workspace with the group.
        sharing = WorkspaceGroupSharingFactory.create(
            workspace=self.upload_workspace.workspace, group=self.dcc_admin_group, access=WorkspaceGroupSharing.WRITER
        )
        audit = upload_workspace_audit.UploadWorkspaceSharingAudit()
        audit.audit_workspace_and_group(self.upload_workspace, self.dcc_admin_group)
        self.assertEqual(len(audit.verified), 0)
        self.assertEqual(len(audit.needs_action), 1)
        self.assertEqual(len(audit.errors), 0)
        record = audit.needs_action[0]
        self.assertIsInstance(record, workspace_sharing_audit_results.ShareAsOwner)
        self.assertEqual(record.workspace, self.upload_workspace.workspace)
        self.assertEqual(record.managed_group, self.dcc_admin_group)
        self.assertEqual(record.current_sharing_instance, sharing)
        self.assertEqual(record.note, upload_workspace_audit.UploadWorkspaceSharingAudit.DCC_ADMIN_AS_OWNER)

    def test_dcc_admin_not_shared(self):
        audit = upload_workspace_audit.UploadWorkspaceSharingAudit()
        audit.audit_workspace_and_group(self.upload_workspace, self.dcc_admin_group)
        self.assertEqual(len(audit.verified), 0)
        self.assertEqual(len(audit.needs_action), 1)
        self.assertEqual(len(audit.errors), 0)
        record = audit.needs_action[0]
        self.assertIsInstance(record, workspace_sharing_audit_results.ShareAsOwner)
        self.assertEqual(record.workspace, self.upload_workspace.workspace)
        self.assertEqual(record.managed_group, self.dcc_admin_group)
        self.assertEqual(record.current_sharing_instance, None)
        self.assertEqual(record.note, upload_workspace_audit.UploadWorkspaceSharingAudit.DCC_ADMIN_AS_OWNER)

    def test_dcc_admin_shared_as_writer_can_compute(self):
        sharing = WorkspaceGroupSharingFactory.create(
            workspace=self.upload_workspace.workspace,
            group=self.dcc_admin_group,
            access=WorkspaceGroupSharing.WRITER,
            can_compute=True,
        )
        audit = upload_workspace_audit.UploadWorkspaceSharingAudit()
        audit.audit_workspace_and_group(self.upload_workspace, self.dcc_admin_group)
        self.assertEqual(len(audit.verified), 0)
        self.assertEqual(len(audit.needs_action), 1)
        self.assertEqual(len(audit.errors), 0)
        record = audit.needs_action[0]
        self.assertIsInstance(record, workspace_sharing_audit_results.ShareAsOwner)
        self.assertEqual(record.workspace, self.upload_workspace.workspace)
        self.assertEqual(record.managed_group, self.dcc_admin_group)
        self.assertEqual(record.current_sharing_instance, sharing)
        self.assertEqual(record.note, upload_workspace_audit.UploadWorkspaceSharingAudit.DCC_ADMIN_AS_OWNER)

    def test_dcc_admin_shared_as_reader(self):
        sharing = WorkspaceGroupSharingFactory.create(
            workspace=self.upload_workspace.workspace, group=self.dcc_admin_group, access=WorkspaceGroupSharing.READER
        )
        audit = upload_workspace_audit.UploadWorkspaceSharingAudit()
        audit.audit_workspace_and_group(self.upload_workspace, self.dcc_admin_group)
        self.assertEqual(len(audit.verified), 0)
        self.assertEqual(len(audit.needs_action), 1)
        self.assertEqual(len(audit.errors), 0)
        record = audit.needs_action[0]
        self.assertIsInstance(record, workspace_sharing_audit_results.ShareAsOwner)
        self.assertEqual(record.workspace, self.upload_workspace.workspace)
        self.assertEqual(record.managed_group, self.dcc_admin_group)
        self.assertEqual(record.current_sharing_instance, sharing)
        self.assertEqual(record.note, upload_workspace_audit.UploadWorkspaceSharingAudit.DCC_ADMIN_AS_OWNER)

    def test_dcc_admin_shared_as_owner(self):
        sharing = WorkspaceGroupSharingFactory.create(
            workspace=self.upload_workspace.workspace, group=self.dcc_admin_group, access=WorkspaceGroupSharing.OWNER
        )
        audit = upload_workspace_audit.UploadWorkspaceSharingAudit()
        audit.audit_workspace_and_group(self.upload_workspace, self.dcc_admin_group)
        self.assertEqual(len(audit.verified), 1)
        self.assertEqual(len(audit.needs_action), 0)
        self.assertEqual(len(audit.errors), 0)
        record = audit.verified[0]
        self.assertIsInstance(record, workspace_sharing_audit_results.VerifiedShared)
        self.assertEqual(record.workspace, self.upload_workspace.workspace)
        self.assertEqual(record.managed_group, self.dcc_admin_group)
        self.assertEqual(record.current_sharing_instance, sharing)
        self.assertEqual(record.note, upload_workspace_audit.UploadWorkspaceSharingAudit.DCC_ADMIN_AS_OWNER)

    @override_settings(ANVIL_DCC_ADMINS_GROUP_NAME="foo")
    def test_dcc_admin_different_setting(self):
        group = ManagedGroupFactory.create(name="foo")
        sharing = WorkspaceGroupSharingFactory.create(
            workspace=self.upload_workspace.workspace, group=group, access=WorkspaceGroupSharing.OWNER
        )
        audit = upload_workspace_audit.UploadWorkspaceSharingAudit()
        audit.audit_workspace_and_group(self.upload_workspace, group)
        self.assertEqual(len(audit.verified), 1)
        self.assertEqual(len(audit.needs_action), 0)
        self.assertEqual(len(audit.errors), 0)
        record = audit.verified[0]
        self.assertIsInstance(record, workspace_sharing_audit_results.VerifiedShared)
        self.assertEqual(record.workspace, self.upload_workspace.workspace)
        self.assertEqual(record.managed_group, group)
        self.assertEqual(record.current_sharing_instance, sharing)
        self.assertEqual(record.note, upload_workspace_audit.UploadWorkspaceSharingAudit.DCC_ADMIN_AS_OWNER)

    def test_anvil_admins_shared_as_writer_no_compute(self):
        # Share the workspace with the group.
        WorkspaceGroupSharingFactory.create(
            workspace=self.upload_workspace.workspace, group=self.anvil_admins, access=WorkspaceGroupSharing.WRITER
        )
        audit = upload_workspace_audit.UploadWorkspaceSharingAudit()
        audit.audit_workspace_and_group(self.upload_workspace, self.anvil_admins)
        self.assertEqual(len(audit.verified), 0)
        self.assertEqual(len(audit.needs_action), 0)
        self.assertEqual(len(audit.errors), 0)

    def test_anvil_admins_not_shared(self):
        audit = upload_workspace_audit.UploadWorkspaceSharingAudit()
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
        audit = upload_workspace_audit.UploadWorkspaceSharingAudit()
        audit.audit_workspace_and_group(self.upload_workspace, self.anvil_admins)
        self.assertEqual(len(audit.verified), 0)
        self.assertEqual(len(audit.needs_action), 0)
        self.assertEqual(len(audit.errors), 0)

    def test_anvil_admins_shared_as_reader(self):
        WorkspaceGroupSharingFactory.create(
            workspace=self.upload_workspace.workspace, group=self.anvil_admins, access=WorkspaceGroupSharing.READER
        )
        audit = upload_workspace_audit.UploadWorkspaceSharingAudit()
        audit.audit_workspace_and_group(self.upload_workspace, self.anvil_admins)
        self.assertEqual(len(audit.verified), 0)
        self.assertEqual(len(audit.needs_action), 0)
        self.assertEqual(len(audit.errors), 0)

    def test_anvil_admins_shared_as_owner(self):
        WorkspaceGroupSharingFactory.create(
            workspace=self.upload_workspace.workspace, group=self.anvil_admins, access=WorkspaceGroupSharing.OWNER
        )
        audit = upload_workspace_audit.UploadWorkspaceSharingAudit()
        audit.audit_workspace_and_group(self.upload_workspace, self.anvil_admins)
        self.assertEqual(len(audit.verified), 0)
        self.assertEqual(len(audit.needs_action), 0)
        self.assertEqual(len(audit.errors), 0)

    def test_anvil_devs_shared_as_writer_no_compute(self):
        # Share the workspace with the group.
        WorkspaceGroupSharingFactory.create(
            workspace=self.upload_workspace.workspace, group=self.anvil_devs, access=WorkspaceGroupSharing.WRITER
        )
        audit = upload_workspace_audit.UploadWorkspaceSharingAudit()
        audit.audit_workspace_and_group(self.upload_workspace, self.anvil_devs)
        self.assertEqual(len(audit.verified), 0)
        self.assertEqual(len(audit.needs_action), 0)
        self.assertEqual(len(audit.errors), 0)

    def test_anvil_devs_not_shared(self):
        audit = upload_workspace_audit.UploadWorkspaceSharingAudit()
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
        audit = upload_workspace_audit.UploadWorkspaceSharingAudit()
        audit.audit_workspace_and_group(self.upload_workspace, self.anvil_devs)
        self.assertEqual(len(audit.verified), 0)
        self.assertEqual(len(audit.needs_action), 0)
        self.assertEqual(len(audit.errors), 0)

    def test_anvil_devs_shared_as_reader(self):
        WorkspaceGroupSharingFactory.create(
            workspace=self.upload_workspace.workspace, group=self.anvil_devs, access=WorkspaceGroupSharing.READER
        )
        audit = upload_workspace_audit.UploadWorkspaceSharingAudit()
        audit.audit_workspace_and_group(self.upload_workspace, self.anvil_devs)
        self.assertEqual(len(audit.verified), 0)
        self.assertEqual(len(audit.needs_action), 0)
        self.assertEqual(len(audit.errors), 0)

    def test_anvil_devs_shared_as_owner(self):
        WorkspaceGroupSharingFactory.create(
            workspace=self.upload_workspace.workspace, group=self.anvil_devs, access=WorkspaceGroupSharing.OWNER
        )
        audit = upload_workspace_audit.UploadWorkspaceSharingAudit()
        audit.audit_workspace_and_group(self.upload_workspace, self.anvil_devs)
        self.assertEqual(len(audit.verified), 0)
        self.assertEqual(len(audit.needs_action), 0)
        self.assertEqual(len(audit.errors), 0)

    def test_other_group_shared_as_writer_no_compute(self):
        # Share the workspace with the group.
        sharing = WorkspaceGroupSharingFactory.create(
            workspace=self.upload_workspace.workspace, group=self.other_group, access=WorkspaceGroupSharing.WRITER
        )
        audit = upload_workspace_audit.UploadWorkspaceSharingAudit()
        audit.audit_workspace_and_group(self.upload_workspace, self.other_group)
        self.assertEqual(len(audit.verified), 0)
        self.assertEqual(len(audit.needs_action), 0)
        self.assertEqual(len(audit.errors), 1)
        record = audit.errors[0]
        self.assertIsInstance(record, workspace_sharing_audit_results.StopSharing)
        self.assertEqual(record.workspace, self.upload_workspace.workspace)
        self.assertEqual(record.managed_group, self.other_group)
        self.assertEqual(record.current_sharing_instance, sharing)
        self.assertEqual(record.note, upload_workspace_audit.UploadWorkspaceSharingAudit.OTHER_GROUP_NO_ACCESS)

    def test_other_group_not_shared(self):
        audit = upload_workspace_audit.UploadWorkspaceSharingAudit()
        audit.audit_workspace_and_group(self.upload_workspace, self.other_group)
        self.assertEqual(len(audit.verified), 1)
        self.assertEqual(len(audit.needs_action), 0)
        self.assertEqual(len(audit.errors), 0)
        record = audit.verified[0]
        self.assertIsInstance(record, workspace_sharing_audit_results.VerifiedNotShared)
        self.assertEqual(record.workspace, self.upload_workspace.workspace)
        self.assertEqual(record.managed_group, self.other_group)
        self.assertEqual(record.current_sharing_instance, None)
        self.assertEqual(record.note, upload_workspace_audit.UploadWorkspaceSharingAudit.OTHER_GROUP_NO_ACCESS)

    def test_other_group_shared_as_writer_can_compute(self):
        sharing = WorkspaceGroupSharingFactory.create(
            workspace=self.upload_workspace.workspace,
            group=self.other_group,
            access=WorkspaceGroupSharing.WRITER,
            can_compute=True,
        )
        audit = upload_workspace_audit.UploadWorkspaceSharingAudit()
        audit.audit_workspace_and_group(self.upload_workspace, self.other_group)
        self.assertEqual(len(audit.verified), 0)
        self.assertEqual(len(audit.needs_action), 0)
        self.assertEqual(len(audit.errors), 1)
        record = audit.errors[0]
        self.assertIsInstance(record, workspace_sharing_audit_results.StopSharing)
        self.assertEqual(record.workspace, self.upload_workspace.workspace)
        self.assertEqual(record.managed_group, self.other_group)
        self.assertEqual(record.current_sharing_instance, sharing)
        self.assertEqual(record.note, upload_workspace_audit.UploadWorkspaceSharingAudit.OTHER_GROUP_NO_ACCESS)

    def test_other_group_shared_as_reader(self):
        sharing = WorkspaceGroupSharingFactory.create(
            workspace=self.upload_workspace.workspace, group=self.other_group, access=WorkspaceGroupSharing.READER
        )
        audit = upload_workspace_audit.UploadWorkspaceSharingAudit()
        audit.audit_workspace_and_group(self.upload_workspace, self.other_group)
        self.assertEqual(len(audit.verified), 0)
        self.assertEqual(len(audit.needs_action), 0)
        self.assertEqual(len(audit.errors), 1)
        record = audit.errors[0]
        self.assertIsInstance(record, workspace_sharing_audit_results.StopSharing)
        self.assertEqual(record.workspace, self.upload_workspace.workspace)
        self.assertEqual(record.managed_group, self.other_group)
        self.assertEqual(record.current_sharing_instance, sharing)
        self.assertEqual(record.note, upload_workspace_audit.UploadWorkspaceSharingAudit.OTHER_GROUP_NO_ACCESS)

    def test_other_group_shared_as_owner(self):
        sharing = WorkspaceGroupSharingFactory.create(
            workspace=self.upload_workspace.workspace, group=self.other_group, access=WorkspaceGroupSharing.OWNER
        )
        audit = upload_workspace_audit.UploadWorkspaceSharingAudit()
        audit.audit_workspace_and_group(self.upload_workspace, self.other_group)
        self.assertEqual(len(audit.verified), 0)
        self.assertEqual(len(audit.needs_action), 0)
        self.assertEqual(len(audit.errors), 1)
        record = audit.errors[0]
        self.assertIsInstance(record, workspace_sharing_audit_results.StopSharing)
        self.assertEqual(record.workspace, self.upload_workspace.workspace)
        self.assertEqual(record.managed_group, self.other_group)
        self.assertEqual(record.current_sharing_instance, sharing)
        self.assertEqual(record.note, upload_workspace_audit.UploadWorkspaceSharingAudit.OTHER_GROUP_NO_ACCESS)


class UploadWorkspaceSharingAuditPastCycleBeforeQCCompleteTest(TestCase):
    """Tests for the `UploadWorkspaceSharingAudit` class for past cycles before QC is complete.

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
        audit = upload_workspace_audit.UploadWorkspaceSharingAudit()
        audit.audit_workspace_and_group(self.upload_workspace, self.rc_uploader_group)
        self.assertEqual(len(audit.verified), 0)
        self.assertEqual(len(audit.needs_action), 1)
        self.assertEqual(len(audit.errors), 0)
        record = audit.needs_action[0]
        self.assertIsInstance(record, workspace_sharing_audit_results.StopSharing)
        self.assertEqual(record.workspace, self.upload_workspace.workspace)
        self.assertEqual(record.managed_group, self.rc_uploader_group)
        self.assertEqual(record.current_sharing_instance, sharing)
        self.assertEqual(
            record.note,
            upload_workspace_audit.UploadWorkspaceSharingAudit.RC_UPLOADERS_PAST_CYCLE_BEFORE_QC_COMPLETE,
        )

    def test_uploaders_not_shared(self):
        audit = upload_workspace_audit.UploadWorkspaceSharingAudit()
        audit.audit_workspace_and_group(self.upload_workspace, self.rc_uploader_group)
        self.assertEqual(len(audit.verified), 1)
        self.assertEqual(len(audit.needs_action), 0)
        self.assertEqual(len(audit.errors), 0)
        record = audit.verified[0]
        self.assertIsInstance(record, workspace_sharing_audit_results.VerifiedNotShared)
        self.assertEqual(record.workspace, self.upload_workspace.workspace)
        self.assertEqual(record.managed_group, self.rc_uploader_group)
        self.assertEqual(record.current_sharing_instance, None)
        self.assertEqual(
            record.note,
            upload_workspace_audit.UploadWorkspaceSharingAudit.RC_UPLOADERS_PAST_CYCLE_BEFORE_QC_COMPLETE,
        )

    def test_uploaders_shared_as_writer_can_compute(self):
        sharing = WorkspaceGroupSharingFactory.create(
            workspace=self.upload_workspace.workspace,
            group=self.rc_uploader_group,
            access=WorkspaceGroupSharing.WRITER,
            can_compute=True,
        )
        audit = upload_workspace_audit.UploadWorkspaceSharingAudit()
        audit.audit_workspace_and_group(self.upload_workspace, self.rc_uploader_group)
        self.assertEqual(len(audit.verified), 0)
        self.assertEqual(len(audit.needs_action), 1)
        self.assertEqual(len(audit.errors), 0)
        record = audit.needs_action[0]
        self.assertIsInstance(record, workspace_sharing_audit_results.StopSharing)
        self.assertEqual(record.workspace, self.upload_workspace.workspace)
        self.assertEqual(record.managed_group, self.rc_uploader_group)
        self.assertEqual(record.current_sharing_instance, sharing)
        self.assertEqual(
            record.note,
            upload_workspace_audit.UploadWorkspaceSharingAudit.RC_UPLOADERS_PAST_CYCLE_BEFORE_QC_COMPLETE,
        )

    def test_uploaders_shared_as_reader(self):
        sharing = WorkspaceGroupSharingFactory.create(
            workspace=self.upload_workspace.workspace, group=self.rc_uploader_group, access=WorkspaceGroupSharing.READER
        )
        audit = upload_workspace_audit.UploadWorkspaceSharingAudit()
        audit.audit_workspace_and_group(self.upload_workspace, self.rc_uploader_group)
        self.assertEqual(len(audit.verified), 0)
        self.assertEqual(len(audit.needs_action), 1)
        self.assertEqual(len(audit.errors), 0)
        record = audit.needs_action[0]
        self.assertIsInstance(record, workspace_sharing_audit_results.StopSharing)
        self.assertEqual(record.workspace, self.upload_workspace.workspace)
        self.assertEqual(record.managed_group, self.rc_uploader_group)
        self.assertEqual(record.current_sharing_instance, sharing)
        self.assertEqual(
            record.note,
            upload_workspace_audit.UploadWorkspaceSharingAudit.RC_UPLOADERS_PAST_CYCLE_BEFORE_QC_COMPLETE,
        )

    def test_uploaders_shared_as_owner(self):
        sharing = WorkspaceGroupSharingFactory.create(
            workspace=self.upload_workspace.workspace, group=self.rc_uploader_group, access=WorkspaceGroupSharing.OWNER
        )
        audit = upload_workspace_audit.UploadWorkspaceSharingAudit()
        audit.audit_workspace_and_group(self.upload_workspace, self.rc_uploader_group)
        self.assertEqual(len(audit.verified), 0)
        self.assertEqual(len(audit.needs_action), 0)
        self.assertEqual(len(audit.errors), 1)
        record = audit.errors[0]
        self.assertIsInstance(record, workspace_sharing_audit_results.StopSharing)
        self.assertEqual(record.workspace, self.upload_workspace.workspace)
        self.assertEqual(record.managed_group, self.rc_uploader_group)
        self.assertEqual(record.current_sharing_instance, sharing)
        self.assertEqual(
            record.note,
            upload_workspace_audit.UploadWorkspaceSharingAudit.RC_UPLOADERS_PAST_CYCLE_BEFORE_QC_COMPLETE,
        )

    def test_dcc_writers_shared_as_writer_no_compute(self):
        # Share the workspace with the group.
        sharing = WorkspaceGroupSharingFactory.create(
            workspace=self.upload_workspace.workspace, group=self.dcc_writer_group, access=WorkspaceGroupSharing.WRITER
        )
        audit = upload_workspace_audit.UploadWorkspaceSharingAudit()
        audit.audit_workspace_and_group(self.upload_workspace, self.dcc_writer_group)
        self.assertEqual(len(audit.verified), 0)
        self.assertEqual(len(audit.needs_action), 1)
        self.assertEqual(len(audit.errors), 0)
        record = audit.needs_action[0]
        self.assertIsInstance(record, workspace_sharing_audit_results.ShareWithCompute)
        self.assertEqual(record.workspace, self.upload_workspace.workspace)
        self.assertEqual(record.managed_group, self.dcc_writer_group)
        self.assertEqual(record.current_sharing_instance, sharing)
        self.assertEqual(
            record.note,
            upload_workspace_audit.UploadWorkspaceSharingAudit.DCC_WRITERS_PAST_CYCLE_BEFORE_QC_COMPLETE,
        )

    def test_dcc_writers_not_shared(self):
        audit = upload_workspace_audit.UploadWorkspaceSharingAudit()
        audit.audit_workspace_and_group(self.upload_workspace, self.dcc_writer_group)
        self.assertEqual(len(audit.verified), 0)
        self.assertEqual(len(audit.needs_action), 1)
        self.assertEqual(len(audit.errors), 0)
        record = audit.needs_action[0]
        self.assertIsInstance(record, workspace_sharing_audit_results.ShareWithCompute)
        self.assertEqual(record.workspace, self.upload_workspace.workspace)
        self.assertEqual(record.managed_group, self.dcc_writer_group)
        self.assertEqual(record.current_sharing_instance, None)
        self.assertEqual(
            record.note,
            upload_workspace_audit.UploadWorkspaceSharingAudit.DCC_WRITERS_PAST_CYCLE_BEFORE_QC_COMPLETE,
        )

    def test_dcc_writers_shared_as_writer_can_compute(self):
        sharing = WorkspaceGroupSharingFactory.create(
            workspace=self.upload_workspace.workspace,
            group=self.dcc_writer_group,
            access=WorkspaceGroupSharing.WRITER,
            can_compute=True,
        )
        audit = upload_workspace_audit.UploadWorkspaceSharingAudit()
        audit.audit_workspace_and_group(self.upload_workspace, self.dcc_writer_group)
        self.assertEqual(len(audit.verified), 1)
        self.assertEqual(len(audit.needs_action), 0)
        self.assertEqual(len(audit.errors), 0)
        record = audit.verified[0]
        self.assertIsInstance(record, workspace_sharing_audit_results.VerifiedShared)
        self.assertEqual(record.workspace, self.upload_workspace.workspace)
        self.assertEqual(record.managed_group, self.dcc_writer_group)
        self.assertEqual(record.current_sharing_instance, sharing)
        self.assertEqual(
            record.note,
            upload_workspace_audit.UploadWorkspaceSharingAudit.DCC_WRITERS_PAST_CYCLE_BEFORE_QC_COMPLETE,
        )

    def test_dcc_writers_shared_as_reader(self):
        sharing = WorkspaceGroupSharingFactory.create(
            workspace=self.upload_workspace.workspace, group=self.dcc_writer_group, access=WorkspaceGroupSharing.READER
        )
        audit = upload_workspace_audit.UploadWorkspaceSharingAudit()
        audit.audit_workspace_and_group(self.upload_workspace, self.dcc_writer_group)
        self.assertEqual(len(audit.verified), 0)
        self.assertEqual(len(audit.needs_action), 1)
        self.assertEqual(len(audit.errors), 0)
        record = audit.needs_action[0]
        self.assertIsInstance(record, workspace_sharing_audit_results.ShareWithCompute)
        self.assertEqual(record.workspace, self.upload_workspace.workspace)
        self.assertEqual(record.managed_group, self.dcc_writer_group)
        self.assertEqual(record.current_sharing_instance, sharing)
        self.assertEqual(
            record.note,
            upload_workspace_audit.UploadWorkspaceSharingAudit.DCC_WRITERS_PAST_CYCLE_BEFORE_QC_COMPLETE,
        )

    def test_dcc_writers_shared_as_owner(self):
        sharing = WorkspaceGroupSharingFactory.create(
            workspace=self.upload_workspace.workspace, group=self.dcc_writer_group, access=WorkspaceGroupSharing.OWNER
        )
        audit = upload_workspace_audit.UploadWorkspaceSharingAudit()
        audit.audit_workspace_and_group(self.upload_workspace, self.dcc_writer_group)
        self.assertEqual(len(audit.verified), 0)
        self.assertEqual(len(audit.needs_action), 0)
        self.assertEqual(len(audit.errors), 1)
        record = audit.errors[0]
        self.assertIsInstance(record, workspace_sharing_audit_results.ShareWithCompute)
        self.assertEqual(record.workspace, self.upload_workspace.workspace)
        self.assertEqual(record.managed_group, self.dcc_writer_group)
        self.assertEqual(record.current_sharing_instance, sharing)
        self.assertEqual(
            record.note,
            upload_workspace_audit.UploadWorkspaceSharingAudit.DCC_WRITERS_PAST_CYCLE_BEFORE_QC_COMPLETE,
        )

    def test_auth_domain_shared_as_writer_no_compute(self):
        # Share the workspace with the group.
        sharing = WorkspaceGroupSharingFactory.create(
            workspace=self.upload_workspace.workspace, group=self.auth_domain, access=WorkspaceGroupSharing.WRITER
        )
        audit = upload_workspace_audit.UploadWorkspaceSharingAudit()
        audit.audit_workspace_and_group(self.upload_workspace, self.auth_domain)
        self.assertEqual(len(audit.verified), 0)
        self.assertEqual(len(audit.needs_action), 1)
        self.assertEqual(len(audit.errors), 0)
        record = audit.needs_action[0]
        self.assertIsInstance(record, workspace_sharing_audit_results.ShareAsReader)
        self.assertEqual(record.workspace, self.upload_workspace.workspace)
        self.assertEqual(record.managed_group, self.auth_domain)
        self.assertEqual(record.current_sharing_instance, sharing)
        self.assertEqual(record.note, upload_workspace_audit.UploadWorkspaceSharingAudit.AUTH_DOMAIN_AS_READER)

    def test_auth_domain_not_shared(self):
        audit = upload_workspace_audit.UploadWorkspaceSharingAudit()
        audit.audit_workspace_and_group(self.upload_workspace, self.auth_domain)
        self.assertEqual(len(audit.verified), 0)
        self.assertEqual(len(audit.needs_action), 1)
        self.assertEqual(len(audit.errors), 0)
        record = audit.needs_action[0]
        self.assertIsInstance(record, workspace_sharing_audit_results.ShareAsReader)
        self.assertEqual(record.workspace, self.upload_workspace.workspace)
        self.assertEqual(record.managed_group, self.auth_domain)
        self.assertEqual(record.current_sharing_instance, None)
        self.assertEqual(record.note, upload_workspace_audit.UploadWorkspaceSharingAudit.AUTH_DOMAIN_AS_READER)

    def test_auth_domain_shared_as_writer_can_compute(self):
        sharing = WorkspaceGroupSharingFactory.create(
            workspace=self.upload_workspace.workspace,
            group=self.auth_domain,
            access=WorkspaceGroupSharing.WRITER,
            can_compute=True,
        )
        audit = upload_workspace_audit.UploadWorkspaceSharingAudit()
        audit.audit_workspace_and_group(self.upload_workspace, self.auth_domain)
        self.assertEqual(len(audit.verified), 0)
        self.assertEqual(len(audit.needs_action), 1)
        self.assertEqual(len(audit.errors), 0)
        record = audit.needs_action[0]
        self.assertIsInstance(record, workspace_sharing_audit_results.ShareAsReader)
        self.assertEqual(record.workspace, self.upload_workspace.workspace)
        self.assertEqual(record.managed_group, self.auth_domain)
        self.assertEqual(record.current_sharing_instance, sharing)
        self.assertEqual(record.note, upload_workspace_audit.UploadWorkspaceSharingAudit.AUTH_DOMAIN_AS_READER)

    def test_auth_domain_shared_as_reader(self):
        sharing = WorkspaceGroupSharingFactory.create(
            workspace=self.upload_workspace.workspace, group=self.auth_domain, access=WorkspaceGroupSharing.READER
        )
        audit = upload_workspace_audit.UploadWorkspaceSharingAudit()
        audit.audit_workspace_and_group(self.upload_workspace, self.auth_domain)
        self.assertEqual(len(audit.verified), 1)
        self.assertEqual(len(audit.needs_action), 0)
        self.assertEqual(len(audit.errors), 0)
        record = audit.verified[0]
        self.assertIsInstance(record, workspace_sharing_audit_results.VerifiedShared)
        self.assertEqual(record.workspace, self.upload_workspace.workspace)
        self.assertEqual(record.managed_group, self.auth_domain)
        self.assertEqual(record.current_sharing_instance, sharing)
        self.assertEqual(record.note, upload_workspace_audit.UploadWorkspaceSharingAudit.AUTH_DOMAIN_AS_READER)

    def test_auth_domain_shared_as_owner(self):
        sharing = WorkspaceGroupSharingFactory.create(
            workspace=self.upload_workspace.workspace, group=self.auth_domain, access=WorkspaceGroupSharing.OWNER
        )
        audit = upload_workspace_audit.UploadWorkspaceSharingAudit()
        audit.audit_workspace_and_group(self.upload_workspace, self.auth_domain)
        self.assertEqual(len(audit.verified), 0)
        self.assertEqual(len(audit.needs_action), 0)
        self.assertEqual(len(audit.errors), 1)
        record = audit.errors[0]
        self.assertIsInstance(record, workspace_sharing_audit_results.ShareAsReader)
        self.assertEqual(record.workspace, self.upload_workspace.workspace)
        self.assertEqual(record.managed_group, self.auth_domain)
        self.assertEqual(record.current_sharing_instance, sharing)
        self.assertEqual(record.note, upload_workspace_audit.UploadWorkspaceSharingAudit.AUTH_DOMAIN_AS_READER)

    def test_dcc_admin_shared_as_writer_no_compute(self):
        # Share the workspace with the group.
        sharing = WorkspaceGroupSharingFactory.create(
            workspace=self.upload_workspace.workspace, group=self.dcc_admin_group, access=WorkspaceGroupSharing.WRITER
        )
        audit = upload_workspace_audit.UploadWorkspaceSharingAudit()
        audit.audit_workspace_and_group(self.upload_workspace, self.dcc_admin_group)
        self.assertEqual(len(audit.verified), 0)
        self.assertEqual(len(audit.needs_action), 1)
        self.assertEqual(len(audit.errors), 0)
        record = audit.needs_action[0]
        self.assertIsInstance(record, workspace_sharing_audit_results.ShareAsOwner)
        self.assertEqual(record.workspace, self.upload_workspace.workspace)
        self.assertEqual(record.managed_group, self.dcc_admin_group)
        self.assertEqual(record.current_sharing_instance, sharing)
        self.assertEqual(record.note, upload_workspace_audit.UploadWorkspaceSharingAudit.DCC_ADMIN_AS_OWNER)

    def test_dcc_admin_not_shared(self):
        audit = upload_workspace_audit.UploadWorkspaceSharingAudit()
        audit.audit_workspace_and_group(self.upload_workspace, self.dcc_admin_group)
        self.assertEqual(len(audit.verified), 0)
        self.assertEqual(len(audit.needs_action), 1)
        self.assertEqual(len(audit.errors), 0)
        record = audit.needs_action[0]
        self.assertIsInstance(record, workspace_sharing_audit_results.ShareAsOwner)
        self.assertEqual(record.workspace, self.upload_workspace.workspace)
        self.assertEqual(record.managed_group, self.dcc_admin_group)
        self.assertEqual(record.current_sharing_instance, None)
        self.assertEqual(record.note, upload_workspace_audit.UploadWorkspaceSharingAudit.DCC_ADMIN_AS_OWNER)

    def test_dcc_admin_shared_as_writer_can_compute(self):
        sharing = WorkspaceGroupSharingFactory.create(
            workspace=self.upload_workspace.workspace,
            group=self.dcc_admin_group,
            access=WorkspaceGroupSharing.WRITER,
            can_compute=True,
        )
        audit = upload_workspace_audit.UploadWorkspaceSharingAudit()
        audit.audit_workspace_and_group(self.upload_workspace, self.dcc_admin_group)
        self.assertEqual(len(audit.verified), 0)
        self.assertEqual(len(audit.needs_action), 1)
        self.assertEqual(len(audit.errors), 0)
        record = audit.needs_action[0]
        self.assertIsInstance(record, workspace_sharing_audit_results.ShareAsOwner)
        self.assertEqual(record.workspace, self.upload_workspace.workspace)
        self.assertEqual(record.managed_group, self.dcc_admin_group)
        self.assertEqual(record.current_sharing_instance, sharing)
        self.assertEqual(record.note, upload_workspace_audit.UploadWorkspaceSharingAudit.DCC_ADMIN_AS_OWNER)

    def test_dcc_admin_shared_as_reader(self):
        sharing = WorkspaceGroupSharingFactory.create(
            workspace=self.upload_workspace.workspace, group=self.dcc_admin_group, access=WorkspaceGroupSharing.READER
        )
        audit = upload_workspace_audit.UploadWorkspaceSharingAudit()
        audit.audit_workspace_and_group(self.upload_workspace, self.dcc_admin_group)
        self.assertEqual(len(audit.verified), 0)
        self.assertEqual(len(audit.needs_action), 1)
        self.assertEqual(len(audit.errors), 0)
        record = audit.needs_action[0]
        self.assertIsInstance(record, workspace_sharing_audit_results.ShareAsOwner)
        self.assertEqual(record.workspace, self.upload_workspace.workspace)
        self.assertEqual(record.managed_group, self.dcc_admin_group)
        self.assertEqual(record.current_sharing_instance, sharing)
        self.assertEqual(record.note, upload_workspace_audit.UploadWorkspaceSharingAudit.DCC_ADMIN_AS_OWNER)

    def test_dcc_admin_shared_as_owner(self):
        sharing = WorkspaceGroupSharingFactory.create(
            workspace=self.upload_workspace.workspace, group=self.dcc_admin_group, access=WorkspaceGroupSharing.OWNER
        )
        audit = upload_workspace_audit.UploadWorkspaceSharingAudit()
        audit.audit_workspace_and_group(self.upload_workspace, self.dcc_admin_group)
        self.assertEqual(len(audit.verified), 1)
        self.assertEqual(len(audit.needs_action), 0)
        self.assertEqual(len(audit.errors), 0)
        record = audit.verified[0]
        self.assertIsInstance(record, workspace_sharing_audit_results.VerifiedShared)
        self.assertEqual(record.workspace, self.upload_workspace.workspace)
        self.assertEqual(record.managed_group, self.dcc_admin_group)
        self.assertEqual(record.current_sharing_instance, sharing)
        self.assertEqual(record.note, upload_workspace_audit.UploadWorkspaceSharingAudit.DCC_ADMIN_AS_OWNER)

    @override_settings(ANVIL_DCC_ADMINS_GROUP_NAME="foo")
    def test_dcc_admin_different_setting(self):
        group = ManagedGroupFactory.create(name="foo")
        sharing = WorkspaceGroupSharingFactory.create(
            workspace=self.upload_workspace.workspace, group=group, access=WorkspaceGroupSharing.OWNER
        )
        audit = upload_workspace_audit.UploadWorkspaceSharingAudit()
        audit.audit_workspace_and_group(self.upload_workspace, group)
        self.assertEqual(len(audit.verified), 1)
        self.assertEqual(len(audit.needs_action), 0)
        self.assertEqual(len(audit.errors), 0)
        record = audit.verified[0]
        self.assertIsInstance(record, workspace_sharing_audit_results.VerifiedShared)
        self.assertEqual(record.workspace, self.upload_workspace.workspace)
        self.assertEqual(record.managed_group, group)
        self.assertEqual(record.current_sharing_instance, sharing)
        self.assertEqual(record.note, upload_workspace_audit.UploadWorkspaceSharingAudit.DCC_ADMIN_AS_OWNER)

    def test_anvil_admins_shared_as_writer_no_compute(self):
        # Share the workspace with the group.
        WorkspaceGroupSharingFactory.create(
            workspace=self.upload_workspace.workspace, group=self.anvil_admins, access=WorkspaceGroupSharing.WRITER
        )
        audit = upload_workspace_audit.UploadWorkspaceSharingAudit()
        audit.audit_workspace_and_group(self.upload_workspace, self.anvil_admins)
        self.assertEqual(len(audit.verified), 0)
        self.assertEqual(len(audit.needs_action), 0)
        self.assertEqual(len(audit.errors), 0)

    def test_anvil_admins_not_shared(self):
        audit = upload_workspace_audit.UploadWorkspaceSharingAudit()
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
        audit = upload_workspace_audit.UploadWorkspaceSharingAudit()
        audit.audit_workspace_and_group(self.upload_workspace, self.anvil_admins)
        self.assertEqual(len(audit.verified), 0)
        self.assertEqual(len(audit.needs_action), 0)
        self.assertEqual(len(audit.errors), 0)

    def test_anvil_admins_shared_as_reader(self):
        WorkspaceGroupSharingFactory.create(
            workspace=self.upload_workspace.workspace, group=self.anvil_admins, access=WorkspaceGroupSharing.READER
        )
        audit = upload_workspace_audit.UploadWorkspaceSharingAudit()
        audit.audit_workspace_and_group(self.upload_workspace, self.anvil_admins)
        self.assertEqual(len(audit.verified), 0)
        self.assertEqual(len(audit.needs_action), 0)
        self.assertEqual(len(audit.errors), 0)

    def test_anvil_admins_shared_as_owner(self):
        WorkspaceGroupSharingFactory.create(
            workspace=self.upload_workspace.workspace, group=self.anvil_admins, access=WorkspaceGroupSharing.OWNER
        )
        audit = upload_workspace_audit.UploadWorkspaceSharingAudit()
        audit.audit_workspace_and_group(self.upload_workspace, self.anvil_admins)
        self.assertEqual(len(audit.verified), 0)
        self.assertEqual(len(audit.needs_action), 0)
        self.assertEqual(len(audit.errors), 0)

    def test_anvil_devs_shared_as_writer_no_compute(self):
        # Share the workspace with the group.
        WorkspaceGroupSharingFactory.create(
            workspace=self.upload_workspace.workspace, group=self.anvil_devs, access=WorkspaceGroupSharing.WRITER
        )
        audit = upload_workspace_audit.UploadWorkspaceSharingAudit()
        audit.audit_workspace_and_group(self.upload_workspace, self.anvil_devs)
        self.assertEqual(len(audit.verified), 0)
        self.assertEqual(len(audit.needs_action), 0)
        self.assertEqual(len(audit.errors), 0)

    def test_anvil_devs_not_shared(self):
        audit = upload_workspace_audit.UploadWorkspaceSharingAudit()
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
        audit = upload_workspace_audit.UploadWorkspaceSharingAudit()
        audit.audit_workspace_and_group(self.upload_workspace, self.anvil_devs)
        self.assertEqual(len(audit.verified), 0)
        self.assertEqual(len(audit.needs_action), 0)
        self.assertEqual(len(audit.errors), 0)

    def test_anvil_devs_shared_as_reader(self):
        WorkspaceGroupSharingFactory.create(
            workspace=self.upload_workspace.workspace, group=self.anvil_devs, access=WorkspaceGroupSharing.READER
        )
        audit = upload_workspace_audit.UploadWorkspaceSharingAudit()
        audit.audit_workspace_and_group(self.upload_workspace, self.anvil_devs)
        self.assertEqual(len(audit.verified), 0)
        self.assertEqual(len(audit.needs_action), 0)
        self.assertEqual(len(audit.errors), 0)

    def test_anvil_devs_shared_as_owner(self):
        WorkspaceGroupSharingFactory.create(
            workspace=self.upload_workspace.workspace, group=self.anvil_devs, access=WorkspaceGroupSharing.OWNER
        )
        audit = upload_workspace_audit.UploadWorkspaceSharingAudit()
        audit.audit_workspace_and_group(self.upload_workspace, self.anvil_devs)
        self.assertEqual(len(audit.verified), 0)
        self.assertEqual(len(audit.needs_action), 0)
        self.assertEqual(len(audit.errors), 0)

    def test_other_group_shared_as_writer_no_compute(self):
        # Share the workspace with the group.
        sharing = WorkspaceGroupSharingFactory.create(
            workspace=self.upload_workspace.workspace, group=self.other_group, access=WorkspaceGroupSharing.WRITER
        )
        audit = upload_workspace_audit.UploadWorkspaceSharingAudit()
        audit.audit_workspace_and_group(self.upload_workspace, self.other_group)
        self.assertEqual(len(audit.verified), 0)
        self.assertEqual(len(audit.needs_action), 0)
        self.assertEqual(len(audit.errors), 1)
        record = audit.errors[0]
        self.assertIsInstance(record, workspace_sharing_audit_results.StopSharing)
        self.assertEqual(record.workspace, self.upload_workspace.workspace)
        self.assertEqual(record.managed_group, self.other_group)
        self.assertEqual(record.current_sharing_instance, sharing)
        self.assertEqual(record.note, upload_workspace_audit.UploadWorkspaceSharingAudit.OTHER_GROUP_NO_ACCESS)

    def test_other_group_not_shared(self):
        audit = upload_workspace_audit.UploadWorkspaceSharingAudit()
        audit.audit_workspace_and_group(self.upload_workspace, self.other_group)
        self.assertEqual(len(audit.verified), 1)
        self.assertEqual(len(audit.needs_action), 0)
        self.assertEqual(len(audit.errors), 0)
        record = audit.verified[0]
        self.assertIsInstance(record, workspace_sharing_audit_results.VerifiedNotShared)
        self.assertEqual(record.workspace, self.upload_workspace.workspace)
        self.assertEqual(record.managed_group, self.other_group)
        self.assertEqual(record.current_sharing_instance, None)
        self.assertEqual(record.note, upload_workspace_audit.UploadWorkspaceSharingAudit.OTHER_GROUP_NO_ACCESS)

    def test_other_group_shared_as_writer_can_compute(self):
        sharing = WorkspaceGroupSharingFactory.create(
            workspace=self.upload_workspace.workspace,
            group=self.other_group,
            access=WorkspaceGroupSharing.WRITER,
            can_compute=True,
        )
        audit = upload_workspace_audit.UploadWorkspaceSharingAudit()
        audit.audit_workspace_and_group(self.upload_workspace, self.other_group)
        self.assertEqual(len(audit.verified), 0)
        self.assertEqual(len(audit.needs_action), 0)
        self.assertEqual(len(audit.errors), 1)
        record = audit.errors[0]
        self.assertIsInstance(record, workspace_sharing_audit_results.StopSharing)
        self.assertEqual(record.workspace, self.upload_workspace.workspace)
        self.assertEqual(record.managed_group, self.other_group)
        self.assertEqual(record.current_sharing_instance, sharing)
        self.assertEqual(record.note, upload_workspace_audit.UploadWorkspaceSharingAudit.OTHER_GROUP_NO_ACCESS)

    def test_other_group_shared_as_reader(self):
        sharing = WorkspaceGroupSharingFactory.create(
            workspace=self.upload_workspace.workspace, group=self.other_group, access=WorkspaceGroupSharing.READER
        )
        audit = upload_workspace_audit.UploadWorkspaceSharingAudit()
        audit.audit_workspace_and_group(self.upload_workspace, self.other_group)
        self.assertEqual(len(audit.verified), 0)
        self.assertEqual(len(audit.needs_action), 0)
        self.assertEqual(len(audit.errors), 1)
        record = audit.errors[0]
        self.assertIsInstance(record, workspace_sharing_audit_results.StopSharing)
        self.assertEqual(record.workspace, self.upload_workspace.workspace)
        self.assertEqual(record.managed_group, self.other_group)
        self.assertEqual(record.current_sharing_instance, sharing)
        self.assertEqual(record.note, upload_workspace_audit.UploadWorkspaceSharingAudit.OTHER_GROUP_NO_ACCESS)

    def test_other_group_shared_as_owner(self):
        sharing = WorkspaceGroupSharingFactory.create(
            workspace=self.upload_workspace.workspace, group=self.other_group, access=WorkspaceGroupSharing.OWNER
        )
        audit = upload_workspace_audit.UploadWorkspaceSharingAudit()
        audit.audit_workspace_and_group(self.upload_workspace, self.other_group)
        self.assertEqual(len(audit.verified), 0)
        self.assertEqual(len(audit.needs_action), 0)
        self.assertEqual(len(audit.errors), 1)
        record = audit.errors[0]
        self.assertIsInstance(record, workspace_sharing_audit_results.StopSharing)
        self.assertEqual(record.workspace, self.upload_workspace.workspace)
        self.assertEqual(record.managed_group, self.other_group)
        self.assertEqual(record.current_sharing_instance, sharing)
        self.assertEqual(record.note, upload_workspace_audit.UploadWorkspaceSharingAudit.OTHER_GROUP_NO_ACCESS)


class UploadWorkspaceSharingAuditPastCycleAfterQCCompleteTest(TestCase):
    """Tests for the `UploadWorkspaceSharingAudit` class for past cycles before QC is complete.

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
        audit = upload_workspace_audit.UploadWorkspaceSharingAudit()
        audit.audit_workspace_and_group(self.upload_workspace, self.rc_uploader_group)
        self.assertEqual(len(audit.verified), 0)
        self.assertEqual(len(audit.needs_action), 1)
        self.assertEqual(len(audit.errors), 0)
        record = audit.needs_action[0]
        self.assertIsInstance(record, workspace_sharing_audit_results.StopSharing)
        self.assertEqual(record.workspace, self.upload_workspace.workspace)
        self.assertEqual(record.managed_group, self.rc_uploader_group)
        self.assertEqual(record.current_sharing_instance, sharing)
        self.assertEqual(
            record.note,
            upload_workspace_audit.UploadWorkspaceSharingAudit.RC_UPLOADERS_PAST_CYCLE_AFTER_QC_COMPLETE,
        )

    def test_uploaders_not_shared(self):
        audit = upload_workspace_audit.UploadWorkspaceSharingAudit()
        audit.audit_workspace_and_group(self.upload_workspace, self.rc_uploader_group)
        self.assertEqual(len(audit.verified), 1)
        self.assertEqual(len(audit.needs_action), 0)
        self.assertEqual(len(audit.errors), 0)
        record = audit.verified[0]
        self.assertIsInstance(record, workspace_sharing_audit_results.VerifiedNotShared)
        self.assertEqual(record.workspace, self.upload_workspace.workspace)
        self.assertEqual(record.managed_group, self.rc_uploader_group)
        self.assertEqual(record.current_sharing_instance, None)
        self.assertEqual(
            record.note,
            upload_workspace_audit.UploadWorkspaceSharingAudit.RC_UPLOADERS_PAST_CYCLE_AFTER_QC_COMPLETE,
        )

    def test_uploaders_shared_as_writer_can_compute(self):
        sharing = WorkspaceGroupSharingFactory.create(
            workspace=self.upload_workspace.workspace,
            group=self.rc_uploader_group,
            access=WorkspaceGroupSharing.WRITER,
            can_compute=True,
        )
        audit = upload_workspace_audit.UploadWorkspaceSharingAudit()
        audit.audit_workspace_and_group(self.upload_workspace, self.rc_uploader_group)
        self.assertEqual(len(audit.verified), 0)
        self.assertEqual(len(audit.needs_action), 1)
        self.assertEqual(len(audit.errors), 0)
        record = audit.needs_action[0]
        self.assertIsInstance(record, workspace_sharing_audit_results.StopSharing)
        self.assertEqual(record.workspace, self.upload_workspace.workspace)
        self.assertEqual(record.managed_group, self.rc_uploader_group)
        self.assertEqual(record.current_sharing_instance, sharing)
        self.assertEqual(
            record.note,
            upload_workspace_audit.UploadWorkspaceSharingAudit.RC_UPLOADERS_PAST_CYCLE_AFTER_QC_COMPLETE,
        )

    def test_uploaders_shared_as_reader(self):
        sharing = WorkspaceGroupSharingFactory.create(
            workspace=self.upload_workspace.workspace, group=self.rc_uploader_group, access=WorkspaceGroupSharing.READER
        )
        audit = upload_workspace_audit.UploadWorkspaceSharingAudit()
        audit.audit_workspace_and_group(self.upload_workspace, self.rc_uploader_group)
        self.assertEqual(len(audit.verified), 0)
        self.assertEqual(len(audit.needs_action), 1)
        self.assertEqual(len(audit.errors), 0)
        record = audit.needs_action[0]
        self.assertIsInstance(record, workspace_sharing_audit_results.StopSharing)
        self.assertEqual(record.workspace, self.upload_workspace.workspace)
        self.assertEqual(record.managed_group, self.rc_uploader_group)
        self.assertEqual(record.current_sharing_instance, sharing)
        self.assertEqual(
            record.note,
            upload_workspace_audit.UploadWorkspaceSharingAudit.RC_UPLOADERS_PAST_CYCLE_AFTER_QC_COMPLETE,
        )

    def test_uploaders_shared_as_owner(self):
        sharing = WorkspaceGroupSharingFactory.create(
            workspace=self.upload_workspace.workspace, group=self.rc_uploader_group, access=WorkspaceGroupSharing.OWNER
        )
        audit = upload_workspace_audit.UploadWorkspaceSharingAudit()
        audit.audit_workspace_and_group(self.upload_workspace, self.rc_uploader_group)
        self.assertEqual(len(audit.verified), 0)
        self.assertEqual(len(audit.needs_action), 0)
        self.assertEqual(len(audit.errors), 1)
        record = audit.errors[0]
        self.assertIsInstance(record, workspace_sharing_audit_results.StopSharing)
        self.assertEqual(record.workspace, self.upload_workspace.workspace)
        self.assertEqual(record.managed_group, self.rc_uploader_group)
        self.assertEqual(record.current_sharing_instance, sharing)
        self.assertEqual(
            record.note,
            upload_workspace_audit.UploadWorkspaceSharingAudit.RC_UPLOADERS_PAST_CYCLE_AFTER_QC_COMPLETE,
        )

    def test_dcc_writers_shared_as_writer_no_compute(self):
        # Share the workspace with the group.
        sharing = WorkspaceGroupSharingFactory.create(
            workspace=self.upload_workspace.workspace, group=self.dcc_writer_group, access=WorkspaceGroupSharing.WRITER
        )
        audit = upload_workspace_audit.UploadWorkspaceSharingAudit()
        audit.audit_workspace_and_group(self.upload_workspace, self.dcc_writer_group)
        self.assertEqual(len(audit.verified), 0)
        self.assertEqual(len(audit.needs_action), 1)
        self.assertEqual(len(audit.errors), 0)
        record = audit.needs_action[0]
        self.assertIsInstance(record, workspace_sharing_audit_results.StopSharing)
        self.assertEqual(record.workspace, self.upload_workspace.workspace)
        self.assertEqual(record.managed_group, self.dcc_writer_group)
        self.assertEqual(record.current_sharing_instance, sharing)
        self.assertEqual(
            record.note,
            upload_workspace_audit.UploadWorkspaceSharingAudit.DCC_WRITERS_PAST_CYCLE_AFTER_QC_COMPLETE,
        )

    def test_dcc_writers_not_shared(self):
        audit = upload_workspace_audit.UploadWorkspaceSharingAudit()
        audit.audit_workspace_and_group(self.upload_workspace, self.dcc_writer_group)
        self.assertEqual(len(audit.verified), 1)
        self.assertEqual(len(audit.needs_action), 0)
        self.assertEqual(len(audit.errors), 0)
        record = audit.verified[0]
        self.assertIsInstance(record, workspace_sharing_audit_results.VerifiedNotShared)
        self.assertEqual(record.workspace, self.upload_workspace.workspace)
        self.assertEqual(record.managed_group, self.dcc_writer_group)
        self.assertEqual(record.current_sharing_instance, None)
        self.assertEqual(
            record.note,
            upload_workspace_audit.UploadWorkspaceSharingAudit.DCC_WRITERS_PAST_CYCLE_AFTER_QC_COMPLETE,
        )

    def test_dcc_writers_shared_as_writer_can_compute(self):
        sharing = WorkspaceGroupSharingFactory.create(
            workspace=self.upload_workspace.workspace,
            group=self.dcc_writer_group,
            access=WorkspaceGroupSharing.WRITER,
            can_compute=True,
        )
        audit = upload_workspace_audit.UploadWorkspaceSharingAudit()
        audit.audit_workspace_and_group(self.upload_workspace, self.dcc_writer_group)
        self.assertEqual(len(audit.verified), 0)
        self.assertEqual(len(audit.needs_action), 1)
        self.assertEqual(len(audit.errors), 0)
        record = audit.needs_action[0]
        self.assertIsInstance(record, workspace_sharing_audit_results.StopSharing)
        self.assertEqual(record.workspace, self.upload_workspace.workspace)
        self.assertEqual(record.managed_group, self.dcc_writer_group)
        self.assertEqual(record.current_sharing_instance, sharing)
        self.assertEqual(
            record.note,
            upload_workspace_audit.UploadWorkspaceSharingAudit.DCC_WRITERS_PAST_CYCLE_AFTER_QC_COMPLETE,
        )

    def test_dcc_writers_shared_as_reader(self):
        sharing = WorkspaceGroupSharingFactory.create(
            workspace=self.upload_workspace.workspace, group=self.dcc_writer_group, access=WorkspaceGroupSharing.READER
        )
        audit = upload_workspace_audit.UploadWorkspaceSharingAudit()
        audit.audit_workspace_and_group(self.upload_workspace, self.dcc_writer_group)
        self.assertEqual(len(audit.verified), 0)
        self.assertEqual(len(audit.needs_action), 1)
        self.assertEqual(len(audit.errors), 0)
        record = audit.needs_action[0]
        self.assertIsInstance(record, workspace_sharing_audit_results.StopSharing)
        self.assertEqual(record.workspace, self.upload_workspace.workspace)
        self.assertEqual(record.managed_group, self.dcc_writer_group)
        self.assertEqual(record.current_sharing_instance, sharing)
        self.assertEqual(
            record.note,
            upload_workspace_audit.UploadWorkspaceSharingAudit.DCC_WRITERS_PAST_CYCLE_AFTER_QC_COMPLETE,
        )

    def test_dcc_writers_shared_as_owner(self):
        sharing = WorkspaceGroupSharingFactory.create(
            workspace=self.upload_workspace.workspace, group=self.dcc_writer_group, access=WorkspaceGroupSharing.OWNER
        )
        audit = upload_workspace_audit.UploadWorkspaceSharingAudit()
        audit.audit_workspace_and_group(self.upload_workspace, self.dcc_writer_group)
        self.assertEqual(len(audit.verified), 0)
        self.assertEqual(len(audit.needs_action), 0)
        self.assertEqual(len(audit.errors), 1)
        record = audit.errors[0]
        self.assertIsInstance(record, workspace_sharing_audit_results.StopSharing)
        self.assertEqual(record.workspace, self.upload_workspace.workspace)
        self.assertEqual(record.managed_group, self.dcc_writer_group)
        self.assertEqual(record.current_sharing_instance, sharing)
        self.assertEqual(
            record.note,
            upload_workspace_audit.UploadWorkspaceSharingAudit.DCC_WRITERS_PAST_CYCLE_AFTER_QC_COMPLETE,
        )

    def test_auth_domain_shared_as_writer_no_compute(self):
        # Share the workspace with the group.
        sharing = WorkspaceGroupSharingFactory.create(
            workspace=self.upload_workspace.workspace, group=self.auth_domain, access=WorkspaceGroupSharing.WRITER
        )
        audit = upload_workspace_audit.UploadWorkspaceSharingAudit()
        audit.audit_workspace_and_group(self.upload_workspace, self.auth_domain)
        self.assertEqual(len(audit.verified), 0)
        self.assertEqual(len(audit.needs_action), 1)
        self.assertEqual(len(audit.errors), 0)
        record = audit.needs_action[0]
        self.assertIsInstance(record, workspace_sharing_audit_results.ShareAsReader)
        self.assertEqual(record.workspace, self.upload_workspace.workspace)
        self.assertEqual(record.managed_group, self.auth_domain)
        self.assertEqual(record.current_sharing_instance, sharing)
        self.assertEqual(record.note, upload_workspace_audit.UploadWorkspaceSharingAudit.AUTH_DOMAIN_AS_READER)

    def test_auth_domain_not_shared(self):
        audit = upload_workspace_audit.UploadWorkspaceSharingAudit()
        audit.audit_workspace_and_group(self.upload_workspace, self.auth_domain)
        self.assertEqual(len(audit.verified), 0)
        self.assertEqual(len(audit.needs_action), 1)
        self.assertEqual(len(audit.errors), 0)
        record = audit.needs_action[0]
        self.assertIsInstance(record, workspace_sharing_audit_results.ShareAsReader)
        self.assertEqual(record.workspace, self.upload_workspace.workspace)
        self.assertEqual(record.managed_group, self.auth_domain)
        self.assertEqual(record.current_sharing_instance, None)
        self.assertEqual(record.note, upload_workspace_audit.UploadWorkspaceSharingAudit.AUTH_DOMAIN_AS_READER)

    def test_auth_domain_shared_as_writer_can_compute(self):
        sharing = WorkspaceGroupSharingFactory.create(
            workspace=self.upload_workspace.workspace,
            group=self.auth_domain,
            access=WorkspaceGroupSharing.WRITER,
            can_compute=True,
        )
        audit = upload_workspace_audit.UploadWorkspaceSharingAudit()
        audit.audit_workspace_and_group(self.upload_workspace, self.auth_domain)
        self.assertEqual(len(audit.verified), 0)
        self.assertEqual(len(audit.needs_action), 1)
        self.assertEqual(len(audit.errors), 0)
        record = audit.needs_action[0]
        self.assertIsInstance(record, workspace_sharing_audit_results.ShareAsReader)
        self.assertEqual(record.workspace, self.upload_workspace.workspace)
        self.assertEqual(record.managed_group, self.auth_domain)
        self.assertEqual(record.current_sharing_instance, sharing)
        self.assertEqual(record.note, upload_workspace_audit.UploadWorkspaceSharingAudit.AUTH_DOMAIN_AS_READER)

    def test_auth_domain_shared_as_reader(self):
        sharing = WorkspaceGroupSharingFactory.create(
            workspace=self.upload_workspace.workspace, group=self.auth_domain, access=WorkspaceGroupSharing.READER
        )
        audit = upload_workspace_audit.UploadWorkspaceSharingAudit()
        audit.audit_workspace_and_group(self.upload_workspace, self.auth_domain)
        self.assertEqual(len(audit.verified), 1)
        self.assertEqual(len(audit.needs_action), 0)
        self.assertEqual(len(audit.errors), 0)
        record = audit.verified[0]
        self.assertIsInstance(record, workspace_sharing_audit_results.VerifiedShared)
        self.assertEqual(record.workspace, self.upload_workspace.workspace)
        self.assertEqual(record.managed_group, self.auth_domain)
        self.assertEqual(record.current_sharing_instance, sharing)
        self.assertEqual(record.note, upload_workspace_audit.UploadWorkspaceSharingAudit.AUTH_DOMAIN_AS_READER)

    def test_auth_domain_shared_as_owner(self):
        sharing = WorkspaceGroupSharingFactory.create(
            workspace=self.upload_workspace.workspace, group=self.auth_domain, access=WorkspaceGroupSharing.OWNER
        )
        audit = upload_workspace_audit.UploadWorkspaceSharingAudit()
        audit.audit_workspace_and_group(self.upload_workspace, self.auth_domain)
        self.assertEqual(len(audit.verified), 0)
        self.assertEqual(len(audit.needs_action), 0)
        self.assertEqual(len(audit.errors), 1)
        record = audit.errors[0]
        self.assertIsInstance(record, workspace_sharing_audit_results.ShareAsReader)
        self.assertEqual(record.workspace, self.upload_workspace.workspace)
        self.assertEqual(record.managed_group, self.auth_domain)
        self.assertEqual(record.current_sharing_instance, sharing)
        self.assertEqual(record.note, upload_workspace_audit.UploadWorkspaceSharingAudit.AUTH_DOMAIN_AS_READER)

    def test_dcc_admin_shared_as_writer_no_compute(self):
        # Share the workspace with the group.
        sharing = WorkspaceGroupSharingFactory.create(
            workspace=self.upload_workspace.workspace, group=self.dcc_admin_group, access=WorkspaceGroupSharing.WRITER
        )
        audit = upload_workspace_audit.UploadWorkspaceSharingAudit()
        audit.audit_workspace_and_group(self.upload_workspace, self.dcc_admin_group)
        self.assertEqual(len(audit.verified), 0)
        self.assertEqual(len(audit.needs_action), 1)
        self.assertEqual(len(audit.errors), 0)
        record = audit.needs_action[0]
        self.assertIsInstance(record, workspace_sharing_audit_results.ShareAsOwner)
        self.assertEqual(record.workspace, self.upload_workspace.workspace)
        self.assertEqual(record.managed_group, self.dcc_admin_group)
        self.assertEqual(record.current_sharing_instance, sharing)
        self.assertEqual(record.note, upload_workspace_audit.UploadWorkspaceSharingAudit.DCC_ADMIN_AS_OWNER)

    def test_dcc_admin_not_shared(self):
        audit = upload_workspace_audit.UploadWorkspaceSharingAudit()
        audit.audit_workspace_and_group(self.upload_workspace, self.dcc_admin_group)
        self.assertEqual(len(audit.verified), 0)
        self.assertEqual(len(audit.needs_action), 1)
        self.assertEqual(len(audit.errors), 0)
        record = audit.needs_action[0]
        self.assertIsInstance(record, workspace_sharing_audit_results.ShareAsOwner)
        self.assertEqual(record.workspace, self.upload_workspace.workspace)
        self.assertEqual(record.managed_group, self.dcc_admin_group)
        self.assertEqual(record.current_sharing_instance, None)
        self.assertEqual(record.note, upload_workspace_audit.UploadWorkspaceSharingAudit.DCC_ADMIN_AS_OWNER)

    def test_dcc_admin_shared_as_writer_can_compute(self):
        sharing = WorkspaceGroupSharingFactory.create(
            workspace=self.upload_workspace.workspace,
            group=self.dcc_admin_group,
            access=WorkspaceGroupSharing.WRITER,
            can_compute=True,
        )
        audit = upload_workspace_audit.UploadWorkspaceSharingAudit()
        audit.audit_workspace_and_group(self.upload_workspace, self.dcc_admin_group)
        self.assertEqual(len(audit.verified), 0)
        self.assertEqual(len(audit.needs_action), 1)
        self.assertEqual(len(audit.errors), 0)
        record = audit.needs_action[0]
        self.assertIsInstance(record, workspace_sharing_audit_results.ShareAsOwner)
        self.assertEqual(record.workspace, self.upload_workspace.workspace)
        self.assertEqual(record.managed_group, self.dcc_admin_group)
        self.assertEqual(record.current_sharing_instance, sharing)
        self.assertEqual(record.note, upload_workspace_audit.UploadWorkspaceSharingAudit.DCC_ADMIN_AS_OWNER)

    def test_dcc_admin_shared_as_reader(self):
        sharing = WorkspaceGroupSharingFactory.create(
            workspace=self.upload_workspace.workspace, group=self.dcc_admin_group, access=WorkspaceGroupSharing.READER
        )
        audit = upload_workspace_audit.UploadWorkspaceSharingAudit()
        audit.audit_workspace_and_group(self.upload_workspace, self.dcc_admin_group)
        self.assertEqual(len(audit.verified), 0)
        self.assertEqual(len(audit.needs_action), 1)
        self.assertEqual(len(audit.errors), 0)
        record = audit.needs_action[0]
        self.assertIsInstance(record, workspace_sharing_audit_results.ShareAsOwner)
        self.assertEqual(record.workspace, self.upload_workspace.workspace)
        self.assertEqual(record.managed_group, self.dcc_admin_group)
        self.assertEqual(record.current_sharing_instance, sharing)
        self.assertEqual(record.note, upload_workspace_audit.UploadWorkspaceSharingAudit.DCC_ADMIN_AS_OWNER)

    def test_dcc_admin_shared_as_owner(self):
        sharing = WorkspaceGroupSharingFactory.create(
            workspace=self.upload_workspace.workspace, group=self.dcc_admin_group, access=WorkspaceGroupSharing.OWNER
        )
        audit = upload_workspace_audit.UploadWorkspaceSharingAudit()
        audit.audit_workspace_and_group(self.upload_workspace, self.dcc_admin_group)
        self.assertEqual(len(audit.verified), 1)
        self.assertEqual(len(audit.needs_action), 0)
        self.assertEqual(len(audit.errors), 0)
        record = audit.verified[0]
        self.assertIsInstance(record, workspace_sharing_audit_results.VerifiedShared)
        self.assertEqual(record.workspace, self.upload_workspace.workspace)
        self.assertEqual(record.managed_group, self.dcc_admin_group)
        self.assertEqual(record.current_sharing_instance, sharing)
        self.assertEqual(record.note, upload_workspace_audit.UploadWorkspaceSharingAudit.DCC_ADMIN_AS_OWNER)

    @override_settings(ANVIL_DCC_ADMINS_GROUP_NAME="foo")
    def test_dcc_admin_different_setting(self):
        group = ManagedGroupFactory.create(name="foo")
        sharing = WorkspaceGroupSharingFactory.create(
            workspace=self.upload_workspace.workspace, group=group, access=WorkspaceGroupSharing.OWNER
        )
        audit = upload_workspace_audit.UploadWorkspaceSharingAudit()
        audit.audit_workspace_and_group(self.upload_workspace, group)
        self.assertEqual(len(audit.verified), 1)
        self.assertEqual(len(audit.needs_action), 0)
        self.assertEqual(len(audit.errors), 0)
        record = audit.verified[0]
        self.assertIsInstance(record, workspace_sharing_audit_results.VerifiedShared)
        self.assertEqual(record.workspace, self.upload_workspace.workspace)
        self.assertEqual(record.managed_group, group)
        self.assertEqual(record.current_sharing_instance, sharing)
        self.assertEqual(record.note, upload_workspace_audit.UploadWorkspaceSharingAudit.DCC_ADMIN_AS_OWNER)

    def test_anvil_admins_shared_as_writer_no_compute(self):
        # Share the workspace with the group.
        WorkspaceGroupSharingFactory.create(
            workspace=self.upload_workspace.workspace, group=self.anvil_admins, access=WorkspaceGroupSharing.WRITER
        )
        audit = upload_workspace_audit.UploadWorkspaceSharingAudit()
        audit.audit_workspace_and_group(self.upload_workspace, self.anvil_admins)
        self.assertEqual(len(audit.verified), 0)
        self.assertEqual(len(audit.needs_action), 0)
        self.assertEqual(len(audit.errors), 0)

    def test_anvil_admins_not_shared(self):
        audit = upload_workspace_audit.UploadWorkspaceSharingAudit()
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
        audit = upload_workspace_audit.UploadWorkspaceSharingAudit()
        audit.audit_workspace_and_group(self.upload_workspace, self.anvil_admins)
        self.assertEqual(len(audit.verified), 0)
        self.assertEqual(len(audit.needs_action), 0)
        self.assertEqual(len(audit.errors), 0)

    def test_anvil_admins_shared_as_reader(self):
        WorkspaceGroupSharingFactory.create(
            workspace=self.upload_workspace.workspace, group=self.anvil_admins, access=WorkspaceGroupSharing.READER
        )
        audit = upload_workspace_audit.UploadWorkspaceSharingAudit()
        audit.audit_workspace_and_group(self.upload_workspace, self.anvil_admins)
        self.assertEqual(len(audit.verified), 0)
        self.assertEqual(len(audit.needs_action), 0)
        self.assertEqual(len(audit.errors), 0)

    def test_anvil_admins_shared_as_owner(self):
        WorkspaceGroupSharingFactory.create(
            workspace=self.upload_workspace.workspace, group=self.anvil_admins, access=WorkspaceGroupSharing.OWNER
        )
        audit = upload_workspace_audit.UploadWorkspaceSharingAudit()
        audit.audit_workspace_and_group(self.upload_workspace, self.anvil_admins)
        self.assertEqual(len(audit.verified), 0)
        self.assertEqual(len(audit.needs_action), 0)
        self.assertEqual(len(audit.errors), 0)

    def test_anvil_devs_shared_as_writer_no_compute(self):
        # Share the workspace with the group.
        WorkspaceGroupSharingFactory.create(
            workspace=self.upload_workspace.workspace, group=self.anvil_devs, access=WorkspaceGroupSharing.WRITER
        )
        audit = upload_workspace_audit.UploadWorkspaceSharingAudit()
        audit.audit_workspace_and_group(self.upload_workspace, self.anvil_devs)
        self.assertEqual(len(audit.verified), 0)
        self.assertEqual(len(audit.needs_action), 0)
        self.assertEqual(len(audit.errors), 0)

    def test_anvil_devs_not_shared(self):
        audit = upload_workspace_audit.UploadWorkspaceSharingAudit()
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
        audit = upload_workspace_audit.UploadWorkspaceSharingAudit()
        audit.audit_workspace_and_group(self.upload_workspace, self.anvil_devs)
        self.assertEqual(len(audit.verified), 0)
        self.assertEqual(len(audit.needs_action), 0)
        self.assertEqual(len(audit.errors), 0)

    def test_anvil_devs_shared_as_reader(self):
        WorkspaceGroupSharingFactory.create(
            workspace=self.upload_workspace.workspace, group=self.anvil_devs, access=WorkspaceGroupSharing.READER
        )
        audit = upload_workspace_audit.UploadWorkspaceSharingAudit()
        audit.audit_workspace_and_group(self.upload_workspace, self.anvil_devs)
        self.assertEqual(len(audit.verified), 0)
        self.assertEqual(len(audit.needs_action), 0)
        self.assertEqual(len(audit.errors), 0)

    def test_anvil_devs_shared_as_owner(self):
        WorkspaceGroupSharingFactory.create(
            workspace=self.upload_workspace.workspace, group=self.anvil_devs, access=WorkspaceGroupSharing.OWNER
        )
        audit = upload_workspace_audit.UploadWorkspaceSharingAudit()
        audit.audit_workspace_and_group(self.upload_workspace, self.anvil_devs)
        self.assertEqual(len(audit.verified), 0)
        self.assertEqual(len(audit.needs_action), 0)
        self.assertEqual(len(audit.errors), 0)

    def test_other_group_shared_as_writer_no_compute(self):
        # Share the workspace with the group.
        sharing = WorkspaceGroupSharingFactory.create(
            workspace=self.upload_workspace.workspace, group=self.other_group, access=WorkspaceGroupSharing.WRITER
        )
        audit = upload_workspace_audit.UploadWorkspaceSharingAudit()
        audit.audit_workspace_and_group(self.upload_workspace, self.other_group)
        self.assertEqual(len(audit.verified), 0)
        self.assertEqual(len(audit.needs_action), 0)
        self.assertEqual(len(audit.errors), 1)
        record = audit.errors[0]
        self.assertIsInstance(record, workspace_sharing_audit_results.StopSharing)
        self.assertEqual(record.workspace, self.upload_workspace.workspace)
        self.assertEqual(record.managed_group, self.other_group)
        self.assertEqual(record.current_sharing_instance, sharing)
        self.assertEqual(record.note, upload_workspace_audit.UploadWorkspaceSharingAudit.OTHER_GROUP_NO_ACCESS)

    def test_other_group_not_shared(self):
        audit = upload_workspace_audit.UploadWorkspaceSharingAudit()
        audit.audit_workspace_and_group(self.upload_workspace, self.other_group)
        self.assertEqual(len(audit.verified), 1)
        self.assertEqual(len(audit.needs_action), 0)
        self.assertEqual(len(audit.errors), 0)
        record = audit.verified[0]
        self.assertIsInstance(record, workspace_sharing_audit_results.VerifiedNotShared)
        self.assertEqual(record.workspace, self.upload_workspace.workspace)
        self.assertEqual(record.managed_group, self.other_group)
        self.assertEqual(record.current_sharing_instance, None)
        self.assertEqual(record.note, upload_workspace_audit.UploadWorkspaceSharingAudit.OTHER_GROUP_NO_ACCESS)

    def test_other_group_shared_as_writer_can_compute(self):
        sharing = WorkspaceGroupSharingFactory.create(
            workspace=self.upload_workspace.workspace,
            group=self.other_group,
            access=WorkspaceGroupSharing.WRITER,
            can_compute=True,
        )
        audit = upload_workspace_audit.UploadWorkspaceSharingAudit()
        audit.audit_workspace_and_group(self.upload_workspace, self.other_group)
        self.assertEqual(len(audit.verified), 0)
        self.assertEqual(len(audit.needs_action), 0)
        self.assertEqual(len(audit.errors), 1)
        record = audit.errors[0]
        self.assertIsInstance(record, workspace_sharing_audit_results.StopSharing)
        self.assertEqual(record.workspace, self.upload_workspace.workspace)
        self.assertEqual(record.managed_group, self.other_group)
        self.assertEqual(record.current_sharing_instance, sharing)
        self.assertEqual(record.note, upload_workspace_audit.UploadWorkspaceSharingAudit.OTHER_GROUP_NO_ACCESS)

    def test_other_group_shared_as_reader(self):
        sharing = WorkspaceGroupSharingFactory.create(
            workspace=self.upload_workspace.workspace, group=self.other_group, access=WorkspaceGroupSharing.READER
        )
        audit = upload_workspace_audit.UploadWorkspaceSharingAudit()
        audit.audit_workspace_and_group(self.upload_workspace, self.other_group)
        self.assertEqual(len(audit.verified), 0)
        self.assertEqual(len(audit.needs_action), 0)
        self.assertEqual(len(audit.errors), 1)
        record = audit.errors[0]
        self.assertIsInstance(record, workspace_sharing_audit_results.StopSharing)
        self.assertEqual(record.workspace, self.upload_workspace.workspace)
        self.assertEqual(record.managed_group, self.other_group)
        self.assertEqual(record.current_sharing_instance, sharing)
        self.assertEqual(record.note, upload_workspace_audit.UploadWorkspaceSharingAudit.OTHER_GROUP_NO_ACCESS)

    def test_other_group_shared_as_owner(self):
        sharing = WorkspaceGroupSharingFactory.create(
            workspace=self.upload_workspace.workspace, group=self.other_group, access=WorkspaceGroupSharing.OWNER
        )
        audit = upload_workspace_audit.UploadWorkspaceSharingAudit()
        audit.audit_workspace_and_group(self.upload_workspace, self.other_group)
        self.assertEqual(len(audit.verified), 0)
        self.assertEqual(len(audit.needs_action), 0)
        self.assertEqual(len(audit.errors), 1)
        record = audit.errors[0]
        self.assertIsInstance(record, workspace_sharing_audit_results.StopSharing)
        self.assertEqual(record.workspace, self.upload_workspace.workspace)
        self.assertEqual(record.managed_group, self.other_group)
        self.assertEqual(record.current_sharing_instance, sharing)
        self.assertEqual(record.note, upload_workspace_audit.UploadWorkspaceSharingAudit.OTHER_GROUP_NO_ACCESS)


class UploadWorkspaceSharingAuditPastCycleAfterCombinedWorkspaceSharedTest(TestCase):
    """Tests for the `UploadWorkspaceSharingAudit` class for past cycles after the combined workspace is ready to share.

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
        audit = upload_workspace_audit.UploadWorkspaceSharingAudit()
        audit.audit_workspace_and_group(self.upload_workspace, self.rc_uploader_group)
        self.assertEqual(len(audit.verified), 0)
        self.assertEqual(len(audit.needs_action), 1)
        self.assertEqual(len(audit.errors), 0)
        record = audit.needs_action[0]
        self.assertIsInstance(record, workspace_sharing_audit_results.StopSharing)
        self.assertEqual(record.workspace, self.upload_workspace.workspace)
        self.assertEqual(record.managed_group, self.rc_uploader_group)
        self.assertEqual(record.current_sharing_instance, sharing)
        self.assertEqual(
            record.note,
            upload_workspace_audit.UploadWorkspaceSharingAudit.RC_UPLOADERS_PAST_CYCLE_COMBINED_WORKSPACE_READY,
        )

    def test_uploaders_not_shared(self):
        audit = upload_workspace_audit.UploadWorkspaceSharingAudit()
        audit.audit_workspace_and_group(self.upload_workspace, self.rc_uploader_group)
        self.assertEqual(len(audit.verified), 1)
        self.assertEqual(len(audit.needs_action), 0)
        self.assertEqual(len(audit.errors), 0)
        record = audit.verified[0]
        self.assertIsInstance(record, workspace_sharing_audit_results.VerifiedNotShared)
        self.assertEqual(record.workspace, self.upload_workspace.workspace)
        self.assertEqual(record.managed_group, self.rc_uploader_group)
        self.assertEqual(record.current_sharing_instance, None)
        self.assertEqual(
            record.note,
            upload_workspace_audit.UploadWorkspaceSharingAudit.RC_UPLOADERS_PAST_CYCLE_COMBINED_WORKSPACE_READY,
        )

    def test_uploaders_shared_as_writer_can_compute(self):
        sharing = WorkspaceGroupSharingFactory.create(
            workspace=self.upload_workspace.workspace,
            group=self.rc_uploader_group,
            access=WorkspaceGroupSharing.WRITER,
            can_compute=True,
        )
        audit = upload_workspace_audit.UploadWorkspaceSharingAudit()
        audit.audit_workspace_and_group(self.upload_workspace, self.rc_uploader_group)
        self.assertEqual(len(audit.verified), 0)
        self.assertEqual(len(audit.needs_action), 1)
        self.assertEqual(len(audit.errors), 0)
        record = audit.needs_action[0]
        self.assertIsInstance(record, workspace_sharing_audit_results.StopSharing)
        self.assertEqual(record.workspace, self.upload_workspace.workspace)
        self.assertEqual(record.managed_group, self.rc_uploader_group)
        self.assertEqual(record.current_sharing_instance, sharing)
        self.assertEqual(
            record.note,
            upload_workspace_audit.UploadWorkspaceSharingAudit.RC_UPLOADERS_PAST_CYCLE_COMBINED_WORKSPACE_READY,
        )

    def test_uploaders_shared_as_reader(self):
        sharing = WorkspaceGroupSharingFactory.create(
            workspace=self.upload_workspace.workspace, group=self.rc_uploader_group, access=WorkspaceGroupSharing.READER
        )
        audit = upload_workspace_audit.UploadWorkspaceSharingAudit()
        audit.audit_workspace_and_group(self.upload_workspace, self.rc_uploader_group)
        self.assertEqual(len(audit.verified), 0)
        self.assertEqual(len(audit.needs_action), 1)
        self.assertEqual(len(audit.errors), 0)
        record = audit.needs_action[0]
        self.assertIsInstance(record, workspace_sharing_audit_results.StopSharing)
        self.assertEqual(record.workspace, self.upload_workspace.workspace)
        self.assertEqual(record.managed_group, self.rc_uploader_group)
        self.assertEqual(record.current_sharing_instance, sharing)
        self.assertEqual(
            record.note,
            upload_workspace_audit.UploadWorkspaceSharingAudit.RC_UPLOADERS_PAST_CYCLE_COMBINED_WORKSPACE_READY,
        )

    def test_uploaders_shared_as_owner(self):
        sharing = WorkspaceGroupSharingFactory.create(
            workspace=self.upload_workspace.workspace, group=self.rc_uploader_group, access=WorkspaceGroupSharing.OWNER
        )
        audit = upload_workspace_audit.UploadWorkspaceSharingAudit()
        audit.audit_workspace_and_group(self.upload_workspace, self.rc_uploader_group)
        self.assertEqual(len(audit.verified), 0)
        self.assertEqual(len(audit.needs_action), 0)
        self.assertEqual(len(audit.errors), 1)
        record = audit.errors[0]
        self.assertIsInstance(record, workspace_sharing_audit_results.StopSharing)
        self.assertEqual(record.workspace, self.upload_workspace.workspace)
        self.assertEqual(record.managed_group, self.rc_uploader_group)
        self.assertEqual(record.current_sharing_instance, sharing)
        self.assertEqual(
            record.note,
            upload_workspace_audit.UploadWorkspaceSharingAudit.RC_UPLOADERS_PAST_CYCLE_COMBINED_WORKSPACE_READY,
        )

    def test_dcc_writers_shared_as_writer_no_compute(self):
        # Share the workspace with the group.
        sharing = WorkspaceGroupSharingFactory.create(
            workspace=self.upload_workspace.workspace, group=self.dcc_writer_group, access=WorkspaceGroupSharing.WRITER
        )
        audit = upload_workspace_audit.UploadWorkspaceSharingAudit()
        audit.audit_workspace_and_group(self.upload_workspace, self.dcc_writer_group)
        self.assertEqual(len(audit.verified), 0)
        self.assertEqual(len(audit.needs_action), 1)
        self.assertEqual(len(audit.errors), 0)
        record = audit.needs_action[0]
        self.assertIsInstance(record, workspace_sharing_audit_results.StopSharing)
        self.assertEqual(record.workspace, self.upload_workspace.workspace)
        self.assertEqual(record.managed_group, self.dcc_writer_group)
        self.assertEqual(record.current_sharing_instance, sharing)
        self.assertEqual(
            record.note,
            upload_workspace_audit.UploadWorkspaceSharingAudit.DCC_WRITERS_PAST_CYCLE_COMBINED_WORKSPACE_READY,
        )

    def test_dcc_writers_not_shared(self):
        audit = upload_workspace_audit.UploadWorkspaceSharingAudit()
        audit.audit_workspace_and_group(self.upload_workspace, self.dcc_writer_group)
        self.assertEqual(len(audit.verified), 1)
        self.assertEqual(len(audit.needs_action), 0)
        self.assertEqual(len(audit.errors), 0)
        record = audit.verified[0]
        self.assertIsInstance(record, workspace_sharing_audit_results.VerifiedNotShared)
        self.assertEqual(record.workspace, self.upload_workspace.workspace)
        self.assertEqual(record.managed_group, self.dcc_writer_group)
        self.assertEqual(record.current_sharing_instance, None)
        self.assertEqual(
            record.note,
            upload_workspace_audit.UploadWorkspaceSharingAudit.DCC_WRITERS_PAST_CYCLE_COMBINED_WORKSPACE_READY,
        )

    def test_dcc_writers_shared_as_writer_can_compute(self):
        sharing = WorkspaceGroupSharingFactory.create(
            workspace=self.upload_workspace.workspace,
            group=self.dcc_writer_group,
            access=WorkspaceGroupSharing.WRITER,
            can_compute=True,
        )
        audit = upload_workspace_audit.UploadWorkspaceSharingAudit()
        audit.audit_workspace_and_group(self.upload_workspace, self.dcc_writer_group)
        self.assertEqual(len(audit.verified), 0)
        self.assertEqual(len(audit.needs_action), 1)
        self.assertEqual(len(audit.errors), 0)
        record = audit.needs_action[0]
        self.assertIsInstance(record, workspace_sharing_audit_results.StopSharing)
        self.assertEqual(record.workspace, self.upload_workspace.workspace)
        self.assertEqual(record.managed_group, self.dcc_writer_group)
        self.assertEqual(record.current_sharing_instance, sharing)
        self.assertEqual(
            record.note,
            upload_workspace_audit.UploadWorkspaceSharingAudit.DCC_WRITERS_PAST_CYCLE_COMBINED_WORKSPACE_READY,
        )

    def test_dcc_writers_shared_as_reader(self):
        sharing = WorkspaceGroupSharingFactory.create(
            workspace=self.upload_workspace.workspace, group=self.dcc_writer_group, access=WorkspaceGroupSharing.READER
        )
        audit = upload_workspace_audit.UploadWorkspaceSharingAudit()
        audit.audit_workspace_and_group(self.upload_workspace, self.dcc_writer_group)
        self.assertEqual(len(audit.verified), 0)
        self.assertEqual(len(audit.needs_action), 1)
        self.assertEqual(len(audit.errors), 0)
        record = audit.needs_action[0]
        self.assertIsInstance(record, workspace_sharing_audit_results.StopSharing)
        self.assertEqual(record.workspace, self.upload_workspace.workspace)
        self.assertEqual(record.managed_group, self.dcc_writer_group)
        self.assertEqual(record.current_sharing_instance, sharing)
        self.assertEqual(
            record.note,
            upload_workspace_audit.UploadWorkspaceSharingAudit.DCC_WRITERS_PAST_CYCLE_COMBINED_WORKSPACE_READY,
        )

    def test_dcc_writers_shared_as_owner(self):
        sharing = WorkspaceGroupSharingFactory.create(
            workspace=self.upload_workspace.workspace, group=self.dcc_writer_group, access=WorkspaceGroupSharing.OWNER
        )
        audit = upload_workspace_audit.UploadWorkspaceSharingAudit()
        audit.audit_workspace_and_group(self.upload_workspace, self.dcc_writer_group)
        self.assertEqual(len(audit.verified), 0)
        self.assertEqual(len(audit.needs_action), 0)
        self.assertEqual(len(audit.errors), 1)
        record = audit.errors[0]
        self.assertIsInstance(record, workspace_sharing_audit_results.StopSharing)
        self.assertEqual(record.workspace, self.upload_workspace.workspace)
        self.assertEqual(record.managed_group, self.dcc_writer_group)
        self.assertEqual(record.current_sharing_instance, sharing)
        self.assertEqual(
            record.note,
            upload_workspace_audit.UploadWorkspaceSharingAudit.DCC_WRITERS_PAST_CYCLE_COMBINED_WORKSPACE_READY,
        )

    def test_auth_domain_shared_as_writer_no_compute(self):
        # Share the workspace with the group.
        sharing = WorkspaceGroupSharingFactory.create(
            workspace=self.upload_workspace.workspace, group=self.auth_domain, access=WorkspaceGroupSharing.WRITER
        )
        audit = upload_workspace_audit.UploadWorkspaceSharingAudit()
        audit.audit_workspace_and_group(self.upload_workspace, self.auth_domain)
        self.assertEqual(len(audit.verified), 0)
        self.assertEqual(len(audit.needs_action), 1)
        self.assertEqual(len(audit.errors), 0)
        record = audit.needs_action[0]
        self.assertIsInstance(record, workspace_sharing_audit_results.ShareAsReader)
        self.assertEqual(record.workspace, self.upload_workspace.workspace)
        self.assertEqual(record.managed_group, self.auth_domain)
        self.assertEqual(record.current_sharing_instance, sharing)
        self.assertEqual(record.note, upload_workspace_audit.UploadWorkspaceSharingAudit.AUTH_DOMAIN_AS_READER)

    def test_auth_domain_not_shared(self):
        audit = upload_workspace_audit.UploadWorkspaceSharingAudit()
        audit.audit_workspace_and_group(self.upload_workspace, self.auth_domain)
        self.assertEqual(len(audit.verified), 0)
        self.assertEqual(len(audit.needs_action), 1)
        self.assertEqual(len(audit.errors), 0)
        record = audit.needs_action[0]
        self.assertIsInstance(record, workspace_sharing_audit_results.ShareAsReader)
        self.assertEqual(record.workspace, self.upload_workspace.workspace)
        self.assertEqual(record.managed_group, self.auth_domain)
        self.assertEqual(record.current_sharing_instance, None)
        self.assertEqual(record.note, upload_workspace_audit.UploadWorkspaceSharingAudit.AUTH_DOMAIN_AS_READER)

    def test_auth_domain_shared_as_writer_can_compute(self):
        sharing = WorkspaceGroupSharingFactory.create(
            workspace=self.upload_workspace.workspace,
            group=self.auth_domain,
            access=WorkspaceGroupSharing.WRITER,
            can_compute=True,
        )
        audit = upload_workspace_audit.UploadWorkspaceSharingAudit()
        audit.audit_workspace_and_group(self.upload_workspace, self.auth_domain)
        self.assertEqual(len(audit.verified), 0)
        self.assertEqual(len(audit.needs_action), 1)
        self.assertEqual(len(audit.errors), 0)
        record = audit.needs_action[0]
        self.assertIsInstance(record, workspace_sharing_audit_results.ShareAsReader)
        self.assertEqual(record.workspace, self.upload_workspace.workspace)
        self.assertEqual(record.managed_group, self.auth_domain)
        self.assertEqual(record.current_sharing_instance, sharing)
        self.assertEqual(record.note, upload_workspace_audit.UploadWorkspaceSharingAudit.AUTH_DOMAIN_AS_READER)

    def test_auth_domain_shared_as_reader(self):
        sharing = WorkspaceGroupSharingFactory.create(
            workspace=self.upload_workspace.workspace, group=self.auth_domain, access=WorkspaceGroupSharing.READER
        )
        audit = upload_workspace_audit.UploadWorkspaceSharingAudit()
        audit.audit_workspace_and_group(self.upload_workspace, self.auth_domain)
        self.assertEqual(len(audit.verified), 1)
        self.assertEqual(len(audit.needs_action), 0)
        self.assertEqual(len(audit.errors), 0)
        record = audit.verified[0]
        self.assertIsInstance(record, workspace_sharing_audit_results.VerifiedShared)
        self.assertEqual(record.workspace, self.upload_workspace.workspace)
        self.assertEqual(record.managed_group, self.auth_domain)
        self.assertEqual(record.current_sharing_instance, sharing)
        self.assertEqual(record.note, upload_workspace_audit.UploadWorkspaceSharingAudit.AUTH_DOMAIN_AS_READER)

    def test_auth_domain_shared_as_owner(self):
        sharing = WorkspaceGroupSharingFactory.create(
            workspace=self.upload_workspace.workspace, group=self.auth_domain, access=WorkspaceGroupSharing.OWNER
        )
        audit = upload_workspace_audit.UploadWorkspaceSharingAudit()
        audit.audit_workspace_and_group(self.upload_workspace, self.auth_domain)
        self.assertEqual(len(audit.verified), 0)
        self.assertEqual(len(audit.needs_action), 0)
        self.assertEqual(len(audit.errors), 1)
        record = audit.errors[0]
        self.assertIsInstance(record, workspace_sharing_audit_results.ShareAsReader)
        self.assertEqual(record.workspace, self.upload_workspace.workspace)
        self.assertEqual(record.managed_group, self.auth_domain)
        self.assertEqual(record.current_sharing_instance, sharing)
        self.assertEqual(record.note, upload_workspace_audit.UploadWorkspaceSharingAudit.AUTH_DOMAIN_AS_READER)

    def test_dcc_admin_shared_as_writer_no_compute(self):
        # Share the workspace with the group.
        sharing = WorkspaceGroupSharingFactory.create(
            workspace=self.upload_workspace.workspace, group=self.dcc_admin_group, access=WorkspaceGroupSharing.WRITER
        )
        audit = upload_workspace_audit.UploadWorkspaceSharingAudit()
        audit.audit_workspace_and_group(self.upload_workspace, self.dcc_admin_group)
        self.assertEqual(len(audit.verified), 0)
        self.assertEqual(len(audit.needs_action), 1)
        self.assertEqual(len(audit.errors), 0)
        record = audit.needs_action[0]
        self.assertIsInstance(record, workspace_sharing_audit_results.ShareAsOwner)
        self.assertEqual(record.workspace, self.upload_workspace.workspace)
        self.assertEqual(record.managed_group, self.dcc_admin_group)
        self.assertEqual(record.current_sharing_instance, sharing)
        self.assertEqual(record.note, upload_workspace_audit.UploadWorkspaceSharingAudit.DCC_ADMIN_AS_OWNER)

    def test_dcc_admin_not_shared(self):
        audit = upload_workspace_audit.UploadWorkspaceSharingAudit()
        audit.audit_workspace_and_group(self.upload_workspace, self.dcc_admin_group)
        self.assertEqual(len(audit.verified), 0)
        self.assertEqual(len(audit.needs_action), 1)
        self.assertEqual(len(audit.errors), 0)
        record = audit.needs_action[0]
        self.assertIsInstance(record, workspace_sharing_audit_results.ShareAsOwner)
        self.assertEqual(record.workspace, self.upload_workspace.workspace)
        self.assertEqual(record.managed_group, self.dcc_admin_group)
        self.assertEqual(record.current_sharing_instance, None)
        self.assertEqual(record.note, upload_workspace_audit.UploadWorkspaceSharingAudit.DCC_ADMIN_AS_OWNER)

    def test_dcc_admin_shared_as_writer_can_compute(self):
        sharing = WorkspaceGroupSharingFactory.create(
            workspace=self.upload_workspace.workspace,
            group=self.dcc_admin_group,
            access=WorkspaceGroupSharing.WRITER,
            can_compute=True,
        )
        audit = upload_workspace_audit.UploadWorkspaceSharingAudit()
        audit.audit_workspace_and_group(self.upload_workspace, self.dcc_admin_group)
        self.assertEqual(len(audit.verified), 0)
        self.assertEqual(len(audit.needs_action), 1)
        self.assertEqual(len(audit.errors), 0)
        record = audit.needs_action[0]
        self.assertIsInstance(record, workspace_sharing_audit_results.ShareAsOwner)
        self.assertEqual(record.workspace, self.upload_workspace.workspace)
        self.assertEqual(record.managed_group, self.dcc_admin_group)
        self.assertEqual(record.current_sharing_instance, sharing)
        self.assertEqual(record.note, upload_workspace_audit.UploadWorkspaceSharingAudit.DCC_ADMIN_AS_OWNER)

    def test_dcc_admin_shared_as_reader(self):
        sharing = WorkspaceGroupSharingFactory.create(
            workspace=self.upload_workspace.workspace, group=self.dcc_admin_group, access=WorkspaceGroupSharing.READER
        )
        audit = upload_workspace_audit.UploadWorkspaceSharingAudit()
        audit.audit_workspace_and_group(self.upload_workspace, self.dcc_admin_group)
        self.assertEqual(len(audit.verified), 0)
        self.assertEqual(len(audit.needs_action), 1)
        self.assertEqual(len(audit.errors), 0)
        record = audit.needs_action[0]
        self.assertIsInstance(record, workspace_sharing_audit_results.ShareAsOwner)
        self.assertEqual(record.workspace, self.upload_workspace.workspace)
        self.assertEqual(record.managed_group, self.dcc_admin_group)
        self.assertEqual(record.current_sharing_instance, sharing)
        self.assertEqual(record.note, upload_workspace_audit.UploadWorkspaceSharingAudit.DCC_ADMIN_AS_OWNER)

    def test_dcc_admin_shared_as_owner(self):
        sharing = WorkspaceGroupSharingFactory.create(
            workspace=self.upload_workspace.workspace, group=self.dcc_admin_group, access=WorkspaceGroupSharing.OWNER
        )
        audit = upload_workspace_audit.UploadWorkspaceSharingAudit()
        audit.audit_workspace_and_group(self.upload_workspace, self.dcc_admin_group)
        self.assertEqual(len(audit.verified), 1)
        self.assertEqual(len(audit.needs_action), 0)
        self.assertEqual(len(audit.errors), 0)
        record = audit.verified[0]
        self.assertIsInstance(record, workspace_sharing_audit_results.VerifiedShared)
        self.assertEqual(record.workspace, self.upload_workspace.workspace)
        self.assertEqual(record.managed_group, self.dcc_admin_group)
        self.assertEqual(record.current_sharing_instance, sharing)
        self.assertEqual(record.note, upload_workspace_audit.UploadWorkspaceSharingAudit.DCC_ADMIN_AS_OWNER)

    @override_settings(ANVIL_DCC_ADMINS_GROUP_NAME="foo")
    def test_dcc_admin_different_setting(self):
        group = ManagedGroupFactory.create(name="foo")
        sharing = WorkspaceGroupSharingFactory.create(
            workspace=self.upload_workspace.workspace, group=group, access=WorkspaceGroupSharing.OWNER
        )
        audit = upload_workspace_audit.UploadWorkspaceSharingAudit()
        audit.audit_workspace_and_group(self.upload_workspace, group)
        self.assertEqual(len(audit.verified), 1)
        self.assertEqual(len(audit.needs_action), 0)
        self.assertEqual(len(audit.errors), 0)
        record = audit.verified[0]
        self.assertIsInstance(record, workspace_sharing_audit_results.VerifiedShared)
        self.assertEqual(record.workspace, self.upload_workspace.workspace)
        self.assertEqual(record.managed_group, group)
        self.assertEqual(record.current_sharing_instance, sharing)
        self.assertEqual(record.note, upload_workspace_audit.UploadWorkspaceSharingAudit.DCC_ADMIN_AS_OWNER)

    def test_anvil_admins_shared_as_writer_no_compute(self):
        # Share the workspace with the group.
        WorkspaceGroupSharingFactory.create(
            workspace=self.upload_workspace.workspace, group=self.anvil_admins, access=WorkspaceGroupSharing.WRITER
        )
        audit = upload_workspace_audit.UploadWorkspaceSharingAudit()
        audit.audit_workspace_and_group(self.upload_workspace, self.anvil_admins)
        self.assertEqual(len(audit.verified), 0)
        self.assertEqual(len(audit.needs_action), 0)
        self.assertEqual(len(audit.errors), 0)

    def test_anvil_admins_not_shared(self):
        audit = upload_workspace_audit.UploadWorkspaceSharingAudit()
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
        audit = upload_workspace_audit.UploadWorkspaceSharingAudit()
        audit.audit_workspace_and_group(self.upload_workspace, self.anvil_admins)
        self.assertEqual(len(audit.verified), 0)
        self.assertEqual(len(audit.needs_action), 0)
        self.assertEqual(len(audit.errors), 0)

    def test_anvil_admins_shared_as_reader(self):
        WorkspaceGroupSharingFactory.create(
            workspace=self.upload_workspace.workspace, group=self.anvil_admins, access=WorkspaceGroupSharing.READER
        )
        audit = upload_workspace_audit.UploadWorkspaceSharingAudit()
        audit.audit_workspace_and_group(self.upload_workspace, self.anvil_admins)
        self.assertEqual(len(audit.verified), 0)
        self.assertEqual(len(audit.needs_action), 0)
        self.assertEqual(len(audit.errors), 0)

    def test_anvil_admins_shared_as_owner(self):
        WorkspaceGroupSharingFactory.create(
            workspace=self.upload_workspace.workspace, group=self.anvil_admins, access=WorkspaceGroupSharing.OWNER
        )
        audit = upload_workspace_audit.UploadWorkspaceSharingAudit()
        audit.audit_workspace_and_group(self.upload_workspace, self.anvil_admins)
        self.assertEqual(len(audit.verified), 0)
        self.assertEqual(len(audit.needs_action), 0)
        self.assertEqual(len(audit.errors), 0)

    def test_anvil_devs_shared_as_writer_no_compute(self):
        # Share the workspace with the group.
        WorkspaceGroupSharingFactory.create(
            workspace=self.upload_workspace.workspace, group=self.anvil_devs, access=WorkspaceGroupSharing.WRITER
        )
        audit = upload_workspace_audit.UploadWorkspaceSharingAudit()
        audit.audit_workspace_and_group(self.upload_workspace, self.anvil_devs)
        self.assertEqual(len(audit.verified), 0)
        self.assertEqual(len(audit.needs_action), 0)
        self.assertEqual(len(audit.errors), 0)

    def test_anvil_devs_not_shared(self):
        audit = upload_workspace_audit.UploadWorkspaceSharingAudit()
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
        audit = upload_workspace_audit.UploadWorkspaceSharingAudit()
        audit.audit_workspace_and_group(self.upload_workspace, self.anvil_devs)
        self.assertEqual(len(audit.verified), 0)
        self.assertEqual(len(audit.needs_action), 0)
        self.assertEqual(len(audit.errors), 0)

    def test_anvil_devs_shared_as_reader(self):
        WorkspaceGroupSharingFactory.create(
            workspace=self.upload_workspace.workspace, group=self.anvil_devs, access=WorkspaceGroupSharing.READER
        )
        audit = upload_workspace_audit.UploadWorkspaceSharingAudit()
        audit.audit_workspace_and_group(self.upload_workspace, self.anvil_devs)
        self.assertEqual(len(audit.verified), 0)
        self.assertEqual(len(audit.needs_action), 0)
        self.assertEqual(len(audit.errors), 0)

    def test_anvil_devs_shared_as_owner(self):
        WorkspaceGroupSharingFactory.create(
            workspace=self.upload_workspace.workspace, group=self.anvil_devs, access=WorkspaceGroupSharing.OWNER
        )
        audit = upload_workspace_audit.UploadWorkspaceSharingAudit()
        audit.audit_workspace_and_group(self.upload_workspace, self.anvil_devs)
        self.assertEqual(len(audit.verified), 0)
        self.assertEqual(len(audit.needs_action), 0)
        self.assertEqual(len(audit.errors), 0)

    def test_other_group_shared_as_writer_no_compute(self):
        # Share the workspace with the group.
        sharing = WorkspaceGroupSharingFactory.create(
            workspace=self.upload_workspace.workspace, group=self.other_group, access=WorkspaceGroupSharing.WRITER
        )
        audit = upload_workspace_audit.UploadWorkspaceSharingAudit()
        audit.audit_workspace_and_group(self.upload_workspace, self.other_group)
        self.assertEqual(len(audit.verified), 0)
        self.assertEqual(len(audit.needs_action), 0)
        self.assertEqual(len(audit.errors), 1)
        record = audit.errors[0]
        self.assertIsInstance(record, workspace_sharing_audit_results.StopSharing)
        self.assertEqual(record.workspace, self.upload_workspace.workspace)
        self.assertEqual(record.managed_group, self.other_group)
        self.assertEqual(record.current_sharing_instance, sharing)
        self.assertEqual(record.note, upload_workspace_audit.UploadWorkspaceSharingAudit.OTHER_GROUP_NO_ACCESS)

    def test_other_group_not_shared(self):
        audit = upload_workspace_audit.UploadWorkspaceSharingAudit()
        audit.audit_workspace_and_group(self.upload_workspace, self.other_group)
        self.assertEqual(len(audit.verified), 1)
        self.assertEqual(len(audit.needs_action), 0)
        self.assertEqual(len(audit.errors), 0)
        record = audit.verified[0]
        self.assertIsInstance(record, workspace_sharing_audit_results.VerifiedNotShared)
        self.assertEqual(record.workspace, self.upload_workspace.workspace)
        self.assertEqual(record.managed_group, self.other_group)
        self.assertEqual(record.current_sharing_instance, None)
        self.assertEqual(record.note, upload_workspace_audit.UploadWorkspaceSharingAudit.OTHER_GROUP_NO_ACCESS)

    def test_other_group_shared_as_writer_can_compute(self):
        sharing = WorkspaceGroupSharingFactory.create(
            workspace=self.upload_workspace.workspace,
            group=self.other_group,
            access=WorkspaceGroupSharing.WRITER,
            can_compute=True,
        )
        audit = upload_workspace_audit.UploadWorkspaceSharingAudit()
        audit.audit_workspace_and_group(self.upload_workspace, self.other_group)
        self.assertEqual(len(audit.verified), 0)
        self.assertEqual(len(audit.needs_action), 0)
        self.assertEqual(len(audit.errors), 1)
        record = audit.errors[0]
        self.assertIsInstance(record, workspace_sharing_audit_results.StopSharing)
        self.assertEqual(record.workspace, self.upload_workspace.workspace)
        self.assertEqual(record.managed_group, self.other_group)
        self.assertEqual(record.current_sharing_instance, sharing)
        self.assertEqual(record.note, upload_workspace_audit.UploadWorkspaceSharingAudit.OTHER_GROUP_NO_ACCESS)

    def test_other_group_shared_as_reader(self):
        sharing = WorkspaceGroupSharingFactory.create(
            workspace=self.upload_workspace.workspace, group=self.other_group, access=WorkspaceGroupSharing.READER
        )
        audit = upload_workspace_audit.UploadWorkspaceSharingAudit()
        audit.audit_workspace_and_group(self.upload_workspace, self.other_group)
        self.assertEqual(len(audit.verified), 0)
        self.assertEqual(len(audit.needs_action), 0)
        self.assertEqual(len(audit.errors), 1)
        record = audit.errors[0]
        self.assertIsInstance(record, workspace_sharing_audit_results.StopSharing)
        self.assertEqual(record.workspace, self.upload_workspace.workspace)
        self.assertEqual(record.managed_group, self.other_group)
        self.assertEqual(record.current_sharing_instance, sharing)
        self.assertEqual(record.note, upload_workspace_audit.UploadWorkspaceSharingAudit.OTHER_GROUP_NO_ACCESS)

    def test_other_group_shared_as_owner(self):
        sharing = WorkspaceGroupSharingFactory.create(
            workspace=self.upload_workspace.workspace, group=self.other_group, access=WorkspaceGroupSharing.OWNER
        )
        audit = upload_workspace_audit.UploadWorkspaceSharingAudit()
        audit.audit_workspace_and_group(self.upload_workspace, self.other_group)
        self.assertEqual(len(audit.verified), 0)
        self.assertEqual(len(audit.needs_action), 0)
        self.assertEqual(len(audit.errors), 1)
        record = audit.errors[0]
        self.assertIsInstance(record, workspace_sharing_audit_results.StopSharing)
        self.assertEqual(record.workspace, self.upload_workspace.workspace)
        self.assertEqual(record.managed_group, self.other_group)
        self.assertEqual(record.current_sharing_instance, sharing)
        self.assertEqual(record.note, upload_workspace_audit.UploadWorkspaceSharingAudit.OTHER_GROUP_NO_ACCESS)


class UploadWorkspaceAuthDomainAuditTableTest(TestCase):
    """General tests of the UploadWorkspaceAuthDomainAuditTable class."""

    def test_no_rows(self):
        """Table works with no rows."""
        table = upload_workspace_audit.UploadWorkspaceAuthDomainAuditTable([])
        self.assertIsInstance(table, upload_workspace_audit.UploadWorkspaceAuthDomainAuditTable)
        self.assertEqual(len(table.rows), 0)

    def test_one_row(self):
        """Table works with one row."""
        upload_workspace = factories.UploadWorkspaceFactory.create()
        group = ManagedGroupFactory.create()
        GroupGroupMembershipFactory.create(
            parent_group=upload_workspace.workspace.authorization_domains.first(),
            child_group=group,
            role=GroupGroupMembership.MEMBER,
        )
        data = [
            {
                "workspace": upload_workspace.workspace,
                "managed_group": group,
                "role": GroupGroupMembership.MEMBER,
                "note": "a note",
                "action": "",
            },
        ]
        table = upload_workspace_audit.UploadWorkspaceAuthDomainAuditTable(data)
        self.assertIsInstance(table, upload_workspace_audit.UploadWorkspaceAuthDomainAuditTable)
        self.assertEqual(len(table.rows), 1)

    def test_two_rows(self):
        """Table works with two rows."""
        upload_workspace = factories.UploadWorkspaceFactory.create()
        group_1 = ManagedGroupFactory.create()
        group_2 = ManagedGroupFactory.create()
        GroupGroupMembershipFactory.create(
            parent_group=upload_workspace.workspace.authorization_domains.first(),
            child_group=group_1,
            role=GroupGroupMembership.MEMBER,
        )
        data = [
            {
                "workspace": upload_workspace.workspace,
                "managed_group": group_1,
                "role": GroupGroupMembership.MEMBER,
                "note": "a note",
                "action": "",
            },
            {
                "workspace": upload_workspace.workspace,
                "managed_group": group_2,
                "role": None,
                "note": "a note",
                "action": "",
            },
        ]
        table = upload_workspace_audit.UploadWorkspaceAuthDomainAuditTable(data)
        self.assertIsInstance(table, upload_workspace_audit.UploadWorkspaceAuthDomainAuditTable)
        self.assertEqual(len(table.rows), 2)


class UploadWorkspaceAuthDomainAuditTest(TestCase):
    """General tests of the `UploadWorkspaceAuthDomainAudit` class."""

    def test_completed(self):
        """The completed attribute is set appropriately."""
        # Instantiate the class.
        audit = upload_workspace_audit.UploadWorkspaceAuthDomainAudit()
        self.assertFalse(audit.completed)
        audit.run_audit()
        self.assertTrue(audit.completed)

    def test_no_upload_workspaces(self):
        """The audit works if there are no UploadWorkspaces."""
        audit = upload_workspace_audit.UploadWorkspaceAuthDomainAudit()
        audit.run_audit()
        self.assertEqual(len(audit.verified), 0)
        self.assertEqual(len(audit.needs_action), 0)
        self.assertEqual(len(audit.errors), 0)

    def test_one_upload_workspace_no_groups(self):
        upload_workspace = factories.UploadWorkspaceFactory.create()
        audit = upload_workspace_audit.UploadWorkspaceAuthDomainAudit()
        audit.run_audit()
        self.assertEqual(len(audit.verified), 0)
        self.assertEqual(len(audit.needs_action), 0)
        self.assertEqual(len(audit.errors), 0)
        self.assertEqual(len(audit.queryset), 1)
        self.assertIn(upload_workspace, audit.queryset)

    def test_two_upload_workspace_no_groups(self):
        upload_workspace_1 = factories.UploadWorkspaceFactory.create()
        upload_workspace_2 = factories.UploadWorkspaceFactory.create()
        audit = upload_workspace_audit.UploadWorkspaceAuthDomainAudit()
        audit.run_audit()
        self.assertEqual(len(audit.verified), 0)
        self.assertEqual(len(audit.needs_action), 0)
        self.assertEqual(len(audit.errors), 0)
        self.assertEqual(len(audit.queryset), 2)
        self.assertIn(upload_workspace_1, audit.queryset)
        self.assertIn(upload_workspace_2, audit.queryset)

    def test_one_upload_workspace_rc_member_group(self):
        group = ManagedGroupFactory.create()
        upload_workspace = factories.UploadWorkspaceFactory.create(
            research_center__member_group=group, upload_cycle__is_future=True
        )
        audit = upload_workspace_audit.UploadWorkspaceAuthDomainAudit()
        audit.run_audit()
        self.assertEqual(len(audit.verified), 1)
        self.assertEqual(len(audit.needs_action), 0)
        self.assertEqual(len(audit.errors), 0)
        record = audit.verified[0]
        self.assertIsInstance(record, workspace_auth_domain_audit_results.VerifiedNotMember)
        self.assertEqual(record.workspace, upload_workspace.workspace)
        self.assertEqual(record.managed_group, group)

    def test_one_upload_workspace_rc_upload_group(self):
        group = ManagedGroupFactory.create()
        upload_workspace = factories.UploadWorkspaceFactory.create(
            research_center__uploader_group=group, upload_cycle__is_future=True
        )
        audit = upload_workspace_audit.UploadWorkspaceAuthDomainAudit()
        audit.run_audit()
        self.assertEqual(len(audit.verified), 1)
        self.assertEqual(len(audit.needs_action), 0)
        self.assertEqual(len(audit.errors), 0)
        record = audit.verified[0]
        self.assertIsInstance(record, workspace_auth_domain_audit_results.VerifiedNotMember)
        self.assertEqual(record.workspace, upload_workspace.workspace)
        self.assertEqual(record.managed_group, group)

    def test_one_upload_workspace_rc_nonmember_group(self):
        group = ManagedGroupFactory.create()
        upload_workspace = factories.UploadWorkspaceFactory.create(
            research_center__non_member_group=group, upload_cycle__is_future=True
        )
        audit = upload_workspace_audit.UploadWorkspaceAuthDomainAudit()
        audit.run_audit()
        self.assertEqual(len(audit.verified), 1)
        self.assertEqual(len(audit.needs_action), 0)
        self.assertEqual(len(audit.errors), 0)
        record = audit.verified[0]
        self.assertIsInstance(record, workspace_auth_domain_audit_results.VerifiedNotMember)
        self.assertEqual(record.workspace, upload_workspace.workspace)
        self.assertEqual(record.managed_group, group)

    def test_one_upload_workspace_dcc_member_group(self):
        group = ManagedGroupFactory.create(name="GREGOR_DCC_MEMBERS")
        upload_workspace = factories.UploadWorkspaceFactory.create(upload_cycle__is_future=True)
        GroupGroupMembershipFactory.create(
            parent_group=upload_workspace.workspace.authorization_domains.first(), child_group=group
        )
        audit = upload_workspace_audit.UploadWorkspaceAuthDomainAudit()
        audit.run_audit()
        self.assertEqual(len(audit.verified), 1)
        self.assertEqual(len(audit.needs_action), 0)
        self.assertEqual(len(audit.errors), 0)
        record = audit.verified[0]
        self.assertIsInstance(record, workspace_auth_domain_audit_results.VerifiedMember)
        self.assertEqual(record.workspace, upload_workspace.workspace)
        self.assertEqual(record.managed_group, group)

    def test_one_upload_workspace_dcc_writer_group(self):
        group = ManagedGroupFactory.create(name="GREGOR_DCC_WRITERS")
        upload_workspace = factories.UploadWorkspaceFactory.create(upload_cycle__is_future=True)
        GroupGroupMembershipFactory.create(
            parent_group=upload_workspace.workspace.authorization_domains.first(), child_group=group
        )
        audit = upload_workspace_audit.UploadWorkspaceAuthDomainAudit()
        audit.run_audit()
        self.assertEqual(len(audit.verified), 1)
        self.assertEqual(len(audit.needs_action), 0)
        self.assertEqual(len(audit.errors), 0)
        record = audit.verified[0]
        self.assertIsInstance(record, workspace_auth_domain_audit_results.VerifiedMember)
        self.assertEqual(record.workspace, upload_workspace.workspace)
        self.assertEqual(record.managed_group, group)

    def test_one_upload_workspace_dcc_admin_group(self):
        group = ManagedGroupFactory.create(name=settings.ANVIL_DCC_ADMINS_GROUP_NAME)
        upload_workspace = factories.UploadWorkspaceFactory.create(upload_cycle__is_future=True)
        GroupGroupMembershipFactory.create(
            parent_group=upload_workspace.workspace.authorization_domains.first(),
            child_group=group,
            role=GroupGroupMembership.ADMIN,
        )
        audit = upload_workspace_audit.UploadWorkspaceAuthDomainAudit()
        audit.run_audit()
        self.assertEqual(len(audit.verified), 1)
        self.assertEqual(len(audit.needs_action), 0)
        self.assertEqual(len(audit.errors), 0)
        record = audit.verified[0]
        self.assertIsInstance(record, workspace_auth_domain_audit_results.VerifiedAdmin)
        self.assertEqual(record.workspace, upload_workspace.workspace)
        self.assertEqual(record.managed_group, group)

    @override_settings(ANVIL_DCC_ADMINS_GROUP_NAME="foo")
    def test_one_upload_workspace_dcc_admin_group_different_name(self):
        group = ManagedGroupFactory.create(name="foo")
        upload_workspace = factories.UploadWorkspaceFactory.create(upload_cycle__is_future=True)
        GroupGroupMembershipFactory.create(
            parent_group=upload_workspace.workspace.authorization_domains.first(),
            child_group=group,
            role=GroupGroupMembership.ADMIN,
        )
        audit = upload_workspace_audit.UploadWorkspaceAuthDomainAudit()
        audit.run_audit()
        self.assertEqual(len(audit.verified), 1)
        self.assertEqual(len(audit.needs_action), 0)
        self.assertEqual(len(audit.errors), 0)
        record = audit.verified[0]
        self.assertIsInstance(record, workspace_auth_domain_audit_results.VerifiedAdmin)
        self.assertEqual(record.workspace, upload_workspace.workspace)
        self.assertEqual(record.managed_group, group)

    def test_one_upload_workspace_anvil_admin_group(self):
        group = ManagedGroupFactory.create(name="anvil-admins")
        upload_workspace = factories.UploadWorkspaceFactory.create(upload_cycle__is_future=True)
        GroupGroupMembershipFactory.create(
            parent_group=upload_workspace.workspace.authorization_domains.first(),
            child_group=group,
            role=GroupGroupMembership.ADMIN,
        )
        audit = upload_workspace_audit.UploadWorkspaceAuthDomainAudit()
        audit.run_audit()
        self.assertEqual(len(audit.verified), 0)
        self.assertEqual(len(audit.needs_action), 0)
        self.assertEqual(len(audit.errors), 0)

    def test_one_upload_workspace_anvil_dev_group(self):
        group = ManagedGroupFactory.create(name="anvil_devs")
        upload_workspace = factories.UploadWorkspaceFactory.create(upload_cycle__is_future=True)
        GroupGroupMembershipFactory.create(
            parent_group=upload_workspace.workspace.authorization_domains.first(),
            child_group=group,
            role=GroupGroupMembership.ADMIN,
        )
        audit = upload_workspace_audit.UploadWorkspaceAuthDomainAudit()
        audit.run_audit()
        self.assertEqual(len(audit.verified), 0)
        self.assertEqual(len(audit.needs_action), 0)
        self.assertEqual(len(audit.errors), 0)

    def test_one_upload_workspace_gregor_all_group(self):
        group = ManagedGroupFactory.create(name="GREGOR_ALL")
        upload_workspace = factories.UploadWorkspaceFactory.create(upload_cycle__is_future=True)
        audit = upload_workspace_audit.UploadWorkspaceAuthDomainAudit()
        audit.run_audit()
        self.assertEqual(len(audit.verified), 1)
        self.assertEqual(len(audit.needs_action), 0)
        self.assertEqual(len(audit.errors), 0)
        record = audit.verified[0]
        self.assertIsInstance(record, workspace_auth_domain_audit_results.VerifiedNotMember)
        self.assertEqual(record.workspace, upload_workspace.workspace)
        self.assertEqual(record.managed_group, group)

    def test_one_upload_workspace_other_group_member(self):
        group = ManagedGroupFactory.create(name="foo")
        upload_workspace = factories.UploadWorkspaceFactory.create(upload_cycle__is_future=True)
        GroupGroupMembershipFactory.create(
            parent_group=upload_workspace.workspace.authorization_domains.first(),
            child_group=group,
            role=GroupGroupMembership.ADMIN,
        )
        audit = upload_workspace_audit.UploadWorkspaceAuthDomainAudit()
        audit.run_audit()
        self.assertEqual(len(audit.verified), 0)
        self.assertEqual(len(audit.needs_action), 0)
        self.assertEqual(len(audit.errors), 1)
        record = audit.errors[0]
        self.assertIsInstance(record, workspace_auth_domain_audit_results.Remove)
        self.assertEqual(record.workspace, upload_workspace.workspace)
        self.assertEqual(record.managed_group, group)

    def test_one_upload_workspace_other_group_not_member(self):
        ManagedGroupFactory.create(name="foo")
        factories.UploadWorkspaceFactory.create(upload_cycle__is_future=True)
        audit = upload_workspace_audit.UploadWorkspaceAuthDomainAudit()
        audit.run_audit()
        self.assertEqual(len(audit.verified), 0)
        self.assertEqual(len(audit.needs_action), 0)
        self.assertEqual(len(audit.errors), 0)

    def test_two_upload_workspaces(self):
        """Audit works with two UploadWorkspaces."""
        admin_group = ManagedGroupFactory.create(name=settings.ANVIL_DCC_ADMINS_GROUP_NAME)
        upload_workspace_1 = factories.UploadWorkspaceFactory.create()
        membership = GroupGroupMembershipFactory.create(
            parent_group=upload_workspace_1.workspace.authorization_domains.first(),
            child_group=admin_group,
            role=GroupGroupMembership.ADMIN,
        )
        upload_workspace_2 = factories.UploadWorkspaceFactory.create()
        audit = upload_workspace_audit.UploadWorkspaceAuthDomainAudit()
        audit.run_audit()
        self.assertEqual(len(audit.verified), 1)
        self.assertEqual(len(audit.needs_action), 1)
        self.assertEqual(len(audit.errors), 0)
        record = audit.verified[0]
        self.assertIsInstance(record, workspace_auth_domain_audit_results.VerifiedAdmin)
        self.assertEqual(record.workspace, upload_workspace_1.workspace)
        self.assertEqual(record.managed_group, admin_group)
        self.assertEqual(record.current_membership_instance, membership)
        self.assertEqual(record.note, upload_workspace_audit.UploadWorkspaceAuthDomainAudit.DCC_ADMINS)
        record = audit.needs_action[0]
        self.assertIsInstance(record, workspace_auth_domain_audit_results.AddAdmin)
        self.assertEqual(record.workspace, upload_workspace_2.workspace)
        self.assertEqual(record.managed_group, admin_group)
        self.assertIsNone(record.current_membership_instance)
        self.assertEqual(record.note, upload_workspace_audit.UploadWorkspaceAuthDomainAudit.DCC_ADMINS)

    def test_queryset(self):
        """Audit only runs on the specified queryset of UploadWorkspaces."""
        admin_group = ManagedGroupFactory.create(name=settings.ANVIL_DCC_ADMINS_GROUP_NAME)
        upload_workspace_1 = factories.UploadWorkspaceFactory.create()
        membership = GroupGroupMembershipFactory.create(
            parent_group=upload_workspace_1.workspace.authorization_domains.first(),
            child_group=admin_group,
            role=GroupGroupMembership.ADMIN,
        )
        upload_workspace_2 = factories.UploadWorkspaceFactory.create()
        # First application
        audit = upload_workspace_audit.UploadWorkspaceAuthDomainAudit(
            queryset=models.UploadWorkspace.objects.filter(pk=upload_workspace_1.pk)
        )
        audit.run_audit()
        self.assertEqual(len(audit.verified), 1)
        self.assertEqual(len(audit.needs_action), 0)
        self.assertEqual(len(audit.errors), 0)
        record = audit.verified[0]
        self.assertIsInstance(record, workspace_auth_domain_audit_results.VerifiedAdmin)
        self.assertEqual(record.workspace, upload_workspace_1.workspace)
        self.assertEqual(record.managed_group, admin_group)
        self.assertEqual(record.current_membership_instance, membership)
        self.assertEqual(record.note, upload_workspace_audit.UploadWorkspaceAuthDomainAudit.DCC_ADMINS)
        # Second application
        audit = upload_workspace_audit.UploadWorkspaceAuthDomainAudit(
            queryset=models.UploadWorkspace.objects.filter(pk=upload_workspace_2.pk)
        )
        audit.run_audit()
        self.assertEqual(len(audit.verified), 0)
        self.assertEqual(len(audit.needs_action), 1)
        self.assertEqual(len(audit.errors), 0)
        record = audit.needs_action[0]
        self.assertIsInstance(record, workspace_auth_domain_audit_results.AddAdmin)
        self.assertEqual(record.workspace, upload_workspace_2.workspace)
        self.assertEqual(record.managed_group, admin_group)
        self.assertIsNone(record.current_membership_instance)
        self.assertEqual(record.note, upload_workspace_audit.UploadWorkspaceAuthDomainAudit.DCC_ADMINS)

    def test_queryset_wrong_class(self):
        """Raises ValueError if queryset is not a QuerySet."""
        with self.assertRaises(ValueError):
            upload_workspace_audit.UploadWorkspaceAuthDomainAudit(queryset="foo")
        with self.assertRaises(ValueError):
            upload_workspace_audit.UploadWorkspaceAuthDomainAudit(
                queryset=models.CombinedConsortiumDataWorkspace.objects.all()
            )


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
        audit = upload_workspace_audit.UploadWorkspaceAuthDomainAudit()
        audit.audit_workspace_and_group(self.upload_workspace, self.rc_uploader_group)
        self.assertEqual(len(audit.verified), 1)
        self.assertEqual(len(audit.needs_action), 0)
        self.assertEqual(len(audit.errors), 0)
        record = audit.verified[0]
        self.assertIsInstance(record, workspace_auth_domain_audit_results.VerifiedNotMember)
        self.assertEqual(record.workspace, self.upload_workspace.workspace)
        self.assertEqual(record.managed_group, self.rc_uploader_group)
        self.assertIsNone(record.current_membership_instance)
        self.assertEqual(record.note, upload_workspace_audit.UploadWorkspaceAuthDomainAudit.RC_FUTURE_CYCLE)

    def test_rc_uploaders_member(self):
        membership = GroupGroupMembershipFactory.create(
            parent_group=self.upload_workspace.workspace.authorization_domains.first(),
            child_group=self.rc_uploader_group,
            role=GroupGroupMembership.MEMBER,
        )
        audit = upload_workspace_audit.UploadWorkspaceAuthDomainAudit()
        audit.audit_workspace_and_group(self.upload_workspace, self.rc_uploader_group)
        self.assertEqual(len(audit.verified), 0)
        self.assertEqual(len(audit.needs_action), 1)
        self.assertEqual(len(audit.errors), 0)
        record = audit.needs_action[0]
        self.assertIsInstance(record, workspace_auth_domain_audit_results.Remove)
        self.assertEqual(record.workspace, self.upload_workspace.workspace)
        self.assertEqual(record.managed_group, self.rc_uploader_group)
        self.assertEqual(record.current_membership_instance, membership)
        self.assertEqual(record.note, upload_workspace_audit.UploadWorkspaceAuthDomainAudit.RC_FUTURE_CYCLE)

    def test_rc_uploaders_admin(self):
        membership = GroupGroupMembershipFactory.create(
            parent_group=self.upload_workspace.workspace.authorization_domains.first(),
            child_group=self.rc_uploader_group,
            role=GroupGroupMembership.ADMIN,
        )
        audit = upload_workspace_audit.UploadWorkspaceAuthDomainAudit()
        audit.audit_workspace_and_group(self.upload_workspace, self.rc_uploader_group)
        self.assertEqual(len(audit.verified), 0)
        self.assertEqual(len(audit.needs_action), 0)
        self.assertEqual(len(audit.errors), 1)
        record = audit.errors[0]
        self.assertIsInstance(record, workspace_auth_domain_audit_results.Remove)
        self.assertEqual(record.workspace, self.upload_workspace.workspace)
        self.assertEqual(record.managed_group, self.rc_uploader_group)
        self.assertEqual(record.current_membership_instance, membership)
        self.assertEqual(record.note, upload_workspace_audit.UploadWorkspaceAuthDomainAudit.RC_FUTURE_CYCLE)

    def test_rc_members_not_member(self):
        audit = upload_workspace_audit.UploadWorkspaceAuthDomainAudit()
        audit.audit_workspace_and_group(self.upload_workspace, self.rc_member_group)
        self.assertEqual(len(audit.verified), 1)
        self.assertEqual(len(audit.needs_action), 0)
        self.assertEqual(len(audit.errors), 0)
        record = audit.verified[0]
        self.assertIsInstance(record, workspace_auth_domain_audit_results.VerifiedNotMember)
        self.assertEqual(record.workspace, self.upload_workspace.workspace)
        self.assertEqual(record.managed_group, self.rc_member_group)
        self.assertIsNone(record.current_membership_instance)
        self.assertEqual(record.note, upload_workspace_audit.UploadWorkspaceAuthDomainAudit.RC_FUTURE_CYCLE)

    def test_rc_members_member(self):
        membership = GroupGroupMembershipFactory.create(
            parent_group=self.upload_workspace.workspace.authorization_domains.first(),
            child_group=self.rc_member_group,
            role=GroupGroupMembership.MEMBER,
        )
        audit = upload_workspace_audit.UploadWorkspaceAuthDomainAudit()
        audit.audit_workspace_and_group(self.upload_workspace, self.rc_member_group)
        self.assertEqual(len(audit.verified), 0)
        self.assertEqual(len(audit.needs_action), 1)
        self.assertEqual(len(audit.errors), 0)
        record = audit.needs_action[0]
        self.assertIsInstance(record, workspace_auth_domain_audit_results.Remove)
        self.assertEqual(record.workspace, self.upload_workspace.workspace)
        self.assertEqual(record.managed_group, self.rc_member_group)
        self.assertEqual(record.current_membership_instance, membership)
        self.assertEqual(record.note, upload_workspace_audit.UploadWorkspaceAuthDomainAudit.RC_FUTURE_CYCLE)

    def test_rc_members_admin(self):
        membership = GroupGroupMembershipFactory.create(
            parent_group=self.upload_workspace.workspace.authorization_domains.first(),
            child_group=self.rc_member_group,
            role=GroupGroupMembership.ADMIN,
        )
        audit = upload_workspace_audit.UploadWorkspaceAuthDomainAudit()
        audit.audit_workspace_and_group(self.upload_workspace, self.rc_member_group)
        self.assertEqual(len(audit.verified), 0)
        self.assertEqual(len(audit.needs_action), 0)
        self.assertEqual(len(audit.errors), 1)
        record = audit.errors[0]
        self.assertIsInstance(record, workspace_auth_domain_audit_results.Remove)
        self.assertEqual(record.workspace, self.upload_workspace.workspace)
        self.assertEqual(record.managed_group, self.rc_member_group)
        self.assertEqual(record.current_membership_instance, membership)
        self.assertEqual(record.note, upload_workspace_audit.UploadWorkspaceAuthDomainAudit.RC_FUTURE_CYCLE)

    def test_rc_non_members_not_member(self):
        audit = upload_workspace_audit.UploadWorkspaceAuthDomainAudit()
        audit.audit_workspace_and_group(self.upload_workspace, self.rc_non_member_group)
        self.assertEqual(len(audit.verified), 1)
        self.assertEqual(len(audit.needs_action), 0)
        self.assertEqual(len(audit.errors), 0)
        record = audit.verified[0]
        self.assertIsInstance(record, workspace_auth_domain_audit_results.VerifiedNotMember)
        self.assertEqual(record.workspace, self.upload_workspace.workspace)
        self.assertEqual(record.managed_group, self.rc_non_member_group)
        self.assertIsNone(record.current_membership_instance)
        self.assertEqual(record.note, upload_workspace_audit.UploadWorkspaceAuthDomainAudit.RC_FUTURE_CYCLE)

    def test_rc_non_members_member(self):
        membership = GroupGroupMembershipFactory.create(
            parent_group=self.upload_workspace.workspace.authorization_domains.first(),
            child_group=self.rc_non_member_group,
            role=GroupGroupMembership.MEMBER,
        )
        audit = upload_workspace_audit.UploadWorkspaceAuthDomainAudit()
        audit.audit_workspace_and_group(self.upload_workspace, self.rc_non_member_group)
        self.assertEqual(len(audit.verified), 0)
        self.assertEqual(len(audit.needs_action), 1)
        self.assertEqual(len(audit.errors), 0)
        record = audit.needs_action[0]
        self.assertIsInstance(record, workspace_auth_domain_audit_results.Remove)
        self.assertEqual(record.workspace, self.upload_workspace.workspace)
        self.assertEqual(record.managed_group, self.rc_non_member_group)
        self.assertEqual(record.current_membership_instance, membership)
        self.assertEqual(record.note, upload_workspace_audit.UploadWorkspaceAuthDomainAudit.RC_FUTURE_CYCLE)

    def test_rc_non_members_admin(self):
        membership = GroupGroupMembershipFactory.create(
            parent_group=self.upload_workspace.workspace.authorization_domains.first(),
            child_group=self.rc_non_member_group,
            role=GroupGroupMembership.ADMIN,
        )
        audit = upload_workspace_audit.UploadWorkspaceAuthDomainAudit()
        audit.audit_workspace_and_group(self.upload_workspace, self.rc_non_member_group)
        self.assertEqual(len(audit.verified), 0)
        self.assertEqual(len(audit.needs_action), 0)
        self.assertEqual(len(audit.errors), 1)
        record = audit.errors[0]
        self.assertIsInstance(record, workspace_auth_domain_audit_results.Remove)
        self.assertEqual(record.workspace, self.upload_workspace.workspace)
        self.assertEqual(record.managed_group, self.rc_non_member_group)
        self.assertEqual(record.current_membership_instance, membership)
        self.assertEqual(record.note, upload_workspace_audit.UploadWorkspaceAuthDomainAudit.RC_FUTURE_CYCLE)

    def test_dcc_admins_not_member(self):
        audit = upload_workspace_audit.UploadWorkspaceAuthDomainAudit()
        audit.audit_workspace_and_group(self.upload_workspace, self.dcc_admin_group)
        self.assertEqual(len(audit.verified), 0)
        self.assertEqual(len(audit.needs_action), 1)
        self.assertEqual(len(audit.errors), 0)
        record = audit.needs_action[0]
        self.assertIsInstance(record, workspace_auth_domain_audit_results.AddAdmin)
        self.assertEqual(record.workspace, self.upload_workspace.workspace)
        self.assertEqual(record.managed_group, self.dcc_admin_group)
        self.assertIsNone(record.current_membership_instance)
        self.assertEqual(record.note, upload_workspace_audit.UploadWorkspaceAuthDomainAudit.DCC_ADMINS)

    def test_dcc_admins_member(self):
        membership = GroupGroupMembershipFactory.create(
            parent_group=self.upload_workspace.workspace.authorization_domains.first(),
            child_group=self.dcc_admin_group,
            role=GroupGroupMembership.MEMBER,
        )
        audit = upload_workspace_audit.UploadWorkspaceAuthDomainAudit()
        audit.audit_workspace_and_group(self.upload_workspace, self.dcc_admin_group)
        self.assertEqual(len(audit.verified), 0)
        self.assertEqual(len(audit.needs_action), 1)
        self.assertEqual(len(audit.errors), 0)
        record = audit.needs_action[0]
        self.assertIsInstance(record, workspace_auth_domain_audit_results.ChangeToAdmin)
        self.assertEqual(record.workspace, self.upload_workspace.workspace)
        self.assertEqual(record.managed_group, self.dcc_admin_group)
        self.assertEqual(record.current_membership_instance, membership)
        self.assertEqual(record.note, upload_workspace_audit.UploadWorkspaceAuthDomainAudit.DCC_ADMINS)

    def test_dcc_admins_admin(self):
        membership = GroupGroupMembershipFactory.create(
            parent_group=self.upload_workspace.workspace.authorization_domains.first(),
            child_group=self.dcc_admin_group,
            role=GroupGroupMembership.ADMIN,
        )
        audit = upload_workspace_audit.UploadWorkspaceAuthDomainAudit()
        audit.audit_workspace_and_group(self.upload_workspace, self.dcc_admin_group)
        self.assertEqual(len(audit.verified), 1)
        self.assertEqual(len(audit.needs_action), 0)
        self.assertEqual(len(audit.errors), 0)
        record = audit.verified[0]
        self.assertIsInstance(record, workspace_auth_domain_audit_results.VerifiedAdmin)
        self.assertEqual(record.workspace, self.upload_workspace.workspace)
        self.assertEqual(record.managed_group, self.dcc_admin_group)
        self.assertEqual(record.current_membership_instance, membership)
        self.assertEqual(record.note, upload_workspace_audit.UploadWorkspaceAuthDomainAudit.DCC_ADMINS)

    @override_settings(ANVIL_DCC_ADMINS_GROUP_NAME="foobar")
    def test_dcc_admins_different_setting(self):
        group = ManagedGroupFactory.create(name="foobar")
        audit = upload_workspace_audit.UploadWorkspaceAuthDomainAudit()
        audit.audit_workspace_and_group(self.upload_workspace, group)
        self.assertEqual(len(audit.verified), 0)
        self.assertEqual(len(audit.needs_action), 1)
        self.assertEqual(len(audit.errors), 0)
        record = audit.needs_action[0]
        self.assertIsInstance(record, workspace_auth_domain_audit_results.AddAdmin)
        self.assertEqual(record.workspace, self.upload_workspace.workspace)
        self.assertEqual(record.managed_group, group)
        self.assertIsNone(record.current_membership_instance)
        self.assertEqual(record.note, upload_workspace_audit.UploadWorkspaceAuthDomainAudit.DCC_ADMINS)

    def test_dcc_writers_not_member(self):
        audit = upload_workspace_audit.UploadWorkspaceAuthDomainAudit()
        audit.audit_workspace_and_group(self.upload_workspace, self.dcc_writer_group)
        self.assertEqual(len(audit.verified), 0)
        self.assertEqual(len(audit.needs_action), 1)
        self.assertEqual(len(audit.errors), 0)
        record = audit.needs_action[0]
        self.assertIsInstance(record, workspace_auth_domain_audit_results.AddMember)
        self.assertEqual(record.workspace, self.upload_workspace.workspace)
        self.assertEqual(record.managed_group, self.dcc_writer_group)
        self.assertIsNone(record.current_membership_instance)
        self.assertEqual(record.note, upload_workspace_audit.UploadWorkspaceAuthDomainAudit.DCC_BEFORE_COMBINED)

    def test_dcc_writers_member(self):
        membership = GroupGroupMembershipFactory.create(
            parent_group=self.upload_workspace.workspace.authorization_domains.first(),
            child_group=self.dcc_writer_group,
            role=GroupGroupMembership.MEMBER,
        )
        audit = upload_workspace_audit.UploadWorkspaceAuthDomainAudit()
        audit.audit_workspace_and_group(self.upload_workspace, self.dcc_writer_group)
        self.assertEqual(len(audit.verified), 1)
        self.assertEqual(len(audit.needs_action), 0)
        self.assertEqual(len(audit.errors), 0)
        record = audit.verified[0]
        self.assertIsInstance(record, workspace_auth_domain_audit_results.VerifiedMember)
        self.assertEqual(record.workspace, self.upload_workspace.workspace)
        self.assertEqual(record.managed_group, self.dcc_writer_group)
        self.assertEqual(record.current_membership_instance, membership)
        self.assertEqual(record.note, upload_workspace_audit.UploadWorkspaceAuthDomainAudit.DCC_BEFORE_COMBINED)

    def test_dcc_writers_admin(self):
        membership = GroupGroupMembershipFactory.create(
            parent_group=self.upload_workspace.workspace.authorization_domains.first(),
            child_group=self.dcc_writer_group,
            role=GroupGroupMembership.ADMIN,
        )
        audit = upload_workspace_audit.UploadWorkspaceAuthDomainAudit()
        audit.audit_workspace_and_group(self.upload_workspace, self.dcc_writer_group)
        self.assertEqual(len(audit.verified), 0)
        self.assertEqual(len(audit.needs_action), 0)
        self.assertEqual(len(audit.errors), 1)
        record = audit.errors[0]
        self.assertIsInstance(record, workspace_auth_domain_audit_results.ChangeToMember)
        self.assertEqual(record.workspace, self.upload_workspace.workspace)
        self.assertEqual(record.managed_group, self.dcc_writer_group)
        self.assertEqual(record.current_membership_instance, membership)
        self.assertEqual(record.note, upload_workspace_audit.UploadWorkspaceAuthDomainAudit.DCC_BEFORE_COMBINED)

    def test_dcc_members_not_member(self):
        audit = upload_workspace_audit.UploadWorkspaceAuthDomainAudit()
        audit.audit_workspace_and_group(self.upload_workspace, self.dcc_member_group)
        self.assertEqual(len(audit.verified), 0)
        self.assertEqual(len(audit.needs_action), 1)
        self.assertEqual(len(audit.errors), 0)
        record = audit.needs_action[0]
        self.assertIsInstance(record, workspace_auth_domain_audit_results.AddMember)
        self.assertEqual(record.workspace, self.upload_workspace.workspace)
        self.assertEqual(record.managed_group, self.dcc_member_group)
        self.assertIsNone(record.current_membership_instance)
        self.assertEqual(record.note, upload_workspace_audit.UploadWorkspaceAuthDomainAudit.DCC_BEFORE_COMBINED)

    def test_dcc_members_member(self):
        membership = GroupGroupMembershipFactory.create(
            parent_group=self.upload_workspace.workspace.authorization_domains.first(),
            child_group=self.dcc_member_group,
            role=GroupGroupMembership.MEMBER,
        )
        audit = upload_workspace_audit.UploadWorkspaceAuthDomainAudit()
        audit.audit_workspace_and_group(self.upload_workspace, self.dcc_member_group)
        self.assertEqual(len(audit.verified), 1)
        self.assertEqual(len(audit.needs_action), 0)
        self.assertEqual(len(audit.errors), 0)
        record = audit.verified[0]
        self.assertIsInstance(record, workspace_auth_domain_audit_results.VerifiedMember)
        self.assertEqual(record.workspace, self.upload_workspace.workspace)
        self.assertEqual(record.managed_group, self.dcc_member_group)
        self.assertEqual(record.current_membership_instance, membership)
        self.assertEqual(record.note, upload_workspace_audit.UploadWorkspaceAuthDomainAudit.DCC_BEFORE_COMBINED)

    def test_dcc_members_admin(self):
        membership = GroupGroupMembershipFactory.create(
            parent_group=self.upload_workspace.workspace.authorization_domains.first(),
            child_group=self.dcc_member_group,
            role=GroupGroupMembership.ADMIN,
        )
        audit = upload_workspace_audit.UploadWorkspaceAuthDomainAudit()
        audit.audit_workspace_and_group(self.upload_workspace, self.dcc_member_group)
        self.assertEqual(len(audit.verified), 0)
        self.assertEqual(len(audit.needs_action), 0)
        self.assertEqual(len(audit.errors), 1)
        record = audit.errors[0]
        self.assertIsInstance(record, workspace_auth_domain_audit_results.ChangeToMember)
        self.assertEqual(record.workspace, self.upload_workspace.workspace)
        self.assertEqual(record.managed_group, self.dcc_member_group)
        self.assertEqual(record.current_membership_instance, membership)
        self.assertEqual(record.note, upload_workspace_audit.UploadWorkspaceAuthDomainAudit.DCC_BEFORE_COMBINED)

    def test_gregor_all_not_member(self):
        audit = upload_workspace_audit.UploadWorkspaceAuthDomainAudit()
        audit.audit_workspace_and_group(self.upload_workspace, self.gregor_all_group)
        self.assertEqual(len(audit.verified), 1)
        self.assertEqual(len(audit.needs_action), 0)
        self.assertEqual(len(audit.errors), 0)
        record = audit.verified[0]
        self.assertIsInstance(record, workspace_auth_domain_audit_results.VerifiedNotMember)
        self.assertEqual(record.workspace, self.upload_workspace.workspace)
        self.assertEqual(record.managed_group, self.gregor_all_group)
        self.assertIsNone(record.current_membership_instance)
        self.assertEqual(record.note, upload_workspace_audit.UploadWorkspaceAuthDomainAudit.GREGOR_ALL_BEFORE_COMBINED)

    def test_gregor_all_member(self):
        membership = GroupGroupMembershipFactory.create(
            parent_group=self.upload_workspace.workspace.authorization_domains.first(),
            child_group=self.gregor_all_group,
            role=GroupGroupMembership.MEMBER,
        )
        audit = upload_workspace_audit.UploadWorkspaceAuthDomainAudit()
        audit.audit_workspace_and_group(self.upload_workspace, self.gregor_all_group)
        self.assertEqual(len(audit.verified), 0)
        self.assertEqual(len(audit.needs_action), 0)
        self.assertEqual(len(audit.errors), 1)
        record = audit.errors[0]
        self.assertIsInstance(record, workspace_auth_domain_audit_results.Remove)
        self.assertEqual(record.workspace, self.upload_workspace.workspace)
        self.assertEqual(record.managed_group, self.gregor_all_group)
        self.assertEqual(record.current_membership_instance, membership)
        self.assertEqual(record.note, upload_workspace_audit.UploadWorkspaceAuthDomainAudit.GREGOR_ALL_BEFORE_COMBINED)

    def test_gregor_all_admin(self):
        membership = GroupGroupMembershipFactory.create(
            parent_group=self.upload_workspace.workspace.authorization_domains.first(),
            child_group=self.gregor_all_group,
            role=GroupGroupMembership.ADMIN,
        )
        audit = upload_workspace_audit.UploadWorkspaceAuthDomainAudit()
        audit.audit_workspace_and_group(self.upload_workspace, self.gregor_all_group)
        self.assertEqual(len(audit.verified), 0)
        self.assertEqual(len(audit.needs_action), 0)
        self.assertEqual(len(audit.errors), 1)
        record = audit.errors[0]
        self.assertIsInstance(record, workspace_auth_domain_audit_results.Remove)
        self.assertEqual(record.workspace, self.upload_workspace.workspace)
        self.assertEqual(record.managed_group, self.gregor_all_group)
        self.assertEqual(record.current_membership_instance, membership)
        self.assertEqual(record.note, upload_workspace_audit.UploadWorkspaceAuthDomainAudit.GREGOR_ALL_BEFORE_COMBINED)

    def test_other_group_not_member(self):
        audit = upload_workspace_audit.UploadWorkspaceAuthDomainAudit()
        audit.audit_workspace_and_group(self.upload_workspace, self.other_group)
        self.assertEqual(len(audit.verified), 1)
        self.assertEqual(len(audit.needs_action), 0)
        self.assertEqual(len(audit.errors), 0)
        record = audit.verified[0]
        self.assertIsInstance(record, workspace_auth_domain_audit_results.VerifiedNotMember)
        self.assertEqual(record.workspace, self.upload_workspace.workspace)
        self.assertEqual(record.managed_group, self.other_group)
        self.assertIsNone(record.current_membership_instance)
        self.assertEqual(record.note, upload_workspace_audit.UploadWorkspaceAuthDomainAudit.OTHER_GROUP)

    def test_other_group_member(self):
        membership = GroupGroupMembershipFactory.create(
            parent_group=self.upload_workspace.workspace.authorization_domains.first(),
            child_group=self.other_group,
            role=GroupGroupMembership.MEMBER,
        )
        audit = upload_workspace_audit.UploadWorkspaceAuthDomainAudit()
        audit.audit_workspace_and_group(self.upload_workspace, self.other_group)
        self.assertEqual(len(audit.verified), 0)
        self.assertEqual(len(audit.needs_action), 0)
        self.assertEqual(len(audit.errors), 1)
        record = audit.errors[0]
        self.assertIsInstance(record, workspace_auth_domain_audit_results.Remove)
        self.assertEqual(record.workspace, self.upload_workspace.workspace)
        self.assertEqual(record.managed_group, self.other_group)
        self.assertEqual(record.current_membership_instance, membership)
        self.assertEqual(record.note, upload_workspace_audit.UploadWorkspaceAuthDomainAudit.OTHER_GROUP)

    def test_other_group_admin(self):
        membership = GroupGroupMembershipFactory.create(
            parent_group=self.upload_workspace.workspace.authorization_domains.first(),
            child_group=self.other_group,
            role=GroupGroupMembership.ADMIN,
        )
        audit = upload_workspace_audit.UploadWorkspaceAuthDomainAudit()
        audit.audit_workspace_and_group(self.upload_workspace, self.other_group)
        self.assertEqual(len(audit.verified), 0)
        self.assertEqual(len(audit.needs_action), 0)
        self.assertEqual(len(audit.errors), 1)
        record = audit.errors[0]
        self.assertIsInstance(record, workspace_auth_domain_audit_results.Remove)
        self.assertEqual(record.workspace, self.upload_workspace.workspace)
        self.assertEqual(record.managed_group, self.other_group)
        self.assertEqual(record.current_membership_instance, membership)
        self.assertEqual(record.note, upload_workspace_audit.UploadWorkspaceAuthDomainAudit.OTHER_GROUP)

    def test_anvil_admins_not_member(self):
        audit = upload_workspace_audit.UploadWorkspaceAuthDomainAudit()
        audit.audit_workspace_and_group(self.upload_workspace, self.anvil_admins)
        self.assertEqual(len(audit.verified), 0)
        self.assertEqual(len(audit.needs_action), 0)
        self.assertEqual(len(audit.errors), 0)

    def test_anvil_admins_member(self):
        GroupGroupMembershipFactory.create(
            parent_group=self.upload_workspace.workspace.authorization_domains.first(),
            child_group=self.anvil_admins,
            role=GroupGroupMembership.MEMBER,
        )
        audit = upload_workspace_audit.UploadWorkspaceAuthDomainAudit()
        audit.audit_workspace_and_group(self.upload_workspace, self.anvil_admins)
        self.assertEqual(len(audit.verified), 0)
        self.assertEqual(len(audit.needs_action), 0)
        self.assertEqual(len(audit.errors), 0)

    def test_anvil_admins_admin(self):
        GroupGroupMembershipFactory.create(
            parent_group=self.upload_workspace.workspace.authorization_domains.first(),
            child_group=self.anvil_admins,
            role=GroupGroupMembership.ADMIN,
        )
        audit = upload_workspace_audit.UploadWorkspaceAuthDomainAudit()
        audit.audit_workspace_and_group(self.upload_workspace, self.anvil_admins)
        self.assertEqual(len(audit.verified), 0)
        self.assertEqual(len(audit.needs_action), 0)
        self.assertEqual(len(audit.errors), 0)

    def test_anvil_devs_not_member(self):
        audit = upload_workspace_audit.UploadWorkspaceAuthDomainAudit()
        audit.audit_workspace_and_group(self.upload_workspace, self.anvil_devs)
        self.assertEqual(len(audit.verified), 0)
        self.assertEqual(len(audit.needs_action), 0)
        self.assertEqual(len(audit.errors), 0)

    def test_anvil_devs_member(self):
        GroupGroupMembershipFactory.create(
            parent_group=self.upload_workspace.workspace.authorization_domains.first(),
            child_group=self.anvil_devs,
            role=GroupGroupMembership.MEMBER,
        )
        audit = upload_workspace_audit.UploadWorkspaceAuthDomainAudit()
        audit.audit_workspace_and_group(self.upload_workspace, self.anvil_devs)
        self.assertEqual(len(audit.verified), 0)
        self.assertEqual(len(audit.needs_action), 0)
        self.assertEqual(len(audit.errors), 0)

    def test_anvil_devs_admin(self):
        GroupGroupMembershipFactory.create(
            parent_group=self.upload_workspace.workspace.authorization_domains.first(),
            child_group=self.anvil_devs,
            role=GroupGroupMembership.ADMIN,
        )
        audit = upload_workspace_audit.UploadWorkspaceAuthDomainAudit()
        audit.audit_workspace_and_group(self.upload_workspace, self.anvil_devs)
        self.assertEqual(len(audit.verified), 0)
        self.assertEqual(len(audit.needs_action), 0)
        self.assertEqual(len(audit.errors), 0)


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
        audit = upload_workspace_audit.UploadWorkspaceAuthDomainAudit()
        audit.audit_workspace_and_group(self.upload_workspace, self.rc_uploader_group)
        self.assertEqual(len(audit.verified), 0)
        self.assertEqual(len(audit.needs_action), 1)
        self.assertEqual(len(audit.errors), 0)
        record = audit.needs_action[0]
        self.assertIsInstance(record, workspace_auth_domain_audit_results.AddMember)
        self.assertEqual(record.workspace, self.upload_workspace.workspace)
        self.assertEqual(record.managed_group, self.rc_uploader_group)
        self.assertIsNone(record.current_membership_instance)
        self.assertEqual(record.note, upload_workspace_audit.UploadWorkspaceAuthDomainAudit.RC_UPLOADERS_BEFORE_QC)

    def test_rc_uploaders_member(self):
        membership = GroupGroupMembershipFactory.create(
            parent_group=self.upload_workspace.workspace.authorization_domains.first(),
            child_group=self.rc_uploader_group,
            role=GroupGroupMembership.MEMBER,
        )
        audit = upload_workspace_audit.UploadWorkspaceAuthDomainAudit()
        audit.audit_workspace_and_group(self.upload_workspace, self.rc_uploader_group)
        self.assertEqual(len(audit.verified), 1)
        self.assertEqual(len(audit.needs_action), 0)
        self.assertEqual(len(audit.errors), 0)
        record = audit.verified[0]
        self.assertIsInstance(record, workspace_auth_domain_audit_results.VerifiedMember)
        self.assertEqual(record.workspace, self.upload_workspace.workspace)
        self.assertEqual(record.managed_group, self.rc_uploader_group)
        self.assertEqual(record.current_membership_instance, membership)
        self.assertEqual(record.note, upload_workspace_audit.UploadWorkspaceAuthDomainAudit.RC_UPLOADERS_BEFORE_QC)

    def test_rc_uploaders_admin(self):
        membership = GroupGroupMembershipFactory.create(
            parent_group=self.upload_workspace.workspace.authorization_domains.first(),
            child_group=self.rc_uploader_group,
            role=GroupGroupMembership.ADMIN,
        )
        audit = upload_workspace_audit.UploadWorkspaceAuthDomainAudit()
        audit.audit_workspace_and_group(self.upload_workspace, self.rc_uploader_group)
        self.assertEqual(len(audit.verified), 0)
        self.assertEqual(len(audit.needs_action), 0)
        self.assertEqual(len(audit.errors), 1)
        record = audit.errors[0]
        self.assertIsInstance(record, workspace_auth_domain_audit_results.ChangeToMember)
        self.assertEqual(record.workspace, self.upload_workspace.workspace)
        self.assertEqual(record.managed_group, self.rc_uploader_group)
        self.assertEqual(record.current_membership_instance, membership)
        self.assertEqual(record.note, upload_workspace_audit.UploadWorkspaceAuthDomainAudit.RC_UPLOADERS_BEFORE_QC)

    def test_rc_members_not_member(self):
        audit = upload_workspace_audit.UploadWorkspaceAuthDomainAudit()
        audit.audit_workspace_and_group(self.upload_workspace, self.rc_member_group)
        self.assertEqual(len(audit.verified), 0)
        self.assertEqual(len(audit.needs_action), 1)
        self.assertEqual(len(audit.errors), 0)
        record = audit.needs_action[0]
        self.assertIsInstance(record, workspace_auth_domain_audit_results.AddMember)
        self.assertEqual(record.workspace, self.upload_workspace.workspace)
        self.assertEqual(record.managed_group, self.rc_member_group)
        self.assertIsNone(record.current_membership_instance)
        self.assertEqual(record.note, upload_workspace_audit.UploadWorkspaceAuthDomainAudit.RC_MEMBERS_BEFORE_COMBINED)

    def test_rc_members_member(self):
        membership = GroupGroupMembershipFactory.create(
            parent_group=self.upload_workspace.workspace.authorization_domains.first(),
            child_group=self.rc_member_group,
            role=GroupGroupMembership.MEMBER,
        )
        audit = upload_workspace_audit.UploadWorkspaceAuthDomainAudit()
        audit.audit_workspace_and_group(self.upload_workspace, self.rc_member_group)
        self.assertEqual(len(audit.verified), 1)
        self.assertEqual(len(audit.needs_action), 0)
        self.assertEqual(len(audit.errors), 0)
        record = audit.verified[0]
        self.assertIsInstance(record, workspace_auth_domain_audit_results.VerifiedMember)
        self.assertEqual(record.workspace, self.upload_workspace.workspace)
        self.assertEqual(record.managed_group, self.rc_member_group)
        self.assertEqual(record.current_membership_instance, membership)
        self.assertEqual(record.note, upload_workspace_audit.UploadWorkspaceAuthDomainAudit.RC_MEMBERS_BEFORE_COMBINED)

    def test_rc_members_admin(self):
        membership = GroupGroupMembershipFactory.create(
            parent_group=self.upload_workspace.workspace.authorization_domains.first(),
            child_group=self.rc_member_group,
            role=GroupGroupMembership.ADMIN,
        )
        audit = upload_workspace_audit.UploadWorkspaceAuthDomainAudit()
        audit.audit_workspace_and_group(self.upload_workspace, self.rc_member_group)
        self.assertEqual(len(audit.verified), 0)
        self.assertEqual(len(audit.needs_action), 0)
        self.assertEqual(len(audit.errors), 1)
        record = audit.errors[0]
        self.assertIsInstance(record, workspace_auth_domain_audit_results.ChangeToMember)
        self.assertEqual(record.workspace, self.upload_workspace.workspace)
        self.assertEqual(record.managed_group, self.rc_member_group)
        self.assertEqual(record.current_membership_instance, membership)
        self.assertEqual(record.note, upload_workspace_audit.UploadWorkspaceAuthDomainAudit.RC_MEMBERS_BEFORE_COMBINED)

    def test_rc_non_members_not_member(self):
        audit = upload_workspace_audit.UploadWorkspaceAuthDomainAudit()
        audit.audit_workspace_and_group(self.upload_workspace, self.rc_non_member_group)
        self.assertEqual(len(audit.verified), 0)
        self.assertEqual(len(audit.needs_action), 1)
        self.assertEqual(len(audit.errors), 0)
        record = audit.needs_action[0]
        self.assertIsInstance(record, workspace_auth_domain_audit_results.AddMember)
        self.assertEqual(record.workspace, self.upload_workspace.workspace)
        self.assertEqual(record.managed_group, self.rc_non_member_group)
        self.assertIsNone(record.current_membership_instance)
        self.assertEqual(record.note, upload_workspace_audit.UploadWorkspaceAuthDomainAudit.RC_NON_MEMBERS_AFTER_START)

    def test_rc_non_members_member(self):
        membership = GroupGroupMembershipFactory.create(
            parent_group=self.upload_workspace.workspace.authorization_domains.first(),
            child_group=self.rc_non_member_group,
            role=GroupGroupMembership.MEMBER,
        )
        audit = upload_workspace_audit.UploadWorkspaceAuthDomainAudit()
        audit.audit_workspace_and_group(self.upload_workspace, self.rc_non_member_group)
        self.assertEqual(len(audit.verified), 1)
        self.assertEqual(len(audit.needs_action), 0)
        self.assertEqual(len(audit.errors), 0)
        record = audit.verified[0]
        self.assertIsInstance(record, workspace_auth_domain_audit_results.VerifiedMember)
        self.assertEqual(record.workspace, self.upload_workspace.workspace)
        self.assertEqual(record.managed_group, self.rc_non_member_group)
        self.assertEqual(record.current_membership_instance, membership)
        self.assertEqual(record.note, upload_workspace_audit.UploadWorkspaceAuthDomainAudit.RC_NON_MEMBERS_AFTER_START)

    def test_rc_non_members_admin(self):
        membership = GroupGroupMembershipFactory.create(
            parent_group=self.upload_workspace.workspace.authorization_domains.first(),
            child_group=self.rc_non_member_group,
            role=GroupGroupMembership.ADMIN,
        )
        audit = upload_workspace_audit.UploadWorkspaceAuthDomainAudit()
        audit.audit_workspace_and_group(self.upload_workspace, self.rc_non_member_group)
        self.assertEqual(len(audit.verified), 0)
        self.assertEqual(len(audit.needs_action), 0)
        self.assertEqual(len(audit.errors), 1)
        record = audit.errors[0]
        self.assertIsInstance(record, workspace_auth_domain_audit_results.ChangeToMember)
        self.assertEqual(record.workspace, self.upload_workspace.workspace)
        self.assertEqual(record.managed_group, self.rc_non_member_group)
        self.assertEqual(record.current_membership_instance, membership)
        self.assertEqual(record.note, upload_workspace_audit.UploadWorkspaceAuthDomainAudit.RC_NON_MEMBERS_AFTER_START)

    def test_dcc_admins_not_member(self):
        audit = upload_workspace_audit.UploadWorkspaceAuthDomainAudit()
        audit.audit_workspace_and_group(self.upload_workspace, self.dcc_admin_group)
        self.assertEqual(len(audit.verified), 0)
        self.assertEqual(len(audit.needs_action), 1)
        self.assertEqual(len(audit.errors), 0)
        record = audit.needs_action[0]
        self.assertIsInstance(record, workspace_auth_domain_audit_results.AddAdmin)
        self.assertEqual(record.workspace, self.upload_workspace.workspace)
        self.assertEqual(record.managed_group, self.dcc_admin_group)
        self.assertIsNone(record.current_membership_instance)
        self.assertEqual(record.note, upload_workspace_audit.UploadWorkspaceAuthDomainAudit.DCC_ADMINS)

    def test_dcc_admins_member(self):
        membership = GroupGroupMembershipFactory.create(
            parent_group=self.upload_workspace.workspace.authorization_domains.first(),
            child_group=self.dcc_admin_group,
            role=GroupGroupMembership.MEMBER,
        )
        audit = upload_workspace_audit.UploadWorkspaceAuthDomainAudit()
        audit.audit_workspace_and_group(self.upload_workspace, self.dcc_admin_group)
        self.assertEqual(len(audit.verified), 0)
        self.assertEqual(len(audit.needs_action), 1)
        self.assertEqual(len(audit.errors), 0)
        record = audit.needs_action[0]
        self.assertIsInstance(record, workspace_auth_domain_audit_results.ChangeToAdmin)
        self.assertEqual(record.workspace, self.upload_workspace.workspace)
        self.assertEqual(record.managed_group, self.dcc_admin_group)
        self.assertEqual(record.current_membership_instance, membership)
        self.assertEqual(record.note, upload_workspace_audit.UploadWorkspaceAuthDomainAudit.DCC_ADMINS)

    def test_dcc_admins_admin(self):
        membership = GroupGroupMembershipFactory.create(
            parent_group=self.upload_workspace.workspace.authorization_domains.first(),
            child_group=self.dcc_admin_group,
            role=GroupGroupMembership.ADMIN,
        )
        audit = upload_workspace_audit.UploadWorkspaceAuthDomainAudit()
        audit.audit_workspace_and_group(self.upload_workspace, self.dcc_admin_group)
        self.assertEqual(len(audit.verified), 1)
        self.assertEqual(len(audit.needs_action), 0)
        self.assertEqual(len(audit.errors), 0)
        record = audit.verified[0]
        self.assertIsInstance(record, workspace_auth_domain_audit_results.VerifiedAdmin)
        self.assertEqual(record.workspace, self.upload_workspace.workspace)
        self.assertEqual(record.managed_group, self.dcc_admin_group)
        self.assertEqual(record.current_membership_instance, membership)
        self.assertEqual(record.note, upload_workspace_audit.UploadWorkspaceAuthDomainAudit.DCC_ADMINS)

    @override_settings(ANVIL_DCC_ADMINS_GROUP_NAME="foobar")
    def test_dcc_admins_different_setting(self):
        group = ManagedGroupFactory.create(name="foobar")
        audit = upload_workspace_audit.UploadWorkspaceAuthDomainAudit()
        audit.audit_workspace_and_group(self.upload_workspace, group)
        self.assertEqual(len(audit.verified), 0)
        self.assertEqual(len(audit.needs_action), 1)
        self.assertEqual(len(audit.errors), 0)
        record = audit.needs_action[0]
        self.assertIsInstance(record, workspace_auth_domain_audit_results.AddAdmin)
        self.assertEqual(record.workspace, self.upload_workspace.workspace)
        self.assertEqual(record.managed_group, group)
        self.assertIsNone(record.current_membership_instance)
        self.assertEqual(record.note, upload_workspace_audit.UploadWorkspaceAuthDomainAudit.DCC_ADMINS)

    def test_dcc_writers_not_member(self):
        audit = upload_workspace_audit.UploadWorkspaceAuthDomainAudit()
        audit.audit_workspace_and_group(self.upload_workspace, self.dcc_writer_group)
        self.assertEqual(len(audit.verified), 0)
        self.assertEqual(len(audit.needs_action), 1)
        self.assertEqual(len(audit.errors), 0)
        record = audit.needs_action[0]
        self.assertIsInstance(record, workspace_auth_domain_audit_results.AddMember)
        self.assertEqual(record.workspace, self.upload_workspace.workspace)
        self.assertEqual(record.managed_group, self.dcc_writer_group)
        self.assertIsNone(record.current_membership_instance)
        self.assertEqual(record.note, upload_workspace_audit.UploadWorkspaceAuthDomainAudit.DCC_BEFORE_COMBINED)

    def test_dcc_writers_member(self):
        membership = GroupGroupMembershipFactory.create(
            parent_group=self.upload_workspace.workspace.authorization_domains.first(),
            child_group=self.dcc_writer_group,
            role=GroupGroupMembership.MEMBER,
        )
        audit = upload_workspace_audit.UploadWorkspaceAuthDomainAudit()
        audit.audit_workspace_and_group(self.upload_workspace, self.dcc_writer_group)
        self.assertEqual(len(audit.verified), 1)
        self.assertEqual(len(audit.needs_action), 0)
        self.assertEqual(len(audit.errors), 0)
        record = audit.verified[0]
        self.assertIsInstance(record, workspace_auth_domain_audit_results.VerifiedMember)
        self.assertEqual(record.workspace, self.upload_workspace.workspace)
        self.assertEqual(record.managed_group, self.dcc_writer_group)
        self.assertEqual(record.current_membership_instance, membership)
        self.assertEqual(record.note, upload_workspace_audit.UploadWorkspaceAuthDomainAudit.DCC_BEFORE_COMBINED)

    def test_dcc_writers_admin(self):
        membership = GroupGroupMembershipFactory.create(
            parent_group=self.upload_workspace.workspace.authorization_domains.first(),
            child_group=self.dcc_writer_group,
            role=GroupGroupMembership.ADMIN,
        )
        audit = upload_workspace_audit.UploadWorkspaceAuthDomainAudit()
        audit.audit_workspace_and_group(self.upload_workspace, self.dcc_writer_group)
        self.assertEqual(len(audit.verified), 0)
        self.assertEqual(len(audit.needs_action), 0)
        self.assertEqual(len(audit.errors), 1)
        record = audit.errors[0]
        self.assertIsInstance(record, workspace_auth_domain_audit_results.ChangeToMember)
        self.assertEqual(record.workspace, self.upload_workspace.workspace)
        self.assertEqual(record.managed_group, self.dcc_writer_group)
        self.assertEqual(record.current_membership_instance, membership)
        self.assertEqual(record.note, upload_workspace_audit.UploadWorkspaceAuthDomainAudit.DCC_BEFORE_COMBINED)

    def test_dcc_members_not_member(self):
        audit = upload_workspace_audit.UploadWorkspaceAuthDomainAudit()
        audit.audit_workspace_and_group(self.upload_workspace, self.dcc_member_group)
        self.assertEqual(len(audit.verified), 0)
        self.assertEqual(len(audit.needs_action), 1)
        self.assertEqual(len(audit.errors), 0)
        record = audit.needs_action[0]
        self.assertIsInstance(record, workspace_auth_domain_audit_results.AddMember)
        self.assertEqual(record.workspace, self.upload_workspace.workspace)
        self.assertEqual(record.managed_group, self.dcc_member_group)
        self.assertIsNone(record.current_membership_instance)
        self.assertEqual(record.note, upload_workspace_audit.UploadWorkspaceAuthDomainAudit.DCC_BEFORE_COMBINED)

    def test_dcc_members_member(self):
        membership = GroupGroupMembershipFactory.create(
            parent_group=self.upload_workspace.workspace.authorization_domains.first(),
            child_group=self.dcc_member_group,
            role=GroupGroupMembership.MEMBER,
        )
        audit = upload_workspace_audit.UploadWorkspaceAuthDomainAudit()
        audit.audit_workspace_and_group(self.upload_workspace, self.dcc_member_group)
        self.assertEqual(len(audit.verified), 1)
        self.assertEqual(len(audit.needs_action), 0)
        self.assertEqual(len(audit.errors), 0)
        record = audit.verified[0]
        self.assertIsInstance(record, workspace_auth_domain_audit_results.VerifiedMember)
        self.assertEqual(record.workspace, self.upload_workspace.workspace)
        self.assertEqual(record.managed_group, self.dcc_member_group)
        self.assertEqual(record.current_membership_instance, membership)
        self.assertEqual(record.note, upload_workspace_audit.UploadWorkspaceAuthDomainAudit.DCC_BEFORE_COMBINED)

    def test_dcc_members_admin(self):
        membership = GroupGroupMembershipFactory.create(
            parent_group=self.upload_workspace.workspace.authorization_domains.first(),
            child_group=self.dcc_member_group,
            role=GroupGroupMembership.ADMIN,
        )
        audit = upload_workspace_audit.UploadWorkspaceAuthDomainAudit()
        audit.audit_workspace_and_group(self.upload_workspace, self.dcc_member_group)
        self.assertEqual(len(audit.verified), 0)
        self.assertEqual(len(audit.needs_action), 0)
        self.assertEqual(len(audit.errors), 1)
        record = audit.errors[0]
        self.assertIsInstance(record, workspace_auth_domain_audit_results.ChangeToMember)
        self.assertEqual(record.workspace, self.upload_workspace.workspace)
        self.assertEqual(record.managed_group, self.dcc_member_group)
        self.assertEqual(record.current_membership_instance, membership)
        self.assertEqual(record.note, upload_workspace_audit.UploadWorkspaceAuthDomainAudit.DCC_BEFORE_COMBINED)

    def test_gregor_all_not_member(self):
        audit = upload_workspace_audit.UploadWorkspaceAuthDomainAudit()
        audit.audit_workspace_and_group(self.upload_workspace, self.gregor_all_group)
        self.assertEqual(len(audit.verified), 1)
        self.assertEqual(len(audit.needs_action), 0)
        self.assertEqual(len(audit.errors), 0)
        record = audit.verified[0]
        self.assertIsInstance(record, workspace_auth_domain_audit_results.VerifiedNotMember)
        self.assertEqual(record.workspace, self.upload_workspace.workspace)
        self.assertEqual(record.managed_group, self.gregor_all_group)
        self.assertIsNone(record.current_membership_instance)
        self.assertEqual(record.note, upload_workspace_audit.UploadWorkspaceAuthDomainAudit.GREGOR_ALL_BEFORE_COMBINED)

    def test_gregor_all_member(self):
        membership = GroupGroupMembershipFactory.create(
            parent_group=self.upload_workspace.workspace.authorization_domains.first(),
            child_group=self.gregor_all_group,
            role=GroupGroupMembership.MEMBER,
        )
        audit = upload_workspace_audit.UploadWorkspaceAuthDomainAudit()
        audit.audit_workspace_and_group(self.upload_workspace, self.gregor_all_group)
        self.assertEqual(len(audit.verified), 0)
        self.assertEqual(len(audit.needs_action), 0)
        self.assertEqual(len(audit.errors), 1)
        record = audit.errors[0]
        self.assertIsInstance(record, workspace_auth_domain_audit_results.Remove)
        self.assertEqual(record.workspace, self.upload_workspace.workspace)
        self.assertEqual(record.managed_group, self.gregor_all_group)
        self.assertEqual(record.current_membership_instance, membership)
        self.assertEqual(record.note, upload_workspace_audit.UploadWorkspaceAuthDomainAudit.GREGOR_ALL_BEFORE_COMBINED)

    def test_gregor_all_admin(self):
        membership = GroupGroupMembershipFactory.create(
            parent_group=self.upload_workspace.workspace.authorization_domains.first(),
            child_group=self.gregor_all_group,
            role=GroupGroupMembership.ADMIN,
        )
        audit = upload_workspace_audit.UploadWorkspaceAuthDomainAudit()
        audit.audit_workspace_and_group(self.upload_workspace, self.gregor_all_group)
        self.assertEqual(len(audit.verified), 0)
        self.assertEqual(len(audit.needs_action), 0)
        self.assertEqual(len(audit.errors), 1)
        record = audit.errors[0]
        self.assertIsInstance(record, workspace_auth_domain_audit_results.Remove)
        self.assertEqual(record.workspace, self.upload_workspace.workspace)
        self.assertEqual(record.managed_group, self.gregor_all_group)
        self.assertEqual(record.current_membership_instance, membership)
        self.assertEqual(record.note, upload_workspace_audit.UploadWorkspaceAuthDomainAudit.GREGOR_ALL_BEFORE_COMBINED)

    def test_other_group_not_member(self):
        audit = upload_workspace_audit.UploadWorkspaceAuthDomainAudit()
        audit.audit_workspace_and_group(self.upload_workspace, self.other_group)
        self.assertEqual(len(audit.verified), 1)
        self.assertEqual(len(audit.needs_action), 0)
        self.assertEqual(len(audit.errors), 0)
        record = audit.verified[0]
        self.assertIsInstance(record, workspace_auth_domain_audit_results.VerifiedNotMember)
        self.assertEqual(record.workspace, self.upload_workspace.workspace)
        self.assertEqual(record.managed_group, self.other_group)
        self.assertIsNone(record.current_membership_instance)
        self.assertEqual(record.note, upload_workspace_audit.UploadWorkspaceAuthDomainAudit.OTHER_GROUP)

    def test_other_group_member(self):
        membership = GroupGroupMembershipFactory.create(
            parent_group=self.upload_workspace.workspace.authorization_domains.first(),
            child_group=self.other_group,
            role=GroupGroupMembership.MEMBER,
        )
        audit = upload_workspace_audit.UploadWorkspaceAuthDomainAudit()
        audit.audit_workspace_and_group(self.upload_workspace, self.other_group)
        self.assertEqual(len(audit.verified), 0)
        self.assertEqual(len(audit.needs_action), 0)
        self.assertEqual(len(audit.errors), 1)
        record = audit.errors[0]
        self.assertIsInstance(record, workspace_auth_domain_audit_results.Remove)
        self.assertEqual(record.workspace, self.upload_workspace.workspace)
        self.assertEqual(record.managed_group, self.other_group)
        self.assertEqual(record.current_membership_instance, membership)
        self.assertEqual(record.note, upload_workspace_audit.UploadWorkspaceAuthDomainAudit.OTHER_GROUP)

    def test_other_group_admin(self):
        membership = GroupGroupMembershipFactory.create(
            parent_group=self.upload_workspace.workspace.authorization_domains.first(),
            child_group=self.other_group,
            role=GroupGroupMembership.ADMIN,
        )
        audit = upload_workspace_audit.UploadWorkspaceAuthDomainAudit()
        audit.audit_workspace_and_group(self.upload_workspace, self.other_group)
        self.assertEqual(len(audit.verified), 0)
        self.assertEqual(len(audit.needs_action), 0)
        self.assertEqual(len(audit.errors), 1)
        record = audit.errors[0]
        self.assertIsInstance(record, workspace_auth_domain_audit_results.Remove)
        self.assertEqual(record.workspace, self.upload_workspace.workspace)
        self.assertEqual(record.managed_group, self.other_group)
        self.assertEqual(record.current_membership_instance, membership)
        self.assertEqual(record.note, upload_workspace_audit.UploadWorkspaceAuthDomainAudit.OTHER_GROUP)

    def test_anvil_admins_not_member(self):
        audit = upload_workspace_audit.UploadWorkspaceAuthDomainAudit()
        audit.audit_workspace_and_group(self.upload_workspace, self.anvil_admins)
        self.assertEqual(len(audit.verified), 0)
        self.assertEqual(len(audit.needs_action), 0)
        self.assertEqual(len(audit.errors), 0)

    def test_anvil_admins_member(self):
        GroupGroupMembershipFactory.create(
            parent_group=self.upload_workspace.workspace.authorization_domains.first(),
            child_group=self.anvil_admins,
            role=GroupGroupMembership.MEMBER,
        )
        audit = upload_workspace_audit.UploadWorkspaceAuthDomainAudit()
        audit.audit_workspace_and_group(self.upload_workspace, self.anvil_admins)
        self.assertEqual(len(audit.verified), 0)
        self.assertEqual(len(audit.needs_action), 0)
        self.assertEqual(len(audit.errors), 0)

    def test_anvil_admins_admin(self):
        GroupGroupMembershipFactory.create(
            parent_group=self.upload_workspace.workspace.authorization_domains.first(),
            child_group=self.anvil_admins,
            role=GroupGroupMembership.ADMIN,
        )
        audit = upload_workspace_audit.UploadWorkspaceAuthDomainAudit()
        audit.audit_workspace_and_group(self.upload_workspace, self.anvil_admins)
        self.assertEqual(len(audit.verified), 0)
        self.assertEqual(len(audit.needs_action), 0)
        self.assertEqual(len(audit.errors), 0)

    def test_anvil_devs_not_member(self):
        audit = upload_workspace_audit.UploadWorkspaceAuthDomainAudit()
        audit.audit_workspace_and_group(self.upload_workspace, self.anvil_devs)
        self.assertEqual(len(audit.verified), 0)
        self.assertEqual(len(audit.needs_action), 0)
        self.assertEqual(len(audit.errors), 0)

    def test_anvil_devs_member(self):
        GroupGroupMembershipFactory.create(
            parent_group=self.upload_workspace.workspace.authorization_domains.first(),
            child_group=self.anvil_devs,
            role=GroupGroupMembership.MEMBER,
        )
        audit = upload_workspace_audit.UploadWorkspaceAuthDomainAudit()
        audit.audit_workspace_and_group(self.upload_workspace, self.anvil_devs)
        self.assertEqual(len(audit.verified), 0)
        self.assertEqual(len(audit.needs_action), 0)
        self.assertEqual(len(audit.errors), 0)

    def test_anvil_devs_admin(self):
        GroupGroupMembershipFactory.create(
            parent_group=self.upload_workspace.workspace.authorization_domains.first(),
            child_group=self.anvil_devs,
            role=GroupGroupMembership.ADMIN,
        )
        audit = upload_workspace_audit.UploadWorkspaceAuthDomainAudit()
        audit.audit_workspace_and_group(self.upload_workspace, self.anvil_devs)
        self.assertEqual(len(audit.verified), 0)
        self.assertEqual(len(audit.needs_action), 0)
        self.assertEqual(len(audit.errors), 0)


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
        audit = upload_workspace_audit.UploadWorkspaceAuthDomainAudit()
        audit.audit_workspace_and_group(self.upload_workspace, self.rc_uploader_group)
        self.assertEqual(len(audit.verified), 0)
        self.assertEqual(len(audit.needs_action), 1)
        self.assertEqual(len(audit.errors), 0)
        record = audit.needs_action[0]
        self.assertIsInstance(record, workspace_auth_domain_audit_results.AddMember)
        self.assertEqual(record.workspace, self.upload_workspace.workspace)
        self.assertEqual(record.managed_group, self.rc_uploader_group)
        self.assertIsNone(record.current_membership_instance)
        self.assertEqual(record.note, upload_workspace_audit.UploadWorkspaceAuthDomainAudit.RC_UPLOADERS_BEFORE_QC)

    def test_rc_uploaders_member(self):
        membership = GroupGroupMembershipFactory.create(
            parent_group=self.upload_workspace.workspace.authorization_domains.first(),
            child_group=self.rc_uploader_group,
            role=GroupGroupMembership.MEMBER,
        )
        audit = upload_workspace_audit.UploadWorkspaceAuthDomainAudit()
        audit.audit_workspace_and_group(self.upload_workspace, self.rc_uploader_group)
        self.assertEqual(len(audit.verified), 1)
        self.assertEqual(len(audit.needs_action), 0)
        self.assertEqual(len(audit.errors), 0)
        record = audit.verified[0]
        self.assertIsInstance(record, workspace_auth_domain_audit_results.VerifiedMember)
        self.assertEqual(record.workspace, self.upload_workspace.workspace)
        self.assertEqual(record.managed_group, self.rc_uploader_group)
        self.assertEqual(record.current_membership_instance, membership)
        self.assertEqual(record.note, upload_workspace_audit.UploadWorkspaceAuthDomainAudit.RC_UPLOADERS_BEFORE_QC)

    def test_rc_uploaders_admin(self):
        membership = GroupGroupMembershipFactory.create(
            parent_group=self.upload_workspace.workspace.authorization_domains.first(),
            child_group=self.rc_uploader_group,
            role=GroupGroupMembership.ADMIN,
        )
        audit = upload_workspace_audit.UploadWorkspaceAuthDomainAudit()
        audit.audit_workspace_and_group(self.upload_workspace, self.rc_uploader_group)
        self.assertEqual(len(audit.verified), 0)
        self.assertEqual(len(audit.needs_action), 0)
        self.assertEqual(len(audit.errors), 1)
        record = audit.errors[0]
        self.assertIsInstance(record, workspace_auth_domain_audit_results.ChangeToMember)
        self.assertEqual(record.workspace, self.upload_workspace.workspace)
        self.assertEqual(record.managed_group, self.rc_uploader_group)
        self.assertEqual(record.current_membership_instance, membership)
        self.assertEqual(record.note, upload_workspace_audit.UploadWorkspaceAuthDomainAudit.RC_UPLOADERS_BEFORE_QC)

    def test_rc_members_not_member(self):
        audit = upload_workspace_audit.UploadWorkspaceAuthDomainAudit()
        audit.audit_workspace_and_group(self.upload_workspace, self.rc_member_group)
        self.assertEqual(len(audit.verified), 0)
        self.assertEqual(len(audit.needs_action), 1)
        self.assertEqual(len(audit.errors), 0)
        record = audit.needs_action[0]
        self.assertIsInstance(record, workspace_auth_domain_audit_results.AddMember)
        self.assertEqual(record.workspace, self.upload_workspace.workspace)
        self.assertEqual(record.managed_group, self.rc_member_group)
        self.assertIsNone(record.current_membership_instance)
        self.assertEqual(record.note, upload_workspace_audit.UploadWorkspaceAuthDomainAudit.RC_MEMBERS_BEFORE_COMBINED)

    def test_rc_members_member(self):
        membership = GroupGroupMembershipFactory.create(
            parent_group=self.upload_workspace.workspace.authorization_domains.first(),
            child_group=self.rc_member_group,
            role=GroupGroupMembership.MEMBER,
        )
        audit = upload_workspace_audit.UploadWorkspaceAuthDomainAudit()
        audit.audit_workspace_and_group(self.upload_workspace, self.rc_member_group)
        self.assertEqual(len(audit.verified), 1)
        self.assertEqual(len(audit.needs_action), 0)
        self.assertEqual(len(audit.errors), 0)
        record = audit.verified[0]
        self.assertIsInstance(record, workspace_auth_domain_audit_results.VerifiedMember)
        self.assertEqual(record.workspace, self.upload_workspace.workspace)
        self.assertEqual(record.managed_group, self.rc_member_group)
        self.assertEqual(record.current_membership_instance, membership)
        self.assertEqual(record.note, upload_workspace_audit.UploadWorkspaceAuthDomainAudit.RC_MEMBERS_BEFORE_COMBINED)

    def test_rc_members_admin(self):
        membership = GroupGroupMembershipFactory.create(
            parent_group=self.upload_workspace.workspace.authorization_domains.first(),
            child_group=self.rc_member_group,
            role=GroupGroupMembership.ADMIN,
        )
        audit = upload_workspace_audit.UploadWorkspaceAuthDomainAudit()
        audit.audit_workspace_and_group(self.upload_workspace, self.rc_member_group)
        self.assertEqual(len(audit.verified), 0)
        self.assertEqual(len(audit.needs_action), 0)
        self.assertEqual(len(audit.errors), 1)
        record = audit.errors[0]
        self.assertIsInstance(record, workspace_auth_domain_audit_results.ChangeToMember)
        self.assertEqual(record.workspace, self.upload_workspace.workspace)
        self.assertEqual(record.managed_group, self.rc_member_group)
        self.assertEqual(record.current_membership_instance, membership)
        self.assertEqual(record.note, upload_workspace_audit.UploadWorkspaceAuthDomainAudit.RC_MEMBERS_BEFORE_COMBINED)

    def test_rc_non_members_not_member(self):
        audit = upload_workspace_audit.UploadWorkspaceAuthDomainAudit()
        audit.audit_workspace_and_group(self.upload_workspace, self.rc_non_member_group)
        self.assertEqual(len(audit.verified), 0)
        self.assertEqual(len(audit.needs_action), 1)
        self.assertEqual(len(audit.errors), 0)
        record = audit.needs_action[0]
        self.assertIsInstance(record, workspace_auth_domain_audit_results.AddMember)
        self.assertEqual(record.workspace, self.upload_workspace.workspace)
        self.assertEqual(record.managed_group, self.rc_non_member_group)
        self.assertIsNone(record.current_membership_instance)
        self.assertEqual(record.note, upload_workspace_audit.UploadWorkspaceAuthDomainAudit.RC_NON_MEMBERS_AFTER_START)

    def test_rc_non_members_member(self):
        membership = GroupGroupMembershipFactory.create(
            parent_group=self.upload_workspace.workspace.authorization_domains.first(),
            child_group=self.rc_non_member_group,
            role=GroupGroupMembership.MEMBER,
        )
        audit = upload_workspace_audit.UploadWorkspaceAuthDomainAudit()
        audit.audit_workspace_and_group(self.upload_workspace, self.rc_non_member_group)
        self.assertEqual(len(audit.verified), 1)
        self.assertEqual(len(audit.needs_action), 0)
        self.assertEqual(len(audit.errors), 0)
        record = audit.verified[0]
        self.assertIsInstance(record, workspace_auth_domain_audit_results.VerifiedMember)
        self.assertEqual(record.workspace, self.upload_workspace.workspace)
        self.assertEqual(record.managed_group, self.rc_non_member_group)
        self.assertEqual(record.current_membership_instance, membership)
        self.assertEqual(record.note, upload_workspace_audit.UploadWorkspaceAuthDomainAudit.RC_NON_MEMBERS_AFTER_START)

    def test_rc_non_members_admin(self):
        membership = GroupGroupMembershipFactory.create(
            parent_group=self.upload_workspace.workspace.authorization_domains.first(),
            child_group=self.rc_non_member_group,
            role=GroupGroupMembership.ADMIN,
        )
        audit = upload_workspace_audit.UploadWorkspaceAuthDomainAudit()
        audit.audit_workspace_and_group(self.upload_workspace, self.rc_non_member_group)
        self.assertEqual(len(audit.verified), 0)
        self.assertEqual(len(audit.needs_action), 0)
        self.assertEqual(len(audit.errors), 1)
        record = audit.errors[0]
        self.assertIsInstance(record, workspace_auth_domain_audit_results.ChangeToMember)
        self.assertEqual(record.workspace, self.upload_workspace.workspace)
        self.assertEqual(record.managed_group, self.rc_non_member_group)
        self.assertEqual(record.current_membership_instance, membership)
        self.assertEqual(record.note, upload_workspace_audit.UploadWorkspaceAuthDomainAudit.RC_NON_MEMBERS_AFTER_START)

    def test_dcc_admins_not_member(self):
        audit = upload_workspace_audit.UploadWorkspaceAuthDomainAudit()
        audit.audit_workspace_and_group(self.upload_workspace, self.dcc_admin_group)
        self.assertEqual(len(audit.verified), 0)
        self.assertEqual(len(audit.needs_action), 1)
        self.assertEqual(len(audit.errors), 0)
        record = audit.needs_action[0]
        self.assertIsInstance(record, workspace_auth_domain_audit_results.AddAdmin)
        self.assertEqual(record.workspace, self.upload_workspace.workspace)
        self.assertEqual(record.managed_group, self.dcc_admin_group)
        self.assertIsNone(record.current_membership_instance)
        self.assertEqual(record.note, upload_workspace_audit.UploadWorkspaceAuthDomainAudit.DCC_ADMINS)

    def test_dcc_admins_member(self):
        membership = GroupGroupMembershipFactory.create(
            parent_group=self.upload_workspace.workspace.authorization_domains.first(),
            child_group=self.dcc_admin_group,
            role=GroupGroupMembership.MEMBER,
        )
        audit = upload_workspace_audit.UploadWorkspaceAuthDomainAudit()
        audit.audit_workspace_and_group(self.upload_workspace, self.dcc_admin_group)
        self.assertEqual(len(audit.verified), 0)
        self.assertEqual(len(audit.needs_action), 1)
        self.assertEqual(len(audit.errors), 0)
        record = audit.needs_action[0]
        self.assertIsInstance(record, workspace_auth_domain_audit_results.ChangeToAdmin)
        self.assertEqual(record.workspace, self.upload_workspace.workspace)
        self.assertEqual(record.managed_group, self.dcc_admin_group)
        self.assertEqual(record.current_membership_instance, membership)
        self.assertEqual(record.note, upload_workspace_audit.UploadWorkspaceAuthDomainAudit.DCC_ADMINS)

    def test_dcc_admins_admin(self):
        membership = GroupGroupMembershipFactory.create(
            parent_group=self.upload_workspace.workspace.authorization_domains.first(),
            child_group=self.dcc_admin_group,
            role=GroupGroupMembership.ADMIN,
        )
        audit = upload_workspace_audit.UploadWorkspaceAuthDomainAudit()
        audit.audit_workspace_and_group(self.upload_workspace, self.dcc_admin_group)
        self.assertEqual(len(audit.verified), 1)
        self.assertEqual(len(audit.needs_action), 0)
        self.assertEqual(len(audit.errors), 0)
        record = audit.verified[0]
        self.assertIsInstance(record, workspace_auth_domain_audit_results.VerifiedAdmin)
        self.assertEqual(record.workspace, self.upload_workspace.workspace)
        self.assertEqual(record.managed_group, self.dcc_admin_group)
        self.assertEqual(record.current_membership_instance, membership)
        self.assertEqual(record.note, upload_workspace_audit.UploadWorkspaceAuthDomainAudit.DCC_ADMINS)

    @override_settings(ANVIL_DCC_ADMINS_GROUP_NAME="foobar")
    def test_dcc_admins_different_setting(self):
        group = ManagedGroupFactory.create(name="foobar")
        audit = upload_workspace_audit.UploadWorkspaceAuthDomainAudit()
        audit.audit_workspace_and_group(self.upload_workspace, group)
        self.assertEqual(len(audit.verified), 0)
        self.assertEqual(len(audit.needs_action), 1)
        self.assertEqual(len(audit.errors), 0)
        record = audit.needs_action[0]
        self.assertIsInstance(record, workspace_auth_domain_audit_results.AddAdmin)
        self.assertEqual(record.workspace, self.upload_workspace.workspace)
        self.assertEqual(record.managed_group, group)
        self.assertIsNone(record.current_membership_instance)
        self.assertEqual(record.note, upload_workspace_audit.UploadWorkspaceAuthDomainAudit.DCC_ADMINS)

    def test_dcc_writers_not_member(self):
        audit = upload_workspace_audit.UploadWorkspaceAuthDomainAudit()
        audit.audit_workspace_and_group(self.upload_workspace, self.dcc_writer_group)
        self.assertEqual(len(audit.verified), 0)
        self.assertEqual(len(audit.needs_action), 1)
        self.assertEqual(len(audit.errors), 0)
        record = audit.needs_action[0]
        self.assertIsInstance(record, workspace_auth_domain_audit_results.AddMember)
        self.assertEqual(record.workspace, self.upload_workspace.workspace)
        self.assertEqual(record.managed_group, self.dcc_writer_group)
        self.assertIsNone(record.current_membership_instance)
        self.assertEqual(record.note, upload_workspace_audit.UploadWorkspaceAuthDomainAudit.DCC_BEFORE_COMBINED)

    def test_dcc_writers_member(self):
        membership = GroupGroupMembershipFactory.create(
            parent_group=self.upload_workspace.workspace.authorization_domains.first(),
            child_group=self.dcc_writer_group,
            role=GroupGroupMembership.MEMBER,
        )
        audit = upload_workspace_audit.UploadWorkspaceAuthDomainAudit()
        audit.audit_workspace_and_group(self.upload_workspace, self.dcc_writer_group)
        self.assertEqual(len(audit.verified), 1)
        self.assertEqual(len(audit.needs_action), 0)
        self.assertEqual(len(audit.errors), 0)
        record = audit.verified[0]
        self.assertIsInstance(record, workspace_auth_domain_audit_results.VerifiedMember)
        self.assertEqual(record.workspace, self.upload_workspace.workspace)
        self.assertEqual(record.managed_group, self.dcc_writer_group)
        self.assertEqual(record.current_membership_instance, membership)
        self.assertEqual(record.note, upload_workspace_audit.UploadWorkspaceAuthDomainAudit.DCC_BEFORE_COMBINED)

    def test_dcc_writers_admin(self):
        membership = GroupGroupMembershipFactory.create(
            parent_group=self.upload_workspace.workspace.authorization_domains.first(),
            child_group=self.dcc_writer_group,
            role=GroupGroupMembership.ADMIN,
        )
        audit = upload_workspace_audit.UploadWorkspaceAuthDomainAudit()
        audit.audit_workspace_and_group(self.upload_workspace, self.dcc_writer_group)
        self.assertEqual(len(audit.verified), 0)
        self.assertEqual(len(audit.needs_action), 0)
        self.assertEqual(len(audit.errors), 1)
        record = audit.errors[0]
        self.assertIsInstance(record, workspace_auth_domain_audit_results.ChangeToMember)
        self.assertEqual(record.workspace, self.upload_workspace.workspace)
        self.assertEqual(record.managed_group, self.dcc_writer_group)
        self.assertEqual(record.current_membership_instance, membership)
        self.assertEqual(record.note, upload_workspace_audit.UploadWorkspaceAuthDomainAudit.DCC_BEFORE_COMBINED)

    def test_dcc_members_not_member(self):
        audit = upload_workspace_audit.UploadWorkspaceAuthDomainAudit()
        audit.audit_workspace_and_group(self.upload_workspace, self.dcc_member_group)
        self.assertEqual(len(audit.verified), 0)
        self.assertEqual(len(audit.needs_action), 1)
        self.assertEqual(len(audit.errors), 0)
        record = audit.needs_action[0]
        self.assertIsInstance(record, workspace_auth_domain_audit_results.AddMember)
        self.assertEqual(record.workspace, self.upload_workspace.workspace)
        self.assertEqual(record.managed_group, self.dcc_member_group)
        self.assertIsNone(record.current_membership_instance)
        self.assertEqual(record.note, upload_workspace_audit.UploadWorkspaceAuthDomainAudit.DCC_BEFORE_COMBINED)

    def test_dcc_members_member(self):
        membership = GroupGroupMembershipFactory.create(
            parent_group=self.upload_workspace.workspace.authorization_domains.first(),
            child_group=self.dcc_member_group,
            role=GroupGroupMembership.MEMBER,
        )
        audit = upload_workspace_audit.UploadWorkspaceAuthDomainAudit()
        audit.audit_workspace_and_group(self.upload_workspace, self.dcc_member_group)
        self.assertEqual(len(audit.verified), 1)
        self.assertEqual(len(audit.needs_action), 0)
        self.assertEqual(len(audit.errors), 0)
        record = audit.verified[0]
        self.assertIsInstance(record, workspace_auth_domain_audit_results.VerifiedMember)
        self.assertEqual(record.workspace, self.upload_workspace.workspace)
        self.assertEqual(record.managed_group, self.dcc_member_group)
        self.assertEqual(record.current_membership_instance, membership)
        self.assertEqual(record.note, upload_workspace_audit.UploadWorkspaceAuthDomainAudit.DCC_BEFORE_COMBINED)

    def test_dcc_members_admin(self):
        membership = GroupGroupMembershipFactory.create(
            parent_group=self.upload_workspace.workspace.authorization_domains.first(),
            child_group=self.dcc_member_group,
            role=GroupGroupMembership.ADMIN,
        )
        audit = upload_workspace_audit.UploadWorkspaceAuthDomainAudit()
        audit.audit_workspace_and_group(self.upload_workspace, self.dcc_member_group)
        self.assertEqual(len(audit.verified), 0)
        self.assertEqual(len(audit.needs_action), 0)
        self.assertEqual(len(audit.errors), 1)
        record = audit.errors[0]
        self.assertIsInstance(record, workspace_auth_domain_audit_results.ChangeToMember)
        self.assertEqual(record.workspace, self.upload_workspace.workspace)
        self.assertEqual(record.managed_group, self.dcc_member_group)
        self.assertEqual(record.current_membership_instance, membership)
        self.assertEqual(record.note, upload_workspace_audit.UploadWorkspaceAuthDomainAudit.DCC_BEFORE_COMBINED)

    def test_gregor_all_not_member(self):
        audit = upload_workspace_audit.UploadWorkspaceAuthDomainAudit()
        audit.audit_workspace_and_group(self.upload_workspace, self.gregor_all_group)
        self.assertEqual(len(audit.verified), 1)
        self.assertEqual(len(audit.needs_action), 0)
        self.assertEqual(len(audit.errors), 0)
        record = audit.verified[0]
        self.assertIsInstance(record, workspace_auth_domain_audit_results.VerifiedNotMember)
        self.assertEqual(record.workspace, self.upload_workspace.workspace)
        self.assertEqual(record.managed_group, self.gregor_all_group)
        self.assertIsNone(record.current_membership_instance)
        self.assertEqual(record.note, upload_workspace_audit.UploadWorkspaceAuthDomainAudit.GREGOR_ALL_BEFORE_COMBINED)

    def test_gregor_all_member(self):
        membership = GroupGroupMembershipFactory.create(
            parent_group=self.upload_workspace.workspace.authorization_domains.first(),
            child_group=self.gregor_all_group,
            role=GroupGroupMembership.MEMBER,
        )
        audit = upload_workspace_audit.UploadWorkspaceAuthDomainAudit()
        audit.audit_workspace_and_group(self.upload_workspace, self.gregor_all_group)
        self.assertEqual(len(audit.verified), 0)
        self.assertEqual(len(audit.needs_action), 0)
        self.assertEqual(len(audit.errors), 1)
        record = audit.errors[0]
        self.assertIsInstance(record, workspace_auth_domain_audit_results.Remove)
        self.assertEqual(record.workspace, self.upload_workspace.workspace)
        self.assertEqual(record.managed_group, self.gregor_all_group)
        self.assertEqual(record.current_membership_instance, membership)
        self.assertEqual(record.note, upload_workspace_audit.UploadWorkspaceAuthDomainAudit.GREGOR_ALL_BEFORE_COMBINED)

    def test_gregor_all_admin(self):
        membership = GroupGroupMembershipFactory.create(
            parent_group=self.upload_workspace.workspace.authorization_domains.first(),
            child_group=self.gregor_all_group,
            role=GroupGroupMembership.ADMIN,
        )
        audit = upload_workspace_audit.UploadWorkspaceAuthDomainAudit()
        audit.audit_workspace_and_group(self.upload_workspace, self.gregor_all_group)
        self.assertEqual(len(audit.verified), 0)
        self.assertEqual(len(audit.needs_action), 0)
        self.assertEqual(len(audit.errors), 1)
        record = audit.errors[0]
        self.assertIsInstance(record, workspace_auth_domain_audit_results.Remove)
        self.assertEqual(record.workspace, self.upload_workspace.workspace)
        self.assertEqual(record.managed_group, self.gregor_all_group)
        self.assertEqual(record.current_membership_instance, membership)
        self.assertEqual(record.note, upload_workspace_audit.UploadWorkspaceAuthDomainAudit.GREGOR_ALL_BEFORE_COMBINED)

    def test_other_group_not_member(self):
        audit = upload_workspace_audit.UploadWorkspaceAuthDomainAudit()
        audit.audit_workspace_and_group(self.upload_workspace, self.other_group)
        self.assertEqual(len(audit.verified), 1)
        self.assertEqual(len(audit.needs_action), 0)
        self.assertEqual(len(audit.errors), 0)
        record = audit.verified[0]
        self.assertIsInstance(record, workspace_auth_domain_audit_results.VerifiedNotMember)
        self.assertEqual(record.workspace, self.upload_workspace.workspace)
        self.assertEqual(record.managed_group, self.other_group)
        self.assertIsNone(record.current_membership_instance)
        self.assertEqual(record.note, upload_workspace_audit.UploadWorkspaceAuthDomainAudit.OTHER_GROUP)

    def test_other_group_member(self):
        membership = GroupGroupMembershipFactory.create(
            parent_group=self.upload_workspace.workspace.authorization_domains.first(),
            child_group=self.other_group,
            role=GroupGroupMembership.MEMBER,
        )
        audit = upload_workspace_audit.UploadWorkspaceAuthDomainAudit()
        audit.audit_workspace_and_group(self.upload_workspace, self.other_group)
        self.assertEqual(len(audit.verified), 0)
        self.assertEqual(len(audit.needs_action), 0)
        self.assertEqual(len(audit.errors), 1)
        record = audit.errors[0]
        self.assertIsInstance(record, workspace_auth_domain_audit_results.Remove)
        self.assertEqual(record.workspace, self.upload_workspace.workspace)
        self.assertEqual(record.managed_group, self.other_group)
        self.assertEqual(record.current_membership_instance, membership)
        self.assertEqual(record.note, upload_workspace_audit.UploadWorkspaceAuthDomainAudit.OTHER_GROUP)

    def test_other_group_admin(self):
        membership = GroupGroupMembershipFactory.create(
            parent_group=self.upload_workspace.workspace.authorization_domains.first(),
            child_group=self.other_group,
            role=GroupGroupMembership.ADMIN,
        )
        audit = upload_workspace_audit.UploadWorkspaceAuthDomainAudit()
        audit.audit_workspace_and_group(self.upload_workspace, self.other_group)
        self.assertEqual(len(audit.verified), 0)
        self.assertEqual(len(audit.needs_action), 0)
        self.assertEqual(len(audit.errors), 1)
        record = audit.errors[0]
        self.assertIsInstance(record, workspace_auth_domain_audit_results.Remove)
        self.assertEqual(record.workspace, self.upload_workspace.workspace)
        self.assertEqual(record.managed_group, self.other_group)
        self.assertEqual(record.current_membership_instance, membership)
        self.assertEqual(record.note, upload_workspace_audit.UploadWorkspaceAuthDomainAudit.OTHER_GROUP)

    def test_anvil_admins_not_member(self):
        audit = upload_workspace_audit.UploadWorkspaceAuthDomainAudit()
        audit.audit_workspace_and_group(self.upload_workspace, self.anvil_admins)
        self.assertEqual(len(audit.verified), 0)
        self.assertEqual(len(audit.needs_action), 0)
        self.assertEqual(len(audit.errors), 0)

    def test_anvil_admins_member(self):
        GroupGroupMembershipFactory.create(
            parent_group=self.upload_workspace.workspace.authorization_domains.first(),
            child_group=self.anvil_admins,
            role=GroupGroupMembership.MEMBER,
        )
        audit = upload_workspace_audit.UploadWorkspaceAuthDomainAudit()
        audit.audit_workspace_and_group(self.upload_workspace, self.anvil_admins)
        self.assertEqual(len(audit.verified), 0)
        self.assertEqual(len(audit.needs_action), 0)
        self.assertEqual(len(audit.errors), 0)

    def test_anvil_admins_admin(self):
        GroupGroupMembershipFactory.create(
            parent_group=self.upload_workspace.workspace.authorization_domains.first(),
            child_group=self.anvil_admins,
            role=GroupGroupMembership.ADMIN,
        )
        audit = upload_workspace_audit.UploadWorkspaceAuthDomainAudit()
        audit.audit_workspace_and_group(self.upload_workspace, self.anvil_admins)
        self.assertEqual(len(audit.verified), 0)
        self.assertEqual(len(audit.needs_action), 0)
        self.assertEqual(len(audit.errors), 0)

    def test_anvil_devs_not_member(self):
        audit = upload_workspace_audit.UploadWorkspaceAuthDomainAudit()
        audit.audit_workspace_and_group(self.upload_workspace, self.anvil_devs)
        self.assertEqual(len(audit.verified), 0)
        self.assertEqual(len(audit.needs_action), 0)
        self.assertEqual(len(audit.errors), 0)

    def test_anvil_devs_member(self):
        GroupGroupMembershipFactory.create(
            parent_group=self.upload_workspace.workspace.authorization_domains.first(),
            child_group=self.anvil_devs,
            role=GroupGroupMembership.MEMBER,
        )
        audit = upload_workspace_audit.UploadWorkspaceAuthDomainAudit()
        audit.audit_workspace_and_group(self.upload_workspace, self.anvil_devs)
        self.assertEqual(len(audit.verified), 0)
        self.assertEqual(len(audit.needs_action), 0)
        self.assertEqual(len(audit.errors), 0)

    def test_anvil_devs_admin(self):
        GroupGroupMembershipFactory.create(
            parent_group=self.upload_workspace.workspace.authorization_domains.first(),
            child_group=self.anvil_devs,
            role=GroupGroupMembership.ADMIN,
        )
        audit = upload_workspace_audit.UploadWorkspaceAuthDomainAudit()
        audit.audit_workspace_and_group(self.upload_workspace, self.anvil_devs)
        self.assertEqual(len(audit.verified), 0)
        self.assertEqual(len(audit.needs_action), 0)
        self.assertEqual(len(audit.errors), 0)


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
        audit = upload_workspace_audit.UploadWorkspaceAuthDomainAudit()
        audit.audit_workspace_and_group(self.upload_workspace, self.rc_uploader_group)
        self.assertEqual(len(audit.verified), 0)
        self.assertEqual(len(audit.needs_action), 1)
        self.assertEqual(len(audit.errors), 0)
        record = audit.needs_action[0]
        self.assertIsInstance(record, workspace_auth_domain_audit_results.AddMember)
        self.assertEqual(record.workspace, self.upload_workspace.workspace)
        self.assertEqual(record.managed_group, self.rc_uploader_group)
        self.assertIsNone(record.current_membership_instance)
        self.assertEqual(record.note, upload_workspace_audit.UploadWorkspaceAuthDomainAudit.RC_UPLOADERS_BEFORE_QC)

    def test_rc_uploaders_member(self):
        membership = GroupGroupMembershipFactory.create(
            parent_group=self.upload_workspace.workspace.authorization_domains.first(),
            child_group=self.rc_uploader_group,
            role=GroupGroupMembership.MEMBER,
        )
        audit = upload_workspace_audit.UploadWorkspaceAuthDomainAudit()
        audit.audit_workspace_and_group(self.upload_workspace, self.rc_uploader_group)
        self.assertEqual(len(audit.verified), 1)
        self.assertEqual(len(audit.needs_action), 0)
        self.assertEqual(len(audit.errors), 0)
        record = audit.verified[0]
        self.assertIsInstance(record, workspace_auth_domain_audit_results.VerifiedMember)
        self.assertEqual(record.workspace, self.upload_workspace.workspace)
        self.assertEqual(record.managed_group, self.rc_uploader_group)
        self.assertEqual(record.current_membership_instance, membership)
        self.assertEqual(record.note, upload_workspace_audit.UploadWorkspaceAuthDomainAudit.RC_UPLOADERS_BEFORE_QC)

    def test_rc_uploaders_admin(self):
        membership = GroupGroupMembershipFactory.create(
            parent_group=self.upload_workspace.workspace.authorization_domains.first(),
            child_group=self.rc_uploader_group,
            role=GroupGroupMembership.ADMIN,
        )
        audit = upload_workspace_audit.UploadWorkspaceAuthDomainAudit()
        audit.audit_workspace_and_group(self.upload_workspace, self.rc_uploader_group)
        self.assertEqual(len(audit.verified), 0)
        self.assertEqual(len(audit.needs_action), 0)
        self.assertEqual(len(audit.errors), 1)
        record = audit.errors[0]
        self.assertIsInstance(record, workspace_auth_domain_audit_results.ChangeToMember)
        self.assertEqual(record.workspace, self.upload_workspace.workspace)
        self.assertEqual(record.managed_group, self.rc_uploader_group)
        self.assertEqual(record.current_membership_instance, membership)
        self.assertEqual(record.note, upload_workspace_audit.UploadWorkspaceAuthDomainAudit.RC_UPLOADERS_BEFORE_QC)

    def test_rc_members_not_member(self):
        audit = upload_workspace_audit.UploadWorkspaceAuthDomainAudit()
        audit.audit_workspace_and_group(self.upload_workspace, self.rc_member_group)
        self.assertEqual(len(audit.verified), 0)
        self.assertEqual(len(audit.needs_action), 1)
        self.assertEqual(len(audit.errors), 0)
        record = audit.needs_action[0]
        self.assertIsInstance(record, workspace_auth_domain_audit_results.AddMember)
        self.assertEqual(record.workspace, self.upload_workspace.workspace)
        self.assertEqual(record.managed_group, self.rc_member_group)
        self.assertIsNone(record.current_membership_instance)
        self.assertEqual(record.note, upload_workspace_audit.UploadWorkspaceAuthDomainAudit.RC_MEMBERS_BEFORE_COMBINED)

    def test_rc_members_member(self):
        membership = GroupGroupMembershipFactory.create(
            parent_group=self.upload_workspace.workspace.authorization_domains.first(),
            child_group=self.rc_member_group,
            role=GroupGroupMembership.MEMBER,
        )
        audit = upload_workspace_audit.UploadWorkspaceAuthDomainAudit()
        audit.audit_workspace_and_group(self.upload_workspace, self.rc_member_group)
        self.assertEqual(len(audit.verified), 1)
        self.assertEqual(len(audit.needs_action), 0)
        self.assertEqual(len(audit.errors), 0)
        record = audit.verified[0]
        self.assertIsInstance(record, workspace_auth_domain_audit_results.VerifiedMember)
        self.assertEqual(record.workspace, self.upload_workspace.workspace)
        self.assertEqual(record.managed_group, self.rc_member_group)
        self.assertEqual(record.current_membership_instance, membership)
        self.assertEqual(record.note, upload_workspace_audit.UploadWorkspaceAuthDomainAudit.RC_MEMBERS_BEFORE_COMBINED)

    def test_rc_members_admin(self):
        membership = GroupGroupMembershipFactory.create(
            parent_group=self.upload_workspace.workspace.authorization_domains.first(),
            child_group=self.rc_member_group,
            role=GroupGroupMembership.ADMIN,
        )
        audit = upload_workspace_audit.UploadWorkspaceAuthDomainAudit()
        audit.audit_workspace_and_group(self.upload_workspace, self.rc_member_group)
        self.assertEqual(len(audit.verified), 0)
        self.assertEqual(len(audit.needs_action), 0)
        self.assertEqual(len(audit.errors), 1)
        record = audit.errors[0]
        self.assertIsInstance(record, workspace_auth_domain_audit_results.ChangeToMember)
        self.assertEqual(record.workspace, self.upload_workspace.workspace)
        self.assertEqual(record.managed_group, self.rc_member_group)
        self.assertEqual(record.current_membership_instance, membership)
        self.assertEqual(record.note, upload_workspace_audit.UploadWorkspaceAuthDomainAudit.RC_MEMBERS_BEFORE_COMBINED)

    def test_rc_non_members_not_member(self):
        audit = upload_workspace_audit.UploadWorkspaceAuthDomainAudit()
        audit.audit_workspace_and_group(self.upload_workspace, self.rc_non_member_group)
        self.assertEqual(len(audit.verified), 0)
        self.assertEqual(len(audit.needs_action), 1)
        self.assertEqual(len(audit.errors), 0)
        record = audit.needs_action[0]
        self.assertIsInstance(record, workspace_auth_domain_audit_results.AddMember)
        self.assertEqual(record.workspace, self.upload_workspace.workspace)
        self.assertEqual(record.managed_group, self.rc_non_member_group)
        self.assertIsNone(record.current_membership_instance)
        self.assertEqual(record.note, upload_workspace_audit.UploadWorkspaceAuthDomainAudit.RC_NON_MEMBERS_AFTER_START)

    def test_rc_non_members_member(self):
        membership = GroupGroupMembershipFactory.create(
            parent_group=self.upload_workspace.workspace.authorization_domains.first(),
            child_group=self.rc_non_member_group,
            role=GroupGroupMembership.MEMBER,
        )
        audit = upload_workspace_audit.UploadWorkspaceAuthDomainAudit()
        audit.audit_workspace_and_group(self.upload_workspace, self.rc_non_member_group)
        self.assertEqual(len(audit.verified), 1)
        self.assertEqual(len(audit.needs_action), 0)
        self.assertEqual(len(audit.errors), 0)
        record = audit.verified[0]
        self.assertIsInstance(record, workspace_auth_domain_audit_results.VerifiedMember)
        self.assertEqual(record.workspace, self.upload_workspace.workspace)
        self.assertEqual(record.managed_group, self.rc_non_member_group)
        self.assertEqual(record.current_membership_instance, membership)
        self.assertEqual(record.note, upload_workspace_audit.UploadWorkspaceAuthDomainAudit.RC_NON_MEMBERS_AFTER_START)

    def test_rc_non_members_admin(self):
        membership = GroupGroupMembershipFactory.create(
            parent_group=self.upload_workspace.workspace.authorization_domains.first(),
            child_group=self.rc_non_member_group,
            role=GroupGroupMembership.ADMIN,
        )
        audit = upload_workspace_audit.UploadWorkspaceAuthDomainAudit()
        audit.audit_workspace_and_group(self.upload_workspace, self.rc_non_member_group)
        self.assertEqual(len(audit.verified), 0)
        self.assertEqual(len(audit.needs_action), 0)
        self.assertEqual(len(audit.errors), 1)
        record = audit.errors[0]
        self.assertIsInstance(record, workspace_auth_domain_audit_results.ChangeToMember)
        self.assertEqual(record.workspace, self.upload_workspace.workspace)
        self.assertEqual(record.managed_group, self.rc_non_member_group)
        self.assertEqual(record.current_membership_instance, membership)
        self.assertEqual(record.note, upload_workspace_audit.UploadWorkspaceAuthDomainAudit.RC_NON_MEMBERS_AFTER_START)

    def test_dcc_admins_not_member(self):
        audit = upload_workspace_audit.UploadWorkspaceAuthDomainAudit()
        audit.audit_workspace_and_group(self.upload_workspace, self.dcc_admin_group)
        self.assertEqual(len(audit.verified), 0)
        self.assertEqual(len(audit.needs_action), 1)
        self.assertEqual(len(audit.errors), 0)
        record = audit.needs_action[0]
        self.assertIsInstance(record, workspace_auth_domain_audit_results.AddAdmin)
        self.assertEqual(record.workspace, self.upload_workspace.workspace)
        self.assertEqual(record.managed_group, self.dcc_admin_group)
        self.assertIsNone(record.current_membership_instance)
        self.assertEqual(record.note, upload_workspace_audit.UploadWorkspaceAuthDomainAudit.DCC_ADMINS)

    def test_dcc_admins_member(self):
        membership = GroupGroupMembershipFactory.create(
            parent_group=self.upload_workspace.workspace.authorization_domains.first(),
            child_group=self.dcc_admin_group,
            role=GroupGroupMembership.MEMBER,
        )
        audit = upload_workspace_audit.UploadWorkspaceAuthDomainAudit()
        audit.audit_workspace_and_group(self.upload_workspace, self.dcc_admin_group)
        self.assertEqual(len(audit.verified), 0)
        self.assertEqual(len(audit.needs_action), 1)
        self.assertEqual(len(audit.errors), 0)
        record = audit.needs_action[0]
        self.assertIsInstance(record, workspace_auth_domain_audit_results.ChangeToAdmin)
        self.assertEqual(record.workspace, self.upload_workspace.workspace)
        self.assertEqual(record.managed_group, self.dcc_admin_group)
        self.assertEqual(record.current_membership_instance, membership)
        self.assertEqual(record.note, upload_workspace_audit.UploadWorkspaceAuthDomainAudit.DCC_ADMINS)

    def test_dcc_admins_admin(self):
        membership = GroupGroupMembershipFactory.create(
            parent_group=self.upload_workspace.workspace.authorization_domains.first(),
            child_group=self.dcc_admin_group,
            role=GroupGroupMembership.ADMIN,
        )
        audit = upload_workspace_audit.UploadWorkspaceAuthDomainAudit()
        audit.audit_workspace_and_group(self.upload_workspace, self.dcc_admin_group)
        self.assertEqual(len(audit.verified), 1)
        self.assertEqual(len(audit.needs_action), 0)
        self.assertEqual(len(audit.errors), 0)
        record = audit.verified[0]
        self.assertIsInstance(record, workspace_auth_domain_audit_results.VerifiedAdmin)
        self.assertEqual(record.workspace, self.upload_workspace.workspace)
        self.assertEqual(record.managed_group, self.dcc_admin_group)
        self.assertEqual(record.current_membership_instance, membership)
        self.assertEqual(record.note, upload_workspace_audit.UploadWorkspaceAuthDomainAudit.DCC_ADMINS)

    @override_settings(ANVIL_DCC_ADMINS_GROUP_NAME="foobar")
    def test_dcc_admins_different_setting(self):
        group = ManagedGroupFactory.create(name="foobar")
        audit = upload_workspace_audit.UploadWorkspaceAuthDomainAudit()
        audit.audit_workspace_and_group(self.upload_workspace, group)
        self.assertEqual(len(audit.verified), 0)
        self.assertEqual(len(audit.needs_action), 1)
        self.assertEqual(len(audit.errors), 0)
        record = audit.needs_action[0]
        self.assertIsInstance(record, workspace_auth_domain_audit_results.AddAdmin)
        self.assertEqual(record.workspace, self.upload_workspace.workspace)
        self.assertEqual(record.managed_group, group)
        self.assertIsNone(record.current_membership_instance)
        self.assertEqual(record.note, upload_workspace_audit.UploadWorkspaceAuthDomainAudit.DCC_ADMINS)

    def test_dcc_writers_not_member(self):
        audit = upload_workspace_audit.UploadWorkspaceAuthDomainAudit()
        audit.audit_workspace_and_group(self.upload_workspace, self.dcc_writer_group)
        self.assertEqual(len(audit.verified), 0)
        self.assertEqual(len(audit.needs_action), 1)
        self.assertEqual(len(audit.errors), 0)
        record = audit.needs_action[0]
        self.assertIsInstance(record, workspace_auth_domain_audit_results.AddMember)
        self.assertEqual(record.workspace, self.upload_workspace.workspace)
        self.assertEqual(record.managed_group, self.dcc_writer_group)
        self.assertIsNone(record.current_membership_instance)
        self.assertEqual(record.note, upload_workspace_audit.UploadWorkspaceAuthDomainAudit.DCC_BEFORE_COMBINED)

    def test_dcc_writers_member(self):
        membership = GroupGroupMembershipFactory.create(
            parent_group=self.upload_workspace.workspace.authorization_domains.first(),
            child_group=self.dcc_writer_group,
            role=GroupGroupMembership.MEMBER,
        )
        audit = upload_workspace_audit.UploadWorkspaceAuthDomainAudit()
        audit.audit_workspace_and_group(self.upload_workspace, self.dcc_writer_group)
        self.assertEqual(len(audit.verified), 1)
        self.assertEqual(len(audit.needs_action), 0)
        self.assertEqual(len(audit.errors), 0)
        record = audit.verified[0]
        self.assertIsInstance(record, workspace_auth_domain_audit_results.VerifiedMember)
        self.assertEqual(record.workspace, self.upload_workspace.workspace)
        self.assertEqual(record.managed_group, self.dcc_writer_group)
        self.assertEqual(record.current_membership_instance, membership)
        self.assertEqual(record.note, upload_workspace_audit.UploadWorkspaceAuthDomainAudit.DCC_BEFORE_COMBINED)

    def test_dcc_writers_admin(self):
        membership = GroupGroupMembershipFactory.create(
            parent_group=self.upload_workspace.workspace.authorization_domains.first(),
            child_group=self.dcc_writer_group,
            role=GroupGroupMembership.ADMIN,
        )
        audit = upload_workspace_audit.UploadWorkspaceAuthDomainAudit()
        audit.audit_workspace_and_group(self.upload_workspace, self.dcc_writer_group)
        self.assertEqual(len(audit.verified), 0)
        self.assertEqual(len(audit.needs_action), 0)
        self.assertEqual(len(audit.errors), 1)
        record = audit.errors[0]
        self.assertIsInstance(record, workspace_auth_domain_audit_results.ChangeToMember)
        self.assertEqual(record.workspace, self.upload_workspace.workspace)
        self.assertEqual(record.managed_group, self.dcc_writer_group)
        self.assertEqual(record.current_membership_instance, membership)
        self.assertEqual(record.note, upload_workspace_audit.UploadWorkspaceAuthDomainAudit.DCC_BEFORE_COMBINED)

    def test_dcc_members_not_member(self):
        audit = upload_workspace_audit.UploadWorkspaceAuthDomainAudit()
        audit.audit_workspace_and_group(self.upload_workspace, self.dcc_member_group)
        self.assertEqual(len(audit.verified), 0)
        self.assertEqual(len(audit.needs_action), 1)
        self.assertEqual(len(audit.errors), 0)
        record = audit.needs_action[0]
        self.assertIsInstance(record, workspace_auth_domain_audit_results.AddMember)
        self.assertEqual(record.workspace, self.upload_workspace.workspace)
        self.assertEqual(record.managed_group, self.dcc_member_group)
        self.assertIsNone(record.current_membership_instance)
        self.assertEqual(record.note, upload_workspace_audit.UploadWorkspaceAuthDomainAudit.DCC_BEFORE_COMBINED)

    def test_dcc_members_member(self):
        membership = GroupGroupMembershipFactory.create(
            parent_group=self.upload_workspace.workspace.authorization_domains.first(),
            child_group=self.dcc_member_group,
            role=GroupGroupMembership.MEMBER,
        )
        audit = upload_workspace_audit.UploadWorkspaceAuthDomainAudit()
        audit.audit_workspace_and_group(self.upload_workspace, self.dcc_member_group)
        self.assertEqual(len(audit.verified), 1)
        self.assertEqual(len(audit.needs_action), 0)
        self.assertEqual(len(audit.errors), 0)
        record = audit.verified[0]
        self.assertIsInstance(record, workspace_auth_domain_audit_results.VerifiedMember)
        self.assertEqual(record.workspace, self.upload_workspace.workspace)
        self.assertEqual(record.managed_group, self.dcc_member_group)
        self.assertEqual(record.current_membership_instance, membership)
        self.assertEqual(record.note, upload_workspace_audit.UploadWorkspaceAuthDomainAudit.DCC_BEFORE_COMBINED)

    def test_dcc_members_admin(self):
        membership = GroupGroupMembershipFactory.create(
            parent_group=self.upload_workspace.workspace.authorization_domains.first(),
            child_group=self.dcc_member_group,
            role=GroupGroupMembership.ADMIN,
        )
        audit = upload_workspace_audit.UploadWorkspaceAuthDomainAudit()
        audit.audit_workspace_and_group(self.upload_workspace, self.dcc_member_group)
        self.assertEqual(len(audit.verified), 0)
        self.assertEqual(len(audit.needs_action), 0)
        self.assertEqual(len(audit.errors), 1)
        record = audit.errors[0]
        self.assertIsInstance(record, workspace_auth_domain_audit_results.ChangeToMember)
        self.assertEqual(record.workspace, self.upload_workspace.workspace)
        self.assertEqual(record.managed_group, self.dcc_member_group)
        self.assertEqual(record.current_membership_instance, membership)
        self.assertEqual(record.note, upload_workspace_audit.UploadWorkspaceAuthDomainAudit.DCC_BEFORE_COMBINED)

    def test_gregor_all_not_member(self):
        audit = upload_workspace_audit.UploadWorkspaceAuthDomainAudit()
        audit.audit_workspace_and_group(self.upload_workspace, self.gregor_all_group)
        self.assertEqual(len(audit.verified), 1)
        self.assertEqual(len(audit.needs_action), 0)
        self.assertEqual(len(audit.errors), 0)
        record = audit.verified[0]
        self.assertIsInstance(record, workspace_auth_domain_audit_results.VerifiedNotMember)
        self.assertEqual(record.workspace, self.upload_workspace.workspace)
        self.assertEqual(record.managed_group, self.gregor_all_group)
        self.assertIsNone(record.current_membership_instance)
        self.assertEqual(record.note, upload_workspace_audit.UploadWorkspaceAuthDomainAudit.GREGOR_ALL_BEFORE_COMBINED)

    def test_gregor_all_member(self):
        membership = GroupGroupMembershipFactory.create(
            parent_group=self.upload_workspace.workspace.authorization_domains.first(),
            child_group=self.gregor_all_group,
            role=GroupGroupMembership.MEMBER,
        )
        audit = upload_workspace_audit.UploadWorkspaceAuthDomainAudit()
        audit.audit_workspace_and_group(self.upload_workspace, self.gregor_all_group)
        self.assertEqual(len(audit.verified), 0)
        self.assertEqual(len(audit.needs_action), 0)
        self.assertEqual(len(audit.errors), 1)
        record = audit.errors[0]
        self.assertIsInstance(record, workspace_auth_domain_audit_results.Remove)
        self.assertEqual(record.workspace, self.upload_workspace.workspace)
        self.assertEqual(record.managed_group, self.gregor_all_group)
        self.assertEqual(record.current_membership_instance, membership)
        self.assertEqual(record.note, upload_workspace_audit.UploadWorkspaceAuthDomainAudit.GREGOR_ALL_BEFORE_COMBINED)

    def test_gregor_all_admin(self):
        membership = GroupGroupMembershipFactory.create(
            parent_group=self.upload_workspace.workspace.authorization_domains.first(),
            child_group=self.gregor_all_group,
            role=GroupGroupMembership.ADMIN,
        )
        audit = upload_workspace_audit.UploadWorkspaceAuthDomainAudit()
        audit.audit_workspace_and_group(self.upload_workspace, self.gregor_all_group)
        self.assertEqual(len(audit.verified), 0)
        self.assertEqual(len(audit.needs_action), 0)
        self.assertEqual(len(audit.errors), 1)
        record = audit.errors[0]
        self.assertIsInstance(record, workspace_auth_domain_audit_results.Remove)
        self.assertEqual(record.workspace, self.upload_workspace.workspace)
        self.assertEqual(record.managed_group, self.gregor_all_group)
        self.assertEqual(record.current_membership_instance, membership)
        self.assertEqual(record.note, upload_workspace_audit.UploadWorkspaceAuthDomainAudit.GREGOR_ALL_BEFORE_COMBINED)

    def test_other_group_not_member(self):
        audit = upload_workspace_audit.UploadWorkspaceAuthDomainAudit()
        audit.audit_workspace_and_group(self.upload_workspace, self.other_group)
        self.assertEqual(len(audit.verified), 1)
        self.assertEqual(len(audit.needs_action), 0)
        self.assertEqual(len(audit.errors), 0)
        record = audit.verified[0]
        self.assertIsInstance(record, workspace_auth_domain_audit_results.VerifiedNotMember)
        self.assertEqual(record.workspace, self.upload_workspace.workspace)
        self.assertEqual(record.managed_group, self.other_group)
        self.assertIsNone(record.current_membership_instance)
        self.assertEqual(record.note, upload_workspace_audit.UploadWorkspaceAuthDomainAudit.OTHER_GROUP)

    def test_other_group_member(self):
        membership = GroupGroupMembershipFactory.create(
            parent_group=self.upload_workspace.workspace.authorization_domains.first(),
            child_group=self.other_group,
            role=GroupGroupMembership.MEMBER,
        )
        audit = upload_workspace_audit.UploadWorkspaceAuthDomainAudit()
        audit.audit_workspace_and_group(self.upload_workspace, self.other_group)
        self.assertEqual(len(audit.verified), 0)
        self.assertEqual(len(audit.needs_action), 0)
        self.assertEqual(len(audit.errors), 1)
        record = audit.errors[0]
        self.assertIsInstance(record, workspace_auth_domain_audit_results.Remove)
        self.assertEqual(record.workspace, self.upload_workspace.workspace)
        self.assertEqual(record.managed_group, self.other_group)
        self.assertEqual(record.current_membership_instance, membership)
        self.assertEqual(record.note, upload_workspace_audit.UploadWorkspaceAuthDomainAudit.OTHER_GROUP)

    def test_other_group_admin(self):
        membership = GroupGroupMembershipFactory.create(
            parent_group=self.upload_workspace.workspace.authorization_domains.first(),
            child_group=self.other_group,
            role=GroupGroupMembership.ADMIN,
        )
        audit = upload_workspace_audit.UploadWorkspaceAuthDomainAudit()
        audit.audit_workspace_and_group(self.upload_workspace, self.other_group)
        self.assertEqual(len(audit.verified), 0)
        self.assertEqual(len(audit.needs_action), 0)
        self.assertEqual(len(audit.errors), 1)
        record = audit.errors[0]
        self.assertIsInstance(record, workspace_auth_domain_audit_results.Remove)
        self.assertEqual(record.workspace, self.upload_workspace.workspace)
        self.assertEqual(record.managed_group, self.other_group)
        self.assertEqual(record.current_membership_instance, membership)
        self.assertEqual(record.note, upload_workspace_audit.UploadWorkspaceAuthDomainAudit.OTHER_GROUP)

    def test_anvil_admins_not_member(self):
        audit = upload_workspace_audit.UploadWorkspaceAuthDomainAudit()
        audit.audit_workspace_and_group(self.upload_workspace, self.anvil_admins)
        self.assertEqual(len(audit.verified), 0)
        self.assertEqual(len(audit.needs_action), 0)
        self.assertEqual(len(audit.errors), 0)

    def test_anvil_admins_member(self):
        GroupGroupMembershipFactory.create(
            parent_group=self.upload_workspace.workspace.authorization_domains.first(),
            child_group=self.anvil_admins,
            role=GroupGroupMembership.MEMBER,
        )
        audit = upload_workspace_audit.UploadWorkspaceAuthDomainAudit()
        audit.audit_workspace_and_group(self.upload_workspace, self.anvil_admins)
        self.assertEqual(len(audit.verified), 0)
        self.assertEqual(len(audit.needs_action), 0)
        self.assertEqual(len(audit.errors), 0)

    def test_anvil_admins_admin(self):
        GroupGroupMembershipFactory.create(
            parent_group=self.upload_workspace.workspace.authorization_domains.first(),
            child_group=self.anvil_admins,
            role=GroupGroupMembership.ADMIN,
        )
        audit = upload_workspace_audit.UploadWorkspaceAuthDomainAudit()
        audit.audit_workspace_and_group(self.upload_workspace, self.anvil_admins)
        self.assertEqual(len(audit.verified), 0)
        self.assertEqual(len(audit.needs_action), 0)
        self.assertEqual(len(audit.errors), 0)

    def test_anvil_devs_not_member(self):
        audit = upload_workspace_audit.UploadWorkspaceAuthDomainAudit()
        audit.audit_workspace_and_group(self.upload_workspace, self.anvil_devs)
        self.assertEqual(len(audit.verified), 0)
        self.assertEqual(len(audit.needs_action), 0)
        self.assertEqual(len(audit.errors), 0)

    def test_anvil_devs_member(self):
        GroupGroupMembershipFactory.create(
            parent_group=self.upload_workspace.workspace.authorization_domains.first(),
            child_group=self.anvil_devs,
            role=GroupGroupMembership.MEMBER,
        )
        audit = upload_workspace_audit.UploadWorkspaceAuthDomainAudit()
        audit.audit_workspace_and_group(self.upload_workspace, self.anvil_devs)
        self.assertEqual(len(audit.verified), 0)
        self.assertEqual(len(audit.needs_action), 0)
        self.assertEqual(len(audit.errors), 0)

    def test_anvil_devs_admin(self):
        GroupGroupMembershipFactory.create(
            parent_group=self.upload_workspace.workspace.authorization_domains.first(),
            child_group=self.anvil_devs,
            role=GroupGroupMembership.ADMIN,
        )
        audit = upload_workspace_audit.UploadWorkspaceAuthDomainAudit()
        audit.audit_workspace_and_group(self.upload_workspace, self.anvil_devs)
        self.assertEqual(len(audit.verified), 0)
        self.assertEqual(len(audit.needs_action), 0)
        self.assertEqual(len(audit.errors), 0)


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
        audit = upload_workspace_audit.UploadWorkspaceAuthDomainAudit()
        audit.audit_workspace_and_group(self.upload_workspace, self.rc_uploader_group)
        self.assertEqual(len(audit.verified), 1)
        self.assertEqual(len(audit.needs_action), 0)
        self.assertEqual(len(audit.errors), 0)
        record = audit.verified[0]
        self.assertIsInstance(record, workspace_auth_domain_audit_results.VerifiedNotMember)
        self.assertEqual(record.workspace, self.upload_workspace.workspace)
        self.assertEqual(record.managed_group, self.rc_uploader_group)
        self.assertIsNone(record.current_membership_instance)
        self.assertEqual(record.note, upload_workspace_audit.UploadWorkspaceAuthDomainAudit.RC_UPLOADERS_AFTER_QC)

    def test_rc_uploaders_member(self):
        membership = GroupGroupMembershipFactory.create(
            parent_group=self.upload_workspace.workspace.authorization_domains.first(),
            child_group=self.rc_uploader_group,
            role=GroupGroupMembership.MEMBER,
        )
        audit = upload_workspace_audit.UploadWorkspaceAuthDomainAudit()
        audit.audit_workspace_and_group(self.upload_workspace, self.rc_uploader_group)
        self.assertEqual(len(audit.verified), 0)
        self.assertEqual(len(audit.needs_action), 1)
        self.assertEqual(len(audit.errors), 0)
        record = audit.needs_action[0]
        self.assertIsInstance(record, workspace_auth_domain_audit_results.Remove)
        self.assertEqual(record.workspace, self.upload_workspace.workspace)
        self.assertEqual(record.managed_group, self.rc_uploader_group)
        self.assertEqual(record.current_membership_instance, membership)
        self.assertEqual(record.note, upload_workspace_audit.UploadWorkspaceAuthDomainAudit.RC_UPLOADERS_AFTER_QC)

    def test_rc_uploaders_admin(self):
        membership = GroupGroupMembershipFactory.create(
            parent_group=self.upload_workspace.workspace.authorization_domains.first(),
            child_group=self.rc_uploader_group,
            role=GroupGroupMembership.ADMIN,
        )
        audit = upload_workspace_audit.UploadWorkspaceAuthDomainAudit()
        audit.audit_workspace_and_group(self.upload_workspace, self.rc_uploader_group)
        self.assertEqual(len(audit.verified), 0)
        self.assertEqual(len(audit.needs_action), 0)
        self.assertEqual(len(audit.errors), 1)
        record = audit.errors[0]
        self.assertIsInstance(record, workspace_auth_domain_audit_results.Remove)
        self.assertEqual(record.workspace, self.upload_workspace.workspace)
        self.assertEqual(record.managed_group, self.rc_uploader_group)
        self.assertEqual(record.current_membership_instance, membership)
        self.assertEqual(record.note, upload_workspace_audit.UploadWorkspaceAuthDomainAudit.RC_UPLOADERS_AFTER_QC)

    def test_rc_members_not_member(self):
        audit = upload_workspace_audit.UploadWorkspaceAuthDomainAudit()
        audit.audit_workspace_and_group(self.upload_workspace, self.rc_member_group)
        self.assertEqual(len(audit.verified), 0)
        self.assertEqual(len(audit.needs_action), 1)
        self.assertEqual(len(audit.errors), 0)
        record = audit.needs_action[0]
        self.assertIsInstance(record, workspace_auth_domain_audit_results.AddMember)
        self.assertEqual(record.workspace, self.upload_workspace.workspace)
        self.assertEqual(record.managed_group, self.rc_member_group)
        self.assertIsNone(record.current_membership_instance)
        self.assertEqual(record.note, upload_workspace_audit.UploadWorkspaceAuthDomainAudit.RC_MEMBERS_BEFORE_COMBINED)

    def test_rc_members_member(self):
        membership = GroupGroupMembershipFactory.create(
            parent_group=self.upload_workspace.workspace.authorization_domains.first(),
            child_group=self.rc_member_group,
            role=GroupGroupMembership.MEMBER,
        )
        audit = upload_workspace_audit.UploadWorkspaceAuthDomainAudit()
        audit.audit_workspace_and_group(self.upload_workspace, self.rc_member_group)
        self.assertEqual(len(audit.verified), 1)
        self.assertEqual(len(audit.needs_action), 0)
        self.assertEqual(len(audit.errors), 0)
        record = audit.verified[0]
        self.assertIsInstance(record, workspace_auth_domain_audit_results.VerifiedMember)
        self.assertEqual(record.workspace, self.upload_workspace.workspace)
        self.assertEqual(record.managed_group, self.rc_member_group)
        self.assertEqual(record.current_membership_instance, membership)
        self.assertEqual(record.note, upload_workspace_audit.UploadWorkspaceAuthDomainAudit.RC_MEMBERS_BEFORE_COMBINED)

    def test_rc_members_admin(self):
        membership = GroupGroupMembershipFactory.create(
            parent_group=self.upload_workspace.workspace.authorization_domains.first(),
            child_group=self.rc_member_group,
            role=GroupGroupMembership.ADMIN,
        )
        audit = upload_workspace_audit.UploadWorkspaceAuthDomainAudit()
        audit.audit_workspace_and_group(self.upload_workspace, self.rc_member_group)
        self.assertEqual(len(audit.verified), 0)
        self.assertEqual(len(audit.needs_action), 0)
        self.assertEqual(len(audit.errors), 1)
        record = audit.errors[0]
        self.assertIsInstance(record, workspace_auth_domain_audit_results.ChangeToMember)
        self.assertEqual(record.workspace, self.upload_workspace.workspace)
        self.assertEqual(record.managed_group, self.rc_member_group)
        self.assertEqual(record.current_membership_instance, membership)
        self.assertEqual(record.note, upload_workspace_audit.UploadWorkspaceAuthDomainAudit.RC_MEMBERS_BEFORE_COMBINED)

    def test_rc_non_members_not_member(self):
        audit = upload_workspace_audit.UploadWorkspaceAuthDomainAudit()
        audit.audit_workspace_and_group(self.upload_workspace, self.rc_non_member_group)
        self.assertEqual(len(audit.verified), 0)
        self.assertEqual(len(audit.needs_action), 1)
        self.assertEqual(len(audit.errors), 0)
        record = audit.needs_action[0]
        self.assertIsInstance(record, workspace_auth_domain_audit_results.AddMember)
        self.assertEqual(record.workspace, self.upload_workspace.workspace)
        self.assertEqual(record.managed_group, self.rc_non_member_group)
        self.assertIsNone(record.current_membership_instance)
        self.assertEqual(record.note, upload_workspace_audit.UploadWorkspaceAuthDomainAudit.RC_NON_MEMBERS_AFTER_START)

    def test_rc_non_members_member(self):
        membership = GroupGroupMembershipFactory.create(
            parent_group=self.upload_workspace.workspace.authorization_domains.first(),
            child_group=self.rc_non_member_group,
            role=GroupGroupMembership.MEMBER,
        )
        audit = upload_workspace_audit.UploadWorkspaceAuthDomainAudit()
        audit.audit_workspace_and_group(self.upload_workspace, self.rc_non_member_group)
        self.assertEqual(len(audit.verified), 1)
        self.assertEqual(len(audit.needs_action), 0)
        self.assertEqual(len(audit.errors), 0)
        record = audit.verified[0]
        self.assertIsInstance(record, workspace_auth_domain_audit_results.VerifiedMember)
        self.assertEqual(record.workspace, self.upload_workspace.workspace)
        self.assertEqual(record.managed_group, self.rc_non_member_group)
        self.assertEqual(record.current_membership_instance, membership)
        self.assertEqual(record.note, upload_workspace_audit.UploadWorkspaceAuthDomainAudit.RC_NON_MEMBERS_AFTER_START)

    def test_rc_non_members_admin(self):
        membership = GroupGroupMembershipFactory.create(
            parent_group=self.upload_workspace.workspace.authorization_domains.first(),
            child_group=self.rc_non_member_group,
            role=GroupGroupMembership.ADMIN,
        )
        audit = upload_workspace_audit.UploadWorkspaceAuthDomainAudit()
        audit.audit_workspace_and_group(self.upload_workspace, self.rc_non_member_group)
        self.assertEqual(len(audit.verified), 0)
        self.assertEqual(len(audit.needs_action), 0)
        self.assertEqual(len(audit.errors), 1)
        record = audit.errors[0]
        self.assertIsInstance(record, workspace_auth_domain_audit_results.ChangeToMember)
        self.assertEqual(record.workspace, self.upload_workspace.workspace)
        self.assertEqual(record.managed_group, self.rc_non_member_group)
        self.assertEqual(record.current_membership_instance, membership)
        self.assertEqual(record.note, upload_workspace_audit.UploadWorkspaceAuthDomainAudit.RC_NON_MEMBERS_AFTER_START)

    def test_dcc_admins_not_member(self):
        audit = upload_workspace_audit.UploadWorkspaceAuthDomainAudit()
        audit.audit_workspace_and_group(self.upload_workspace, self.dcc_admin_group)
        self.assertEqual(len(audit.verified), 0)
        self.assertEqual(len(audit.needs_action), 1)
        self.assertEqual(len(audit.errors), 0)
        record = audit.needs_action[0]
        self.assertIsInstance(record, workspace_auth_domain_audit_results.AddAdmin)
        self.assertEqual(record.workspace, self.upload_workspace.workspace)
        self.assertEqual(record.managed_group, self.dcc_admin_group)
        self.assertIsNone(record.current_membership_instance)
        self.assertEqual(record.note, upload_workspace_audit.UploadWorkspaceAuthDomainAudit.DCC_ADMINS)

    def test_dcc_admins_member(self):
        membership = GroupGroupMembershipFactory.create(
            parent_group=self.upload_workspace.workspace.authorization_domains.first(),
            child_group=self.dcc_admin_group,
            role=GroupGroupMembership.MEMBER,
        )
        audit = upload_workspace_audit.UploadWorkspaceAuthDomainAudit()
        audit.audit_workspace_and_group(self.upload_workspace, self.dcc_admin_group)
        self.assertEqual(len(audit.verified), 0)
        self.assertEqual(len(audit.needs_action), 1)
        self.assertEqual(len(audit.errors), 0)
        record = audit.needs_action[0]
        self.assertIsInstance(record, workspace_auth_domain_audit_results.ChangeToAdmin)
        self.assertEqual(record.workspace, self.upload_workspace.workspace)
        self.assertEqual(record.managed_group, self.dcc_admin_group)
        self.assertEqual(record.current_membership_instance, membership)
        self.assertEqual(record.note, upload_workspace_audit.UploadWorkspaceAuthDomainAudit.DCC_ADMINS)

    def test_dcc_admins_admin(self):
        membership = GroupGroupMembershipFactory.create(
            parent_group=self.upload_workspace.workspace.authorization_domains.first(),
            child_group=self.dcc_admin_group,
            role=GroupGroupMembership.ADMIN,
        )
        audit = upload_workspace_audit.UploadWorkspaceAuthDomainAudit()
        audit.audit_workspace_and_group(self.upload_workspace, self.dcc_admin_group)
        self.assertEqual(len(audit.verified), 1)
        self.assertEqual(len(audit.needs_action), 0)
        self.assertEqual(len(audit.errors), 0)
        record = audit.verified[0]
        self.assertIsInstance(record, workspace_auth_domain_audit_results.VerifiedAdmin)
        self.assertEqual(record.workspace, self.upload_workspace.workspace)
        self.assertEqual(record.managed_group, self.dcc_admin_group)
        self.assertEqual(record.current_membership_instance, membership)
        self.assertEqual(record.note, upload_workspace_audit.UploadWorkspaceAuthDomainAudit.DCC_ADMINS)

    @override_settings(ANVIL_DCC_ADMINS_GROUP_NAME="foobar")
    def test_dcc_admins_different_setting(self):
        group = ManagedGroupFactory.create(name="foobar")
        audit = upload_workspace_audit.UploadWorkspaceAuthDomainAudit()
        audit.audit_workspace_and_group(self.upload_workspace, group)
        self.assertEqual(len(audit.verified), 0)
        self.assertEqual(len(audit.needs_action), 1)
        self.assertEqual(len(audit.errors), 0)
        record = audit.needs_action[0]
        self.assertIsInstance(record, workspace_auth_domain_audit_results.AddAdmin)
        self.assertEqual(record.workspace, self.upload_workspace.workspace)
        self.assertEqual(record.managed_group, group)
        self.assertIsNone(record.current_membership_instance)
        self.assertEqual(record.note, upload_workspace_audit.UploadWorkspaceAuthDomainAudit.DCC_ADMINS)

    def test_dcc_writers_not_member(self):
        audit = upload_workspace_audit.UploadWorkspaceAuthDomainAudit()
        audit.audit_workspace_and_group(self.upload_workspace, self.dcc_writer_group)
        self.assertEqual(len(audit.verified), 0)
        self.assertEqual(len(audit.needs_action), 1)
        self.assertEqual(len(audit.errors), 0)
        record = audit.needs_action[0]
        self.assertIsInstance(record, workspace_auth_domain_audit_results.AddMember)
        self.assertEqual(record.workspace, self.upload_workspace.workspace)
        self.assertEqual(record.managed_group, self.dcc_writer_group)
        self.assertIsNone(record.current_membership_instance)
        self.assertEqual(record.note, upload_workspace_audit.UploadWorkspaceAuthDomainAudit.DCC_BEFORE_COMBINED)

    def test_dcc_writers_member(self):
        membership = GroupGroupMembershipFactory.create(
            parent_group=self.upload_workspace.workspace.authorization_domains.first(),
            child_group=self.dcc_writer_group,
            role=GroupGroupMembership.MEMBER,
        )
        audit = upload_workspace_audit.UploadWorkspaceAuthDomainAudit()
        audit.audit_workspace_and_group(self.upload_workspace, self.dcc_writer_group)
        self.assertEqual(len(audit.verified), 1)
        self.assertEqual(len(audit.needs_action), 0)
        self.assertEqual(len(audit.errors), 0)
        record = audit.verified[0]
        self.assertIsInstance(record, workspace_auth_domain_audit_results.VerifiedMember)
        self.assertEqual(record.workspace, self.upload_workspace.workspace)
        self.assertEqual(record.managed_group, self.dcc_writer_group)
        self.assertEqual(record.current_membership_instance, membership)
        self.assertEqual(record.note, upload_workspace_audit.UploadWorkspaceAuthDomainAudit.DCC_BEFORE_COMBINED)

    def test_dcc_writers_admin(self):
        membership = GroupGroupMembershipFactory.create(
            parent_group=self.upload_workspace.workspace.authorization_domains.first(),
            child_group=self.dcc_writer_group,
            role=GroupGroupMembership.ADMIN,
        )
        audit = upload_workspace_audit.UploadWorkspaceAuthDomainAudit()
        audit.audit_workspace_and_group(self.upload_workspace, self.dcc_writer_group)
        self.assertEqual(len(audit.verified), 0)
        self.assertEqual(len(audit.needs_action), 0)
        self.assertEqual(len(audit.errors), 1)
        record = audit.errors[0]
        self.assertIsInstance(record, workspace_auth_domain_audit_results.ChangeToMember)
        self.assertEqual(record.workspace, self.upload_workspace.workspace)
        self.assertEqual(record.managed_group, self.dcc_writer_group)
        self.assertEqual(record.current_membership_instance, membership)
        self.assertEqual(record.note, upload_workspace_audit.UploadWorkspaceAuthDomainAudit.DCC_BEFORE_COMBINED)

    def test_dcc_members_not_member(self):
        audit = upload_workspace_audit.UploadWorkspaceAuthDomainAudit()
        audit.audit_workspace_and_group(self.upload_workspace, self.dcc_member_group)
        self.assertEqual(len(audit.verified), 0)
        self.assertEqual(len(audit.needs_action), 1)
        self.assertEqual(len(audit.errors), 0)
        record = audit.needs_action[0]
        self.assertIsInstance(record, workspace_auth_domain_audit_results.AddMember)
        self.assertEqual(record.workspace, self.upload_workspace.workspace)
        self.assertEqual(record.managed_group, self.dcc_member_group)
        self.assertIsNone(record.current_membership_instance)
        self.assertEqual(record.note, upload_workspace_audit.UploadWorkspaceAuthDomainAudit.DCC_BEFORE_COMBINED)

    def test_dcc_members_member(self):
        membership = GroupGroupMembershipFactory.create(
            parent_group=self.upload_workspace.workspace.authorization_domains.first(),
            child_group=self.dcc_member_group,
            role=GroupGroupMembership.MEMBER,
        )
        audit = upload_workspace_audit.UploadWorkspaceAuthDomainAudit()
        audit.audit_workspace_and_group(self.upload_workspace, self.dcc_member_group)
        self.assertEqual(len(audit.verified), 1)
        self.assertEqual(len(audit.needs_action), 0)
        self.assertEqual(len(audit.errors), 0)
        record = audit.verified[0]
        self.assertIsInstance(record, workspace_auth_domain_audit_results.VerifiedMember)
        self.assertEqual(record.workspace, self.upload_workspace.workspace)
        self.assertEqual(record.managed_group, self.dcc_member_group)
        self.assertEqual(record.current_membership_instance, membership)
        self.assertEqual(record.note, upload_workspace_audit.UploadWorkspaceAuthDomainAudit.DCC_BEFORE_COMBINED)

    def test_dcc_members_admin(self):
        membership = GroupGroupMembershipFactory.create(
            parent_group=self.upload_workspace.workspace.authorization_domains.first(),
            child_group=self.dcc_member_group,
            role=GroupGroupMembership.ADMIN,
        )
        audit = upload_workspace_audit.UploadWorkspaceAuthDomainAudit()
        audit.audit_workspace_and_group(self.upload_workspace, self.dcc_member_group)
        self.assertEqual(len(audit.verified), 0)
        self.assertEqual(len(audit.needs_action), 0)
        self.assertEqual(len(audit.errors), 1)
        record = audit.errors[0]
        self.assertIsInstance(record, workspace_auth_domain_audit_results.ChangeToMember)
        self.assertEqual(record.workspace, self.upload_workspace.workspace)
        self.assertEqual(record.managed_group, self.dcc_member_group)
        self.assertEqual(record.current_membership_instance, membership)
        self.assertEqual(record.note, upload_workspace_audit.UploadWorkspaceAuthDomainAudit.DCC_BEFORE_COMBINED)

    def test_gregor_all_not_member(self):
        audit = upload_workspace_audit.UploadWorkspaceAuthDomainAudit()
        audit.audit_workspace_and_group(self.upload_workspace, self.gregor_all_group)
        self.assertEqual(len(audit.verified), 1)
        self.assertEqual(len(audit.needs_action), 0)
        self.assertEqual(len(audit.errors), 0)
        record = audit.verified[0]
        self.assertIsInstance(record, workspace_auth_domain_audit_results.VerifiedNotMember)
        self.assertEqual(record.workspace, self.upload_workspace.workspace)
        self.assertEqual(record.managed_group, self.gregor_all_group)
        self.assertIsNone(record.current_membership_instance)
        self.assertEqual(record.note, upload_workspace_audit.UploadWorkspaceAuthDomainAudit.GREGOR_ALL_BEFORE_COMBINED)

    def test_gregor_all_member(self):
        membership = GroupGroupMembershipFactory.create(
            parent_group=self.upload_workspace.workspace.authorization_domains.first(),
            child_group=self.gregor_all_group,
            role=GroupGroupMembership.MEMBER,
        )
        audit = upload_workspace_audit.UploadWorkspaceAuthDomainAudit()
        audit.audit_workspace_and_group(self.upload_workspace, self.gregor_all_group)
        self.assertEqual(len(audit.verified), 0)
        self.assertEqual(len(audit.needs_action), 0)
        self.assertEqual(len(audit.errors), 1)
        record = audit.errors[0]
        self.assertIsInstance(record, workspace_auth_domain_audit_results.Remove)
        self.assertEqual(record.workspace, self.upload_workspace.workspace)
        self.assertEqual(record.managed_group, self.gregor_all_group)
        self.assertEqual(record.current_membership_instance, membership)
        self.assertEqual(record.note, upload_workspace_audit.UploadWorkspaceAuthDomainAudit.GREGOR_ALL_BEFORE_COMBINED)

    def test_gregor_all_admin(self):
        membership = GroupGroupMembershipFactory.create(
            parent_group=self.upload_workspace.workspace.authorization_domains.first(),
            child_group=self.gregor_all_group,
            role=GroupGroupMembership.ADMIN,
        )
        audit = upload_workspace_audit.UploadWorkspaceAuthDomainAudit()
        audit.audit_workspace_and_group(self.upload_workspace, self.gregor_all_group)
        self.assertEqual(len(audit.verified), 0)
        self.assertEqual(len(audit.needs_action), 0)
        self.assertEqual(len(audit.errors), 1)
        record = audit.errors[0]
        self.assertIsInstance(record, workspace_auth_domain_audit_results.Remove)
        self.assertEqual(record.workspace, self.upload_workspace.workspace)
        self.assertEqual(record.managed_group, self.gregor_all_group)
        self.assertEqual(record.current_membership_instance, membership)
        self.assertEqual(record.note, upload_workspace_audit.UploadWorkspaceAuthDomainAudit.GREGOR_ALL_BEFORE_COMBINED)

    def test_other_group_not_member(self):
        audit = upload_workspace_audit.UploadWorkspaceAuthDomainAudit()
        audit.audit_workspace_and_group(self.upload_workspace, self.other_group)
        self.assertEqual(len(audit.verified), 1)
        self.assertEqual(len(audit.needs_action), 0)
        self.assertEqual(len(audit.errors), 0)
        record = audit.verified[0]
        self.assertIsInstance(record, workspace_auth_domain_audit_results.VerifiedNotMember)
        self.assertEqual(record.workspace, self.upload_workspace.workspace)
        self.assertEqual(record.managed_group, self.other_group)
        self.assertIsNone(record.current_membership_instance)
        self.assertEqual(record.note, upload_workspace_audit.UploadWorkspaceAuthDomainAudit.OTHER_GROUP)

    def test_other_group_member(self):
        membership = GroupGroupMembershipFactory.create(
            parent_group=self.upload_workspace.workspace.authorization_domains.first(),
            child_group=self.other_group,
            role=GroupGroupMembership.MEMBER,
        )
        audit = upload_workspace_audit.UploadWorkspaceAuthDomainAudit()
        audit.audit_workspace_and_group(self.upload_workspace, self.other_group)
        self.assertEqual(len(audit.verified), 0)
        self.assertEqual(len(audit.needs_action), 0)
        self.assertEqual(len(audit.errors), 1)
        record = audit.errors[0]
        self.assertIsInstance(record, workspace_auth_domain_audit_results.Remove)
        self.assertEqual(record.workspace, self.upload_workspace.workspace)
        self.assertEqual(record.managed_group, self.other_group)
        self.assertEqual(record.current_membership_instance, membership)
        self.assertEqual(record.note, upload_workspace_audit.UploadWorkspaceAuthDomainAudit.OTHER_GROUP)

    def test_other_group_admin(self):
        membership = GroupGroupMembershipFactory.create(
            parent_group=self.upload_workspace.workspace.authorization_domains.first(),
            child_group=self.other_group,
            role=GroupGroupMembership.ADMIN,
        )
        audit = upload_workspace_audit.UploadWorkspaceAuthDomainAudit()
        audit.audit_workspace_and_group(self.upload_workspace, self.other_group)
        self.assertEqual(len(audit.verified), 0)
        self.assertEqual(len(audit.needs_action), 0)
        self.assertEqual(len(audit.errors), 1)
        record = audit.errors[0]
        self.assertIsInstance(record, workspace_auth_domain_audit_results.Remove)
        self.assertEqual(record.workspace, self.upload_workspace.workspace)
        self.assertEqual(record.managed_group, self.other_group)
        self.assertEqual(record.current_membership_instance, membership)
        self.assertEqual(record.note, upload_workspace_audit.UploadWorkspaceAuthDomainAudit.OTHER_GROUP)

    def test_anvil_admins_not_member(self):
        audit = upload_workspace_audit.UploadWorkspaceAuthDomainAudit()
        audit.audit_workspace_and_group(self.upload_workspace, self.anvil_admins)
        self.assertEqual(len(audit.verified), 0)
        self.assertEqual(len(audit.needs_action), 0)
        self.assertEqual(len(audit.errors), 0)

    def test_anvil_admins_member(self):
        GroupGroupMembershipFactory.create(
            parent_group=self.upload_workspace.workspace.authorization_domains.first(),
            child_group=self.anvil_admins,
            role=GroupGroupMembership.MEMBER,
        )
        audit = upload_workspace_audit.UploadWorkspaceAuthDomainAudit()
        audit.audit_workspace_and_group(self.upload_workspace, self.anvil_admins)
        self.assertEqual(len(audit.verified), 0)
        self.assertEqual(len(audit.needs_action), 0)
        self.assertEqual(len(audit.errors), 0)

    def test_anvil_admins_admin(self):
        GroupGroupMembershipFactory.create(
            parent_group=self.upload_workspace.workspace.authorization_domains.first(),
            child_group=self.anvil_admins,
            role=GroupGroupMembership.ADMIN,
        )
        audit = upload_workspace_audit.UploadWorkspaceAuthDomainAudit()
        audit.audit_workspace_and_group(self.upload_workspace, self.anvil_admins)
        self.assertEqual(len(audit.verified), 0)
        self.assertEqual(len(audit.needs_action), 0)
        self.assertEqual(len(audit.errors), 0)

    def test_anvil_devs_not_member(self):
        audit = upload_workspace_audit.UploadWorkspaceAuthDomainAudit()
        audit.audit_workspace_and_group(self.upload_workspace, self.anvil_devs)
        self.assertEqual(len(audit.verified), 0)
        self.assertEqual(len(audit.needs_action), 0)
        self.assertEqual(len(audit.errors), 0)

    def test_anvil_devs_member(self):
        GroupGroupMembershipFactory.create(
            parent_group=self.upload_workspace.workspace.authorization_domains.first(),
            child_group=self.anvil_devs,
            role=GroupGroupMembership.MEMBER,
        )
        audit = upload_workspace_audit.UploadWorkspaceAuthDomainAudit()
        audit.audit_workspace_and_group(self.upload_workspace, self.anvil_devs)
        self.assertEqual(len(audit.verified), 0)
        self.assertEqual(len(audit.needs_action), 0)
        self.assertEqual(len(audit.errors), 0)

    def test_anvil_devs_admin(self):
        GroupGroupMembershipFactory.create(
            parent_group=self.upload_workspace.workspace.authorization_domains.first(),
            child_group=self.anvil_devs,
            role=GroupGroupMembership.ADMIN,
        )
        audit = upload_workspace_audit.UploadWorkspaceAuthDomainAudit()
        audit.audit_workspace_and_group(self.upload_workspace, self.anvil_devs)
        self.assertEqual(len(audit.verified), 0)
        self.assertEqual(len(audit.needs_action), 0)
        self.assertEqual(len(audit.errors), 0)


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
        audit = upload_workspace_audit.UploadWorkspaceAuthDomainAudit()
        audit.audit_workspace_and_group(self.upload_workspace, self.rc_uploader_group)
        self.assertEqual(len(audit.verified), 1)
        self.assertEqual(len(audit.needs_action), 0)
        self.assertEqual(len(audit.errors), 0)
        record = audit.verified[0]
        self.assertIsInstance(record, workspace_auth_domain_audit_results.VerifiedNotMember)
        self.assertEqual(record.workspace, self.upload_workspace.workspace)
        self.assertEqual(record.managed_group, self.rc_uploader_group)
        self.assertIsNone(record.current_membership_instance)
        self.assertEqual(record.note, upload_workspace_audit.UploadWorkspaceAuthDomainAudit.RC_UPLOADERS_AFTER_QC)

    def test_rc_uploaders_member(self):
        membership = GroupGroupMembershipFactory.create(
            parent_group=self.upload_workspace.workspace.authorization_domains.first(),
            child_group=self.rc_uploader_group,
            role=GroupGroupMembership.MEMBER,
        )
        audit = upload_workspace_audit.UploadWorkspaceAuthDomainAudit()
        audit.audit_workspace_and_group(self.upload_workspace, self.rc_uploader_group)
        self.assertEqual(len(audit.verified), 0)
        self.assertEqual(len(audit.needs_action), 1)
        self.assertEqual(len(audit.errors), 0)
        record = audit.needs_action[0]
        self.assertIsInstance(record, workspace_auth_domain_audit_results.Remove)
        self.assertEqual(record.workspace, self.upload_workspace.workspace)
        self.assertEqual(record.managed_group, self.rc_uploader_group)
        self.assertEqual(record.current_membership_instance, membership)
        self.assertEqual(record.note, upload_workspace_audit.UploadWorkspaceAuthDomainAudit.RC_UPLOADERS_AFTER_QC)

    def test_rc_uploaders_admin(self):
        membership = GroupGroupMembershipFactory.create(
            parent_group=self.upload_workspace.workspace.authorization_domains.first(),
            child_group=self.rc_uploader_group,
            role=GroupGroupMembership.ADMIN,
        )
        audit = upload_workspace_audit.UploadWorkspaceAuthDomainAudit()
        audit.audit_workspace_and_group(self.upload_workspace, self.rc_uploader_group)
        self.assertEqual(len(audit.verified), 0)
        self.assertEqual(len(audit.needs_action), 0)
        self.assertEqual(len(audit.errors), 1)
        record = audit.errors[0]
        self.assertIsInstance(record, workspace_auth_domain_audit_results.Remove)
        self.assertEqual(record.workspace, self.upload_workspace.workspace)
        self.assertEqual(record.managed_group, self.rc_uploader_group)
        self.assertEqual(record.current_membership_instance, membership)
        self.assertEqual(record.note, upload_workspace_audit.UploadWorkspaceAuthDomainAudit.RC_UPLOADERS_AFTER_QC)

    def test_rc_members_not_member(self):
        audit = upload_workspace_audit.UploadWorkspaceAuthDomainAudit()
        audit.audit_workspace_and_group(self.upload_workspace, self.rc_member_group)
        self.assertEqual(len(audit.verified), 1)
        self.assertEqual(len(audit.needs_action), 0)
        self.assertEqual(len(audit.errors), 0)
        record = audit.verified[0]
        self.assertIsInstance(record, workspace_auth_domain_audit_results.VerifiedNotMember)
        self.assertEqual(record.workspace, self.upload_workspace.workspace)
        self.assertEqual(record.managed_group, self.rc_member_group)
        self.assertIsNone(record.current_membership_instance)
        self.assertEqual(record.note, upload_workspace_audit.UploadWorkspaceAuthDomainAudit.RC_MEMBERS_AFTER_COMBINED)

    def test_rc_members_member(self):
        membership = GroupGroupMembershipFactory.create(
            parent_group=self.upload_workspace.workspace.authorization_domains.first(),
            child_group=self.rc_member_group,
            role=GroupGroupMembership.MEMBER,
        )
        audit = upload_workspace_audit.UploadWorkspaceAuthDomainAudit()
        audit.audit_workspace_and_group(self.upload_workspace, self.rc_member_group)
        self.assertEqual(len(audit.verified), 0)
        self.assertEqual(len(audit.needs_action), 1)
        self.assertEqual(len(audit.errors), 0)
        record = audit.needs_action[0]
        self.assertIsInstance(record, workspace_auth_domain_audit_results.Remove)
        self.assertEqual(record.workspace, self.upload_workspace.workspace)
        self.assertEqual(record.managed_group, self.rc_member_group)
        self.assertEqual(record.current_membership_instance, membership)
        self.assertEqual(record.note, upload_workspace_audit.UploadWorkspaceAuthDomainAudit.RC_MEMBERS_AFTER_COMBINED)

    def test_rc_members_admin(self):
        membership = GroupGroupMembershipFactory.create(
            parent_group=self.upload_workspace.workspace.authorization_domains.first(),
            child_group=self.rc_member_group,
            role=GroupGroupMembership.ADMIN,
        )
        audit = upload_workspace_audit.UploadWorkspaceAuthDomainAudit()
        audit.audit_workspace_and_group(self.upload_workspace, self.rc_member_group)
        self.assertEqual(len(audit.verified), 0)
        self.assertEqual(len(audit.needs_action), 0)
        self.assertEqual(len(audit.errors), 1)
        record = audit.errors[0]
        self.assertIsInstance(record, workspace_auth_domain_audit_results.Remove)
        self.assertEqual(record.workspace, self.upload_workspace.workspace)
        self.assertEqual(record.managed_group, self.rc_member_group)
        self.assertEqual(record.current_membership_instance, membership)
        self.assertEqual(record.note, upload_workspace_audit.UploadWorkspaceAuthDomainAudit.RC_MEMBERS_AFTER_COMBINED)

    def test_rc_non_members_not_member(self):
        audit = upload_workspace_audit.UploadWorkspaceAuthDomainAudit()
        audit.audit_workspace_and_group(self.upload_workspace, self.rc_non_member_group)
        self.assertEqual(len(audit.verified), 0)
        self.assertEqual(len(audit.needs_action), 1)
        self.assertEqual(len(audit.errors), 0)
        record = audit.needs_action[0]
        self.assertIsInstance(record, workspace_auth_domain_audit_results.AddMember)
        self.assertEqual(record.workspace, self.upload_workspace.workspace)
        self.assertEqual(record.managed_group, self.rc_non_member_group)
        self.assertIsNone(record.current_membership_instance)
        self.assertEqual(record.note, upload_workspace_audit.UploadWorkspaceAuthDomainAudit.RC_NON_MEMBERS_AFTER_START)

    def test_rc_non_members_member(self):
        membership = GroupGroupMembershipFactory.create(
            parent_group=self.upload_workspace.workspace.authorization_domains.first(),
            child_group=self.rc_non_member_group,
            role=GroupGroupMembership.MEMBER,
        )
        audit = upload_workspace_audit.UploadWorkspaceAuthDomainAudit()
        audit.audit_workspace_and_group(self.upload_workspace, self.rc_non_member_group)
        self.assertEqual(len(audit.verified), 1)
        self.assertEqual(len(audit.needs_action), 0)
        self.assertEqual(len(audit.errors), 0)
        record = audit.verified[0]
        self.assertIsInstance(record, workspace_auth_domain_audit_results.VerifiedMember)
        self.assertEqual(record.workspace, self.upload_workspace.workspace)
        self.assertEqual(record.managed_group, self.rc_non_member_group)
        self.assertEqual(record.current_membership_instance, membership)
        self.assertEqual(record.note, upload_workspace_audit.UploadWorkspaceAuthDomainAudit.RC_NON_MEMBERS_AFTER_START)

    def test_rc_non_members_admin(self):
        membership = GroupGroupMembershipFactory.create(
            parent_group=self.upload_workspace.workspace.authorization_domains.first(),
            child_group=self.rc_non_member_group,
            role=GroupGroupMembership.ADMIN,
        )
        audit = upload_workspace_audit.UploadWorkspaceAuthDomainAudit()
        audit.audit_workspace_and_group(self.upload_workspace, self.rc_non_member_group)
        self.assertEqual(len(audit.verified), 0)
        self.assertEqual(len(audit.needs_action), 0)
        self.assertEqual(len(audit.errors), 1)
        record = audit.errors[0]
        self.assertIsInstance(record, workspace_auth_domain_audit_results.ChangeToMember)
        self.assertEqual(record.workspace, self.upload_workspace.workspace)
        self.assertEqual(record.managed_group, self.rc_non_member_group)
        self.assertEqual(record.current_membership_instance, membership)
        self.assertEqual(record.note, upload_workspace_audit.UploadWorkspaceAuthDomainAudit.RC_NON_MEMBERS_AFTER_START)

    def test_dcc_admins_not_member(self):
        audit = upload_workspace_audit.UploadWorkspaceAuthDomainAudit()
        audit.audit_workspace_and_group(self.upload_workspace, self.dcc_admin_group)
        self.assertEqual(len(audit.verified), 0)
        self.assertEqual(len(audit.needs_action), 1)
        self.assertEqual(len(audit.errors), 0)
        record = audit.needs_action[0]
        self.assertIsInstance(record, workspace_auth_domain_audit_results.AddAdmin)
        self.assertEqual(record.workspace, self.upload_workspace.workspace)
        self.assertEqual(record.managed_group, self.dcc_admin_group)
        self.assertIsNone(record.current_membership_instance)
        self.assertEqual(record.note, upload_workspace_audit.UploadWorkspaceAuthDomainAudit.DCC_ADMINS)

    def test_dcc_admins_member(self):
        membership = GroupGroupMembershipFactory.create(
            parent_group=self.upload_workspace.workspace.authorization_domains.first(),
            child_group=self.dcc_admin_group,
            role=GroupGroupMembership.MEMBER,
        )
        audit = upload_workspace_audit.UploadWorkspaceAuthDomainAudit()
        audit.audit_workspace_and_group(self.upload_workspace, self.dcc_admin_group)
        self.assertEqual(len(audit.verified), 0)
        self.assertEqual(len(audit.needs_action), 1)
        self.assertEqual(len(audit.errors), 0)
        record = audit.needs_action[0]
        self.assertIsInstance(record, workspace_auth_domain_audit_results.ChangeToAdmin)
        self.assertEqual(record.workspace, self.upload_workspace.workspace)
        self.assertEqual(record.managed_group, self.dcc_admin_group)
        self.assertEqual(record.current_membership_instance, membership)
        self.assertEqual(record.note, upload_workspace_audit.UploadWorkspaceAuthDomainAudit.DCC_ADMINS)

    def test_dcc_admins_admin(self):
        membership = GroupGroupMembershipFactory.create(
            parent_group=self.upload_workspace.workspace.authorization_domains.first(),
            child_group=self.dcc_admin_group,
            role=GroupGroupMembership.ADMIN,
        )
        audit = upload_workspace_audit.UploadWorkspaceAuthDomainAudit()
        audit.audit_workspace_and_group(self.upload_workspace, self.dcc_admin_group)
        self.assertEqual(len(audit.verified), 1)
        self.assertEqual(len(audit.needs_action), 0)
        self.assertEqual(len(audit.errors), 0)
        record = audit.verified[0]
        self.assertIsInstance(record, workspace_auth_domain_audit_results.VerifiedAdmin)
        self.assertEqual(record.workspace, self.upload_workspace.workspace)
        self.assertEqual(record.managed_group, self.dcc_admin_group)
        self.assertEqual(record.current_membership_instance, membership)
        self.assertEqual(record.note, upload_workspace_audit.UploadWorkspaceAuthDomainAudit.DCC_ADMINS)

    @override_settings(ANVIL_DCC_ADMINS_GROUP_NAME="foobar")
    def test_dcc_admins_different_setting(self):
        group = ManagedGroupFactory.create(name="foobar")
        audit = upload_workspace_audit.UploadWorkspaceAuthDomainAudit()
        audit.audit_workspace_and_group(self.upload_workspace, group)
        self.assertEqual(len(audit.verified), 0)
        self.assertEqual(len(audit.needs_action), 1)
        self.assertEqual(len(audit.errors), 0)
        record = audit.needs_action[0]
        self.assertIsInstance(record, workspace_auth_domain_audit_results.AddAdmin)
        self.assertEqual(record.workspace, self.upload_workspace.workspace)
        self.assertEqual(record.managed_group, group)
        self.assertIsNone(record.current_membership_instance)
        self.assertEqual(record.note, upload_workspace_audit.UploadWorkspaceAuthDomainAudit.DCC_ADMINS)

    def test_dcc_writers_not_member(self):
        audit = upload_workspace_audit.UploadWorkspaceAuthDomainAudit()
        audit.audit_workspace_and_group(self.upload_workspace, self.dcc_writer_group)
        self.assertEqual(len(audit.verified), 1)
        self.assertEqual(len(audit.needs_action), 0)
        self.assertEqual(len(audit.errors), 0)
        record = audit.verified[0]
        self.assertIsInstance(record, workspace_auth_domain_audit_results.VerifiedNotMember)
        self.assertEqual(record.workspace, self.upload_workspace.workspace)
        self.assertEqual(record.managed_group, self.dcc_writer_group)
        self.assertIsNone(record.current_membership_instance)
        self.assertEqual(record.note, upload_workspace_audit.UploadWorkspaceAuthDomainAudit.DCC_AFTER_COMBINED)

    def test_dcc_writers_member(self):
        membership = GroupGroupMembershipFactory.create(
            parent_group=self.upload_workspace.workspace.authorization_domains.first(),
            child_group=self.dcc_writer_group,
            role=GroupGroupMembership.MEMBER,
        )
        audit = upload_workspace_audit.UploadWorkspaceAuthDomainAudit()
        audit.audit_workspace_and_group(self.upload_workspace, self.dcc_writer_group)
        self.assertEqual(len(audit.verified), 0)
        self.assertEqual(len(audit.needs_action), 1)
        self.assertEqual(len(audit.errors), 0)
        record = audit.needs_action[0]
        self.assertIsInstance(record, workspace_auth_domain_audit_results.Remove)
        self.assertEqual(record.workspace, self.upload_workspace.workspace)
        self.assertEqual(record.managed_group, self.dcc_writer_group)
        self.assertEqual(record.current_membership_instance, membership)
        self.assertEqual(record.note, upload_workspace_audit.UploadWorkspaceAuthDomainAudit.DCC_AFTER_COMBINED)

    def test_dcc_writers_admin(self):
        membership = GroupGroupMembershipFactory.create(
            parent_group=self.upload_workspace.workspace.authorization_domains.first(),
            child_group=self.dcc_writer_group,
            role=GroupGroupMembership.ADMIN,
        )
        audit = upload_workspace_audit.UploadWorkspaceAuthDomainAudit()
        audit.audit_workspace_and_group(self.upload_workspace, self.dcc_writer_group)
        self.assertEqual(len(audit.verified), 0)
        self.assertEqual(len(audit.needs_action), 0)
        self.assertEqual(len(audit.errors), 1)
        record = audit.errors[0]
        self.assertIsInstance(record, workspace_auth_domain_audit_results.Remove)
        self.assertEqual(record.workspace, self.upload_workspace.workspace)
        self.assertEqual(record.managed_group, self.dcc_writer_group)
        self.assertEqual(record.current_membership_instance, membership)
        self.assertEqual(record.note, upload_workspace_audit.UploadWorkspaceAuthDomainAudit.DCC_AFTER_COMBINED)

    def test_dcc_members_not_member(self):
        audit = upload_workspace_audit.UploadWorkspaceAuthDomainAudit()
        audit.audit_workspace_and_group(self.upload_workspace, self.dcc_member_group)
        self.assertEqual(len(audit.verified), 1)
        self.assertEqual(len(audit.needs_action), 0)
        self.assertEqual(len(audit.errors), 0)
        record = audit.verified[0]
        self.assertIsInstance(record, workspace_auth_domain_audit_results.VerifiedNotMember)
        self.assertEqual(record.workspace, self.upload_workspace.workspace)
        self.assertEqual(record.managed_group, self.dcc_member_group)
        self.assertIsNone(record.current_membership_instance)
        self.assertEqual(record.note, upload_workspace_audit.UploadWorkspaceAuthDomainAudit.DCC_AFTER_COMBINED)

    def test_dcc_members_member(self):
        membership = GroupGroupMembershipFactory.create(
            parent_group=self.upload_workspace.workspace.authorization_domains.first(),
            child_group=self.dcc_member_group,
            role=GroupGroupMembership.MEMBER,
        )
        audit = upload_workspace_audit.UploadWorkspaceAuthDomainAudit()
        audit.audit_workspace_and_group(self.upload_workspace, self.dcc_member_group)
        self.assertEqual(len(audit.verified), 0)
        self.assertEqual(len(audit.needs_action), 1)
        self.assertEqual(len(audit.errors), 0)
        record = audit.needs_action[0]
        self.assertIsInstance(record, workspace_auth_domain_audit_results.Remove)
        self.assertEqual(record.workspace, self.upload_workspace.workspace)
        self.assertEqual(record.managed_group, self.dcc_member_group)
        self.assertEqual(record.current_membership_instance, membership)
        self.assertEqual(record.note, upload_workspace_audit.UploadWorkspaceAuthDomainAudit.DCC_AFTER_COMBINED)

    def test_dcc_members_admin(self):
        membership = GroupGroupMembershipFactory.create(
            parent_group=self.upload_workspace.workspace.authorization_domains.first(),
            child_group=self.dcc_member_group,
            role=GroupGroupMembership.ADMIN,
        )
        audit = upload_workspace_audit.UploadWorkspaceAuthDomainAudit()
        audit.audit_workspace_and_group(self.upload_workspace, self.dcc_member_group)
        self.assertEqual(len(audit.verified), 0)
        self.assertEqual(len(audit.needs_action), 0)
        self.assertEqual(len(audit.errors), 1)
        record = audit.errors[0]
        self.assertIsInstance(record, workspace_auth_domain_audit_results.Remove)
        self.assertEqual(record.workspace, self.upload_workspace.workspace)
        self.assertEqual(record.managed_group, self.dcc_member_group)
        self.assertEqual(record.current_membership_instance, membership)
        self.assertEqual(record.note, upload_workspace_audit.UploadWorkspaceAuthDomainAudit.DCC_AFTER_COMBINED)

    def test_gregor_all_not_member(self):
        audit = upload_workspace_audit.UploadWorkspaceAuthDomainAudit()
        audit.audit_workspace_and_group(self.upload_workspace, self.gregor_all_group)
        self.assertEqual(len(audit.verified), 0)
        self.assertEqual(len(audit.needs_action), 1)
        self.assertEqual(len(audit.errors), 0)
        record = audit.needs_action[0]
        self.assertIsInstance(record, workspace_auth_domain_audit_results.AddMember)
        self.assertEqual(record.workspace, self.upload_workspace.workspace)
        self.assertEqual(record.managed_group, self.gregor_all_group)
        self.assertIsNone(record.current_membership_instance)
        self.assertEqual(record.note, upload_workspace_audit.UploadWorkspaceAuthDomainAudit.GREGOR_ALL_AFTER_COMBINED)

    def test_gregor_all_member(self):
        membership = GroupGroupMembershipFactory.create(
            parent_group=self.upload_workspace.workspace.authorization_domains.first(),
            child_group=self.gregor_all_group,
            role=GroupGroupMembership.MEMBER,
        )
        audit = upload_workspace_audit.UploadWorkspaceAuthDomainAudit()
        audit.audit_workspace_and_group(self.upload_workspace, self.gregor_all_group)
        self.assertEqual(len(audit.verified), 1)
        self.assertEqual(len(audit.needs_action), 0)
        self.assertEqual(len(audit.errors), 0)
        record = audit.verified[0]
        self.assertIsInstance(record, workspace_auth_domain_audit_results.VerifiedMember)
        self.assertEqual(record.workspace, self.upload_workspace.workspace)
        self.assertEqual(record.managed_group, self.gregor_all_group)
        self.assertEqual(record.current_membership_instance, membership)
        self.assertEqual(record.note, upload_workspace_audit.UploadWorkspaceAuthDomainAudit.GREGOR_ALL_AFTER_COMBINED)

    def test_gregor_all_admin(self):
        membership = GroupGroupMembershipFactory.create(
            parent_group=self.upload_workspace.workspace.authorization_domains.first(),
            child_group=self.gregor_all_group,
            role=GroupGroupMembership.ADMIN,
        )
        audit = upload_workspace_audit.UploadWorkspaceAuthDomainAudit()
        audit.audit_workspace_and_group(self.upload_workspace, self.gregor_all_group)
        self.assertEqual(len(audit.verified), 0)
        self.assertEqual(len(audit.needs_action), 0)
        self.assertEqual(len(audit.errors), 1)
        record = audit.errors[0]
        self.assertIsInstance(record, workspace_auth_domain_audit_results.ChangeToMember)
        self.assertEqual(record.workspace, self.upload_workspace.workspace)
        self.assertEqual(record.managed_group, self.gregor_all_group)
        self.assertEqual(record.current_membership_instance, membership)
        self.assertEqual(record.note, upload_workspace_audit.UploadWorkspaceAuthDomainAudit.GREGOR_ALL_AFTER_COMBINED)

    def test_other_group_not_member(self):
        audit = upload_workspace_audit.UploadWorkspaceAuthDomainAudit()
        audit.audit_workspace_and_group(self.upload_workspace, self.other_group)
        self.assertEqual(len(audit.verified), 1)
        self.assertEqual(len(audit.needs_action), 0)
        self.assertEqual(len(audit.errors), 0)
        record = audit.verified[0]
        self.assertIsInstance(record, workspace_auth_domain_audit_results.VerifiedNotMember)
        self.assertEqual(record.workspace, self.upload_workspace.workspace)
        self.assertEqual(record.managed_group, self.other_group)
        self.assertIsNone(record.current_membership_instance)
        self.assertEqual(record.note, upload_workspace_audit.UploadWorkspaceAuthDomainAudit.OTHER_GROUP)

    def test_other_group_member(self):
        membership = GroupGroupMembershipFactory.create(
            parent_group=self.upload_workspace.workspace.authorization_domains.first(),
            child_group=self.other_group,
            role=GroupGroupMembership.MEMBER,
        )
        audit = upload_workspace_audit.UploadWorkspaceAuthDomainAudit()
        audit.audit_workspace_and_group(self.upload_workspace, self.other_group)
        self.assertEqual(len(audit.verified), 0)
        self.assertEqual(len(audit.needs_action), 0)
        self.assertEqual(len(audit.errors), 1)
        record = audit.errors[0]
        self.assertIsInstance(record, workspace_auth_domain_audit_results.Remove)
        self.assertEqual(record.workspace, self.upload_workspace.workspace)
        self.assertEqual(record.managed_group, self.other_group)
        self.assertEqual(record.current_membership_instance, membership)
        self.assertEqual(record.note, upload_workspace_audit.UploadWorkspaceAuthDomainAudit.OTHER_GROUP)

    def test_other_group_admin(self):
        membership = GroupGroupMembershipFactory.create(
            parent_group=self.upload_workspace.workspace.authorization_domains.first(),
            child_group=self.other_group,
            role=GroupGroupMembership.ADMIN,
        )
        audit = upload_workspace_audit.UploadWorkspaceAuthDomainAudit()
        audit.audit_workspace_and_group(self.upload_workspace, self.other_group)
        self.assertEqual(len(audit.verified), 0)
        self.assertEqual(len(audit.needs_action), 0)
        self.assertEqual(len(audit.errors), 1)
        record = audit.errors[0]
        self.assertIsInstance(record, workspace_auth_domain_audit_results.Remove)
        self.assertEqual(record.workspace, self.upload_workspace.workspace)
        self.assertEqual(record.managed_group, self.other_group)
        self.assertEqual(record.current_membership_instance, membership)
        self.assertEqual(record.note, upload_workspace_audit.UploadWorkspaceAuthDomainAudit.OTHER_GROUP)

    def test_anvil_admins_not_member(self):
        audit = upload_workspace_audit.UploadWorkspaceAuthDomainAudit()
        audit.audit_workspace_and_group(self.upload_workspace, self.anvil_admins)
        self.assertEqual(len(audit.verified), 0)
        self.assertEqual(len(audit.needs_action), 0)
        self.assertEqual(len(audit.errors), 0)

    def test_anvil_admins_member(self):
        GroupGroupMembershipFactory.create(
            parent_group=self.upload_workspace.workspace.authorization_domains.first(),
            child_group=self.anvil_admins,
            role=GroupGroupMembership.MEMBER,
        )
        audit = upload_workspace_audit.UploadWorkspaceAuthDomainAudit()
        audit.audit_workspace_and_group(self.upload_workspace, self.anvil_admins)
        self.assertEqual(len(audit.verified), 0)
        self.assertEqual(len(audit.needs_action), 0)
        self.assertEqual(len(audit.errors), 0)

    def test_anvil_admins_admin(self):
        GroupGroupMembershipFactory.create(
            parent_group=self.upload_workspace.workspace.authorization_domains.first(),
            child_group=self.anvil_admins,
            role=GroupGroupMembership.ADMIN,
        )
        audit = upload_workspace_audit.UploadWorkspaceAuthDomainAudit()
        audit.audit_workspace_and_group(self.upload_workspace, self.anvil_admins)
        self.assertEqual(len(audit.verified), 0)
        self.assertEqual(len(audit.needs_action), 0)
        self.assertEqual(len(audit.errors), 0)

    def test_anvil_devs_not_member(self):
        audit = upload_workspace_audit.UploadWorkspaceAuthDomainAudit()
        audit.audit_workspace_and_group(self.upload_workspace, self.anvil_devs)
        self.assertEqual(len(audit.verified), 0)
        self.assertEqual(len(audit.needs_action), 0)
        self.assertEqual(len(audit.errors), 0)

    def test_anvil_devs_member(self):
        GroupGroupMembershipFactory.create(
            parent_group=self.upload_workspace.workspace.authorization_domains.first(),
            child_group=self.anvil_devs,
            role=GroupGroupMembership.MEMBER,
        )
        audit = upload_workspace_audit.UploadWorkspaceAuthDomainAudit()
        audit.audit_workspace_and_group(self.upload_workspace, self.anvil_devs)
        self.assertEqual(len(audit.verified), 0)
        self.assertEqual(len(audit.needs_action), 0)
        self.assertEqual(len(audit.errors), 0)

    def test_anvil_devs_admin(self):
        GroupGroupMembershipFactory.create(
            parent_group=self.upload_workspace.workspace.authorization_domains.first(),
            child_group=self.anvil_devs,
            role=GroupGroupMembership.ADMIN,
        )
        audit = upload_workspace_audit.UploadWorkspaceAuthDomainAudit()
        audit.audit_workspace_and_group(self.upload_workspace, self.anvil_devs)
        self.assertEqual(len(audit.verified), 0)
        self.assertEqual(len(audit.needs_action), 0)
        self.assertEqual(len(audit.errors), 0)


class CombinedConsortiumWorkspaceAuthDomainAuditTest(TestCase):
    def test_completed(self):
        """The completed attribute is set appropriately."""
        # Instantiate the class.
        audit = combined_workspace_audit.CombinedConsortiumDataWorkspaceAuthDomainAudit()
        self.assertFalse(audit.completed)
        audit.run_audit()
        self.assertTrue(audit.completed)

    def test_no_workspaces(self):
        """The audit works if there are no combined workspaces."""
        audit = combined_workspace_audit.CombinedConsortiumDataWorkspaceAuthDomainAudit()
        audit.run_audit()
        self.assertEqual(len(audit.verified), 0)
        self.assertEqual(len(audit.needs_action), 0)
        self.assertEqual(len(audit.errors), 0)

    def test_one_workspace_no_groups(self):
        factories.CombinedConsortiumDataWorkspaceFactory.create()
        audit = combined_workspace_audit.CombinedConsortiumDataWorkspaceAuthDomainAudit()
        audit.run_audit()
        self.assertEqual(len(audit.verified), 0)
        self.assertEqual(len(audit.needs_action), 0)
        self.assertEqual(len(audit.errors), 0)

    def test_one_workspace_dcc_admin_group(self):
        group = ManagedGroupFactory.create(name=settings.ANVIL_DCC_ADMINS_GROUP_NAME)
        combined_workspace = factories.CombinedConsortiumDataWorkspaceFactory.create()
        audit = combined_workspace_audit.CombinedConsortiumDataWorkspaceAuthDomainAudit()
        audit.run_audit()
        self.assertEqual(len(audit.verified), 0)
        self.assertEqual(len(audit.needs_action), 1)
        self.assertEqual(len(audit.errors), 0)
        record = audit.needs_action[0]
        self.assertIsInstance(record, workspace_auth_domain_audit_results.AddAdmin)
        self.assertEqual(record.workspace, combined_workspace.workspace)
        self.assertEqual(record.managed_group, group)

    @override_settings(ANVIL_DCC_ADMINS_GROUP_NAME="foo")
    def test_one_workspace_dcc_admin_group_different_setting(self):
        group = ManagedGroupFactory.create(name="foo")
        combined_workspace = factories.CombinedConsortiumDataWorkspaceFactory.create()
        audit = combined_workspace_audit.CombinedConsortiumDataWorkspaceAuthDomainAudit()
        audit.run_audit()
        self.assertEqual(len(audit.verified), 0)
        self.assertEqual(len(audit.needs_action), 1)
        self.assertEqual(len(audit.errors), 0)
        record = audit.needs_action[0]
        self.assertIsInstance(record, workspace_auth_domain_audit_results.AddAdmin)
        self.assertEqual(record.workspace, combined_workspace.workspace)
        self.assertEqual(record.managed_group, group)

    def test_one_workspace_gregor_all_group(self):
        group = ManagedGroupFactory.create(name="GREGOR_ALL")
        combined_workspace = factories.CombinedConsortiumDataWorkspaceFactory.create()
        audit = combined_workspace_audit.CombinedConsortiumDataWorkspaceAuthDomainAudit()
        audit.run_audit()
        self.assertEqual(len(audit.verified), 0)
        self.assertEqual(len(audit.needs_action), 1)
        self.assertEqual(len(audit.errors), 0)
        record = audit.needs_action[0]
        self.assertIsInstance(record, workspace_auth_domain_audit_results.AddMember)
        self.assertEqual(record.workspace, combined_workspace.workspace)
        self.assertEqual(record.managed_group, group)

    def test_one_workspace_anvil_admins_group(self):
        ManagedGroupFactory.create(name="anvil-admins")
        factories.CombinedConsortiumDataWorkspaceFactory.create()
        audit = combined_workspace_audit.CombinedConsortiumDataWorkspaceAuthDomainAudit()
        audit.run_audit()
        self.assertEqual(len(audit.verified), 0)
        self.assertEqual(len(audit.needs_action), 0)
        self.assertEqual(len(audit.errors), 0)

    def test_one_workspace_anvil_devs_group(self):
        ManagedGroupFactory.create(name="anvil_devs")
        factories.CombinedConsortiumDataWorkspaceFactory.create()
        audit = combined_workspace_audit.CombinedConsortiumDataWorkspaceAuthDomainAudit()
        audit.run_audit()
        self.assertEqual(len(audit.verified), 0)
        self.assertEqual(len(audit.needs_action), 0)
        self.assertEqual(len(audit.errors), 0)

    def test_one_workspace_other_group_member(self):
        group = ManagedGroupFactory.create()
        combined_workspace = factories.CombinedConsortiumDataWorkspaceFactory.create()
        GroupGroupMembershipFactory.create(
            parent_group=combined_workspace.workspace.authorization_domains.first(), child_group=group
        )
        audit = combined_workspace_audit.CombinedConsortiumDataWorkspaceAuthDomainAudit()
        audit.run_audit()
        self.assertEqual(len(audit.verified), 0)
        self.assertEqual(len(audit.needs_action), 0)
        self.assertEqual(len(audit.errors), 1)
        record = audit.errors[0]
        self.assertIsInstance(record, workspace_auth_domain_audit_results.Remove)
        self.assertEqual(record.workspace, combined_workspace.workspace)
        self.assertEqual(record.managed_group, group)

    def test_one_workspace_other_group_not_member(self):
        ManagedGroupFactory.create()
        factories.CombinedConsortiumDataWorkspaceFactory.create()
        audit = combined_workspace_audit.CombinedConsortiumDataWorkspaceAuthDomainAudit()
        audit.run_audit()
        self.assertEqual(len(audit.verified), 0)
        self.assertEqual(len(audit.needs_action), 0)
        self.assertEqual(len(audit.errors), 0)

    def test_two_workspaces(self):
        """Audit works with two UploadWorkspaces."""
        group = ManagedGroupFactory.create(name=settings.ANVIL_DCC_ADMINS_GROUP_NAME)
        combined_workspace_1 = factories.CombinedConsortiumDataWorkspaceFactory.create()
        membership = GroupGroupMembershipFactory.create(
            parent_group=combined_workspace_1.workspace.authorization_domains.first(),
            child_group=group,
            role=GroupGroupMembership.ADMIN,
        )
        combined_workspace_2 = factories.CombinedConsortiumDataWorkspaceFactory.create()
        audit = combined_workspace_audit.CombinedConsortiumDataWorkspaceAuthDomainAudit()
        audit.run_audit()
        self.assertEqual(len(audit.verified), 1)
        self.assertEqual(len(audit.needs_action), 1)
        self.assertEqual(len(audit.errors), 0)
        record = audit.verified[0]
        self.assertIsInstance(record, workspace_auth_domain_audit_results.VerifiedAdmin)
        self.assertEqual(record.workspace, combined_workspace_1.workspace)
        self.assertEqual(record.managed_group, group)
        self.assertEqual(record.current_membership_instance, membership)
        record = audit.needs_action[0]
        self.assertIsInstance(record, workspace_auth_domain_audit_results.AddAdmin)
        self.assertEqual(record.workspace, combined_workspace_2.workspace)
        self.assertEqual(record.managed_group, group)
        self.assertIsNone(record.current_membership_instance)

    def test_queryset(self):
        """Audit only runs on the specified queryset."""
        group = ManagedGroupFactory.create(name=settings.ANVIL_DCC_ADMINS_GROUP_NAME)
        combined_workspace_1 = factories.CombinedConsortiumDataWorkspaceFactory.create()
        membership = GroupGroupMembershipFactory.create(
            parent_group=combined_workspace_1.workspace.authorization_domains.first(),
            child_group=group,
            role=GroupGroupMembership.ADMIN,
        )
        combined_workspace_2 = factories.CombinedConsortiumDataWorkspaceFactory.create()
        # First application
        audit = combined_workspace_audit.CombinedConsortiumDataWorkspaceAuthDomainAudit(
            queryset=models.CombinedConsortiumDataWorkspace.objects.filter(pk=combined_workspace_1.pk)
        )
        audit.run_audit()
        self.assertEqual(len(audit.verified), 1)
        self.assertEqual(len(audit.needs_action), 0)
        self.assertEqual(len(audit.errors), 0)
        record = audit.verified[0]
        self.assertIsInstance(record, workspace_auth_domain_audit_results.VerifiedAdmin)
        self.assertEqual(record.workspace, combined_workspace_1.workspace)
        self.assertEqual(record.managed_group, group)
        self.assertEqual(record.current_membership_instance, membership)
        # Second application
        audit = combined_workspace_audit.CombinedConsortiumDataWorkspaceAuthDomainAudit(
            queryset=models.CombinedConsortiumDataWorkspace.objects.filter(pk=combined_workspace_2.pk)
        )
        audit.run_audit()
        self.assertEqual(len(audit.verified), 0)
        self.assertEqual(len(audit.needs_action), 1)
        self.assertEqual(len(audit.errors), 0)
        record = audit.needs_action[0]
        self.assertIsInstance(record, workspace_auth_domain_audit_results.AddAdmin)
        self.assertEqual(record.workspace, combined_workspace_2.workspace)
        self.assertEqual(record.managed_group, group)
        self.assertIsNone(record.current_membership_instance)

    def test_queryset_wrong_class(self):
        """Raises ValueError if queryset is not a QuerySet."""
        with self.assertRaises(ValueError):
            combined_workspace_audit.CombinedConsortiumDataWorkspaceAuthDomainAudit(queryset="foo")
        with self.assertRaises(ValueError):
            combined_workspace_audit.CombinedConsortiumDataWorkspaceAuthDomainAudit(
                queryset=models.UploadWorkspace.objects.all()
            )


class CombinedConsortiumWorkspaceAuthDomainAuditBeforeCompleteTest(TestCase):
    """Tests for the `CombinedConsortiumDataWorkspaceAuthDomainAudit` class for workspaces that are not yet complete."""

    def setUp(self):
        super().setUp()
        self.dcc_member_group = ManagedGroupFactory.create(name="GREGOR_DCC_MEMBERS")
        self.dcc_writer_group = ManagedGroupFactory.create(name="GREGOR_DCC_WRITERS")
        self.dcc_admin_group = ManagedGroupFactory.create(name=settings.ANVIL_DCC_ADMINS_GROUP_NAME)
        self.gregor_all_group = ManagedGroupFactory.create(name="GREGOR_ALL")
        self.combined_workspace = factories.CombinedConsortiumDataWorkspaceFactory.create(
            upload_cycle__is_past=True,
            date_completed=None,
        )
        self.auth_domain = self.combined_workspace.workspace.authorization_domains.first()
        self.other_group = ManagedGroupFactory.create()
        self.anvil_admins = ManagedGroupFactory.create(name="anvil-admins")
        self.anvil_devs = ManagedGroupFactory.create(name="anvil_devs")

    def test_dcc_admin_as_admin(self):
        membership = GroupGroupMembershipFactory.create(
            parent_group=self.combined_workspace.workspace.authorization_domains.first(),
            child_group=self.dcc_admin_group,
            role=GroupGroupMembership.ADMIN,
        )
        audit = combined_workspace_audit.CombinedConsortiumDataWorkspaceAuthDomainAudit()
        audit.audit_workspace_and_group(self.combined_workspace, self.dcc_admin_group)
        self.assertEqual(len(audit.verified), 1)
        self.assertEqual(len(audit.needs_action), 0)
        self.assertEqual(len(audit.errors), 0)
        record = audit.verified[0]
        self.assertIsInstance(record, workspace_auth_domain_audit_results.VerifiedAdmin)
        self.assertEqual(record.workspace, self.combined_workspace.workspace)
        self.assertEqual(record.managed_group, self.dcc_admin_group)
        self.assertEqual(record.current_membership_instance, membership)
        self.assertEqual(
            record.note, combined_workspace_audit.CombinedConsortiumDataWorkspaceAuthDomainAudit.DCC_ADMIN_AS_ADMIN
        )

    def test_dcc_admin_as_member(self):
        membership = GroupGroupMembershipFactory.create(
            parent_group=self.combined_workspace.workspace.authorization_domains.first(),
            child_group=self.dcc_admin_group,
            role=GroupGroupMembership.MEMBER,
        )
        audit = combined_workspace_audit.CombinedConsortiumDataWorkspaceAuthDomainAudit()
        audit.audit_workspace_and_group(self.combined_workspace, self.dcc_admin_group)
        self.assertEqual(len(audit.verified), 0)
        self.assertEqual(len(audit.needs_action), 1)
        self.assertEqual(len(audit.errors), 0)
        record = audit.needs_action[0]
        self.assertIsInstance(record, workspace_auth_domain_audit_results.ChangeToAdmin)
        self.assertEqual(record.workspace, self.combined_workspace.workspace)
        self.assertEqual(record.managed_group, self.dcc_admin_group)
        self.assertEqual(record.current_membership_instance, membership)
        self.assertEqual(
            record.note, combined_workspace_audit.CombinedConsortiumDataWorkspaceAuthDomainAudit.DCC_ADMIN_AS_ADMIN
        )

    def test_dcc_admin_not_member(self):
        audit = combined_workspace_audit.CombinedConsortiumDataWorkspaceAuthDomainAudit()
        audit.audit_workspace_and_group(self.combined_workspace, self.dcc_admin_group)
        self.assertEqual(len(audit.verified), 0)
        self.assertEqual(len(audit.needs_action), 1)
        self.assertEqual(len(audit.errors), 0)
        record = audit.needs_action[0]
        self.assertIsInstance(record, workspace_auth_domain_audit_results.AddAdmin)
        self.assertEqual(record.workspace, self.combined_workspace.workspace)
        self.assertEqual(record.managed_group, self.dcc_admin_group)
        self.assertIsNone(record.current_membership_instance)
        self.assertEqual(
            record.note, combined_workspace_audit.CombinedConsortiumDataWorkspaceAuthDomainAudit.DCC_ADMIN_AS_ADMIN
        )

    @override_settings(ANVIL_DCC_ADMINS_GROUP_NAME="foo")
    def test_dcc_admin_different_setting(self):
        group = ManagedGroupFactory.create(name="foo")
        audit = combined_workspace_audit.CombinedConsortiumDataWorkspaceAuthDomainAudit()
        audit.audit_workspace_and_group(self.combined_workspace, group)
        self.assertEqual(len(audit.verified), 0)
        self.assertEqual(len(audit.needs_action), 1)
        self.assertEqual(len(audit.errors), 0)
        record = audit.needs_action[0]
        self.assertIsInstance(record, workspace_auth_domain_audit_results.AddAdmin)
        self.assertEqual(record.workspace, self.combined_workspace.workspace)
        self.assertEqual(record.managed_group, group)
        self.assertIsNone(record.current_membership_instance)
        self.assertEqual(
            record.note, combined_workspace_audit.CombinedConsortiumDataWorkspaceAuthDomainAudit.DCC_ADMIN_AS_ADMIN
        )

    def test_gregor_all_as_admin(self):
        membership = GroupGroupMembershipFactory.create(
            parent_group=self.combined_workspace.workspace.authorization_domains.first(),
            child_group=self.gregor_all_group,
            role=GroupGroupMembership.ADMIN,
        )
        audit = combined_workspace_audit.CombinedConsortiumDataWorkspaceAuthDomainAudit()
        audit.audit_workspace_and_group(self.combined_workspace, self.gregor_all_group)
        self.assertEqual(len(audit.verified), 0)
        self.assertEqual(len(audit.needs_action), 0)
        self.assertEqual(len(audit.errors), 1)
        record = audit.errors[0]
        self.assertIsInstance(record, workspace_auth_domain_audit_results.ChangeToMember)
        self.assertEqual(record.workspace, self.combined_workspace.workspace)
        self.assertEqual(record.managed_group, self.gregor_all_group)
        self.assertEqual(record.current_membership_instance, membership)
        self.assertEqual(
            record.note,
            combined_workspace_audit.CombinedConsortiumDataWorkspaceAuthDomainAudit.GREGOR_ALL_AS_MEMBER,
        )

    def test_gregor_all_as_member(self):
        membership = GroupGroupMembershipFactory.create(
            parent_group=self.combined_workspace.workspace.authorization_domains.first(),
            child_group=self.gregor_all_group,
            role=GroupGroupMembership.MEMBER,
        )
        audit = combined_workspace_audit.CombinedConsortiumDataWorkspaceAuthDomainAudit()
        audit.audit_workspace_and_group(self.combined_workspace, self.gregor_all_group)
        self.assertEqual(len(audit.verified), 1)
        self.assertEqual(len(audit.needs_action), 0)
        self.assertEqual(len(audit.errors), 0)
        record = audit.verified[0]
        self.assertIsInstance(record, workspace_auth_domain_audit_results.VerifiedMember)
        self.assertEqual(record.workspace, self.combined_workspace.workspace)
        self.assertEqual(record.managed_group, self.gregor_all_group)
        self.assertEqual(record.current_membership_instance, membership)
        self.assertEqual(
            record.note, combined_workspace_audit.CombinedConsortiumDataWorkspaceAuthDomainAudit.GREGOR_ALL_AS_MEMBER
        )

    def test_gregor_all_not_member(self):
        audit = combined_workspace_audit.CombinedConsortiumDataWorkspaceAuthDomainAudit()
        audit.audit_workspace_and_group(self.combined_workspace, self.gregor_all_group)
        self.assertEqual(len(audit.verified), 0)
        self.assertEqual(len(audit.needs_action), 1)
        self.assertEqual(len(audit.errors), 0)
        record = audit.needs_action[0]
        self.assertIsInstance(record, workspace_auth_domain_audit_results.AddMember)
        self.assertEqual(record.workspace, self.combined_workspace.workspace)
        self.assertEqual(record.managed_group, self.gregor_all_group)
        self.assertIsNone(record.current_membership_instance)
        self.assertEqual(
            record.note, combined_workspace_audit.CombinedConsortiumDataWorkspaceAuthDomainAudit.GREGOR_ALL_AS_MEMBER
        )

    def test_anvil_admins_not_member(self):
        audit = combined_workspace_audit.CombinedConsortiumDataWorkspaceAuthDomainAudit()
        audit.audit_workspace_and_group(self.combined_workspace, self.anvil_admins)
        self.assertEqual(len(audit.verified), 0)
        self.assertEqual(len(audit.needs_action), 0)
        self.assertEqual(len(audit.errors), 0)

    def test_anvil_admins_member(self):
        GroupGroupMembershipFactory.create(
            parent_group=self.combined_workspace.workspace.authorization_domains.first(),
            child_group=self.anvil_admins,
            role=GroupGroupMembership.MEMBER,
        )
        audit = combined_workspace_audit.CombinedConsortiumDataWorkspaceAuthDomainAudit()
        audit.audit_workspace_and_group(self.combined_workspace, self.anvil_admins)
        self.assertEqual(len(audit.verified), 0)
        self.assertEqual(len(audit.needs_action), 0)
        self.assertEqual(len(audit.errors), 0)

    def test_anvil_admins_admin(self):
        GroupGroupMembershipFactory.create(
            parent_group=self.combined_workspace.workspace.authorization_domains.first(),
            child_group=self.anvil_admins,
            role=GroupGroupMembership.ADMIN,
        )
        audit = combined_workspace_audit.CombinedConsortiumDataWorkspaceAuthDomainAudit()
        audit.audit_workspace_and_group(self.combined_workspace, self.anvil_admins)
        self.assertEqual(len(audit.verified), 0)
        self.assertEqual(len(audit.needs_action), 0)
        self.assertEqual(len(audit.errors), 0)

    def test_anvil_devs_not_member(self):
        audit = combined_workspace_audit.CombinedConsortiumDataWorkspaceAuthDomainAudit()
        audit.audit_workspace_and_group(self.combined_workspace, self.anvil_devs)
        self.assertEqual(len(audit.verified), 0)
        self.assertEqual(len(audit.needs_action), 0)
        self.assertEqual(len(audit.errors), 0)

    def test_anvil_devs_member(self):
        GroupGroupMembershipFactory.create(
            parent_group=self.combined_workspace.workspace.authorization_domains.first(),
            child_group=self.anvil_devs,
            role=GroupGroupMembership.MEMBER,
        )
        audit = combined_workspace_audit.CombinedConsortiumDataWorkspaceAuthDomainAudit()
        audit.audit_workspace_and_group(self.combined_workspace, self.anvil_devs)
        self.assertEqual(len(audit.verified), 0)
        self.assertEqual(len(audit.needs_action), 0)
        self.assertEqual(len(audit.errors), 0)

    def test_anvil_devs_admin(self):
        GroupGroupMembershipFactory.create(
            parent_group=self.combined_workspace.workspace.authorization_domains.first(),
            child_group=self.anvil_devs,
            role=GroupGroupMembership.ADMIN,
        )
        audit = combined_workspace_audit.CombinedConsortiumDataWorkspaceAuthDomainAudit()
        audit.audit_workspace_and_group(self.combined_workspace, self.anvil_devs)
        self.assertEqual(len(audit.verified), 0)
        self.assertEqual(len(audit.needs_action), 0)
        self.assertEqual(len(audit.errors), 0)

    def test_other_group_as_admin(self):
        membership = GroupGroupMembershipFactory.create(
            parent_group=self.combined_workspace.workspace.authorization_domains.first(),
            child_group=self.other_group,
            role=GroupGroupMembership.ADMIN,
        )
        audit = combined_workspace_audit.CombinedConsortiumDataWorkspaceAuthDomainAudit()
        audit.audit_workspace_and_group(self.combined_workspace, self.other_group)
        self.assertEqual(len(audit.verified), 0)
        self.assertEqual(len(audit.needs_action), 0)
        self.assertEqual(len(audit.errors), 1)
        record = audit.errors[0]
        self.assertIsInstance(record, workspace_auth_domain_audit_results.Remove)
        self.assertEqual(record.workspace, self.combined_workspace.workspace)
        self.assertEqual(record.managed_group, self.other_group)
        self.assertEqual(record.current_membership_instance, membership)
        self.assertEqual(
            record.note,
            combined_workspace_audit.CombinedConsortiumDataWorkspaceAuthDomainAudit.OTHER_GROUP,
        )

    def test_other_group_as_member(self):
        membership = GroupGroupMembershipFactory.create(
            parent_group=self.combined_workspace.workspace.authorization_domains.first(),
            child_group=self.other_group,
            role=GroupGroupMembership.MEMBER,
        )
        audit = combined_workspace_audit.CombinedConsortiumDataWorkspaceAuthDomainAudit()
        audit.audit_workspace_and_group(self.combined_workspace, self.other_group)
        self.assertEqual(len(audit.verified), 0)
        self.assertEqual(len(audit.needs_action), 0)
        self.assertEqual(len(audit.errors), 1)
        record = audit.errors[0]
        self.assertIsInstance(record, workspace_auth_domain_audit_results.Remove)
        self.assertEqual(record.workspace, self.combined_workspace.workspace)
        self.assertEqual(record.managed_group, self.other_group)
        self.assertEqual(record.current_membership_instance, membership)
        self.assertEqual(
            record.note, combined_workspace_audit.CombinedConsortiumDataWorkspaceAuthDomainAudit.OTHER_GROUP
        )

    def test_other_group_not_member(self):
        audit = combined_workspace_audit.CombinedConsortiumDataWorkspaceAuthDomainAudit()
        audit.audit_workspace_and_group(self.combined_workspace, self.other_group)
        self.assertEqual(len(audit.verified), 1)
        self.assertEqual(len(audit.needs_action), 0)
        self.assertEqual(len(audit.errors), 0)
        record = audit.verified[0]
        self.assertIsInstance(record, workspace_auth_domain_audit_results.VerifiedNotMember)
        self.assertEqual(record.workspace, self.combined_workspace.workspace)
        self.assertEqual(record.managed_group, self.other_group)
        self.assertIsNone(record.current_membership_instance)
        self.assertEqual(
            record.note, combined_workspace_audit.CombinedConsortiumDataWorkspaceAuthDomainAudit.OTHER_GROUP
        )


class CombinedConsortiumWorkspaceAuthDomainAuditAfterCompleteTest(TestCase):
    """Tests for the `CombinedConsortiumDataWorkspaceAuthDomainAudit` class for workspaces that are complete."""

    def setUp(self):
        super().setUp()
        self.dcc_member_group = ManagedGroupFactory.create(name="GREGOR_DCC_MEMBERS")
        self.dcc_writer_group = ManagedGroupFactory.create(name="GREGOR_DCC_WRITERS")
        self.dcc_admin_group = ManagedGroupFactory.create(name=settings.ANVIL_DCC_ADMINS_GROUP_NAME)
        self.gregor_all_group = ManagedGroupFactory.create(name="GREGOR_ALL")
        self.combined_workspace = factories.CombinedConsortiumDataWorkspaceFactory.create(
            upload_cycle__is_past=True,
            date_completed=fake.date_this_year(before_today=True, after_today=False),
        )
        self.auth_domain = self.combined_workspace.workspace.authorization_domains.first()
        self.other_group = ManagedGroupFactory.create()
        self.anvil_admins = ManagedGroupFactory.create(name="anvil-admins")
        self.anvil_devs = ManagedGroupFactory.create(name="anvil_devs")

    def test_dcc_admin_as_admin(self):
        membership = GroupGroupMembershipFactory.create(
            parent_group=self.combined_workspace.workspace.authorization_domains.first(),
            child_group=self.dcc_admin_group,
            role=GroupGroupMembership.ADMIN,
        )
        audit = combined_workspace_audit.CombinedConsortiumDataWorkspaceAuthDomainAudit()
        audit.audit_workspace_and_group(self.combined_workspace, self.dcc_admin_group)
        self.assertEqual(len(audit.verified), 1)
        self.assertEqual(len(audit.needs_action), 0)
        self.assertEqual(len(audit.errors), 0)
        record = audit.verified[0]
        self.assertIsInstance(record, workspace_auth_domain_audit_results.VerifiedAdmin)
        self.assertEqual(record.workspace, self.combined_workspace.workspace)
        self.assertEqual(record.managed_group, self.dcc_admin_group)
        self.assertEqual(record.current_membership_instance, membership)
        self.assertEqual(
            record.note, combined_workspace_audit.CombinedConsortiumDataWorkspaceAuthDomainAudit.DCC_ADMIN_AS_ADMIN
        )

    def test_dcc_admin_as_member(self):
        membership = GroupGroupMembershipFactory.create(
            parent_group=self.combined_workspace.workspace.authorization_domains.first(),
            child_group=self.dcc_admin_group,
            role=GroupGroupMembership.MEMBER,
        )
        audit = combined_workspace_audit.CombinedConsortiumDataWorkspaceAuthDomainAudit()
        audit.audit_workspace_and_group(self.combined_workspace, self.dcc_admin_group)
        self.assertEqual(len(audit.verified), 0)
        self.assertEqual(len(audit.needs_action), 1)
        self.assertEqual(len(audit.errors), 0)
        record = audit.needs_action[0]
        self.assertIsInstance(record, workspace_auth_domain_audit_results.ChangeToAdmin)
        self.assertEqual(record.workspace, self.combined_workspace.workspace)
        self.assertEqual(record.managed_group, self.dcc_admin_group)
        self.assertEqual(record.current_membership_instance, membership)
        self.assertEqual(
            record.note, combined_workspace_audit.CombinedConsortiumDataWorkspaceAuthDomainAudit.DCC_ADMIN_AS_ADMIN
        )

    def test_dcc_admin_not_member(self):
        audit = combined_workspace_audit.CombinedConsortiumDataWorkspaceAuthDomainAudit()
        audit.audit_workspace_and_group(self.combined_workspace, self.dcc_admin_group)
        self.assertEqual(len(audit.verified), 0)
        self.assertEqual(len(audit.needs_action), 1)
        self.assertEqual(len(audit.errors), 0)
        record = audit.needs_action[0]
        self.assertIsInstance(record, workspace_auth_domain_audit_results.AddAdmin)
        self.assertEqual(record.workspace, self.combined_workspace.workspace)
        self.assertEqual(record.managed_group, self.dcc_admin_group)
        self.assertIsNone(record.current_membership_instance)
        self.assertEqual(
            record.note, combined_workspace_audit.CombinedConsortiumDataWorkspaceAuthDomainAudit.DCC_ADMIN_AS_ADMIN
        )

    @override_settings(ANVIL_DCC_ADMINS_GROUP_NAME="foo")
    def test_dcc_admin_different_setting(self):
        group = ManagedGroupFactory.create(name="foo")
        audit = combined_workspace_audit.CombinedConsortiumDataWorkspaceAuthDomainAudit()
        audit.audit_workspace_and_group(self.combined_workspace, group)
        self.assertEqual(len(audit.verified), 0)
        self.assertEqual(len(audit.needs_action), 1)
        self.assertEqual(len(audit.errors), 0)
        record = audit.needs_action[0]
        self.assertIsInstance(record, workspace_auth_domain_audit_results.AddAdmin)
        self.assertEqual(record.workspace, self.combined_workspace.workspace)
        self.assertEqual(record.managed_group, group)
        self.assertIsNone(record.current_membership_instance)
        self.assertEqual(
            record.note, combined_workspace_audit.CombinedConsortiumDataWorkspaceAuthDomainAudit.DCC_ADMIN_AS_ADMIN
        )

    def test_gregor_all_as_admin(self):
        membership = GroupGroupMembershipFactory.create(
            parent_group=self.combined_workspace.workspace.authorization_domains.first(),
            child_group=self.gregor_all_group,
            role=GroupGroupMembership.ADMIN,
        )
        audit = combined_workspace_audit.CombinedConsortiumDataWorkspaceAuthDomainAudit()
        audit.audit_workspace_and_group(self.combined_workspace, self.gregor_all_group)
        self.assertEqual(len(audit.verified), 0)
        self.assertEqual(len(audit.needs_action), 0)
        self.assertEqual(len(audit.errors), 1)
        record = audit.errors[0]
        self.assertIsInstance(record, workspace_auth_domain_audit_results.ChangeToMember)
        self.assertEqual(record.workspace, self.combined_workspace.workspace)
        self.assertEqual(record.managed_group, self.gregor_all_group)
        self.assertEqual(record.current_membership_instance, membership)
        self.assertEqual(
            record.note,
            combined_workspace_audit.CombinedConsortiumDataWorkspaceAuthDomainAudit.GREGOR_ALL_AS_MEMBER,
        )

    def test_gregor_all_as_member(self):
        membership = GroupGroupMembershipFactory.create(
            parent_group=self.combined_workspace.workspace.authorization_domains.first(),
            child_group=self.gregor_all_group,
            role=GroupGroupMembership.MEMBER,
        )
        audit = combined_workspace_audit.CombinedConsortiumDataWorkspaceAuthDomainAudit()
        audit.audit_workspace_and_group(self.combined_workspace, self.gregor_all_group)
        self.assertEqual(len(audit.verified), 1)
        self.assertEqual(len(audit.needs_action), 0)
        self.assertEqual(len(audit.errors), 0)
        record = audit.verified[0]
        self.assertIsInstance(record, workspace_auth_domain_audit_results.VerifiedMember)
        self.assertEqual(record.workspace, self.combined_workspace.workspace)
        self.assertEqual(record.managed_group, self.gregor_all_group)
        self.assertEqual(record.current_membership_instance, membership)
        self.assertEqual(
            record.note, combined_workspace_audit.CombinedConsortiumDataWorkspaceAuthDomainAudit.GREGOR_ALL_AS_MEMBER
        )

    def test_gregor_all_not_member(self):
        audit = combined_workspace_audit.CombinedConsortiumDataWorkspaceAuthDomainAudit()
        audit.audit_workspace_and_group(self.combined_workspace, self.gregor_all_group)
        self.assertEqual(len(audit.verified), 0)
        self.assertEqual(len(audit.needs_action), 1)
        self.assertEqual(len(audit.errors), 0)
        record = audit.needs_action[0]
        self.assertIsInstance(record, workspace_auth_domain_audit_results.AddMember)
        self.assertEqual(record.workspace, self.combined_workspace.workspace)
        self.assertEqual(record.managed_group, self.gregor_all_group)
        self.assertIsNone(record.current_membership_instance)
        self.assertEqual(
            record.note, combined_workspace_audit.CombinedConsortiumDataWorkspaceAuthDomainAudit.GREGOR_ALL_AS_MEMBER
        )

    def test_anvil_admins_not_member(self):
        audit = combined_workspace_audit.CombinedConsortiumDataWorkspaceAuthDomainAudit()
        audit.audit_workspace_and_group(self.combined_workspace, self.anvil_admins)
        self.assertEqual(len(audit.verified), 0)
        self.assertEqual(len(audit.needs_action), 0)
        self.assertEqual(len(audit.errors), 0)

    def test_anvil_admins_member(self):
        GroupGroupMembershipFactory.create(
            parent_group=self.combined_workspace.workspace.authorization_domains.first(),
            child_group=self.anvil_admins,
            role=GroupGroupMembership.MEMBER,
        )
        audit = combined_workspace_audit.CombinedConsortiumDataWorkspaceAuthDomainAudit()
        audit.audit_workspace_and_group(self.combined_workspace, self.anvil_admins)
        self.assertEqual(len(audit.verified), 0)
        self.assertEqual(len(audit.needs_action), 0)
        self.assertEqual(len(audit.errors), 0)

    def test_anvil_admins_admin(self):
        GroupGroupMembershipFactory.create(
            parent_group=self.combined_workspace.workspace.authorization_domains.first(),
            child_group=self.anvil_admins,
            role=GroupGroupMembership.ADMIN,
        )
        audit = combined_workspace_audit.CombinedConsortiumDataWorkspaceAuthDomainAudit()
        audit.audit_workspace_and_group(self.combined_workspace, self.anvil_admins)
        self.assertEqual(len(audit.verified), 0)
        self.assertEqual(len(audit.needs_action), 0)
        self.assertEqual(len(audit.errors), 0)

    def test_anvil_devs_not_member(self):
        audit = combined_workspace_audit.CombinedConsortiumDataWorkspaceAuthDomainAudit()
        audit.audit_workspace_and_group(self.combined_workspace, self.anvil_devs)
        self.assertEqual(len(audit.verified), 0)
        self.assertEqual(len(audit.needs_action), 0)
        self.assertEqual(len(audit.errors), 0)

    def test_anvil_devs_member(self):
        GroupGroupMembershipFactory.create(
            parent_group=self.combined_workspace.workspace.authorization_domains.first(),
            child_group=self.anvil_devs,
            role=GroupGroupMembership.MEMBER,
        )
        audit = combined_workspace_audit.CombinedConsortiumDataWorkspaceAuthDomainAudit()
        audit.audit_workspace_and_group(self.combined_workspace, self.anvil_devs)
        self.assertEqual(len(audit.verified), 0)
        self.assertEqual(len(audit.needs_action), 0)
        self.assertEqual(len(audit.errors), 0)

    def test_anvil_devs_admin(self):
        GroupGroupMembershipFactory.create(
            parent_group=self.combined_workspace.workspace.authorization_domains.first(),
            child_group=self.anvil_devs,
            role=GroupGroupMembership.ADMIN,
        )
        audit = combined_workspace_audit.CombinedConsortiumDataWorkspaceAuthDomainAudit()
        audit.audit_workspace_and_group(self.combined_workspace, self.anvil_devs)
        self.assertEqual(len(audit.verified), 0)
        self.assertEqual(len(audit.needs_action), 0)
        self.assertEqual(len(audit.errors), 0)

    def test_other_group_as_admin(self):
        membership = GroupGroupMembershipFactory.create(
            parent_group=self.combined_workspace.workspace.authorization_domains.first(),
            child_group=self.other_group,
            role=GroupGroupMembership.ADMIN,
        )
        audit = combined_workspace_audit.CombinedConsortiumDataWorkspaceAuthDomainAudit()
        audit.audit_workspace_and_group(self.combined_workspace, self.other_group)
        self.assertEqual(len(audit.verified), 0)
        self.assertEqual(len(audit.needs_action), 0)
        self.assertEqual(len(audit.errors), 1)
        record = audit.errors[0]
        self.assertIsInstance(record, workspace_auth_domain_audit_results.Remove)
        self.assertEqual(record.workspace, self.combined_workspace.workspace)
        self.assertEqual(record.managed_group, self.other_group)
        self.assertEqual(record.current_membership_instance, membership)
        self.assertEqual(
            record.note,
            combined_workspace_audit.CombinedConsortiumDataWorkspaceAuthDomainAudit.OTHER_GROUP,
        )

    def test_other_group_as_member(self):
        membership = GroupGroupMembershipFactory.create(
            parent_group=self.combined_workspace.workspace.authorization_domains.first(),
            child_group=self.other_group,
            role=GroupGroupMembership.MEMBER,
        )
        audit = combined_workspace_audit.CombinedConsortiumDataWorkspaceAuthDomainAudit()
        audit.audit_workspace_and_group(self.combined_workspace, self.other_group)
        self.assertEqual(len(audit.verified), 0)
        self.assertEqual(len(audit.needs_action), 0)
        self.assertEqual(len(audit.errors), 1)
        record = audit.errors[0]
        self.assertIsInstance(record, workspace_auth_domain_audit_results.Remove)
        self.assertEqual(record.workspace, self.combined_workspace.workspace)
        self.assertEqual(record.managed_group, self.other_group)
        self.assertEqual(record.current_membership_instance, membership)
        self.assertEqual(
            record.note, combined_workspace_audit.CombinedConsortiumDataWorkspaceAuthDomainAudit.OTHER_GROUP
        )

    def test_other_group_not_member(self):
        audit = combined_workspace_audit.CombinedConsortiumDataWorkspaceAuthDomainAudit()
        audit.audit_workspace_and_group(self.combined_workspace, self.other_group)
        self.assertEqual(len(audit.verified), 1)
        self.assertEqual(len(audit.needs_action), 0)
        self.assertEqual(len(audit.errors), 0)
        record = audit.verified[0]
        self.assertIsInstance(record, workspace_auth_domain_audit_results.VerifiedNotMember)
        self.assertEqual(record.workspace, self.combined_workspace.workspace)
        self.assertEqual(record.managed_group, self.other_group)
        self.assertIsNone(record.current_membership_instance)
        self.assertEqual(
            record.note, combined_workspace_audit.CombinedConsortiumDataWorkspaceAuthDomainAudit.OTHER_GROUP
        )


class CombinedConsortiumWorkspaceSharingAuditTest(TestCase):
    def test_completed(self):
        """The completed attribute is set appropriately."""
        # Instantiate the class.
        audit = combined_workspace_audit.CombinedConsortiumDataWorkspaceSharingAudit()
        self.assertFalse(audit.completed)
        audit.run_audit()
        self.assertTrue(audit.completed)

    def test_no_workspaces(self):
        """The audit works if there are no combined workspaces."""
        audit = combined_workspace_audit.CombinedConsortiumDataWorkspaceSharingAudit()
        audit.run_audit()
        self.assertEqual(len(audit.verified), 0)
        self.assertEqual(len(audit.needs_action), 0)
        self.assertEqual(len(audit.errors), 0)

    def test_one_workspace_no_groups(self):
        factories.CombinedConsortiumDataWorkspaceFactory.create()
        audit = combined_workspace_audit.CombinedConsortiumDataWorkspaceSharingAudit()
        audit.run_audit()
        self.assertEqual(len(audit.verified), 1)  # The auth domain
        self.assertEqual(len(audit.needs_action), 0)
        self.assertEqual(len(audit.errors), 0)

    def test_one_workspace_dcc_admin_group(self):
        group = ManagedGroupFactory.create(name=settings.ANVIL_DCC_ADMINS_GROUP_NAME)
        combined_workspace = factories.CombinedConsortiumDataWorkspaceFactory.create()
        audit = combined_workspace_audit.CombinedConsortiumDataWorkspaceSharingAudit()
        audit.run_audit()
        self.assertEqual(len(audit.verified), 1)  # The auth domain
        self.assertEqual(len(audit.needs_action), 1)
        self.assertEqual(len(audit.errors), 0)
        record = audit.needs_action[0]
        self.assertIsInstance(record, workspace_sharing_audit_results.ShareAsOwner)
        self.assertEqual(record.workspace, combined_workspace.workspace)
        self.assertEqual(record.managed_group, group)

    @override_settings(ANVIL_DCC_ADMINS_GROUP_NAME="foo")
    def test_one_workspace_dcc_admin_group_different_name(self):
        group = ManagedGroupFactory.create(name="foo")
        combined_workspace = factories.CombinedConsortiumDataWorkspaceFactory.create()
        audit = combined_workspace_audit.CombinedConsortiumDataWorkspaceSharingAudit()
        audit.run_audit()
        self.assertEqual(len(audit.verified), 1)  # The auth domain
        self.assertEqual(len(audit.needs_action), 1)
        self.assertEqual(len(audit.errors), 0)
        record = audit.needs_action[0]
        self.assertIsInstance(record, workspace_sharing_audit_results.ShareAsOwner)
        self.assertEqual(record.workspace, combined_workspace.workspace)
        self.assertEqual(record.managed_group, group)

    def test_one_workspace_dcc_writer_group(self):
        group = ManagedGroupFactory.create(name="GREGOR_DCC_WRITERS")
        combined_workspace = factories.CombinedConsortiumDataWorkspaceFactory.create()
        audit = combined_workspace_audit.CombinedConsortiumDataWorkspaceSharingAudit()
        audit.run_audit()
        self.assertEqual(len(audit.verified), 1)  # The auth domain
        self.assertEqual(len(audit.needs_action), 1)
        self.assertEqual(len(audit.errors), 0)
        record = audit.needs_action[0]
        self.assertIsInstance(record, workspace_sharing_audit_results.ShareWithCompute)
        self.assertEqual(record.workspace, combined_workspace.workspace)
        self.assertEqual(record.managed_group, group)

    def test_one_workspace_dcc_member_group(self):
        group = ManagedGroupFactory.create(name="GREGOR_DCC_MEMBERS")
        combined_workspace = factories.CombinedConsortiumDataWorkspaceFactory.create()
        audit = combined_workspace_audit.CombinedConsortiumDataWorkspaceSharingAudit()
        audit.run_audit()
        self.assertEqual(len(audit.verified), 1)  # The auth domain
        self.assertEqual(len(audit.needs_action), 1)
        self.assertEqual(len(audit.errors), 0)
        record = audit.needs_action[0]
        self.assertIsInstance(record, workspace_sharing_audit_results.ShareAsReader)
        self.assertEqual(record.workspace, combined_workspace.workspace)
        self.assertEqual(record.managed_group, group)

    def test_one_workspace_anvil_admins(self):
        ManagedGroupFactory.create(name="anvil-admins")
        factories.CombinedConsortiumDataWorkspaceFactory.create()
        audit = combined_workspace_audit.CombinedConsortiumDataWorkspaceSharingAudit()
        audit.run_audit()
        self.assertEqual(len(audit.verified), 1)  # The auth domain
        self.assertEqual(len(audit.needs_action), 0)
        self.assertEqual(len(audit.errors), 0)

    def test_one_workspace_anvil_devs(self):
        ManagedGroupFactory.create(name="anvil_devs")
        factories.CombinedConsortiumDataWorkspaceFactory.create()
        audit = combined_workspace_audit.CombinedConsortiumDataWorkspaceSharingAudit()
        audit.run_audit()
        self.assertEqual(len(audit.verified), 1)  # The auth domain
        self.assertEqual(len(audit.needs_action), 0)
        self.assertEqual(len(audit.errors), 0)

    def test_one_workspace_auth_domain(self):
        combined_workspace = factories.CombinedConsortiumDataWorkspaceFactory.create()
        group = combined_workspace.workspace.authorization_domains.first()
        audit = combined_workspace_audit.CombinedConsortiumDataWorkspaceSharingAudit()
        audit.run_audit()
        self.assertEqual(len(audit.verified), 1)
        self.assertEqual(len(audit.needs_action), 0)
        self.assertEqual(len(audit.errors), 0)
        record = audit.verified[0]
        self.assertIsInstance(record, workspace_sharing_audit_results.VerifiedNotShared)
        self.assertEqual(record.workspace, combined_workspace.workspace)
        self.assertEqual(record.managed_group, group)

    def test_one_workspace_other_group_shared(self):
        group = ManagedGroupFactory.create()
        combined_workspace = factories.CombinedConsortiumDataWorkspaceFactory.create()
        WorkspaceGroupSharingFactory.create(workspace=combined_workspace.workspace, group=group)
        audit = combined_workspace_audit.CombinedConsortiumDataWorkspaceSharingAudit()
        audit.run_audit()
        self.assertEqual(len(audit.verified), 1)  # The auth domain
        self.assertEqual(len(audit.needs_action), 0)
        self.assertEqual(len(audit.errors), 1)
        record = audit.errors[0]
        self.assertIsInstance(record, workspace_sharing_audit_results.StopSharing)
        self.assertEqual(record.workspace, combined_workspace.workspace)
        self.assertEqual(record.managed_group, group)

    def test_one_workspace_other_group_not_shared(self):
        ManagedGroupFactory.create()
        factories.CombinedConsortiumDataWorkspaceFactory.create()
        audit = combined_workspace_audit.CombinedConsortiumDataWorkspaceSharingAudit()
        audit.run_audit()
        self.assertEqual(len(audit.verified), 1)  # The auth domain
        self.assertEqual(len(audit.needs_action), 0)
        self.assertEqual(len(audit.errors), 0)

    def test_two_workspaces(self):
        """Audit works with two UploadWorkspaces."""
        combined_workspace_1 = factories.CombinedConsortiumDataWorkspaceFactory.create()
        combined_workspace_2 = factories.CombinedConsortiumDataWorkspaceFactory.create(
            date_completed=fake.date_this_year(before_today=True, after_today=False)
        )
        audit = combined_workspace_audit.CombinedConsortiumDataWorkspaceSharingAudit()
        audit.run_audit()
        self.assertEqual(len(audit.verified), 1)
        self.assertEqual(len(audit.needs_action), 1)
        self.assertEqual(len(audit.errors), 0)
        record = audit.verified[0]
        self.assertIsInstance(record, workspace_sharing_audit_results.VerifiedNotShared)
        self.assertEqual(record.workspace, combined_workspace_1.workspace)
        self.assertEqual(record.managed_group, combined_workspace_1.workspace.authorization_domains.first())
        self.assertIsNone(record.current_sharing_instance)
        record = audit.needs_action[0]
        self.assertIsInstance(record, workspace_sharing_audit_results.ShareAsReader)
        self.assertEqual(record.workspace, combined_workspace_2.workspace)
        self.assertEqual(record.managed_group, combined_workspace_2.workspace.authorization_domains.first())
        self.assertIsNone(record.current_sharing_instance)

    def test_queryset(self):
        """Audit only runs on the specified queryset."""
        combined_workspace_1 = factories.CombinedConsortiumDataWorkspaceFactory.create()
        combined_workspace_2 = factories.CombinedConsortiumDataWorkspaceFactory.create(
            date_completed=fake.date_this_year(before_today=True, after_today=False)
        )
        # First application
        audit = combined_workspace_audit.CombinedConsortiumDataWorkspaceSharingAudit(
            queryset=models.CombinedConsortiumDataWorkspace.objects.filter(pk=combined_workspace_1.pk)
        )
        audit.run_audit()
        self.assertEqual(len(audit.verified), 1)
        self.assertEqual(len(audit.needs_action), 0)
        self.assertEqual(len(audit.errors), 0)
        record = audit.verified[0]
        self.assertIsInstance(record, workspace_sharing_audit_results.VerifiedNotShared)
        self.assertEqual(record.workspace, combined_workspace_1.workspace)
        self.assertEqual(record.managed_group, combined_workspace_1.workspace.authorization_domains.first())
        self.assertIsNone(record.current_sharing_instance)
        # Second application
        audit = combined_workspace_audit.CombinedConsortiumDataWorkspaceSharingAudit(
            queryset=models.CombinedConsortiumDataWorkspace.objects.filter(pk=combined_workspace_2.pk)
        )
        audit.run_audit()
        self.assertEqual(len(audit.verified), 0)
        self.assertEqual(len(audit.needs_action), 1)
        self.assertEqual(len(audit.errors), 0)
        record = audit.needs_action[0]
        self.assertIsInstance(record, workspace_sharing_audit_results.ShareAsReader)
        self.assertEqual(record.workspace, combined_workspace_2.workspace)
        self.assertEqual(record.managed_group, combined_workspace_2.workspace.authorization_domains.first())
        self.assertIsNone(record.current_sharing_instance)

    def test_queryset_wrong_class(self):
        """Raises ValueError if queryset is not a QuerySet."""
        with self.assertRaises(ValueError):
            combined_workspace_audit.CombinedConsortiumDataWorkspaceSharingAudit(queryset="foo")
        with self.assertRaises(ValueError):
            combined_workspace_audit.CombinedConsortiumDataWorkspaceSharingAudit(
                queryset=models.UploadWorkspace.objects.all()
            )


class CombinedConsortiumWorkspaceSharingAuditBeforeCompleteTest(TestCase):
    def setUp(self):
        super().setUp()
        self.dcc_member_group = ManagedGroupFactory.create(name="GREGOR_DCC_MEMBERS")
        self.dcc_writer_group = ManagedGroupFactory.create(name="GREGOR_DCC_WRITERS")
        self.dcc_admin_group = ManagedGroupFactory.create(name=settings.ANVIL_DCC_ADMINS_GROUP_NAME)
        self.combined_workspace = factories.CombinedConsortiumDataWorkspaceFactory.create(
            upload_cycle__is_past=True,
            date_completed=None,
        )
        self.auth_domain = self.combined_workspace.workspace.authorization_domains.first()
        self.other_group = ManagedGroupFactory.create()
        self.anvil_admins = ManagedGroupFactory.create(name="anvil-admins")
        self.anvil_devs = ManagedGroupFactory.create(name="anvil_devs")

    def test_dcc_admin_shared_as_writer_no_compute(self):
        # Share the workspace with the group.
        sharing = WorkspaceGroupSharingFactory.create(
            workspace=self.combined_workspace.workspace, group=self.dcc_admin_group, access=WorkspaceGroupSharing.WRITER
        )
        audit = combined_workspace_audit.CombinedConsortiumDataWorkspaceSharingAudit()
        audit.audit_workspace_and_group(self.combined_workspace, self.dcc_admin_group)
        self.assertEqual(len(audit.verified), 0)
        self.assertEqual(len(audit.needs_action), 1)
        self.assertEqual(len(audit.errors), 0)
        record = audit.needs_action[0]
        self.assertIsInstance(record, workspace_sharing_audit_results.ShareAsOwner)
        self.assertEqual(record.workspace, self.combined_workspace.workspace)
        self.assertEqual(record.managed_group, self.dcc_admin_group)
        self.assertEqual(record.current_sharing_instance, sharing)
        self.assertEqual(
            record.note, combined_workspace_audit.CombinedConsortiumDataWorkspaceSharingAudit.DCC_ADMIN_AS_OWNER
        )

    def test_dcc_admin_not_shared(self):
        audit = combined_workspace_audit.CombinedConsortiumDataWorkspaceSharingAudit()
        audit.audit_workspace_and_group(self.combined_workspace, self.dcc_admin_group)
        self.assertEqual(len(audit.verified), 0)
        self.assertEqual(len(audit.needs_action), 1)
        self.assertEqual(len(audit.errors), 0)
        record = audit.needs_action[0]
        self.assertIsInstance(record, workspace_sharing_audit_results.ShareAsOwner)
        self.assertEqual(record.workspace, self.combined_workspace.workspace)
        self.assertEqual(record.managed_group, self.dcc_admin_group)
        self.assertEqual(record.current_sharing_instance, None)
        self.assertEqual(
            record.note, combined_workspace_audit.CombinedConsortiumDataWorkspaceSharingAudit.DCC_ADMIN_AS_OWNER
        )

    def test_dcc_admin_shared_as_writer_can_compute(self):
        sharing = WorkspaceGroupSharingFactory.create(
            workspace=self.combined_workspace.workspace,
            group=self.dcc_admin_group,
            access=WorkspaceGroupSharing.WRITER,
            can_compute=True,
        )
        audit = combined_workspace_audit.CombinedConsortiumDataWorkspaceSharingAudit()
        audit.audit_workspace_and_group(self.combined_workspace, self.dcc_admin_group)
        self.assertEqual(len(audit.verified), 0)
        self.assertEqual(len(audit.needs_action), 1)
        self.assertEqual(len(audit.errors), 0)
        record = audit.needs_action[0]
        self.assertIsInstance(record, workspace_sharing_audit_results.ShareAsOwner)
        self.assertEqual(record.workspace, self.combined_workspace.workspace)
        self.assertEqual(record.managed_group, self.dcc_admin_group)
        self.assertEqual(record.current_sharing_instance, sharing)
        self.assertEqual(
            record.note, combined_workspace_audit.CombinedConsortiumDataWorkspaceSharingAudit.DCC_ADMIN_AS_OWNER
        )

    def test_dcc_admin_shared_as_reader(self):
        sharing = WorkspaceGroupSharingFactory.create(
            workspace=self.combined_workspace.workspace, group=self.dcc_admin_group, access=WorkspaceGroupSharing.READER
        )
        audit = combined_workspace_audit.CombinedConsortiumDataWorkspaceSharingAudit()
        audit.audit_workspace_and_group(self.combined_workspace, self.dcc_admin_group)
        self.assertEqual(len(audit.verified), 0)
        self.assertEqual(len(audit.needs_action), 1)
        self.assertEqual(len(audit.errors), 0)
        record = audit.needs_action[0]
        self.assertIsInstance(record, workspace_sharing_audit_results.ShareAsOwner)
        self.assertEqual(record.workspace, self.combined_workspace.workspace)
        self.assertEqual(record.managed_group, self.dcc_admin_group)
        self.assertEqual(record.current_sharing_instance, sharing)
        self.assertEqual(
            record.note, combined_workspace_audit.CombinedConsortiumDataWorkspaceSharingAudit.DCC_ADMIN_AS_OWNER
        )

    def test_dcc_admin_shared_as_owner(self):
        sharing = WorkspaceGroupSharingFactory.create(
            workspace=self.combined_workspace.workspace, group=self.dcc_admin_group, access=WorkspaceGroupSharing.OWNER
        )
        audit = combined_workspace_audit.CombinedConsortiumDataWorkspaceSharingAudit()
        audit.audit_workspace_and_group(self.combined_workspace, self.dcc_admin_group)
        self.assertEqual(len(audit.verified), 1)
        self.assertEqual(len(audit.needs_action), 0)
        self.assertEqual(len(audit.errors), 0)
        record = audit.verified[0]
        self.assertIsInstance(record, workspace_sharing_audit_results.VerifiedShared)
        self.assertEqual(record.workspace, self.combined_workspace.workspace)
        self.assertEqual(record.managed_group, self.dcc_admin_group)
        self.assertEqual(record.current_sharing_instance, sharing)
        self.assertEqual(
            record.note, combined_workspace_audit.CombinedConsortiumDataWorkspaceSharingAudit.DCC_ADMIN_AS_OWNER
        )

    @override_settings(ANVIL_DCC_ADMINS_GROUP_NAME="foo")
    def test_dcc_admin_different_setting(self):
        group = ManagedGroupFactory.create(name="foo")
        sharing = WorkspaceGroupSharingFactory.create(
            workspace=self.combined_workspace.workspace, group=group, access=WorkspaceGroupSharing.OWNER
        )
        audit = combined_workspace_audit.CombinedConsortiumDataWorkspaceSharingAudit()
        audit.audit_workspace_and_group(self.combined_workspace, group)
        self.assertEqual(len(audit.verified), 1)
        self.assertEqual(len(audit.needs_action), 0)
        self.assertEqual(len(audit.errors), 0)
        record = audit.verified[0]
        self.assertIsInstance(record, workspace_sharing_audit_results.VerifiedShared)
        self.assertEqual(record.workspace, self.combined_workspace.workspace)
        self.assertEqual(record.managed_group, group)
        self.assertEqual(record.current_sharing_instance, sharing)
        self.assertEqual(
            record.note, combined_workspace_audit.CombinedConsortiumDataWorkspaceSharingAudit.DCC_ADMIN_AS_OWNER
        )

    def test_dcc_writers_shared_as_writer_no_compute(self):
        # Share the workspace with the group.
        sharing = WorkspaceGroupSharingFactory.create(
            workspace=self.combined_workspace.workspace,
            group=self.dcc_writer_group,
            access=WorkspaceGroupSharing.WRITER,
        )
        audit = combined_workspace_audit.CombinedConsortiumDataWorkspaceSharingAudit()
        audit.audit_workspace_and_group(self.combined_workspace, self.dcc_writer_group)
        self.assertEqual(len(audit.verified), 0)
        self.assertEqual(len(audit.needs_action), 1)
        self.assertEqual(len(audit.errors), 0)
        record = audit.needs_action[0]
        self.assertIsInstance(record, workspace_sharing_audit_results.ShareWithCompute)
        self.assertEqual(record.workspace, self.combined_workspace.workspace)
        self.assertEqual(record.managed_group, self.dcc_writer_group)
        self.assertEqual(record.current_sharing_instance, sharing)
        self.assertEqual(
            record.note,
            combined_workspace_audit.CombinedConsortiumDataWorkspaceSharingAudit.DCC_WRITERS_BEFORE_COMPLETE,
        )

    def test_dcc_writers_not_shared(self):
        audit = combined_workspace_audit.CombinedConsortiumDataWorkspaceSharingAudit()
        audit.audit_workspace_and_group(self.combined_workspace, self.dcc_writer_group)
        self.assertEqual(len(audit.verified), 0)
        self.assertEqual(len(audit.needs_action), 1)
        self.assertEqual(len(audit.errors), 0)
        record = audit.needs_action[0]
        self.assertIsInstance(record, workspace_sharing_audit_results.ShareWithCompute)
        self.assertEqual(record.workspace, self.combined_workspace.workspace)
        self.assertEqual(record.managed_group, self.dcc_writer_group)
        self.assertEqual(record.current_sharing_instance, None)
        self.assertEqual(
            record.note,
            combined_workspace_audit.CombinedConsortiumDataWorkspaceSharingAudit.DCC_WRITERS_BEFORE_COMPLETE,
        )

    def test_dcc_writers_shared_as_writer_can_compute(self):
        sharing = WorkspaceGroupSharingFactory.create(
            workspace=self.combined_workspace.workspace,
            group=self.dcc_writer_group,
            access=WorkspaceGroupSharing.WRITER,
            can_compute=True,
        )
        audit = combined_workspace_audit.CombinedConsortiumDataWorkspaceSharingAudit()
        audit.audit_workspace_and_group(self.combined_workspace, self.dcc_writer_group)
        self.assertEqual(len(audit.verified), 1)
        self.assertEqual(len(audit.needs_action), 0)
        self.assertEqual(len(audit.errors), 0)
        record = audit.verified[0]
        self.assertIsInstance(record, workspace_sharing_audit_results.VerifiedShared)
        self.assertEqual(record.workspace, self.combined_workspace.workspace)
        self.assertEqual(record.managed_group, self.dcc_writer_group)
        self.assertEqual(record.current_sharing_instance, sharing)
        self.assertEqual(
            record.note,
            combined_workspace_audit.CombinedConsortiumDataWorkspaceSharingAudit.DCC_WRITERS_BEFORE_COMPLETE,
        )

    def test_dcc_writers_shared_as_reader(self):
        sharing = WorkspaceGroupSharingFactory.create(
            workspace=self.combined_workspace.workspace,
            group=self.dcc_writer_group,
            access=WorkspaceGroupSharing.READER,
        )
        audit = combined_workspace_audit.CombinedConsortiumDataWorkspaceSharingAudit()
        audit.audit_workspace_and_group(self.combined_workspace, self.dcc_writer_group)
        self.assertEqual(len(audit.verified), 0)
        self.assertEqual(len(audit.needs_action), 1)
        self.assertEqual(len(audit.errors), 0)
        record = audit.needs_action[0]
        self.assertIsInstance(record, workspace_sharing_audit_results.ShareWithCompute)
        self.assertEqual(record.workspace, self.combined_workspace.workspace)
        self.assertEqual(record.managed_group, self.dcc_writer_group)
        self.assertEqual(record.current_sharing_instance, sharing)
        self.assertEqual(
            record.note,
            combined_workspace_audit.CombinedConsortiumDataWorkspaceSharingAudit.DCC_WRITERS_BEFORE_COMPLETE,
        )

    def test_dcc_writers_shared_as_owner(self):
        sharing = WorkspaceGroupSharingFactory.create(
            workspace=self.combined_workspace.workspace, group=self.dcc_writer_group, access=WorkspaceGroupSharing.OWNER
        )
        audit = combined_workspace_audit.CombinedConsortiumDataWorkspaceSharingAudit()
        audit.audit_workspace_and_group(self.combined_workspace, self.dcc_writer_group)
        self.assertEqual(len(audit.verified), 0)
        self.assertEqual(len(audit.needs_action), 0)
        self.assertEqual(len(audit.errors), 1)
        record = audit.errors[0]
        self.assertIsInstance(record, workspace_sharing_audit_results.ShareWithCompute)
        self.assertEqual(record.workspace, self.combined_workspace.workspace)
        self.assertEqual(record.managed_group, self.dcc_writer_group)
        self.assertEqual(record.current_sharing_instance, sharing)
        self.assertEqual(
            record.note,
            combined_workspace_audit.CombinedConsortiumDataWorkspaceSharingAudit.DCC_WRITERS_BEFORE_COMPLETE,
        )

    def test_dcc_members_shared_as_writer_no_compute(self):
        # Share the workspace with the group.
        sharing = WorkspaceGroupSharingFactory.create(
            workspace=self.combined_workspace.workspace,
            group=self.dcc_member_group,
            access=WorkspaceGroupSharing.WRITER,
        )
        audit = combined_workspace_audit.CombinedConsortiumDataWorkspaceSharingAudit()
        audit.audit_workspace_and_group(self.combined_workspace, self.dcc_member_group)
        self.assertEqual(len(audit.verified), 0)
        self.assertEqual(len(audit.needs_action), 0)
        self.assertEqual(len(audit.errors), 1)
        record = audit.errors[0]
        self.assertIsInstance(record, workspace_sharing_audit_results.ShareAsReader)
        self.assertEqual(record.workspace, self.combined_workspace.workspace)
        self.assertEqual(record.managed_group, self.dcc_member_group)
        self.assertEqual(record.current_sharing_instance, sharing)
        self.assertEqual(
            record.note,
            combined_workspace_audit.CombinedConsortiumDataWorkspaceSharingAudit.DCC_MEMBERS_BEFORE_COMPLETE,
        )

    def test_dcc_members_not_shared(self):
        audit = combined_workspace_audit.CombinedConsortiumDataWorkspaceSharingAudit()
        audit.audit_workspace_and_group(self.combined_workspace, self.dcc_member_group)
        self.assertEqual(len(audit.verified), 0)
        self.assertEqual(len(audit.needs_action), 1)
        self.assertEqual(len(audit.errors), 0)
        record = audit.needs_action[0]
        self.assertIsInstance(record, workspace_sharing_audit_results.ShareAsReader)
        self.assertEqual(record.workspace, self.combined_workspace.workspace)
        self.assertEqual(record.managed_group, self.dcc_member_group)
        self.assertEqual(record.current_sharing_instance, None)
        self.assertEqual(
            record.note,
            combined_workspace_audit.CombinedConsortiumDataWorkspaceSharingAudit.DCC_MEMBERS_BEFORE_COMPLETE,
        )

    def test_dcc_members_shared_as_writer_can_compute(self):
        sharing = WorkspaceGroupSharingFactory.create(
            workspace=self.combined_workspace.workspace,
            group=self.dcc_member_group,
            access=WorkspaceGroupSharing.WRITER,
            can_compute=True,
        )
        audit = combined_workspace_audit.CombinedConsortiumDataWorkspaceSharingAudit()
        audit.audit_workspace_and_group(self.combined_workspace, self.dcc_member_group)
        self.assertEqual(len(audit.verified), 0)
        self.assertEqual(len(audit.needs_action), 0)
        self.assertEqual(len(audit.errors), 1)
        record = audit.errors[0]
        self.assertIsInstance(record, workspace_sharing_audit_results.ShareAsReader)
        self.assertEqual(record.workspace, self.combined_workspace.workspace)
        self.assertEqual(record.managed_group, self.dcc_member_group)
        self.assertEqual(record.current_sharing_instance, sharing)
        self.assertEqual(
            record.note,
            combined_workspace_audit.CombinedConsortiumDataWorkspaceSharingAudit.DCC_MEMBERS_BEFORE_COMPLETE,
        )

    def test_dcc_members_shared_as_reader(self):
        sharing = WorkspaceGroupSharingFactory.create(
            workspace=self.combined_workspace.workspace,
            group=self.dcc_member_group,
            access=WorkspaceGroupSharing.READER,
        )
        audit = combined_workspace_audit.CombinedConsortiumDataWorkspaceSharingAudit()
        audit.audit_workspace_and_group(self.combined_workspace, self.dcc_member_group)
        self.assertEqual(len(audit.verified), 1)
        self.assertEqual(len(audit.needs_action), 0)
        self.assertEqual(len(audit.errors), 0)
        record = audit.verified[0]
        self.assertIsInstance(record, workspace_sharing_audit_results.VerifiedShared)
        self.assertEqual(record.workspace, self.combined_workspace.workspace)
        self.assertEqual(record.managed_group, self.dcc_member_group)
        self.assertEqual(record.current_sharing_instance, sharing)
        self.assertEqual(
            record.note,
            combined_workspace_audit.CombinedConsortiumDataWorkspaceSharingAudit.DCC_MEMBERS_BEFORE_COMPLETE,
        )

    def test_dcc_members_shared_as_owner(self):
        sharing = WorkspaceGroupSharingFactory.create(
            workspace=self.combined_workspace.workspace, group=self.dcc_member_group, access=WorkspaceGroupSharing.OWNER
        )
        audit = combined_workspace_audit.CombinedConsortiumDataWorkspaceSharingAudit()
        audit.audit_workspace_and_group(self.combined_workspace, self.dcc_member_group)
        self.assertEqual(len(audit.verified), 0)
        self.assertEqual(len(audit.needs_action), 0)
        self.assertEqual(len(audit.errors), 1)
        record = audit.errors[0]
        self.assertIsInstance(record, workspace_sharing_audit_results.ShareAsReader)
        self.assertEqual(record.workspace, self.combined_workspace.workspace)
        self.assertEqual(record.managed_group, self.dcc_member_group)
        self.assertEqual(record.current_sharing_instance, sharing)
        self.assertEqual(
            record.note,
            combined_workspace_audit.CombinedConsortiumDataWorkspaceSharingAudit.DCC_MEMBERS_BEFORE_COMPLETE,
        )

    def test_auth_domain_shared_as_writer_no_compute(self):
        # Share the workspace with the group.
        sharing = WorkspaceGroupSharingFactory.create(
            workspace=self.combined_workspace.workspace, group=self.auth_domain, access=WorkspaceGroupSharing.WRITER
        )
        audit = combined_workspace_audit.CombinedConsortiumDataWorkspaceSharingAudit()
        audit.audit_workspace_and_group(self.combined_workspace, self.auth_domain)
        self.assertEqual(len(audit.verified), 0)
        self.assertEqual(len(audit.needs_action), 0)
        self.assertEqual(len(audit.errors), 1)
        record = audit.errors[0]
        self.assertIsInstance(record, workspace_sharing_audit_results.StopSharing)
        self.assertEqual(record.workspace, self.combined_workspace.workspace)
        self.assertEqual(record.managed_group, self.auth_domain)
        self.assertEqual(record.current_sharing_instance, sharing)
        self.assertEqual(
            record.note,
            combined_workspace_audit.CombinedConsortiumDataWorkspaceSharingAudit.AUTH_DOMAIN_BEFORE_COMPLETE,
        )

    def test_auth_domain_not_shared(self):
        audit = combined_workspace_audit.CombinedConsortiumDataWorkspaceSharingAudit()
        audit.audit_workspace_and_group(self.combined_workspace, self.auth_domain)
        self.assertEqual(len(audit.verified), 1)
        self.assertEqual(len(audit.needs_action), 0)
        self.assertEqual(len(audit.errors), 0)
        record = audit.verified[0]
        self.assertIsInstance(record, workspace_sharing_audit_results.VerifiedNotShared)
        self.assertEqual(record.workspace, self.combined_workspace.workspace)
        self.assertEqual(record.managed_group, self.auth_domain)
        self.assertEqual(record.current_sharing_instance, None)
        self.assertEqual(
            record.note,
            combined_workspace_audit.CombinedConsortiumDataWorkspaceSharingAudit.AUTH_DOMAIN_BEFORE_COMPLETE,
        )

    def test_auth_domain_shared_as_writer_can_compute(self):
        sharing = WorkspaceGroupSharingFactory.create(
            workspace=self.combined_workspace.workspace,
            group=self.auth_domain,
            access=WorkspaceGroupSharing.WRITER,
            can_compute=True,
        )
        audit = combined_workspace_audit.CombinedConsortiumDataWorkspaceSharingAudit()
        audit.audit_workspace_and_group(self.combined_workspace, self.auth_domain)
        self.assertEqual(len(audit.verified), 0)
        self.assertEqual(len(audit.needs_action), 0)
        self.assertEqual(len(audit.errors), 1)
        record = audit.errors[0]
        self.assertIsInstance(record, workspace_sharing_audit_results.StopSharing)
        self.assertEqual(record.workspace, self.combined_workspace.workspace)
        self.assertEqual(record.managed_group, self.auth_domain)
        self.assertEqual(record.current_sharing_instance, sharing)
        self.assertEqual(
            record.note,
            combined_workspace_audit.CombinedConsortiumDataWorkspaceSharingAudit.AUTH_DOMAIN_BEFORE_COMPLETE,
        )

    def test_auth_domain_shared_as_reader(self):
        sharing = WorkspaceGroupSharingFactory.create(
            workspace=self.combined_workspace.workspace, group=self.auth_domain, access=WorkspaceGroupSharing.READER
        )
        audit = combined_workspace_audit.CombinedConsortiumDataWorkspaceSharingAudit()
        audit.audit_workspace_and_group(self.combined_workspace, self.auth_domain)
        self.assertEqual(len(audit.verified), 0)
        self.assertEqual(len(audit.needs_action), 0)
        self.assertEqual(len(audit.errors), 1)
        record = audit.errors[0]
        self.assertIsInstance(record, workspace_sharing_audit_results.StopSharing)
        self.assertEqual(record.workspace, self.combined_workspace.workspace)
        self.assertEqual(record.managed_group, self.auth_domain)
        self.assertEqual(record.current_sharing_instance, sharing)
        self.assertEqual(
            record.note,
            combined_workspace_audit.CombinedConsortiumDataWorkspaceSharingAudit.AUTH_DOMAIN_BEFORE_COMPLETE,
        )

    def test_auth_domain_shared_as_owner(self):
        sharing = WorkspaceGroupSharingFactory.create(
            workspace=self.combined_workspace.workspace, group=self.auth_domain, access=WorkspaceGroupSharing.OWNER
        )
        audit = combined_workspace_audit.CombinedConsortiumDataWorkspaceSharingAudit()
        audit.audit_workspace_and_group(self.combined_workspace, self.auth_domain)
        self.assertEqual(len(audit.verified), 0)
        self.assertEqual(len(audit.needs_action), 0)
        self.assertEqual(len(audit.errors), 1)
        record = audit.errors[0]
        self.assertIsInstance(record, workspace_sharing_audit_results.StopSharing)
        self.assertEqual(record.workspace, self.combined_workspace.workspace)
        self.assertEqual(record.managed_group, self.auth_domain)
        self.assertEqual(record.current_sharing_instance, sharing)
        self.assertEqual(
            record.note,
            combined_workspace_audit.CombinedConsortiumDataWorkspaceSharingAudit.AUTH_DOMAIN_BEFORE_COMPLETE,
        )

    def test_anvil_admins_shared_as_writer_no_compute(self):
        # Share the workspace with the group.
        WorkspaceGroupSharingFactory.create(
            workspace=self.combined_workspace.workspace, group=self.anvil_admins, access=WorkspaceGroupSharing.WRITER
        )
        audit = combined_workspace_audit.CombinedConsortiumDataWorkspaceSharingAudit()
        audit.audit_workspace_and_group(self.combined_workspace, self.anvil_admins)
        self.assertEqual(len(audit.verified), 0)
        self.assertEqual(len(audit.needs_action), 0)
        self.assertEqual(len(audit.errors), 0)

    def test_anvil_admins_not_shared(self):
        audit = combined_workspace_audit.CombinedConsortiumDataWorkspaceSharingAudit()
        audit.audit_workspace_and_group(self.combined_workspace, self.anvil_admins)
        self.assertEqual(len(audit.verified), 0)
        self.assertEqual(len(audit.needs_action), 0)
        self.assertEqual(len(audit.errors), 0)

    def test_anvil_admins_shared_as_writer_can_compute(self):
        WorkspaceGroupSharingFactory.create(
            workspace=self.combined_workspace.workspace,
            group=self.anvil_admins,
            access=WorkspaceGroupSharing.WRITER,
            can_compute=True,
        )
        audit = combined_workspace_audit.CombinedConsortiumDataWorkspaceSharingAudit()
        audit.audit_workspace_and_group(self.combined_workspace, self.anvil_admins)
        self.assertEqual(len(audit.verified), 0)
        self.assertEqual(len(audit.needs_action), 0)
        self.assertEqual(len(audit.errors), 0)

    def test_anvil_admins_shared_as_reader(self):
        WorkspaceGroupSharingFactory.create(
            workspace=self.combined_workspace.workspace, group=self.anvil_admins, access=WorkspaceGroupSharing.READER
        )
        audit = combined_workspace_audit.CombinedConsortiumDataWorkspaceSharingAudit()
        audit.audit_workspace_and_group(self.combined_workspace, self.anvil_admins)
        self.assertEqual(len(audit.verified), 0)
        self.assertEqual(len(audit.needs_action), 0)
        self.assertEqual(len(audit.errors), 0)

    def test_anvil_admins_shared_as_owner(self):
        WorkspaceGroupSharingFactory.create(
            workspace=self.combined_workspace.workspace, group=self.anvil_admins, access=WorkspaceGroupSharing.OWNER
        )
        audit = combined_workspace_audit.CombinedConsortiumDataWorkspaceSharingAudit()
        audit.audit_workspace_and_group(self.combined_workspace, self.anvil_admins)
        self.assertEqual(len(audit.verified), 0)
        self.assertEqual(len(audit.needs_action), 0)
        self.assertEqual(len(audit.errors), 0)

    def test_anvil_devs_shared_as_writer_no_compute(self):
        # Share the workspace with the group.
        WorkspaceGroupSharingFactory.create(
            workspace=self.combined_workspace.workspace, group=self.anvil_devs, access=WorkspaceGroupSharing.WRITER
        )
        audit = combined_workspace_audit.CombinedConsortiumDataWorkspaceSharingAudit()
        audit.audit_workspace_and_group(self.combined_workspace, self.anvil_devs)
        self.assertEqual(len(audit.verified), 0)
        self.assertEqual(len(audit.needs_action), 0)
        self.assertEqual(len(audit.errors), 0)

    def test_anvil_devs_not_shared(self):
        audit = combined_workspace_audit.CombinedConsortiumDataWorkspaceSharingAudit()
        audit.audit_workspace_and_group(self.combined_workspace, self.anvil_devs)
        self.assertEqual(len(audit.verified), 0)
        self.assertEqual(len(audit.needs_action), 0)
        self.assertEqual(len(audit.errors), 0)

    def test_anvil_devs_shared_as_writer_can_compute(self):
        WorkspaceGroupSharingFactory.create(
            workspace=self.combined_workspace.workspace,
            group=self.anvil_devs,
            access=WorkspaceGroupSharing.WRITER,
            can_compute=True,
        )
        audit = combined_workspace_audit.CombinedConsortiumDataWorkspaceSharingAudit()
        audit.audit_workspace_and_group(self.combined_workspace, self.anvil_devs)
        self.assertEqual(len(audit.verified), 0)
        self.assertEqual(len(audit.needs_action), 0)
        self.assertEqual(len(audit.errors), 0)

    def test_anvil_devs_shared_as_reader(self):
        WorkspaceGroupSharingFactory.create(
            workspace=self.combined_workspace.workspace, group=self.anvil_devs, access=WorkspaceGroupSharing.READER
        )
        audit = combined_workspace_audit.CombinedConsortiumDataWorkspaceSharingAudit()
        audit.audit_workspace_and_group(self.combined_workspace, self.anvil_devs)
        self.assertEqual(len(audit.verified), 0)
        self.assertEqual(len(audit.needs_action), 0)
        self.assertEqual(len(audit.errors), 0)

    def test_anvil_devs_shared_as_owner(self):
        WorkspaceGroupSharingFactory.create(
            workspace=self.combined_workspace.workspace, group=self.anvil_devs, access=WorkspaceGroupSharing.OWNER
        )
        audit = combined_workspace_audit.CombinedConsortiumDataWorkspaceSharingAudit()
        audit.audit_workspace_and_group(self.combined_workspace, self.anvil_devs)
        self.assertEqual(len(audit.verified), 0)
        self.assertEqual(len(audit.needs_action), 0)
        self.assertEqual(len(audit.errors), 0)

    def test_other_group_shared_as_writer_no_compute(self):
        # Share the workspace with the group.
        sharing = WorkspaceGroupSharingFactory.create(
            workspace=self.combined_workspace.workspace, group=self.other_group, access=WorkspaceGroupSharing.WRITER
        )
        audit = combined_workspace_audit.CombinedConsortiumDataWorkspaceSharingAudit()
        audit.audit_workspace_and_group(self.combined_workspace, self.other_group)
        self.assertEqual(len(audit.verified), 0)
        self.assertEqual(len(audit.needs_action), 0)
        self.assertEqual(len(audit.errors), 1)
        record = audit.errors[0]
        self.assertIsInstance(record, workspace_sharing_audit_results.StopSharing)
        self.assertEqual(record.workspace, self.combined_workspace.workspace)
        self.assertEqual(record.managed_group, self.other_group)
        self.assertEqual(record.current_sharing_instance, sharing)
        self.assertEqual(record.note, combined_workspace_audit.CombinedConsortiumDataWorkspaceSharingAudit.OTHER_GROUP)

    def test_other_group_not_shared(self):
        audit = combined_workspace_audit.CombinedConsortiumDataWorkspaceSharingAudit()
        audit.audit_workspace_and_group(self.combined_workspace, self.other_group)
        self.assertEqual(len(audit.verified), 1)
        self.assertEqual(len(audit.needs_action), 0)
        self.assertEqual(len(audit.errors), 0)
        record = audit.verified[0]
        self.assertIsInstance(record, workspace_sharing_audit_results.VerifiedNotShared)
        self.assertEqual(record.workspace, self.combined_workspace.workspace)
        self.assertEqual(record.managed_group, self.other_group)
        self.assertEqual(record.current_sharing_instance, None)
        self.assertEqual(record.note, combined_workspace_audit.CombinedConsortiumDataWorkspaceSharingAudit.OTHER_GROUP)

    def test_other_group_shared_as_writer_can_compute(self):
        sharing = WorkspaceGroupSharingFactory.create(
            workspace=self.combined_workspace.workspace,
            group=self.other_group,
            access=WorkspaceGroupSharing.WRITER,
            can_compute=True,
        )
        audit = combined_workspace_audit.CombinedConsortiumDataWorkspaceSharingAudit()
        audit.audit_workspace_and_group(self.combined_workspace, self.other_group)
        self.assertEqual(len(audit.verified), 0)
        self.assertEqual(len(audit.needs_action), 0)
        self.assertEqual(len(audit.errors), 1)
        record = audit.errors[0]
        self.assertIsInstance(record, workspace_sharing_audit_results.StopSharing)
        self.assertEqual(record.workspace, self.combined_workspace.workspace)
        self.assertEqual(record.managed_group, self.other_group)
        self.assertEqual(record.current_sharing_instance, sharing)
        self.assertEqual(record.note, combined_workspace_audit.CombinedConsortiumDataWorkspaceSharingAudit.OTHER_GROUP)

    def test_other_group_shared_as_reader(self):
        sharing = WorkspaceGroupSharingFactory.create(
            workspace=self.combined_workspace.workspace, group=self.other_group, access=WorkspaceGroupSharing.READER
        )
        audit = combined_workspace_audit.CombinedConsortiumDataWorkspaceSharingAudit()
        audit.audit_workspace_and_group(self.combined_workspace, self.other_group)
        self.assertEqual(len(audit.verified), 0)
        self.assertEqual(len(audit.needs_action), 0)
        self.assertEqual(len(audit.errors), 1)
        record = audit.errors[0]
        self.assertIsInstance(record, workspace_sharing_audit_results.StopSharing)
        self.assertEqual(record.workspace, self.combined_workspace.workspace)
        self.assertEqual(record.managed_group, self.other_group)
        self.assertEqual(record.current_sharing_instance, sharing)
        self.assertEqual(record.note, combined_workspace_audit.CombinedConsortiumDataWorkspaceSharingAudit.OTHER_GROUP)

    def test_other_group_shared_as_owner(self):
        sharing = WorkspaceGroupSharingFactory.create(
            workspace=self.combined_workspace.workspace, group=self.other_group, access=WorkspaceGroupSharing.OWNER
        )
        audit = combined_workspace_audit.CombinedConsortiumDataWorkspaceSharingAudit()
        audit.audit_workspace_and_group(self.combined_workspace, self.other_group)
        self.assertEqual(len(audit.verified), 0)
        self.assertEqual(len(audit.needs_action), 0)
        self.assertEqual(len(audit.errors), 1)
        record = audit.errors[0]
        self.assertIsInstance(record, workspace_sharing_audit_results.StopSharing)
        self.assertEqual(record.workspace, self.combined_workspace.workspace)
        self.assertEqual(record.managed_group, self.other_group)
        self.assertEqual(record.current_sharing_instance, sharing)
        self.assertEqual(record.note, combined_workspace_audit.CombinedConsortiumDataWorkspaceSharingAudit.OTHER_GROUP)


class CombinedConsortiumWorkspaceSharingAuditAfterCompleteTest(TestCase):
    def setUp(self):
        super().setUp()
        self.dcc_member_group = ManagedGroupFactory.create(name="GREGOR_DCC_MEMBERS")
        self.dcc_writer_group = ManagedGroupFactory.create(name="GREGOR_DCC_WRITERS")
        self.dcc_admin_group = ManagedGroupFactory.create(name=settings.ANVIL_DCC_ADMINS_GROUP_NAME)
        self.combined_workspace = factories.CombinedConsortiumDataWorkspaceFactory.create(
            upload_cycle__is_past=True,
            date_completed=fake.date_this_year(before_today=True, after_today=False),
        )
        self.auth_domain = self.combined_workspace.workspace.authorization_domains.first()
        self.other_group = ManagedGroupFactory.create()
        self.anvil_admins = ManagedGroupFactory.create(name="anvil-admins")
        self.anvil_devs = ManagedGroupFactory.create(name="anvil_devs")

    def test_dcc_admin_shared_as_writer_no_compute(self):
        # Share the workspace with the group.
        sharing = WorkspaceGroupSharingFactory.create(
            workspace=self.combined_workspace.workspace, group=self.dcc_admin_group, access=WorkspaceGroupSharing.WRITER
        )
        audit = combined_workspace_audit.CombinedConsortiumDataWorkspaceSharingAudit()
        audit.audit_workspace_and_group(self.combined_workspace, self.dcc_admin_group)
        self.assertEqual(len(audit.verified), 0)
        self.assertEqual(len(audit.needs_action), 1)
        self.assertEqual(len(audit.errors), 0)
        record = audit.needs_action[0]
        self.assertIsInstance(record, workspace_sharing_audit_results.ShareAsOwner)
        self.assertEqual(record.workspace, self.combined_workspace.workspace)
        self.assertEqual(record.managed_group, self.dcc_admin_group)
        self.assertEqual(record.current_sharing_instance, sharing)
        self.assertEqual(
            record.note, combined_workspace_audit.CombinedConsortiumDataWorkspaceSharingAudit.DCC_ADMIN_AS_OWNER
        )

    def test_dcc_admin_not_shared(self):
        audit = combined_workspace_audit.CombinedConsortiumDataWorkspaceSharingAudit()
        audit.audit_workspace_and_group(self.combined_workspace, self.dcc_admin_group)
        self.assertEqual(len(audit.verified), 0)
        self.assertEqual(len(audit.needs_action), 1)
        self.assertEqual(len(audit.errors), 0)
        record = audit.needs_action[0]
        self.assertIsInstance(record, workspace_sharing_audit_results.ShareAsOwner)
        self.assertEqual(record.workspace, self.combined_workspace.workspace)
        self.assertEqual(record.managed_group, self.dcc_admin_group)
        self.assertEqual(record.current_sharing_instance, None)
        self.assertEqual(
            record.note, combined_workspace_audit.CombinedConsortiumDataWorkspaceSharingAudit.DCC_ADMIN_AS_OWNER
        )

    def test_dcc_admin_shared_as_writer_can_compute(self):
        sharing = WorkspaceGroupSharingFactory.create(
            workspace=self.combined_workspace.workspace,
            group=self.dcc_admin_group,
            access=WorkspaceGroupSharing.WRITER,
            can_compute=True,
        )
        audit = combined_workspace_audit.CombinedConsortiumDataWorkspaceSharingAudit()
        audit.audit_workspace_and_group(self.combined_workspace, self.dcc_admin_group)
        self.assertEqual(len(audit.verified), 0)
        self.assertEqual(len(audit.needs_action), 1)
        self.assertEqual(len(audit.errors), 0)
        record = audit.needs_action[0]
        self.assertIsInstance(record, workspace_sharing_audit_results.ShareAsOwner)
        self.assertEqual(record.workspace, self.combined_workspace.workspace)
        self.assertEqual(record.managed_group, self.dcc_admin_group)
        self.assertEqual(record.current_sharing_instance, sharing)
        self.assertEqual(
            record.note, combined_workspace_audit.CombinedConsortiumDataWorkspaceSharingAudit.DCC_ADMIN_AS_OWNER
        )

    def test_dcc_admin_shared_as_reader(self):
        sharing = WorkspaceGroupSharingFactory.create(
            workspace=self.combined_workspace.workspace, group=self.dcc_admin_group, access=WorkspaceGroupSharing.READER
        )
        audit = combined_workspace_audit.CombinedConsortiumDataWorkspaceSharingAudit()
        audit.audit_workspace_and_group(self.combined_workspace, self.dcc_admin_group)
        self.assertEqual(len(audit.verified), 0)
        self.assertEqual(len(audit.needs_action), 1)
        self.assertEqual(len(audit.errors), 0)
        record = audit.needs_action[0]
        self.assertIsInstance(record, workspace_sharing_audit_results.ShareAsOwner)
        self.assertEqual(record.workspace, self.combined_workspace.workspace)
        self.assertEqual(record.managed_group, self.dcc_admin_group)
        self.assertEqual(record.current_sharing_instance, sharing)
        self.assertEqual(
            record.note, combined_workspace_audit.CombinedConsortiumDataWorkspaceSharingAudit.DCC_ADMIN_AS_OWNER
        )

    def test_dcc_admin_shared_as_owner(self):
        sharing = WorkspaceGroupSharingFactory.create(
            workspace=self.combined_workspace.workspace, group=self.dcc_admin_group, access=WorkspaceGroupSharing.OWNER
        )
        audit = combined_workspace_audit.CombinedConsortiumDataWorkspaceSharingAudit()
        audit.audit_workspace_and_group(self.combined_workspace, self.dcc_admin_group)
        self.assertEqual(len(audit.verified), 1)
        self.assertEqual(len(audit.needs_action), 0)
        self.assertEqual(len(audit.errors), 0)
        record = audit.verified[0]
        self.assertIsInstance(record, workspace_sharing_audit_results.VerifiedShared)
        self.assertEqual(record.workspace, self.combined_workspace.workspace)
        self.assertEqual(record.managed_group, self.dcc_admin_group)
        self.assertEqual(record.current_sharing_instance, sharing)
        self.assertEqual(
            record.note, combined_workspace_audit.CombinedConsortiumDataWorkspaceSharingAudit.DCC_ADMIN_AS_OWNER
        )

    @override_settings(ANVIL_DCC_ADMINS_GROUP_NAME="foo")
    def test_dcc_admin_different_setting(self):
        group = ManagedGroupFactory.create(name="foo")
        sharing = WorkspaceGroupSharingFactory.create(
            workspace=self.combined_workspace.workspace, group=group, access=WorkspaceGroupSharing.OWNER
        )
        audit = combined_workspace_audit.CombinedConsortiumDataWorkspaceSharingAudit()
        audit.audit_workspace_and_group(self.combined_workspace, group)
        self.assertEqual(len(audit.verified), 1)
        self.assertEqual(len(audit.needs_action), 0)
        self.assertEqual(len(audit.errors), 0)
        record = audit.verified[0]
        self.assertIsInstance(record, workspace_sharing_audit_results.VerifiedShared)
        self.assertEqual(record.workspace, self.combined_workspace.workspace)
        self.assertEqual(record.managed_group, group)
        self.assertEqual(record.current_sharing_instance, sharing)
        self.assertEqual(
            record.note, combined_workspace_audit.CombinedConsortiumDataWorkspaceSharingAudit.DCC_ADMIN_AS_OWNER
        )

    def test_dcc_writers_shared_as_writer_no_compute(self):
        # Share the workspace with the group.
        sharing = WorkspaceGroupSharingFactory.create(
            workspace=self.combined_workspace.workspace,
            group=self.dcc_writer_group,
            access=WorkspaceGroupSharing.WRITER,
        )
        audit = combined_workspace_audit.CombinedConsortiumDataWorkspaceSharingAudit()
        audit.audit_workspace_and_group(self.combined_workspace, self.dcc_writer_group)
        self.assertEqual(len(audit.verified), 0)
        self.assertEqual(len(audit.needs_action), 1)
        self.assertEqual(len(audit.errors), 0)
        record = audit.needs_action[0]
        self.assertIsInstance(record, workspace_sharing_audit_results.StopSharing)
        self.assertEqual(record.workspace, self.combined_workspace.workspace)
        self.assertEqual(record.managed_group, self.dcc_writer_group)
        self.assertEqual(record.current_sharing_instance, sharing)
        self.assertEqual(
            record.note, combined_workspace_audit.CombinedConsortiumDataWorkspaceSharingAudit.DCC_WRITERS_AFTER_COMPLETE
        )

    def test_dcc_writers_not_shared(self):
        audit = combined_workspace_audit.CombinedConsortiumDataWorkspaceSharingAudit()
        audit.audit_workspace_and_group(self.combined_workspace, self.dcc_writer_group)
        self.assertEqual(len(audit.verified), 1)
        self.assertEqual(len(audit.needs_action), 0)
        self.assertEqual(len(audit.errors), 0)
        record = audit.verified[0]
        self.assertIsInstance(record, workspace_sharing_audit_results.VerifiedNotShared)
        self.assertEqual(record.workspace, self.combined_workspace.workspace)
        self.assertEqual(record.managed_group, self.dcc_writer_group)
        self.assertEqual(record.current_sharing_instance, None)
        self.assertEqual(
            record.note, combined_workspace_audit.CombinedConsortiumDataWorkspaceSharingAudit.DCC_WRITERS_AFTER_COMPLETE
        )

    def test_dcc_writers_shared_as_writer_can_compute(self):
        sharing = WorkspaceGroupSharingFactory.create(
            workspace=self.combined_workspace.workspace,
            group=self.dcc_writer_group,
            access=WorkspaceGroupSharing.WRITER,
            can_compute=True,
        )
        audit = combined_workspace_audit.CombinedConsortiumDataWorkspaceSharingAudit()
        audit.audit_workspace_and_group(self.combined_workspace, self.dcc_writer_group)
        self.assertEqual(len(audit.verified), 0)
        self.assertEqual(len(audit.needs_action), 1)
        self.assertEqual(len(audit.errors), 0)
        record = audit.needs_action[0]
        self.assertIsInstance(record, workspace_sharing_audit_results.StopSharing)
        self.assertEqual(record.workspace, self.combined_workspace.workspace)
        self.assertEqual(record.managed_group, self.dcc_writer_group)
        self.assertEqual(record.current_sharing_instance, sharing)
        self.assertEqual(
            record.note, combined_workspace_audit.CombinedConsortiumDataWorkspaceSharingAudit.DCC_WRITERS_AFTER_COMPLETE
        )

    def test_dcc_writers_shared_as_reader(self):
        sharing = WorkspaceGroupSharingFactory.create(
            workspace=self.combined_workspace.workspace,
            group=self.dcc_writer_group,
            access=WorkspaceGroupSharing.READER,
        )
        audit = combined_workspace_audit.CombinedConsortiumDataWorkspaceSharingAudit()
        audit.audit_workspace_and_group(self.combined_workspace, self.dcc_writer_group)
        self.assertEqual(len(audit.verified), 0)
        self.assertEqual(len(audit.needs_action), 1)
        self.assertEqual(len(audit.errors), 0)
        record = audit.needs_action[0]
        self.assertIsInstance(record, workspace_sharing_audit_results.StopSharing)
        self.assertEqual(record.workspace, self.combined_workspace.workspace)
        self.assertEqual(record.managed_group, self.dcc_writer_group)
        self.assertEqual(record.current_sharing_instance, sharing)
        self.assertEqual(
            record.note, combined_workspace_audit.CombinedConsortiumDataWorkspaceSharingAudit.DCC_WRITERS_AFTER_COMPLETE
        )

    def test_dcc_writers_shared_as_owner(self):
        sharing = WorkspaceGroupSharingFactory.create(
            workspace=self.combined_workspace.workspace, group=self.dcc_writer_group, access=WorkspaceGroupSharing.OWNER
        )
        audit = combined_workspace_audit.CombinedConsortiumDataWorkspaceSharingAudit()
        audit.audit_workspace_and_group(self.combined_workspace, self.dcc_writer_group)
        self.assertEqual(len(audit.verified), 0)
        self.assertEqual(len(audit.needs_action), 0)
        self.assertEqual(len(audit.errors), 1)
        record = audit.errors[0]
        self.assertIsInstance(record, workspace_sharing_audit_results.StopSharing)
        self.assertEqual(record.workspace, self.combined_workspace.workspace)
        self.assertEqual(record.managed_group, self.dcc_writer_group)
        self.assertEqual(record.current_sharing_instance, sharing)
        self.assertEqual(
            record.note, combined_workspace_audit.CombinedConsortiumDataWorkspaceSharingAudit.DCC_WRITERS_AFTER_COMPLETE
        )

    def test_dcc_members_shared_as_writer_no_compute(self):
        # Share the workspace with the group.
        sharing = WorkspaceGroupSharingFactory.create(
            workspace=self.combined_workspace.workspace,
            group=self.dcc_member_group,
            access=WorkspaceGroupSharing.WRITER,
        )
        audit = combined_workspace_audit.CombinedConsortiumDataWorkspaceSharingAudit()
        audit.audit_workspace_and_group(self.combined_workspace, self.dcc_member_group)
        self.assertEqual(len(audit.verified), 0)
        self.assertEqual(len(audit.needs_action), 0)
        self.assertEqual(len(audit.errors), 1)
        record = audit.errors[0]
        self.assertIsInstance(record, workspace_sharing_audit_results.StopSharing)
        self.assertEqual(record.workspace, self.combined_workspace.workspace)
        self.assertEqual(record.managed_group, self.dcc_member_group)
        self.assertEqual(record.current_sharing_instance, sharing)
        self.assertEqual(
            record.note, combined_workspace_audit.CombinedConsortiumDataWorkspaceSharingAudit.DCC_MEMBERS_AFTER_COMPLETE
        )

    def test_dcc_members_not_shared(self):
        audit = combined_workspace_audit.CombinedConsortiumDataWorkspaceSharingAudit()
        audit.audit_workspace_and_group(self.combined_workspace, self.dcc_member_group)
        self.assertEqual(len(audit.verified), 1)
        self.assertEqual(len(audit.needs_action), 0)
        self.assertEqual(len(audit.errors), 0)
        record = audit.verified[0]
        self.assertIsInstance(record, workspace_sharing_audit_results.VerifiedNotShared)
        self.assertEqual(record.workspace, self.combined_workspace.workspace)
        self.assertEqual(record.managed_group, self.dcc_member_group)
        self.assertEqual(record.current_sharing_instance, None)
        self.assertEqual(
            record.note, combined_workspace_audit.CombinedConsortiumDataWorkspaceSharingAudit.DCC_MEMBERS_AFTER_COMPLETE
        )

    def test_dcc_members_shared_as_writer_can_compute(self):
        sharing = WorkspaceGroupSharingFactory.create(
            workspace=self.combined_workspace.workspace,
            group=self.dcc_member_group,
            access=WorkspaceGroupSharing.WRITER,
            can_compute=True,
        )
        audit = combined_workspace_audit.CombinedConsortiumDataWorkspaceSharingAudit()
        audit.audit_workspace_and_group(self.combined_workspace, self.dcc_member_group)
        self.assertEqual(len(audit.verified), 0)
        self.assertEqual(len(audit.needs_action), 0)
        self.assertEqual(len(audit.errors), 1)
        record = audit.errors[0]
        self.assertIsInstance(record, workspace_sharing_audit_results.StopSharing)
        self.assertEqual(record.workspace, self.combined_workspace.workspace)
        self.assertEqual(record.managed_group, self.dcc_member_group)
        self.assertEqual(record.current_sharing_instance, sharing)
        self.assertEqual(
            record.note, combined_workspace_audit.CombinedConsortiumDataWorkspaceSharingAudit.DCC_MEMBERS_AFTER_COMPLETE
        )

    def test_dcc_members_shared_as_reader(self):
        sharing = WorkspaceGroupSharingFactory.create(
            workspace=self.combined_workspace.workspace,
            group=self.dcc_member_group,
            access=WorkspaceGroupSharing.READER,
        )
        audit = combined_workspace_audit.CombinedConsortiumDataWorkspaceSharingAudit()
        audit.audit_workspace_and_group(self.combined_workspace, self.dcc_member_group)
        self.assertEqual(len(audit.verified), 0)
        self.assertEqual(len(audit.needs_action), 1)
        self.assertEqual(len(audit.errors), 0)
        record = audit.needs_action[0]
        self.assertIsInstance(record, workspace_sharing_audit_results.StopSharing)
        self.assertEqual(record.workspace, self.combined_workspace.workspace)
        self.assertEqual(record.managed_group, self.dcc_member_group)
        self.assertEqual(record.current_sharing_instance, sharing)
        self.assertEqual(
            record.note, combined_workspace_audit.CombinedConsortiumDataWorkspaceSharingAudit.DCC_MEMBERS_AFTER_COMPLETE
        )

    def test_dcc_members_shared_as_owner(self):
        sharing = WorkspaceGroupSharingFactory.create(
            workspace=self.combined_workspace.workspace, group=self.dcc_member_group, access=WorkspaceGroupSharing.OWNER
        )
        audit = combined_workspace_audit.CombinedConsortiumDataWorkspaceSharingAudit()
        audit.audit_workspace_and_group(self.combined_workspace, self.dcc_member_group)
        self.assertEqual(len(audit.verified), 0)
        self.assertEqual(len(audit.needs_action), 0)
        self.assertEqual(len(audit.errors), 1)
        record = audit.errors[0]
        self.assertIsInstance(record, workspace_sharing_audit_results.StopSharing)
        self.assertEqual(record.workspace, self.combined_workspace.workspace)
        self.assertEqual(record.managed_group, self.dcc_member_group)
        self.assertEqual(record.current_sharing_instance, sharing)
        self.assertEqual(
            record.note, combined_workspace_audit.CombinedConsortiumDataWorkspaceSharingAudit.DCC_MEMBERS_AFTER_COMPLETE
        )

    def test_auth_domain_shared_as_writer_no_compute(self):
        # Share the workspace with the group.
        sharing = WorkspaceGroupSharingFactory.create(
            workspace=self.combined_workspace.workspace, group=self.auth_domain, access=WorkspaceGroupSharing.WRITER
        )
        audit = combined_workspace_audit.CombinedConsortiumDataWorkspaceSharingAudit()
        audit.audit_workspace_and_group(self.combined_workspace, self.auth_domain)
        self.assertEqual(len(audit.verified), 0)
        self.assertEqual(len(audit.needs_action), 0)
        self.assertEqual(len(audit.errors), 1)
        record = audit.errors[0]
        self.assertIsInstance(record, workspace_sharing_audit_results.ShareAsReader)
        self.assertEqual(record.workspace, self.combined_workspace.workspace)
        self.assertEqual(record.managed_group, self.auth_domain)
        self.assertEqual(record.current_sharing_instance, sharing)
        self.assertEqual(
            record.note, combined_workspace_audit.CombinedConsortiumDataWorkspaceSharingAudit.AUTH_DOMAIN_AFTER_COMPLETE
        )

    def test_auth_domain_not_shared(self):
        audit = combined_workspace_audit.CombinedConsortiumDataWorkspaceSharingAudit()
        audit.audit_workspace_and_group(self.combined_workspace, self.auth_domain)
        self.assertEqual(len(audit.verified), 0)
        self.assertEqual(len(audit.needs_action), 1)
        self.assertEqual(len(audit.errors), 0)
        record = audit.needs_action[0]
        self.assertIsInstance(record, workspace_sharing_audit_results.ShareAsReader)
        self.assertEqual(record.workspace, self.combined_workspace.workspace)
        self.assertEqual(record.managed_group, self.auth_domain)
        self.assertEqual(record.current_sharing_instance, None)
        self.assertEqual(
            record.note, combined_workspace_audit.CombinedConsortiumDataWorkspaceSharingAudit.AUTH_DOMAIN_AFTER_COMPLETE
        )

    def test_auth_domain_shared_as_writer_can_compute(self):
        sharing = WorkspaceGroupSharingFactory.create(
            workspace=self.combined_workspace.workspace,
            group=self.auth_domain,
            access=WorkspaceGroupSharing.WRITER,
            can_compute=True,
        )
        audit = combined_workspace_audit.CombinedConsortiumDataWorkspaceSharingAudit()
        audit.audit_workspace_and_group(self.combined_workspace, self.auth_domain)
        self.assertEqual(len(audit.verified), 0)
        self.assertEqual(len(audit.needs_action), 0)
        self.assertEqual(len(audit.errors), 1)
        record = audit.errors[0]
        self.assertIsInstance(record, workspace_sharing_audit_results.ShareAsReader)
        self.assertEqual(record.workspace, self.combined_workspace.workspace)
        self.assertEqual(record.managed_group, self.auth_domain)
        self.assertEqual(record.current_sharing_instance, sharing)
        self.assertEqual(
            record.note, combined_workspace_audit.CombinedConsortiumDataWorkspaceSharingAudit.AUTH_DOMAIN_AFTER_COMPLETE
        )

    def test_auth_domain_shared_as_reader(self):
        sharing = WorkspaceGroupSharingFactory.create(
            workspace=self.combined_workspace.workspace, group=self.auth_domain, access=WorkspaceGroupSharing.READER
        )
        audit = combined_workspace_audit.CombinedConsortiumDataWorkspaceSharingAudit()
        audit.audit_workspace_and_group(self.combined_workspace, self.auth_domain)
        self.assertEqual(len(audit.verified), 1)
        self.assertEqual(len(audit.needs_action), 0)
        self.assertEqual(len(audit.errors), 0)
        record = audit.verified[0]
        self.assertIsInstance(record, workspace_sharing_audit_results.VerifiedShared)
        self.assertEqual(record.workspace, self.combined_workspace.workspace)
        self.assertEqual(record.managed_group, self.auth_domain)
        self.assertEqual(record.current_sharing_instance, sharing)
        self.assertEqual(
            record.note, combined_workspace_audit.CombinedConsortiumDataWorkspaceSharingAudit.AUTH_DOMAIN_AFTER_COMPLETE
        )

    def test_auth_domain_shared_as_owner(self):
        sharing = WorkspaceGroupSharingFactory.create(
            workspace=self.combined_workspace.workspace, group=self.auth_domain, access=WorkspaceGroupSharing.OWNER
        )
        audit = combined_workspace_audit.CombinedConsortiumDataWorkspaceSharingAudit()
        audit.audit_workspace_and_group(self.combined_workspace, self.auth_domain)
        self.assertEqual(len(audit.verified), 0)
        self.assertEqual(len(audit.needs_action), 0)
        self.assertEqual(len(audit.errors), 1)
        record = audit.errors[0]
        self.assertIsInstance(record, workspace_sharing_audit_results.ShareAsReader)
        self.assertEqual(record.workspace, self.combined_workspace.workspace)
        self.assertEqual(record.managed_group, self.auth_domain)
        self.assertEqual(record.current_sharing_instance, sharing)
        self.assertEqual(
            record.note, combined_workspace_audit.CombinedConsortiumDataWorkspaceSharingAudit.AUTH_DOMAIN_AFTER_COMPLETE
        )

    def test_anvil_admins_shared_as_writer_no_compute(self):
        # Share the workspace with the group.
        WorkspaceGroupSharingFactory.create(
            workspace=self.combined_workspace.workspace, group=self.anvil_admins, access=WorkspaceGroupSharing.WRITER
        )
        audit = combined_workspace_audit.CombinedConsortiumDataWorkspaceSharingAudit()
        audit.audit_workspace_and_group(self.combined_workspace, self.anvil_admins)
        self.assertEqual(len(audit.verified), 0)
        self.assertEqual(len(audit.needs_action), 0)
        self.assertEqual(len(audit.errors), 0)

    def test_anvil_admins_not_shared(self):
        audit = combined_workspace_audit.CombinedConsortiumDataWorkspaceSharingAudit()
        audit.audit_workspace_and_group(self.combined_workspace, self.anvil_admins)
        self.assertEqual(len(audit.verified), 0)
        self.assertEqual(len(audit.needs_action), 0)
        self.assertEqual(len(audit.errors), 0)

    def test_anvil_admins_shared_as_writer_can_compute(self):
        WorkspaceGroupSharingFactory.create(
            workspace=self.combined_workspace.workspace,
            group=self.anvil_admins,
            access=WorkspaceGroupSharing.WRITER,
            can_compute=True,
        )
        audit = combined_workspace_audit.CombinedConsortiumDataWorkspaceSharingAudit()
        audit.audit_workspace_and_group(self.combined_workspace, self.anvil_admins)
        self.assertEqual(len(audit.verified), 0)
        self.assertEqual(len(audit.needs_action), 0)
        self.assertEqual(len(audit.errors), 0)

    def test_anvil_admins_shared_as_reader(self):
        WorkspaceGroupSharingFactory.create(
            workspace=self.combined_workspace.workspace, group=self.anvil_admins, access=WorkspaceGroupSharing.READER
        )
        audit = combined_workspace_audit.CombinedConsortiumDataWorkspaceSharingAudit()
        audit.audit_workspace_and_group(self.combined_workspace, self.anvil_admins)
        self.assertEqual(len(audit.verified), 0)
        self.assertEqual(len(audit.needs_action), 0)
        self.assertEqual(len(audit.errors), 0)

    def test_anvil_admins_shared_as_owner(self):
        WorkspaceGroupSharingFactory.create(
            workspace=self.combined_workspace.workspace, group=self.anvil_admins, access=WorkspaceGroupSharing.OWNER
        )
        audit = combined_workspace_audit.CombinedConsortiumDataWorkspaceSharingAudit()
        audit.audit_workspace_and_group(self.combined_workspace, self.anvil_admins)
        self.assertEqual(len(audit.verified), 0)
        self.assertEqual(len(audit.needs_action), 0)
        self.assertEqual(len(audit.errors), 0)

    def test_anvil_devs_shared_as_writer_no_compute(self):
        # Share the workspace with the group.
        WorkspaceGroupSharingFactory.create(
            workspace=self.combined_workspace.workspace, group=self.anvil_devs, access=WorkspaceGroupSharing.WRITER
        )
        audit = combined_workspace_audit.CombinedConsortiumDataWorkspaceSharingAudit()
        audit.audit_workspace_and_group(self.combined_workspace, self.anvil_devs)
        self.assertEqual(len(audit.verified), 0)
        self.assertEqual(len(audit.needs_action), 0)
        self.assertEqual(len(audit.errors), 0)

    def test_anvil_devs_not_shared(self):
        audit = combined_workspace_audit.CombinedConsortiumDataWorkspaceSharingAudit()
        audit.audit_workspace_and_group(self.combined_workspace, self.anvil_devs)
        self.assertEqual(len(audit.verified), 0)
        self.assertEqual(len(audit.needs_action), 0)
        self.assertEqual(len(audit.errors), 0)

    def test_anvil_devs_shared_as_writer_can_compute(self):
        WorkspaceGroupSharingFactory.create(
            workspace=self.combined_workspace.workspace,
            group=self.anvil_devs,
            access=WorkspaceGroupSharing.WRITER,
            can_compute=True,
        )
        audit = combined_workspace_audit.CombinedConsortiumDataWorkspaceSharingAudit()
        audit.audit_workspace_and_group(self.combined_workspace, self.anvil_devs)
        self.assertEqual(len(audit.verified), 0)
        self.assertEqual(len(audit.needs_action), 0)
        self.assertEqual(len(audit.errors), 0)

    def test_anvil_devs_shared_as_reader(self):
        WorkspaceGroupSharingFactory.create(
            workspace=self.combined_workspace.workspace, group=self.anvil_devs, access=WorkspaceGroupSharing.READER
        )
        audit = combined_workspace_audit.CombinedConsortiumDataWorkspaceSharingAudit()
        audit.audit_workspace_and_group(self.combined_workspace, self.anvil_devs)
        self.assertEqual(len(audit.verified), 0)
        self.assertEqual(len(audit.needs_action), 0)
        self.assertEqual(len(audit.errors), 0)

    def test_anvil_devs_shared_as_owner(self):
        WorkspaceGroupSharingFactory.create(
            workspace=self.combined_workspace.workspace, group=self.anvil_devs, access=WorkspaceGroupSharing.OWNER
        )
        audit = combined_workspace_audit.CombinedConsortiumDataWorkspaceSharingAudit()
        audit.audit_workspace_and_group(self.combined_workspace, self.anvil_devs)
        self.assertEqual(len(audit.verified), 0)
        self.assertEqual(len(audit.needs_action), 0)
        self.assertEqual(len(audit.errors), 0)

    def test_other_group_shared_as_writer_no_compute(self):
        # Share the workspace with the group.
        sharing = WorkspaceGroupSharingFactory.create(
            workspace=self.combined_workspace.workspace, group=self.other_group, access=WorkspaceGroupSharing.WRITER
        )
        audit = combined_workspace_audit.CombinedConsortiumDataWorkspaceSharingAudit()
        audit.audit_workspace_and_group(self.combined_workspace, self.other_group)
        self.assertEqual(len(audit.verified), 0)
        self.assertEqual(len(audit.needs_action), 0)
        self.assertEqual(len(audit.errors), 1)
        record = audit.errors[0]
        self.assertIsInstance(record, workspace_sharing_audit_results.StopSharing)
        self.assertEqual(record.workspace, self.combined_workspace.workspace)
        self.assertEqual(record.managed_group, self.other_group)
        self.assertEqual(record.current_sharing_instance, sharing)
        self.assertEqual(record.note, combined_workspace_audit.CombinedConsortiumDataWorkspaceSharingAudit.OTHER_GROUP)

    def test_other_group_not_shared(self):
        audit = combined_workspace_audit.CombinedConsortiumDataWorkspaceSharingAudit()
        audit.audit_workspace_and_group(self.combined_workspace, self.other_group)
        self.assertEqual(len(audit.verified), 1)
        self.assertEqual(len(audit.needs_action), 0)
        self.assertEqual(len(audit.errors), 0)
        record = audit.verified[0]
        self.assertIsInstance(record, workspace_sharing_audit_results.VerifiedNotShared)
        self.assertEqual(record.workspace, self.combined_workspace.workspace)
        self.assertEqual(record.managed_group, self.other_group)
        self.assertEqual(record.current_sharing_instance, None)
        self.assertEqual(record.note, combined_workspace_audit.CombinedConsortiumDataWorkspaceSharingAudit.OTHER_GROUP)

    def test_other_group_shared_as_writer_can_compute(self):
        sharing = WorkspaceGroupSharingFactory.create(
            workspace=self.combined_workspace.workspace,
            group=self.other_group,
            access=WorkspaceGroupSharing.WRITER,
            can_compute=True,
        )
        audit = combined_workspace_audit.CombinedConsortiumDataWorkspaceSharingAudit()
        audit.audit_workspace_and_group(self.combined_workspace, self.other_group)
        self.assertEqual(len(audit.verified), 0)
        self.assertEqual(len(audit.needs_action), 0)
        self.assertEqual(len(audit.errors), 1)
        record = audit.errors[0]
        self.assertIsInstance(record, workspace_sharing_audit_results.StopSharing)
        self.assertEqual(record.workspace, self.combined_workspace.workspace)
        self.assertEqual(record.managed_group, self.other_group)
        self.assertEqual(record.current_sharing_instance, sharing)
        self.assertEqual(record.note, combined_workspace_audit.CombinedConsortiumDataWorkspaceSharingAudit.OTHER_GROUP)

    def test_other_group_shared_as_reader(self):
        sharing = WorkspaceGroupSharingFactory.create(
            workspace=self.combined_workspace.workspace, group=self.other_group, access=WorkspaceGroupSharing.READER
        )
        audit = combined_workspace_audit.CombinedConsortiumDataWorkspaceSharingAudit()
        audit.audit_workspace_and_group(self.combined_workspace, self.other_group)
        self.assertEqual(len(audit.verified), 0)
        self.assertEqual(len(audit.needs_action), 0)
        self.assertEqual(len(audit.errors), 1)
        record = audit.errors[0]
        self.assertIsInstance(record, workspace_sharing_audit_results.StopSharing)
        self.assertEqual(record.workspace, self.combined_workspace.workspace)
        self.assertEqual(record.managed_group, self.other_group)
        self.assertEqual(record.current_sharing_instance, sharing)
        self.assertEqual(record.note, combined_workspace_audit.CombinedConsortiumDataWorkspaceSharingAudit.OTHER_GROUP)

    def test_other_group_shared_as_owner(self):
        sharing = WorkspaceGroupSharingFactory.create(
            workspace=self.combined_workspace.workspace, group=self.other_group, access=WorkspaceGroupSharing.OWNER
        )
        audit = combined_workspace_audit.CombinedConsortiumDataWorkspaceSharingAudit()
        audit.audit_workspace_and_group(self.combined_workspace, self.other_group)
        self.assertEqual(len(audit.verified), 0)
        self.assertEqual(len(audit.needs_action), 0)
        self.assertEqual(len(audit.errors), 1)
        record = audit.errors[0]
        self.assertIsInstance(record, workspace_sharing_audit_results.StopSharing)
        self.assertEqual(record.workspace, self.combined_workspace.workspace)
        self.assertEqual(record.managed_group, self.other_group)
        self.assertEqual(record.current_sharing_instance, sharing)
        self.assertEqual(record.note, combined_workspace_audit.CombinedConsortiumDataWorkspaceSharingAudit.OTHER_GROUP)


class DCCProcessedDataWorkspaceSharingAuditTest(TestCase):
    def test_completed(self):
        """The completed attribute is set appropriately."""
        # Instantiate the class.
        audit = dcc_processed_data_workspace_audit.DCCProcessedDataWorkspaceSharingAudit()
        self.assertFalse(audit.completed)
        audit.run_audit()
        self.assertTrue(audit.completed)

    def test_no_workspaces(self):
        """The audit works if there are no combined workspaces."""
        audit = dcc_processed_data_workspace_audit.DCCProcessedDataWorkspaceSharingAudit()
        audit.run_audit()
        self.assertEqual(len(audit.get_all_results()), 0)

    def test_one_workspace_no_groups(self):
        workspace_data = factories.DCCProcessedDataWorkspaceFactory.create()
        # Delete the auth domain to mimic having no other groups.
        workspace_data.workspace.authorization_domains.clear()
        audit = dcc_processed_data_workspace_audit.DCCProcessedDataWorkspaceSharingAudit()
        audit.run_audit()
        self.assertEqual(len(audit.get_all_results()), 0)

    def test_one_workspace_dcc_admin_group(self):
        group = ManagedGroupFactory.create(name=settings.ANVIL_DCC_ADMINS_GROUP_NAME)
        workspace_data = factories.DCCProcessedDataWorkspaceFactory.create()
        # Delete the auth domain to mimic having no other groups.
        workspace_data.workspace.authorization_domains.clear()
        audit = dcc_processed_data_workspace_audit.DCCProcessedDataWorkspaceSharingAudit()
        audit.run_audit()
        self.assertEqual(len(audit.get_all_results()), 1)
        record = audit.get_all_results()[0]
        self.assertIsInstance(record, workspace_sharing_audit_results.WorkspaceSharingAuditResult)
        self.assertEqual(record.workspace, workspace_data.workspace)
        self.assertEqual(record.managed_group, group)
        self.assertNotEqual(record.note, audit.OTHER_GROUP)

    @override_settings(ANVIL_DCC_ADMINS_GROUP_NAME="foo")
    def test_one_workspace_dcc_admin_group_different_name(self):
        group = ManagedGroupFactory.create(name="foo")
        workspace_data = factories.DCCProcessedDataWorkspaceFactory.create()
        # Delete the auth domain to mimic having no other groups.
        workspace_data.workspace.authorization_domains.clear()
        audit = dcc_processed_data_workspace_audit.DCCProcessedDataWorkspaceSharingAudit()
        audit.run_audit()
        self.assertEqual(len(audit.get_all_results()), 1)
        record = audit.get_all_results()[0]
        self.assertIsInstance(record, workspace_sharing_audit_results.WorkspaceSharingAuditResult)
        self.assertEqual(record.workspace, workspace_data.workspace)
        self.assertEqual(record.managed_group, group)
        self.assertNotEqual(record.note, audit.OTHER_GROUP)

    def test_one_workspace_dcc_writer_group(self):
        group = ManagedGroupFactory.create(name="GREGOR_DCC_WRITERS")
        workspace_data = factories.DCCProcessedDataWorkspaceFactory.create()
        # Delete the auth domain to mimic having no other groups.
        workspace_data.workspace.authorization_domains.clear()
        audit = dcc_processed_data_workspace_audit.DCCProcessedDataWorkspaceSharingAudit()
        audit.run_audit()
        self.assertEqual(len(audit.get_all_results()), 1)
        record = audit.get_all_results()[0]
        self.assertIsInstance(record, workspace_sharing_audit_results.WorkspaceSharingAuditResult)
        self.assertEqual(record.workspace, workspace_data.workspace)
        self.assertEqual(record.managed_group, group)
        self.assertNotEqual(record.note, audit.OTHER_GROUP)

    def test_one_workspace_anvil_admins(self):
        workspace_data = factories.DCCProcessedDataWorkspaceFactory.create()
        # Delete the auth domain to mimic having no other groups.
        workspace_data.workspace.authorization_domains.clear()
        WorkspaceGroupSharingFactory.create(workspace=workspace_data.workspace, group__name="anvil-admins")
        audit = dcc_processed_data_workspace_audit.DCCProcessedDataWorkspaceSharingAudit()
        audit.run_audit()
        self.assertEqual(len(audit.get_all_results()), 0)

    def test_one_workspace_anvil_devs(self):
        workspace_data = factories.DCCProcessedDataWorkspaceFactory.create()
        # Delete the auth domain to mimic having no other groups.
        workspace_data.workspace.authorization_domains.clear()
        WorkspaceGroupSharingFactory.create(workspace=workspace_data.workspace, group__name="anvil_devs")
        audit = dcc_processed_data_workspace_audit.DCCProcessedDataWorkspaceSharingAudit()
        audit.run_audit()
        self.assertEqual(len(audit.get_all_results()), 0)

    def test_one_workspace_auth_domain(self):
        workspace_data = factories.DCCProcessedDataWorkspaceFactory.create()
        group = workspace_data.workspace.authorization_domains.first()
        audit = dcc_processed_data_workspace_audit.DCCProcessedDataWorkspaceSharingAudit()
        audit.run_audit()
        self.assertEqual(len(audit.get_all_results()), 1)
        record = audit.get_all_results()[0]
        self.assertIsInstance(record, workspace_sharing_audit_results.WorkspaceSharingAuditResult)
        self.assertEqual(record.workspace, workspace_data.workspace)
        self.assertEqual(record.managed_group, group)
        self.assertNotEqual(record.note, audit.OTHER_GROUP)

    def test_one_workspace_other_group_shared(self):
        group = ManagedGroupFactory.create()
        workspace_data = factories.DCCProcessedDataWorkspaceFactory.create()
        WorkspaceGroupSharingFactory.create(workspace=workspace_data.workspace, group=group)
        # Delete the auth domain to mimic having no other groups.
        workspace_data.workspace.authorization_domains.clear()
        audit = dcc_processed_data_workspace_audit.DCCProcessedDataWorkspaceSharingAudit()
        audit.run_audit()
        self.assertEqual(len(audit.get_all_results()), 1)
        record = audit.get_all_results()[0]
        self.assertIsInstance(record, workspace_sharing_audit_results.WorkspaceSharingAuditResult)
        self.assertEqual(record.workspace, workspace_data.workspace)
        self.assertEqual(record.managed_group, group)
        self.assertEqual(record.note, audit.OTHER_GROUP)

    def test_one_workspace_other_group_not_shared(self):
        ManagedGroupFactory.create()
        workspace_data = factories.DCCProcessedDataWorkspaceFactory.create()
        # Delete the auth domain to mimic having no other groups.
        workspace_data.workspace.authorization_domains.clear()
        audit = dcc_processed_data_workspace_audit.DCCProcessedDataWorkspaceSharingAudit()
        audit.run_audit()
        self.assertEqual(len(audit.get_all_results()), 0)

    def test_two_workspaces(self):
        """Audit works with two workspaces."""
        workspace_data_1 = factories.DCCProcessedDataWorkspaceFactory.create()
        workspace_data_2 = factories.DCCProcessedDataWorkspaceFactory.create()
        audit = dcc_processed_data_workspace_audit.DCCProcessedDataWorkspaceSharingAudit()
        audit.run_audit()
        results = audit.get_all_results()
        self.assertEqual(len(results), 2)
        record = [x for x in results if x.workspace == workspace_data_1.workspace][0]
        self.assertIsInstance(record, workspace_sharing_audit_results.WorkspaceSharingAuditResult)
        self.assertEqual(record.workspace, workspace_data_1.workspace)
        self.assertEqual(record.managed_group, workspace_data_1.workspace.authorization_domains.first())
        self.assertNotEqual(record.note, audit.OTHER_GROUP)
        record = [x for x in results if x.workspace == workspace_data_2.workspace][0]
        self.assertIsInstance(record, workspace_sharing_audit_results.WorkspaceSharingAuditResult)
        self.assertEqual(record.workspace, workspace_data_2.workspace)
        self.assertEqual(record.managed_group, workspace_data_2.workspace.authorization_domains.first())
        self.assertNotEqual(record.note, audit.OTHER_GROUP)

    def test_queryset(self):
        """Audit only runs on the specified queryset."""
        workspace_data_1 = factories.DCCProcessedDataWorkspaceFactory.create()
        workspace_data_2 = factories.DCCProcessedDataWorkspaceFactory.create()
        # First workspace
        audit = dcc_processed_data_workspace_audit.DCCProcessedDataWorkspaceSharingAudit(
            queryset=models.DCCProcessedDataWorkspace.objects.filter(pk=workspace_data_1.pk)
        )
        audit.run_audit()
        self.assertEqual(len(audit.get_all_results()), 1)
        record = audit.get_all_results()[0]
        self.assertIsInstance(record, workspace_sharing_audit_results.WorkspaceSharingAuditResult)
        self.assertEqual(record.workspace, workspace_data_1.workspace)
        self.assertEqual(record.managed_group, workspace_data_1.workspace.authorization_domains.first())
        # Second workspace
        audit = dcc_processed_data_workspace_audit.DCCProcessedDataWorkspaceSharingAudit(
            queryset=models.DCCProcessedDataWorkspace.objects.filter(pk=workspace_data_2.pk)
        )
        audit.run_audit()
        self.assertEqual(len(audit.get_all_results()), 1)
        record = audit.get_all_results()[0]
        self.assertIsInstance(record, workspace_sharing_audit_results.WorkspaceSharingAuditResult)
        self.assertEqual(record.workspace, workspace_data_2.workspace)
        self.assertEqual(record.managed_group, workspace_data_2.workspace.authorization_domains.first())

    def test_queryset_wrong_class(self):
        """Raises ValueError if queryset is not a QuerySet."""
        with self.assertRaises(ValueError):
            dcc_processed_data_workspace_audit.DCCProcessedDataWorkspaceSharingAudit(queryset="foo")
        with self.assertRaises(ValueError):
            dcc_processed_data_workspace_audit.DCCProcessedDataWorkspaceSharingAudit(
                # wrong model type.
                queryset=models.UploadWorkspace.objects.all()
            )


class DCCProcessedDataWorkspaceSharingAuditBeforeCombinedTest(TestCase):
    """Tests for the `DCCProcessedDataWorkspaceSharingAudit` class before the combined workspace exists."""

    def setUp(self):
        super().setUp()
        self.dcc_writer_group = ManagedGroupFactory.create(name="GREGOR_DCC_WRITERS")
        self.dcc_member_group = ManagedGroupFactory.create(name="GREGOR_DCC_MEMBERS")
        self.dcc_admin_group = ManagedGroupFactory.create(name=settings.ANVIL_DCC_ADMINS_GROUP_NAME)
        self.workspace_data = factories.DCCProcessedDataWorkspaceFactory.create(upload_cycle__is_current=True)
        self.auth_domain = self.workspace_data.workspace.authorization_domains.get()
        self.other_group = ManagedGroupFactory.create()
        self.anvil_admins = ManagedGroupFactory.create(name="anvil-admins")
        self.anvil_devs = ManagedGroupFactory.create(name="anvil_devs")
        # No combined workspace.

    def test_dcc_admin_shared_as_writer_no_compute(self):
        # Share the workspace with the group.
        sharing = WorkspaceGroupSharingFactory.create(
            workspace=self.workspace_data.workspace, group=self.dcc_admin_group, access=WorkspaceGroupSharing.WRITER
        )
        audit = dcc_processed_data_workspace_audit.DCCProcessedDataWorkspaceSharingAudit()
        audit.audit_workspace_and_group(self.workspace_data, self.dcc_admin_group)
        self.assertEqual(len(audit.verified), 0)
        self.assertEqual(len(audit.needs_action), 1)
        self.assertEqual(len(audit.errors), 0)
        record = audit.needs_action[0]
        self.assertIsInstance(record, workspace_sharing_audit_results.ShareAsOwner)
        self.assertEqual(record.workspace, self.workspace_data.workspace)
        self.assertEqual(record.managed_group, self.dcc_admin_group)
        self.assertEqual(record.current_sharing_instance, sharing)
        self.assertEqual(
            record.note, dcc_processed_data_workspace_audit.DCCProcessedDataWorkspaceSharingAudit.DCC_ADMIN_AS_OWNER
        )

    def test_dcc_admin_not_shared(self):
        audit = dcc_processed_data_workspace_audit.DCCProcessedDataWorkspaceSharingAudit()
        audit.audit_workspace_and_group(self.workspace_data, self.dcc_admin_group)
        self.assertEqual(len(audit.verified), 0)
        self.assertEqual(len(audit.needs_action), 1)
        self.assertEqual(len(audit.errors), 0)
        record = audit.needs_action[0]
        self.assertIsInstance(record, workspace_sharing_audit_results.ShareAsOwner)
        self.assertEqual(record.workspace, self.workspace_data.workspace)
        self.assertEqual(record.managed_group, self.dcc_admin_group)
        self.assertEqual(record.current_sharing_instance, None)
        self.assertEqual(
            record.note, dcc_processed_data_workspace_audit.DCCProcessedDataWorkspaceSharingAudit.DCC_ADMIN_AS_OWNER
        )

    def test_dcc_admin_shared_as_writer_can_compute(self):
        sharing = WorkspaceGroupSharingFactory.create(
            workspace=self.workspace_data.workspace,
            group=self.dcc_admin_group,
            access=WorkspaceGroupSharing.WRITER,
            can_compute=True,
        )
        audit = dcc_processed_data_workspace_audit.DCCProcessedDataWorkspaceSharingAudit()
        audit.audit_workspace_and_group(self.workspace_data, self.dcc_admin_group)
        self.assertEqual(len(audit.verified), 0)
        self.assertEqual(len(audit.needs_action), 1)
        self.assertEqual(len(audit.errors), 0)
        record = audit.needs_action[0]
        self.assertIsInstance(record, workspace_sharing_audit_results.ShareAsOwner)
        self.assertEqual(record.workspace, self.workspace_data.workspace)
        self.assertEqual(record.managed_group, self.dcc_admin_group)
        self.assertEqual(record.current_sharing_instance, sharing)
        self.assertEqual(
            record.note, dcc_processed_data_workspace_audit.DCCProcessedDataWorkspaceSharingAudit.DCC_ADMIN_AS_OWNER
        )

    def test_dcc_admin_shared_as_reader(self):
        sharing = WorkspaceGroupSharingFactory.create(
            workspace=self.workspace_data.workspace, group=self.dcc_admin_group, access=WorkspaceGroupSharing.READER
        )
        audit = dcc_processed_data_workspace_audit.DCCProcessedDataWorkspaceSharingAudit()
        audit.audit_workspace_and_group(self.workspace_data, self.dcc_admin_group)
        self.assertEqual(len(audit.verified), 0)
        self.assertEqual(len(audit.needs_action), 1)
        self.assertEqual(len(audit.errors), 0)
        record = audit.needs_action[0]
        self.assertIsInstance(record, workspace_sharing_audit_results.ShareAsOwner)
        self.assertEqual(record.workspace, self.workspace_data.workspace)
        self.assertEqual(record.managed_group, self.dcc_admin_group)
        self.assertEqual(record.current_sharing_instance, sharing)
        self.assertEqual(
            record.note, dcc_processed_data_workspace_audit.DCCProcessedDataWorkspaceSharingAudit.DCC_ADMIN_AS_OWNER
        )

    def test_dcc_admin_shared_as_owner(self):
        sharing = WorkspaceGroupSharingFactory.create(
            workspace=self.workspace_data.workspace, group=self.dcc_admin_group, access=WorkspaceGroupSharing.OWNER
        )
        audit = dcc_processed_data_workspace_audit.DCCProcessedDataWorkspaceSharingAudit()
        audit.audit_workspace_and_group(self.workspace_data, self.dcc_admin_group)
        self.assertEqual(len(audit.verified), 1)
        self.assertEqual(len(audit.needs_action), 0)
        self.assertEqual(len(audit.errors), 0)
        record = audit.verified[0]
        self.assertIsInstance(record, workspace_sharing_audit_results.VerifiedShared)
        self.assertEqual(record.workspace, self.workspace_data.workspace)
        self.assertEqual(record.managed_group, self.dcc_admin_group)
        self.assertEqual(record.current_sharing_instance, sharing)
        self.assertEqual(
            record.note, dcc_processed_data_workspace_audit.DCCProcessedDataWorkspaceSharingAudit.DCC_ADMIN_AS_OWNER
        )

    @override_settings(ANVIL_DCC_ADMINS_GROUP_NAME="foo")
    def test_dcc_admin_different_setting(self):
        group = ManagedGroupFactory.create(name="foo")
        sharing = WorkspaceGroupSharingFactory.create(
            workspace=self.workspace_data.workspace, group=group, access=WorkspaceGroupSharing.OWNER
        )
        audit = dcc_processed_data_workspace_audit.DCCProcessedDataWorkspaceSharingAudit()
        audit.audit_workspace_and_group(self.workspace_data, group)
        self.assertEqual(len(audit.verified), 1)
        self.assertEqual(len(audit.needs_action), 0)
        self.assertEqual(len(audit.errors), 0)
        record = audit.verified[0]
        self.assertIsInstance(record, workspace_sharing_audit_results.VerifiedShared)
        self.assertEqual(record.workspace, self.workspace_data.workspace)
        self.assertEqual(record.managed_group, group)
        self.assertEqual(record.current_sharing_instance, sharing)
        self.assertEqual(
            record.note, dcc_processed_data_workspace_audit.DCCProcessedDataWorkspaceSharingAudit.DCC_ADMIN_AS_OWNER
        )

    def test_dcc_writers_shared_as_writer_no_compute(self):
        # Share the workspace with the group.
        sharing = WorkspaceGroupSharingFactory.create(
            workspace=self.workspace_data.workspace, group=self.dcc_writer_group, access=WorkspaceGroupSharing.WRITER
        )
        audit = dcc_processed_data_workspace_audit.DCCProcessedDataWorkspaceSharingAudit()
        audit.audit_workspace_and_group(self.workspace_data, self.dcc_writer_group)
        self.assertEqual(len(audit.verified), 0)
        self.assertEqual(len(audit.needs_action), 1)
        self.assertEqual(len(audit.errors), 0)
        record = audit.needs_action[0]
        self.assertIsInstance(record, workspace_sharing_audit_results.ShareWithCompute)
        self.assertEqual(record.workspace, self.workspace_data.workspace)
        self.assertEqual(record.managed_group, self.dcc_writer_group)
        self.assertEqual(record.current_sharing_instance, sharing)
        self.assertEqual(
            record.note,
            dcc_processed_data_workspace_audit.DCCProcessedDataWorkspaceSharingAudit.DCC_WRITERS_BEFORE_COMBINED_COMPLETE,  # noqa: E501
        )

    def test_dcc_writers_not_shared(self):
        audit = dcc_processed_data_workspace_audit.DCCProcessedDataWorkspaceSharingAudit()
        audit.audit_workspace_and_group(self.workspace_data, self.dcc_writer_group)
        audit.completed = True
        self.assertEqual(len(audit.verified), 0)
        self.assertEqual(len(audit.needs_action), 1)
        self.assertEqual(len(audit.errors), 0)
        record = audit.get_all_results()[0]
        self.assertIsInstance(record, workspace_sharing_audit_results.ShareWithCompute)
        self.assertEqual(record.workspace, self.workspace_data.workspace)
        self.assertEqual(record.managed_group, self.dcc_writer_group)
        self.assertEqual(record.current_sharing_instance, None)
        self.assertEqual(
            record.note,
            dcc_processed_data_workspace_audit.DCCProcessedDataWorkspaceSharingAudit.DCC_WRITERS_BEFORE_COMBINED_COMPLETE,  # noqa: E501
        )

    def test_dcc_writers_shared_as_writer_can_compute(self):
        sharing = WorkspaceGroupSharingFactory.create(
            workspace=self.workspace_data.workspace,
            group=self.dcc_writer_group,
            access=WorkspaceGroupSharing.WRITER,
            can_compute=True,
        )
        audit = dcc_processed_data_workspace_audit.DCCProcessedDataWorkspaceSharingAudit()
        audit.audit_workspace_and_group(self.workspace_data, self.dcc_writer_group)
        audit.completed = True
        self.assertEqual(len(audit.verified), 1)
        self.assertEqual(len(audit.needs_action), 0)
        self.assertEqual(len(audit.errors), 0)
        record = audit.get_all_results()[0]
        self.assertIsInstance(record, workspace_sharing_audit_results.VerifiedShared)
        self.assertEqual(record.workspace, self.workspace_data.workspace)
        self.assertEqual(record.managed_group, self.dcc_writer_group)
        self.assertEqual(record.current_sharing_instance, sharing)
        self.assertEqual(
            record.note,
            dcc_processed_data_workspace_audit.DCCProcessedDataWorkspaceSharingAudit.DCC_WRITERS_BEFORE_COMBINED_COMPLETE,  # noqa: E501
        )

    def test_dcc_writers_shared_as_reader(self):
        sharing = WorkspaceGroupSharingFactory.create(
            workspace=self.workspace_data.workspace, group=self.dcc_writer_group, access=WorkspaceGroupSharing.READER
        )
        audit = dcc_processed_data_workspace_audit.DCCProcessedDataWorkspaceSharingAudit()
        audit.audit_workspace_and_group(self.workspace_data, self.dcc_writer_group)
        audit.completed = True
        self.assertEqual(len(audit.verified), 0)
        self.assertEqual(len(audit.needs_action), 1)
        self.assertEqual(len(audit.errors), 0)
        record = audit.get_all_results()[0]
        self.assertIsInstance(record, workspace_sharing_audit_results.ShareWithCompute)
        self.assertEqual(record.workspace, self.workspace_data.workspace)
        self.assertEqual(record.managed_group, self.dcc_writer_group)
        self.assertEqual(record.current_sharing_instance, sharing)
        self.assertEqual(
            record.note,
            dcc_processed_data_workspace_audit.DCCProcessedDataWorkspaceSharingAudit.DCC_WRITERS_BEFORE_COMBINED_COMPLETE,  # noqa: E501
        )

    def test_dcc_writers_shared_as_owner(self):
        sharing = WorkspaceGroupSharingFactory.create(
            workspace=self.workspace_data.workspace, group=self.dcc_writer_group, access=WorkspaceGroupSharing.OWNER
        )
        audit = dcc_processed_data_workspace_audit.DCCProcessedDataWorkspaceSharingAudit()
        audit.audit_workspace_and_group(self.workspace_data, self.dcc_writer_group)
        audit.completed = True
        self.assertEqual(len(audit.verified), 0)
        self.assertEqual(len(audit.needs_action), 0)
        self.assertEqual(len(audit.errors), 1)
        record = audit.get_all_results()[0]
        self.assertIsInstance(record, workspace_sharing_audit_results.ShareWithCompute)
        self.assertEqual(record.workspace, self.workspace_data.workspace)
        self.assertEqual(record.managed_group, self.dcc_writer_group)
        self.assertEqual(record.current_sharing_instance, sharing)
        self.assertEqual(
            record.note,
            dcc_processed_data_workspace_audit.DCCProcessedDataWorkspaceSharingAudit.DCC_WRITERS_BEFORE_COMBINED_COMPLETE,  # noqa: E501
        )

    def test_auth_domain_shared_as_writer_no_compute(self):
        # Share the workspace with the group.
        sharing = WorkspaceGroupSharingFactory.create(
            workspace=self.workspace_data.workspace, group=self.auth_domain, access=WorkspaceGroupSharing.WRITER
        )
        audit = dcc_processed_data_workspace_audit.DCCProcessedDataWorkspaceSharingAudit()
        audit.audit_workspace_and_group(self.workspace_data, self.auth_domain)
        audit.completed = True
        self.assertEqual(len(audit.verified), 0)
        self.assertEqual(len(audit.needs_action), 0)
        self.assertEqual(len(audit.errors), 1)
        record = audit.get_all_results()[0]
        self.assertIsInstance(record, workspace_sharing_audit_results.ShareAsReader)
        self.assertEqual(record.workspace, self.workspace_data.workspace)
        self.assertEqual(record.managed_group, self.auth_domain)
        self.assertEqual(record.current_sharing_instance, sharing)
        self.assertEqual(
            record.note, dcc_processed_data_workspace_audit.DCCProcessedDataWorkspaceSharingAudit.AUTH_DOMAIN_AS_READER
        )

    def test_auth_domain_not_shared(self):
        audit = dcc_processed_data_workspace_audit.DCCProcessedDataWorkspaceSharingAudit()
        audit.audit_workspace_and_group(self.workspace_data, self.auth_domain)
        audit.completed = True
        self.assertEqual(len(audit.verified), 0)
        self.assertEqual(len(audit.needs_action), 1)
        self.assertEqual(len(audit.errors), 0)
        record = audit.get_all_results()[0]
        self.assertIsInstance(record, workspace_sharing_audit_results.ShareAsReader)
        self.assertEqual(record.workspace, self.workspace_data.workspace)
        self.assertEqual(record.managed_group, self.auth_domain)
        self.assertEqual(record.current_sharing_instance, None)
        self.assertEqual(
            record.note, dcc_processed_data_workspace_audit.DCCProcessedDataWorkspaceSharingAudit.AUTH_DOMAIN_AS_READER
        )

    def test_auth_domain_shared_as_writer_can_compute(self):
        sharing = WorkspaceGroupSharingFactory.create(
            workspace=self.workspace_data.workspace,
            group=self.auth_domain,
            access=WorkspaceGroupSharing.WRITER,
            can_compute=True,
        )
        audit = dcc_processed_data_workspace_audit.DCCProcessedDataWorkspaceSharingAudit()
        audit.audit_workspace_and_group(self.workspace_data, self.auth_domain)
        audit.completed = True
        self.assertEqual(len(audit.verified), 0)
        self.assertEqual(len(audit.needs_action), 0)
        self.assertEqual(len(audit.errors), 1)
        record = audit.get_all_results()[0]
        self.assertIsInstance(record, workspace_sharing_audit_results.ShareAsReader)
        self.assertEqual(record.workspace, self.workspace_data.workspace)
        self.assertEqual(record.managed_group, self.auth_domain)
        self.assertEqual(record.current_sharing_instance, sharing)
        self.assertEqual(
            record.note, dcc_processed_data_workspace_audit.DCCProcessedDataWorkspaceSharingAudit.AUTH_DOMAIN_AS_READER
        )

    def test_auth_domain_shared_as_reader(self):
        sharing = WorkspaceGroupSharingFactory.create(
            workspace=self.workspace_data.workspace, group=self.auth_domain, access=WorkspaceGroupSharing.READER
        )
        audit = dcc_processed_data_workspace_audit.DCCProcessedDataWorkspaceSharingAudit()
        audit.audit_workspace_and_group(self.workspace_data, self.auth_domain)
        audit.completed = True
        self.assertEqual(len(audit.verified), 1)
        self.assertEqual(len(audit.needs_action), 0)
        self.assertEqual(len(audit.errors), 0)
        record = audit.get_all_results()[0]
        self.assertIsInstance(record, workspace_sharing_audit_results.VerifiedShared)
        self.assertEqual(record.workspace, self.workspace_data.workspace)
        self.assertEqual(record.managed_group, self.auth_domain)
        self.assertEqual(record.current_sharing_instance, sharing)
        self.assertEqual(
            record.note, dcc_processed_data_workspace_audit.DCCProcessedDataWorkspaceSharingAudit.AUTH_DOMAIN_AS_READER
        )

    def test_auth_domain_shared_as_owner(self):
        sharing = WorkspaceGroupSharingFactory.create(
            workspace=self.workspace_data.workspace, group=self.auth_domain, access=WorkspaceGroupSharing.OWNER
        )
        audit = dcc_processed_data_workspace_audit.DCCProcessedDataWorkspaceSharingAudit()
        audit.audit_workspace_and_group(self.workspace_data, self.auth_domain)
        audit.completed = True
        self.assertEqual(len(audit.verified), 0)
        self.assertEqual(len(audit.needs_action), 0)
        self.assertEqual(len(audit.errors), 1)
        record = audit.get_all_results()[0]
        self.assertIsInstance(record, workspace_sharing_audit_results.ShareAsReader)
        self.assertEqual(record.workspace, self.workspace_data.workspace)
        self.assertEqual(record.managed_group, self.auth_domain)
        self.assertEqual(record.current_sharing_instance, sharing)
        self.assertEqual(
            record.note, dcc_processed_data_workspace_audit.DCCProcessedDataWorkspaceSharingAudit.AUTH_DOMAIN_AS_READER
        )

    def test_anvil_admins_shared_as_writer_no_compute(self):
        # Share the workspace with the group.
        WorkspaceGroupSharingFactory.create(
            workspace=self.workspace_data.workspace, group=self.anvil_admins, access=WorkspaceGroupSharing.WRITER
        )
        audit = dcc_processed_data_workspace_audit.DCCProcessedDataWorkspaceSharingAudit()
        audit.audit_workspace_and_group(self.workspace_data, self.anvil_admins)
        self.assertEqual(len(audit.verified), 0)
        self.assertEqual(len(audit.needs_action), 0)
        self.assertEqual(len(audit.errors), 0)

    def test_anvil_admins_not_shared(self):
        audit = dcc_processed_data_workspace_audit.DCCProcessedDataWorkspaceSharingAudit()
        audit.audit_workspace_and_group(self.workspace_data, self.anvil_admins)
        self.assertEqual(len(audit.verified), 0)
        self.assertEqual(len(audit.needs_action), 0)
        self.assertEqual(len(audit.errors), 0)

    def test_anvil_admins_shared_as_writer_can_compute(self):
        WorkspaceGroupSharingFactory.create(
            workspace=self.workspace_data.workspace,
            group=self.anvil_admins,
            access=WorkspaceGroupSharing.WRITER,
            can_compute=True,
        )
        audit = dcc_processed_data_workspace_audit.DCCProcessedDataWorkspaceSharingAudit()
        audit.audit_workspace_and_group(self.workspace_data, self.anvil_admins)
        self.assertEqual(len(audit.verified), 0)
        self.assertEqual(len(audit.needs_action), 0)
        self.assertEqual(len(audit.errors), 0)

    def test_anvil_admins_shared_as_reader(self):
        WorkspaceGroupSharingFactory.create(
            workspace=self.workspace_data.workspace, group=self.anvil_admins, access=WorkspaceGroupSharing.READER
        )
        audit = dcc_processed_data_workspace_audit.DCCProcessedDataWorkspaceSharingAudit()
        audit.audit_workspace_and_group(self.workspace_data, self.anvil_admins)
        self.assertEqual(len(audit.verified), 0)
        self.assertEqual(len(audit.needs_action), 0)
        self.assertEqual(len(audit.errors), 0)

    def test_anvil_admins_shared_as_owner(self):
        WorkspaceGroupSharingFactory.create(
            workspace=self.workspace_data.workspace, group=self.anvil_admins, access=WorkspaceGroupSharing.OWNER
        )
        audit = dcc_processed_data_workspace_audit.DCCProcessedDataWorkspaceSharingAudit()
        audit.audit_workspace_and_group(self.workspace_data, self.anvil_admins)
        self.assertEqual(len(audit.verified), 0)
        self.assertEqual(len(audit.needs_action), 0)
        self.assertEqual(len(audit.errors), 0)

    def test_anvil_devs_shared_as_writer_no_compute(self):
        # Share the workspace with the group.
        WorkspaceGroupSharingFactory.create(
            workspace=self.workspace_data.workspace, group=self.anvil_devs, access=WorkspaceGroupSharing.WRITER
        )
        audit = dcc_processed_data_workspace_audit.DCCProcessedDataWorkspaceSharingAudit()
        audit.audit_workspace_and_group(self.workspace_data, self.anvil_devs)
        self.assertEqual(len(audit.verified), 0)
        self.assertEqual(len(audit.needs_action), 0)
        self.assertEqual(len(audit.errors), 0)

    def test_anvil_devs_not_shared(self):
        audit = dcc_processed_data_workspace_audit.DCCProcessedDataWorkspaceSharingAudit()
        audit.audit_workspace_and_group(self.workspace_data, self.anvil_devs)
        self.assertEqual(len(audit.verified), 0)
        self.assertEqual(len(audit.needs_action), 0)
        self.assertEqual(len(audit.errors), 0)

    def test_anvil_devs_shared_as_writer_can_compute(self):
        WorkspaceGroupSharingFactory.create(
            workspace=self.workspace_data.workspace,
            group=self.anvil_devs,
            access=WorkspaceGroupSharing.WRITER,
            can_compute=True,
        )
        audit = dcc_processed_data_workspace_audit.DCCProcessedDataWorkspaceSharingAudit()
        audit.audit_workspace_and_group(self.workspace_data, self.anvil_devs)
        self.assertEqual(len(audit.verified), 0)
        self.assertEqual(len(audit.needs_action), 0)
        self.assertEqual(len(audit.errors), 0)

    def test_anvil_devs_shared_as_reader(self):
        WorkspaceGroupSharingFactory.create(
            workspace=self.workspace_data.workspace, group=self.anvil_devs, access=WorkspaceGroupSharing.READER
        )
        audit = dcc_processed_data_workspace_audit.DCCProcessedDataWorkspaceSharingAudit()
        audit.audit_workspace_and_group(self.workspace_data, self.anvil_devs)
        self.assertEqual(len(audit.verified), 0)
        self.assertEqual(len(audit.needs_action), 0)
        self.assertEqual(len(audit.errors), 0)

    def test_anvil_devs_shared_as_owner(self):
        WorkspaceGroupSharingFactory.create(
            workspace=self.workspace_data.workspace, group=self.anvil_devs, access=WorkspaceGroupSharing.OWNER
        )
        audit = dcc_processed_data_workspace_audit.DCCProcessedDataWorkspaceSharingAudit()
        audit.audit_workspace_and_group(self.workspace_data, self.anvil_devs)
        self.assertEqual(len(audit.verified), 0)
        self.assertEqual(len(audit.needs_action), 0)
        self.assertEqual(len(audit.errors), 0)

    def test_other_group_shared_as_writer_no_compute(self):
        # Share the workspace with the group.
        sharing = WorkspaceGroupSharingFactory.create(
            workspace=self.workspace_data.workspace, group=self.other_group, access=WorkspaceGroupSharing.WRITER
        )
        audit = dcc_processed_data_workspace_audit.DCCProcessedDataWorkspaceSharingAudit()
        audit.audit_workspace_and_group(self.workspace_data, self.other_group)
        self.assertEqual(len(audit.verified), 0)
        self.assertEqual(len(audit.needs_action), 0)
        self.assertEqual(len(audit.errors), 1)
        record = audit.errors[0]
        self.assertIsInstance(record, workspace_sharing_audit_results.StopSharing)
        self.assertEqual(record.workspace, self.workspace_data.workspace)
        self.assertEqual(record.managed_group, self.other_group)
        self.assertEqual(record.current_sharing_instance, sharing)
        self.assertEqual(
            record.note, dcc_processed_data_workspace_audit.DCCProcessedDataWorkspaceSharingAudit.OTHER_GROUP
        )

    def test_other_group_not_shared(self):
        audit = dcc_processed_data_workspace_audit.DCCProcessedDataWorkspaceSharingAudit()
        audit.audit_workspace_and_group(self.workspace_data, self.other_group)
        self.assertEqual(len(audit.verified), 1)
        self.assertEqual(len(audit.needs_action), 0)
        self.assertEqual(len(audit.errors), 0)
        record = audit.verified[0]
        self.assertIsInstance(record, workspace_sharing_audit_results.VerifiedNotShared)
        self.assertEqual(record.workspace, self.workspace_data.workspace)
        self.assertEqual(record.managed_group, self.other_group)
        self.assertEqual(record.current_sharing_instance, None)
        self.assertEqual(
            record.note, dcc_processed_data_workspace_audit.DCCProcessedDataWorkspaceSharingAudit.OTHER_GROUP
        )

    def test_other_group_shared_as_writer_can_compute(self):
        sharing = WorkspaceGroupSharingFactory.create(
            workspace=self.workspace_data.workspace,
            group=self.other_group,
            access=WorkspaceGroupSharing.WRITER,
            can_compute=True,
        )
        audit = dcc_processed_data_workspace_audit.DCCProcessedDataWorkspaceSharingAudit()
        audit.audit_workspace_and_group(self.workspace_data, self.other_group)
        self.assertEqual(len(audit.verified), 0)
        self.assertEqual(len(audit.needs_action), 0)
        self.assertEqual(len(audit.errors), 1)
        record = audit.errors[0]
        self.assertIsInstance(record, workspace_sharing_audit_results.StopSharing)
        self.assertEqual(record.workspace, self.workspace_data.workspace)
        self.assertEqual(record.managed_group, self.other_group)
        self.assertEqual(record.current_sharing_instance, sharing)
        self.assertEqual(
            record.note, dcc_processed_data_workspace_audit.DCCProcessedDataWorkspaceSharingAudit.OTHER_GROUP
        )

    def test_other_group_shared_as_reader(self):
        sharing = WorkspaceGroupSharingFactory.create(
            workspace=self.workspace_data.workspace, group=self.other_group, access=WorkspaceGroupSharing.READER
        )
        audit = dcc_processed_data_workspace_audit.DCCProcessedDataWorkspaceSharingAudit()
        audit.audit_workspace_and_group(self.workspace_data, self.other_group)
        self.assertEqual(len(audit.verified), 0)
        self.assertEqual(len(audit.needs_action), 0)
        self.assertEqual(len(audit.errors), 1)
        record = audit.errors[0]
        self.assertIsInstance(record, workspace_sharing_audit_results.StopSharing)
        self.assertEqual(record.workspace, self.workspace_data.workspace)
        self.assertEqual(record.managed_group, self.other_group)
        self.assertEqual(record.current_sharing_instance, sharing)
        self.assertEqual(
            record.note, dcc_processed_data_workspace_audit.DCCProcessedDataWorkspaceSharingAudit.OTHER_GROUP
        )

    def test_other_group_shared_as_owner(self):
        sharing = WorkspaceGroupSharingFactory.create(
            workspace=self.workspace_data.workspace, group=self.other_group, access=WorkspaceGroupSharing.OWNER
        )
        audit = dcc_processed_data_workspace_audit.DCCProcessedDataWorkspaceSharingAudit()
        audit.audit_workspace_and_group(self.workspace_data, self.other_group)
        self.assertEqual(len(audit.verified), 0)
        self.assertEqual(len(audit.needs_action), 0)
        self.assertEqual(len(audit.errors), 1)
        record = audit.errors[0]
        self.assertIsInstance(record, workspace_sharing_audit_results.StopSharing)
        self.assertEqual(record.workspace, self.workspace_data.workspace)
        self.assertEqual(record.managed_group, self.other_group)
        self.assertEqual(record.current_sharing_instance, sharing)
        self.assertEqual(
            record.note, dcc_processed_data_workspace_audit.DCCProcessedDataWorkspaceSharingAudit.OTHER_GROUP
        )


class DCCProcessedDataWorkspaceSharingAuditBeforeCombinedReadyTest(TestCase):
    """Tests for the `DCCProcessedDataWorkspaceSharingAudit` class before the combined workspace is ready."""

    def setUp(self):
        super().setUp()
        self.dcc_writer_group = ManagedGroupFactory.create(name="GREGOR_DCC_WRITERS")
        self.dcc_member_group = ManagedGroupFactory.create(name="GREGOR_DCC_MEMBERS")
        self.dcc_admin_group = ManagedGroupFactory.create(name=settings.ANVIL_DCC_ADMINS_GROUP_NAME)
        self.workspace_data = factories.DCCProcessedDataWorkspaceFactory.create(upload_cycle__is_current=True)
        self.auth_domain = self.workspace_data.workspace.authorization_domains.get()
        self.other_group = ManagedGroupFactory.create()
        self.anvil_admins = ManagedGroupFactory.create(name="anvil-admins")
        self.anvil_devs = ManagedGroupFactory.create(name="anvil_devs")
        # Create a corresponding combined workspace.
        self.combined_workspace = factories.CombinedConsortiumDataWorkspaceFactory.create(
            upload_cycle=self.workspace_data.upload_cycle,
            date_completed=None,
        )

    def test_dcc_admin_shared_as_writer_no_compute(self):
        # Share the workspace with the group.
        sharing = WorkspaceGroupSharingFactory.create(
            workspace=self.workspace_data.workspace, group=self.dcc_admin_group, access=WorkspaceGroupSharing.WRITER
        )
        audit = dcc_processed_data_workspace_audit.DCCProcessedDataWorkspaceSharingAudit()
        audit.audit_workspace_and_group(self.workspace_data, self.dcc_admin_group)
        self.assertEqual(len(audit.verified), 0)
        self.assertEqual(len(audit.needs_action), 1)
        self.assertEqual(len(audit.errors), 0)
        record = audit.needs_action[0]
        self.assertIsInstance(record, workspace_sharing_audit_results.ShareAsOwner)
        self.assertEqual(record.workspace, self.workspace_data.workspace)
        self.assertEqual(record.managed_group, self.dcc_admin_group)
        self.assertEqual(record.current_sharing_instance, sharing)
        self.assertEqual(
            record.note, dcc_processed_data_workspace_audit.DCCProcessedDataWorkspaceSharingAudit.DCC_ADMIN_AS_OWNER
        )

    def test_dcc_admin_not_shared(self):
        audit = dcc_processed_data_workspace_audit.DCCProcessedDataWorkspaceSharingAudit()
        audit.audit_workspace_and_group(self.workspace_data, self.dcc_admin_group)
        self.assertEqual(len(audit.verified), 0)
        self.assertEqual(len(audit.needs_action), 1)
        self.assertEqual(len(audit.errors), 0)
        record = audit.needs_action[0]
        self.assertIsInstance(record, workspace_sharing_audit_results.ShareAsOwner)
        self.assertEqual(record.workspace, self.workspace_data.workspace)
        self.assertEqual(record.managed_group, self.dcc_admin_group)
        self.assertEqual(record.current_sharing_instance, None)
        self.assertEqual(
            record.note, dcc_processed_data_workspace_audit.DCCProcessedDataWorkspaceSharingAudit.DCC_ADMIN_AS_OWNER
        )

    def test_dcc_admin_shared_as_writer_can_compute(self):
        sharing = WorkspaceGroupSharingFactory.create(
            workspace=self.workspace_data.workspace,
            group=self.dcc_admin_group,
            access=WorkspaceGroupSharing.WRITER,
            can_compute=True,
        )
        audit = dcc_processed_data_workspace_audit.DCCProcessedDataWorkspaceSharingAudit()
        audit.audit_workspace_and_group(self.workspace_data, self.dcc_admin_group)
        self.assertEqual(len(audit.verified), 0)
        self.assertEqual(len(audit.needs_action), 1)
        self.assertEqual(len(audit.errors), 0)
        record = audit.needs_action[0]
        self.assertIsInstance(record, workspace_sharing_audit_results.ShareAsOwner)
        self.assertEqual(record.workspace, self.workspace_data.workspace)
        self.assertEqual(record.managed_group, self.dcc_admin_group)
        self.assertEqual(record.current_sharing_instance, sharing)
        self.assertEqual(
            record.note, dcc_processed_data_workspace_audit.DCCProcessedDataWorkspaceSharingAudit.DCC_ADMIN_AS_OWNER
        )

    def test_dcc_admin_shared_as_reader(self):
        sharing = WorkspaceGroupSharingFactory.create(
            workspace=self.workspace_data.workspace, group=self.dcc_admin_group, access=WorkspaceGroupSharing.READER
        )
        audit = dcc_processed_data_workspace_audit.DCCProcessedDataWorkspaceSharingAudit()
        audit.audit_workspace_and_group(self.workspace_data, self.dcc_admin_group)
        self.assertEqual(len(audit.verified), 0)
        self.assertEqual(len(audit.needs_action), 1)
        self.assertEqual(len(audit.errors), 0)
        record = audit.needs_action[0]
        self.assertIsInstance(record, workspace_sharing_audit_results.ShareAsOwner)
        self.assertEqual(record.workspace, self.workspace_data.workspace)
        self.assertEqual(record.managed_group, self.dcc_admin_group)
        self.assertEqual(record.current_sharing_instance, sharing)
        self.assertEqual(
            record.note, dcc_processed_data_workspace_audit.DCCProcessedDataWorkspaceSharingAudit.DCC_ADMIN_AS_OWNER
        )

    def test_dcc_admin_shared_as_owner(self):
        sharing = WorkspaceGroupSharingFactory.create(
            workspace=self.workspace_data.workspace, group=self.dcc_admin_group, access=WorkspaceGroupSharing.OWNER
        )
        audit = dcc_processed_data_workspace_audit.DCCProcessedDataWorkspaceSharingAudit()
        audit.audit_workspace_and_group(self.workspace_data, self.dcc_admin_group)
        self.assertEqual(len(audit.verified), 1)
        self.assertEqual(len(audit.needs_action), 0)
        self.assertEqual(len(audit.errors), 0)
        record = audit.verified[0]
        self.assertIsInstance(record, workspace_sharing_audit_results.VerifiedShared)
        self.assertEqual(record.workspace, self.workspace_data.workspace)
        self.assertEqual(record.managed_group, self.dcc_admin_group)
        self.assertEqual(record.current_sharing_instance, sharing)
        self.assertEqual(
            record.note, dcc_processed_data_workspace_audit.DCCProcessedDataWorkspaceSharingAudit.DCC_ADMIN_AS_OWNER
        )

    @override_settings(ANVIL_DCC_ADMINS_GROUP_NAME="foo")
    def test_dcc_admin_different_setting(self):
        group = ManagedGroupFactory.create(name="foo")
        sharing = WorkspaceGroupSharingFactory.create(
            workspace=self.workspace_data.workspace, group=group, access=WorkspaceGroupSharing.OWNER
        )
        audit = dcc_processed_data_workspace_audit.DCCProcessedDataWorkspaceSharingAudit()
        audit.audit_workspace_and_group(self.workspace_data, group)
        self.assertEqual(len(audit.verified), 1)
        self.assertEqual(len(audit.needs_action), 0)
        self.assertEqual(len(audit.errors), 0)
        record = audit.verified[0]
        self.assertIsInstance(record, workspace_sharing_audit_results.VerifiedShared)
        self.assertEqual(record.workspace, self.workspace_data.workspace)
        self.assertEqual(record.managed_group, group)
        self.assertEqual(record.current_sharing_instance, sharing)
        self.assertEqual(
            record.note, dcc_processed_data_workspace_audit.DCCProcessedDataWorkspaceSharingAudit.DCC_ADMIN_AS_OWNER
        )

    def test_dcc_writers_shared_as_writer_no_compute(self):
        # Share the workspace with the group.
        sharing = WorkspaceGroupSharingFactory.create(
            workspace=self.workspace_data.workspace, group=self.dcc_writer_group, access=WorkspaceGroupSharing.WRITER
        )
        audit = dcc_processed_data_workspace_audit.DCCProcessedDataWorkspaceSharingAudit()
        audit.audit_workspace_and_group(self.workspace_data, self.dcc_writer_group)
        self.assertEqual(len(audit.verified), 0)
        self.assertEqual(len(audit.needs_action), 1)
        self.assertEqual(len(audit.errors), 0)
        record = audit.needs_action[0]
        self.assertIsInstance(record, workspace_sharing_audit_results.ShareWithCompute)
        self.assertEqual(record.workspace, self.workspace_data.workspace)
        self.assertEqual(record.managed_group, self.dcc_writer_group)
        self.assertEqual(record.current_sharing_instance, sharing)
        self.assertEqual(
            record.note,
            dcc_processed_data_workspace_audit.DCCProcessedDataWorkspaceSharingAudit.DCC_WRITERS_BEFORE_COMBINED_COMPLETE,  # noqa: E501
        )

    def test_dcc_writers_not_shared(self):
        audit = dcc_processed_data_workspace_audit.DCCProcessedDataWorkspaceSharingAudit()
        audit.audit_workspace_and_group(self.workspace_data, self.dcc_writer_group)
        audit.completed = True
        self.assertEqual(len(audit.verified), 0)
        self.assertEqual(len(audit.needs_action), 1)
        self.assertEqual(len(audit.errors), 0)
        record = audit.get_all_results()[0]
        self.assertIsInstance(record, workspace_sharing_audit_results.ShareWithCompute)
        self.assertEqual(record.workspace, self.workspace_data.workspace)
        self.assertEqual(record.managed_group, self.dcc_writer_group)
        self.assertEqual(record.current_sharing_instance, None)
        self.assertEqual(
            record.note,
            dcc_processed_data_workspace_audit.DCCProcessedDataWorkspaceSharingAudit.DCC_WRITERS_BEFORE_COMBINED_COMPLETE,  # noqa: E501
        )

    def test_dcc_writers_shared_as_writer_can_compute(self):
        sharing = WorkspaceGroupSharingFactory.create(
            workspace=self.workspace_data.workspace,
            group=self.dcc_writer_group,
            access=WorkspaceGroupSharing.WRITER,
            can_compute=True,
        )
        audit = dcc_processed_data_workspace_audit.DCCProcessedDataWorkspaceSharingAudit()
        audit.audit_workspace_and_group(self.workspace_data, self.dcc_writer_group)
        audit.completed = True
        self.assertEqual(len(audit.verified), 1)
        self.assertEqual(len(audit.needs_action), 0)
        self.assertEqual(len(audit.errors), 0)
        record = audit.get_all_results()[0]
        self.assertIsInstance(record, workspace_sharing_audit_results.VerifiedShared)
        self.assertEqual(record.workspace, self.workspace_data.workspace)
        self.assertEqual(record.managed_group, self.dcc_writer_group)
        self.assertEqual(record.current_sharing_instance, sharing)
        self.assertEqual(
            record.note,
            dcc_processed_data_workspace_audit.DCCProcessedDataWorkspaceSharingAudit.DCC_WRITERS_BEFORE_COMBINED_COMPLETE,  # noqa: E501
        )

    def test_dcc_writers_shared_as_reader(self):
        sharing = WorkspaceGroupSharingFactory.create(
            workspace=self.workspace_data.workspace, group=self.dcc_writer_group, access=WorkspaceGroupSharing.READER
        )
        audit = dcc_processed_data_workspace_audit.DCCProcessedDataWorkspaceSharingAudit()
        audit.audit_workspace_and_group(self.workspace_data, self.dcc_writer_group)
        audit.completed = True
        self.assertEqual(len(audit.verified), 0)
        self.assertEqual(len(audit.needs_action), 1)
        self.assertEqual(len(audit.errors), 0)
        record = audit.get_all_results()[0]
        self.assertIsInstance(record, workspace_sharing_audit_results.ShareWithCompute)
        self.assertEqual(record.workspace, self.workspace_data.workspace)
        self.assertEqual(record.managed_group, self.dcc_writer_group)
        self.assertEqual(record.current_sharing_instance, sharing)
        self.assertEqual(
            record.note,
            dcc_processed_data_workspace_audit.DCCProcessedDataWorkspaceSharingAudit.DCC_WRITERS_BEFORE_COMBINED_COMPLETE,  # noqa: E501
        )

    def test_dcc_writers_shared_as_owner(self):
        sharing = WorkspaceGroupSharingFactory.create(
            workspace=self.workspace_data.workspace, group=self.dcc_writer_group, access=WorkspaceGroupSharing.OWNER
        )
        audit = dcc_processed_data_workspace_audit.DCCProcessedDataWorkspaceSharingAudit()
        audit.audit_workspace_and_group(self.workspace_data, self.dcc_writer_group)
        audit.completed = True
        self.assertEqual(len(audit.verified), 0)
        self.assertEqual(len(audit.needs_action), 0)
        self.assertEqual(len(audit.errors), 1)
        record = audit.get_all_results()[0]
        self.assertIsInstance(record, workspace_sharing_audit_results.ShareWithCompute)
        self.assertEqual(record.workspace, self.workspace_data.workspace)
        self.assertEqual(record.managed_group, self.dcc_writer_group)
        self.assertEqual(record.current_sharing_instance, sharing)
        self.assertEqual(
            record.note,
            dcc_processed_data_workspace_audit.DCCProcessedDataWorkspaceSharingAudit.DCC_WRITERS_BEFORE_COMBINED_COMPLETE,  # noqa: E501
        )

    def test_auth_domain_shared_as_writer_no_compute(self):
        # Share the workspace with the group.
        sharing = WorkspaceGroupSharingFactory.create(
            workspace=self.workspace_data.workspace, group=self.auth_domain, access=WorkspaceGroupSharing.WRITER
        )
        audit = dcc_processed_data_workspace_audit.DCCProcessedDataWorkspaceSharingAudit()
        audit.audit_workspace_and_group(self.workspace_data, self.auth_domain)
        audit.completed = True
        self.assertEqual(len(audit.verified), 0)
        self.assertEqual(len(audit.needs_action), 0)
        self.assertEqual(len(audit.errors), 1)
        record = audit.get_all_results()[0]
        self.assertIsInstance(record, workspace_sharing_audit_results.ShareAsReader)
        self.assertEqual(record.workspace, self.workspace_data.workspace)
        self.assertEqual(record.managed_group, self.auth_domain)
        self.assertEqual(record.current_sharing_instance, sharing)
        self.assertEqual(
            record.note, dcc_processed_data_workspace_audit.DCCProcessedDataWorkspaceSharingAudit.AUTH_DOMAIN_AS_READER
        )

    def test_auth_domain_not_shared(self):
        audit = dcc_processed_data_workspace_audit.DCCProcessedDataWorkspaceSharingAudit()
        audit.audit_workspace_and_group(self.workspace_data, self.auth_domain)
        audit.completed = True
        self.assertEqual(len(audit.verified), 0)
        self.assertEqual(len(audit.needs_action), 1)
        self.assertEqual(len(audit.errors), 0)
        record = audit.get_all_results()[0]
        self.assertIsInstance(record, workspace_sharing_audit_results.ShareAsReader)
        self.assertEqual(record.workspace, self.workspace_data.workspace)
        self.assertEqual(record.managed_group, self.auth_domain)
        self.assertEqual(record.current_sharing_instance, None)
        self.assertEqual(
            record.note, dcc_processed_data_workspace_audit.DCCProcessedDataWorkspaceSharingAudit.AUTH_DOMAIN_AS_READER
        )

    def test_auth_domain_shared_as_writer_can_compute(self):
        sharing = WorkspaceGroupSharingFactory.create(
            workspace=self.workspace_data.workspace,
            group=self.auth_domain,
            access=WorkspaceGroupSharing.WRITER,
            can_compute=True,
        )
        audit = dcc_processed_data_workspace_audit.DCCProcessedDataWorkspaceSharingAudit()
        audit.audit_workspace_and_group(self.workspace_data, self.auth_domain)
        audit.completed = True
        self.assertEqual(len(audit.verified), 0)
        self.assertEqual(len(audit.needs_action), 0)
        self.assertEqual(len(audit.errors), 1)
        record = audit.get_all_results()[0]
        self.assertIsInstance(record, workspace_sharing_audit_results.ShareAsReader)
        self.assertEqual(record.workspace, self.workspace_data.workspace)
        self.assertEqual(record.managed_group, self.auth_domain)
        self.assertEqual(record.current_sharing_instance, sharing)
        self.assertEqual(
            record.note, dcc_processed_data_workspace_audit.DCCProcessedDataWorkspaceSharingAudit.AUTH_DOMAIN_AS_READER
        )

    def test_auth_domain_shared_as_reader(self):
        sharing = WorkspaceGroupSharingFactory.create(
            workspace=self.workspace_data.workspace, group=self.auth_domain, access=WorkspaceGroupSharing.READER
        )
        audit = dcc_processed_data_workspace_audit.DCCProcessedDataWorkspaceSharingAudit()
        audit.audit_workspace_and_group(self.workspace_data, self.auth_domain)
        audit.completed = True
        self.assertEqual(len(audit.verified), 1)
        self.assertEqual(len(audit.needs_action), 0)
        self.assertEqual(len(audit.errors), 0)
        record = audit.get_all_results()[0]
        self.assertIsInstance(record, workspace_sharing_audit_results.VerifiedShared)
        self.assertEqual(record.workspace, self.workspace_data.workspace)
        self.assertEqual(record.managed_group, self.auth_domain)
        self.assertEqual(record.current_sharing_instance, sharing)
        self.assertEqual(
            record.note, dcc_processed_data_workspace_audit.DCCProcessedDataWorkspaceSharingAudit.AUTH_DOMAIN_AS_READER
        )

    def test_auth_domain_shared_as_owner(self):
        sharing = WorkspaceGroupSharingFactory.create(
            workspace=self.workspace_data.workspace, group=self.auth_domain, access=WorkspaceGroupSharing.OWNER
        )
        audit = dcc_processed_data_workspace_audit.DCCProcessedDataWorkspaceSharingAudit()
        audit.audit_workspace_and_group(self.workspace_data, self.auth_domain)
        audit.completed = True
        self.assertEqual(len(audit.verified), 0)
        self.assertEqual(len(audit.needs_action), 0)
        self.assertEqual(len(audit.errors), 1)
        record = audit.get_all_results()[0]
        self.assertIsInstance(record, workspace_sharing_audit_results.ShareAsReader)
        self.assertEqual(record.workspace, self.workspace_data.workspace)
        self.assertEqual(record.managed_group, self.auth_domain)
        self.assertEqual(record.current_sharing_instance, sharing)
        self.assertEqual(
            record.note, dcc_processed_data_workspace_audit.DCCProcessedDataWorkspaceSharingAudit.AUTH_DOMAIN_AS_READER
        )

    def test_anvil_admins_shared_as_writer_no_compute(self):
        # Share the workspace with the group.
        WorkspaceGroupSharingFactory.create(
            workspace=self.workspace_data.workspace, group=self.anvil_admins, access=WorkspaceGroupSharing.WRITER
        )
        audit = dcc_processed_data_workspace_audit.DCCProcessedDataWorkspaceSharingAudit()
        audit.audit_workspace_and_group(self.workspace_data, self.anvil_admins)
        self.assertEqual(len(audit.verified), 0)
        self.assertEqual(len(audit.needs_action), 0)
        self.assertEqual(len(audit.errors), 0)

    def test_anvil_admins_not_shared(self):
        audit = dcc_processed_data_workspace_audit.DCCProcessedDataWorkspaceSharingAudit()
        audit.audit_workspace_and_group(self.workspace_data, self.anvil_admins)
        self.assertEqual(len(audit.verified), 0)
        self.assertEqual(len(audit.needs_action), 0)
        self.assertEqual(len(audit.errors), 0)

    def test_anvil_admins_shared_as_writer_can_compute(self):
        WorkspaceGroupSharingFactory.create(
            workspace=self.workspace_data.workspace,
            group=self.anvil_admins,
            access=WorkspaceGroupSharing.WRITER,
            can_compute=True,
        )
        audit = dcc_processed_data_workspace_audit.DCCProcessedDataWorkspaceSharingAudit()
        audit.audit_workspace_and_group(self.workspace_data, self.anvil_admins)
        self.assertEqual(len(audit.verified), 0)
        self.assertEqual(len(audit.needs_action), 0)
        self.assertEqual(len(audit.errors), 0)

    def test_anvil_admins_shared_as_reader(self):
        WorkspaceGroupSharingFactory.create(
            workspace=self.workspace_data.workspace, group=self.anvil_admins, access=WorkspaceGroupSharing.READER
        )
        audit = dcc_processed_data_workspace_audit.DCCProcessedDataWorkspaceSharingAudit()
        audit.audit_workspace_and_group(self.workspace_data, self.anvil_admins)
        self.assertEqual(len(audit.verified), 0)
        self.assertEqual(len(audit.needs_action), 0)
        self.assertEqual(len(audit.errors), 0)

    def test_anvil_admins_shared_as_owner(self):
        WorkspaceGroupSharingFactory.create(
            workspace=self.workspace_data.workspace, group=self.anvil_admins, access=WorkspaceGroupSharing.OWNER
        )
        audit = dcc_processed_data_workspace_audit.DCCProcessedDataWorkspaceSharingAudit()
        audit.audit_workspace_and_group(self.workspace_data, self.anvil_admins)
        self.assertEqual(len(audit.verified), 0)
        self.assertEqual(len(audit.needs_action), 0)
        self.assertEqual(len(audit.errors), 0)

    def test_anvil_devs_shared_as_writer_no_compute(self):
        # Share the workspace with the group.
        WorkspaceGroupSharingFactory.create(
            workspace=self.workspace_data.workspace, group=self.anvil_devs, access=WorkspaceGroupSharing.WRITER
        )
        audit = dcc_processed_data_workspace_audit.DCCProcessedDataWorkspaceSharingAudit()
        audit.audit_workspace_and_group(self.workspace_data, self.anvil_devs)
        self.assertEqual(len(audit.verified), 0)
        self.assertEqual(len(audit.needs_action), 0)
        self.assertEqual(len(audit.errors), 0)

    def test_anvil_devs_not_shared(self):
        audit = dcc_processed_data_workspace_audit.DCCProcessedDataWorkspaceSharingAudit()
        audit.audit_workspace_and_group(self.workspace_data, self.anvil_devs)
        self.assertEqual(len(audit.verified), 0)
        self.assertEqual(len(audit.needs_action), 0)
        self.assertEqual(len(audit.errors), 0)

    def test_anvil_devs_shared_as_writer_can_compute(self):
        WorkspaceGroupSharingFactory.create(
            workspace=self.workspace_data.workspace,
            group=self.anvil_devs,
            access=WorkspaceGroupSharing.WRITER,
            can_compute=True,
        )
        audit = dcc_processed_data_workspace_audit.DCCProcessedDataWorkspaceSharingAudit()
        audit.audit_workspace_and_group(self.workspace_data, self.anvil_devs)
        self.assertEqual(len(audit.verified), 0)
        self.assertEqual(len(audit.needs_action), 0)
        self.assertEqual(len(audit.errors), 0)

    def test_anvil_devs_shared_as_reader(self):
        WorkspaceGroupSharingFactory.create(
            workspace=self.workspace_data.workspace, group=self.anvil_devs, access=WorkspaceGroupSharing.READER
        )
        audit = dcc_processed_data_workspace_audit.DCCProcessedDataWorkspaceSharingAudit()
        audit.audit_workspace_and_group(self.workspace_data, self.anvil_devs)
        self.assertEqual(len(audit.verified), 0)
        self.assertEqual(len(audit.needs_action), 0)
        self.assertEqual(len(audit.errors), 0)

    def test_anvil_devs_shared_as_owner(self):
        WorkspaceGroupSharingFactory.create(
            workspace=self.workspace_data.workspace, group=self.anvil_devs, access=WorkspaceGroupSharing.OWNER
        )
        audit = dcc_processed_data_workspace_audit.DCCProcessedDataWorkspaceSharingAudit()
        audit.audit_workspace_and_group(self.workspace_data, self.anvil_devs)
        self.assertEqual(len(audit.verified), 0)
        self.assertEqual(len(audit.needs_action), 0)
        self.assertEqual(len(audit.errors), 0)

    def test_other_group_shared_as_writer_no_compute(self):
        # Share the workspace with the group.
        sharing = WorkspaceGroupSharingFactory.create(
            workspace=self.workspace_data.workspace, group=self.other_group, access=WorkspaceGroupSharing.WRITER
        )
        audit = dcc_processed_data_workspace_audit.DCCProcessedDataWorkspaceSharingAudit()
        audit.audit_workspace_and_group(self.workspace_data, self.other_group)
        self.assertEqual(len(audit.verified), 0)
        self.assertEqual(len(audit.needs_action), 0)
        self.assertEqual(len(audit.errors), 1)
        record = audit.errors[0]
        self.assertIsInstance(record, workspace_sharing_audit_results.StopSharing)
        self.assertEqual(record.workspace, self.workspace_data.workspace)
        self.assertEqual(record.managed_group, self.other_group)
        self.assertEqual(record.current_sharing_instance, sharing)
        self.assertEqual(
            record.note, dcc_processed_data_workspace_audit.DCCProcessedDataWorkspaceSharingAudit.OTHER_GROUP
        )

    def test_other_group_not_shared(self):
        audit = dcc_processed_data_workspace_audit.DCCProcessedDataWorkspaceSharingAudit()
        audit.audit_workspace_and_group(self.workspace_data, self.other_group)
        self.assertEqual(len(audit.verified), 1)
        self.assertEqual(len(audit.needs_action), 0)
        self.assertEqual(len(audit.errors), 0)
        record = audit.verified[0]
        self.assertIsInstance(record, workspace_sharing_audit_results.VerifiedNotShared)
        self.assertEqual(record.workspace, self.workspace_data.workspace)
        self.assertEqual(record.managed_group, self.other_group)
        self.assertEqual(record.current_sharing_instance, None)
        self.assertEqual(
            record.note, dcc_processed_data_workspace_audit.DCCProcessedDataWorkspaceSharingAudit.OTHER_GROUP
        )

    def test_other_group_shared_as_writer_can_compute(self):
        sharing = WorkspaceGroupSharingFactory.create(
            workspace=self.workspace_data.workspace,
            group=self.other_group,
            access=WorkspaceGroupSharing.WRITER,
            can_compute=True,
        )
        audit = dcc_processed_data_workspace_audit.DCCProcessedDataWorkspaceSharingAudit()
        audit.audit_workspace_and_group(self.workspace_data, self.other_group)
        self.assertEqual(len(audit.verified), 0)
        self.assertEqual(len(audit.needs_action), 0)
        self.assertEqual(len(audit.errors), 1)
        record = audit.errors[0]
        self.assertIsInstance(record, workspace_sharing_audit_results.StopSharing)
        self.assertEqual(record.workspace, self.workspace_data.workspace)
        self.assertEqual(record.managed_group, self.other_group)
        self.assertEqual(record.current_sharing_instance, sharing)
        self.assertEqual(
            record.note, dcc_processed_data_workspace_audit.DCCProcessedDataWorkspaceSharingAudit.OTHER_GROUP
        )

    def test_other_group_shared_as_reader(self):
        sharing = WorkspaceGroupSharingFactory.create(
            workspace=self.workspace_data.workspace, group=self.other_group, access=WorkspaceGroupSharing.READER
        )
        audit = dcc_processed_data_workspace_audit.DCCProcessedDataWorkspaceSharingAudit()
        audit.audit_workspace_and_group(self.workspace_data, self.other_group)
        self.assertEqual(len(audit.verified), 0)
        self.assertEqual(len(audit.needs_action), 0)
        self.assertEqual(len(audit.errors), 1)
        record = audit.errors[0]
        self.assertIsInstance(record, workspace_sharing_audit_results.StopSharing)
        self.assertEqual(record.workspace, self.workspace_data.workspace)
        self.assertEqual(record.managed_group, self.other_group)
        self.assertEqual(record.current_sharing_instance, sharing)
        self.assertEqual(
            record.note, dcc_processed_data_workspace_audit.DCCProcessedDataWorkspaceSharingAudit.OTHER_GROUP
        )

    def test_other_group_shared_as_owner(self):
        sharing = WorkspaceGroupSharingFactory.create(
            workspace=self.workspace_data.workspace, group=self.other_group, access=WorkspaceGroupSharing.OWNER
        )
        audit = dcc_processed_data_workspace_audit.DCCProcessedDataWorkspaceSharingAudit()
        audit.audit_workspace_and_group(self.workspace_data, self.other_group)
        self.assertEqual(len(audit.verified), 0)
        self.assertEqual(len(audit.needs_action), 0)
        self.assertEqual(len(audit.errors), 1)
        record = audit.errors[0]
        self.assertIsInstance(record, workspace_sharing_audit_results.StopSharing)
        self.assertEqual(record.workspace, self.workspace_data.workspace)
        self.assertEqual(record.managed_group, self.other_group)
        self.assertEqual(record.current_sharing_instance, sharing)
        self.assertEqual(
            record.note, dcc_processed_data_workspace_audit.DCCProcessedDataWorkspaceSharingAudit.OTHER_GROUP
        )


class DCCProcessedDataWorkspaceSharingAuditAfterCombinedReadyTest(TestCase):
    """Tests for the `DCCProcessedDataWorkspaceSharingAudit` class after the combined workspace is ready."""

    def setUp(self):
        super().setUp()
        self.dcc_writer_group = ManagedGroupFactory.create(name="GREGOR_DCC_WRITERS")
        self.dcc_member_group = ManagedGroupFactory.create(name="GREGOR_DCC_MEMBERS")
        self.dcc_admin_group = ManagedGroupFactory.create(name=settings.ANVIL_DCC_ADMINS_GROUP_NAME)
        self.workspace_data = factories.DCCProcessedDataWorkspaceFactory.create(upload_cycle__is_current=True)
        self.auth_domain = self.workspace_data.workspace.authorization_domains.get()
        self.other_group = ManagedGroupFactory.create()
        self.anvil_admins = ManagedGroupFactory.create(name="anvil-admins")
        self.anvil_devs = ManagedGroupFactory.create(name="anvil_devs")
        # Create a corresponding combined workspace.
        self.combined_workspace = factories.CombinedConsortiumDataWorkspaceFactory.create(
            upload_cycle=self.workspace_data.upload_cycle,
            date_completed=fake.date_this_year(
                before_today=True,
                after_today=False,
            ),
        )

    def test_dcc_admin_shared_as_writer_no_compute(self):
        # Share the workspace with the group.
        sharing = WorkspaceGroupSharingFactory.create(
            workspace=self.workspace_data.workspace, group=self.dcc_admin_group, access=WorkspaceGroupSharing.WRITER
        )
        audit = dcc_processed_data_workspace_audit.DCCProcessedDataWorkspaceSharingAudit()
        audit.audit_workspace_and_group(self.workspace_data, self.dcc_admin_group)
        self.assertEqual(len(audit.verified), 0)
        self.assertEqual(len(audit.needs_action), 1)
        self.assertEqual(len(audit.errors), 0)
        record = audit.needs_action[0]
        self.assertIsInstance(record, workspace_sharing_audit_results.ShareAsOwner)
        self.assertEqual(record.workspace, self.workspace_data.workspace)
        self.assertEqual(record.managed_group, self.dcc_admin_group)
        self.assertEqual(record.current_sharing_instance, sharing)
        self.assertEqual(
            record.note, dcc_processed_data_workspace_audit.DCCProcessedDataWorkspaceSharingAudit.DCC_ADMIN_AS_OWNER
        )

    def test_dcc_admin_not_shared(self):
        audit = dcc_processed_data_workspace_audit.DCCProcessedDataWorkspaceSharingAudit()
        audit.audit_workspace_and_group(self.workspace_data, self.dcc_admin_group)
        self.assertEqual(len(audit.verified), 0)
        self.assertEqual(len(audit.needs_action), 1)
        self.assertEqual(len(audit.errors), 0)
        record = audit.needs_action[0]
        self.assertIsInstance(record, workspace_sharing_audit_results.ShareAsOwner)
        self.assertEqual(record.workspace, self.workspace_data.workspace)
        self.assertEqual(record.managed_group, self.dcc_admin_group)
        self.assertEqual(record.current_sharing_instance, None)
        self.assertEqual(
            record.note, dcc_processed_data_workspace_audit.DCCProcessedDataWorkspaceSharingAudit.DCC_ADMIN_AS_OWNER
        )

    def test_dcc_admin_shared_as_writer_can_compute(self):
        sharing = WorkspaceGroupSharingFactory.create(
            workspace=self.workspace_data.workspace,
            group=self.dcc_admin_group,
            access=WorkspaceGroupSharing.WRITER,
            can_compute=True,
        )
        audit = dcc_processed_data_workspace_audit.DCCProcessedDataWorkspaceSharingAudit()
        audit.audit_workspace_and_group(self.workspace_data, self.dcc_admin_group)
        self.assertEqual(len(audit.verified), 0)
        self.assertEqual(len(audit.needs_action), 1)
        self.assertEqual(len(audit.errors), 0)
        record = audit.needs_action[0]
        self.assertIsInstance(record, workspace_sharing_audit_results.ShareAsOwner)
        self.assertEqual(record.workspace, self.workspace_data.workspace)
        self.assertEqual(record.managed_group, self.dcc_admin_group)
        self.assertEqual(record.current_sharing_instance, sharing)
        self.assertEqual(
            record.note, dcc_processed_data_workspace_audit.DCCProcessedDataWorkspaceSharingAudit.DCC_ADMIN_AS_OWNER
        )

    def test_dcc_admin_shared_as_reader(self):
        sharing = WorkspaceGroupSharingFactory.create(
            workspace=self.workspace_data.workspace, group=self.dcc_admin_group, access=WorkspaceGroupSharing.READER
        )
        audit = dcc_processed_data_workspace_audit.DCCProcessedDataWorkspaceSharingAudit()
        audit.audit_workspace_and_group(self.workspace_data, self.dcc_admin_group)
        self.assertEqual(len(audit.verified), 0)
        self.assertEqual(len(audit.needs_action), 1)
        self.assertEqual(len(audit.errors), 0)
        record = audit.needs_action[0]
        self.assertIsInstance(record, workspace_sharing_audit_results.ShareAsOwner)
        self.assertEqual(record.workspace, self.workspace_data.workspace)
        self.assertEqual(record.managed_group, self.dcc_admin_group)
        self.assertEqual(record.current_sharing_instance, sharing)
        self.assertEqual(
            record.note, dcc_processed_data_workspace_audit.DCCProcessedDataWorkspaceSharingAudit.DCC_ADMIN_AS_OWNER
        )

    def test_dcc_admin_shared_as_owner(self):
        sharing = WorkspaceGroupSharingFactory.create(
            workspace=self.workspace_data.workspace, group=self.dcc_admin_group, access=WorkspaceGroupSharing.OWNER
        )
        audit = dcc_processed_data_workspace_audit.DCCProcessedDataWorkspaceSharingAudit()
        audit.audit_workspace_and_group(self.workspace_data, self.dcc_admin_group)
        self.assertEqual(len(audit.verified), 1)
        self.assertEqual(len(audit.needs_action), 0)
        self.assertEqual(len(audit.errors), 0)
        record = audit.verified[0]
        self.assertIsInstance(record, workspace_sharing_audit_results.VerifiedShared)
        self.assertEqual(record.workspace, self.workspace_data.workspace)
        self.assertEqual(record.managed_group, self.dcc_admin_group)
        self.assertEqual(record.current_sharing_instance, sharing)
        self.assertEqual(
            record.note, dcc_processed_data_workspace_audit.DCCProcessedDataWorkspaceSharingAudit.DCC_ADMIN_AS_OWNER
        )

    @override_settings(ANVIL_DCC_ADMINS_GROUP_NAME="foo")
    def test_dcc_admin_different_setting(self):
        group = ManagedGroupFactory.create(name="foo")
        sharing = WorkspaceGroupSharingFactory.create(
            workspace=self.workspace_data.workspace, group=group, access=WorkspaceGroupSharing.OWNER
        )
        audit = dcc_processed_data_workspace_audit.DCCProcessedDataWorkspaceSharingAudit()
        audit.audit_workspace_and_group(self.workspace_data, group)
        self.assertEqual(len(audit.verified), 1)
        self.assertEqual(len(audit.needs_action), 0)
        self.assertEqual(len(audit.errors), 0)
        record = audit.verified[0]
        self.assertIsInstance(record, workspace_sharing_audit_results.VerifiedShared)
        self.assertEqual(record.workspace, self.workspace_data.workspace)
        self.assertEqual(record.managed_group, group)
        self.assertEqual(record.current_sharing_instance, sharing)
        self.assertEqual(
            record.note, dcc_processed_data_workspace_audit.DCCProcessedDataWorkspaceSharingAudit.DCC_ADMIN_AS_OWNER
        )

    def test_dcc_writers_shared_as_writer_no_compute(self):
        # Share the workspace with the group.
        sharing = WorkspaceGroupSharingFactory.create(
            workspace=self.workspace_data.workspace, group=self.dcc_writer_group, access=WorkspaceGroupSharing.WRITER
        )
        audit = dcc_processed_data_workspace_audit.DCCProcessedDataWorkspaceSharingAudit()
        audit.audit_workspace_and_group(self.workspace_data, self.dcc_writer_group)
        self.assertEqual(len(audit.verified), 0)
        self.assertEqual(len(audit.needs_action), 1)
        self.assertEqual(len(audit.errors), 0)
        record = audit.needs_action[0]
        self.assertIsInstance(record, workspace_sharing_audit_results.StopSharing)
        self.assertEqual(record.workspace, self.workspace_data.workspace)
        self.assertEqual(record.managed_group, self.dcc_writer_group)
        self.assertEqual(record.current_sharing_instance, sharing)
        self.assertEqual(
            record.note,
            dcc_processed_data_workspace_audit.DCCProcessedDataWorkspaceSharingAudit.DCC_WRITERS_AFTER_COMBINED_COMPLETE,  # noqa: E501
        )

    def test_dcc_writers_not_shared(self):
        audit = dcc_processed_data_workspace_audit.DCCProcessedDataWorkspaceSharingAudit()
        audit.audit_workspace_and_group(self.workspace_data, self.dcc_writer_group)
        audit.completed = True
        self.assertEqual(len(audit.verified), 1)
        self.assertEqual(len(audit.needs_action), 0)
        self.assertEqual(len(audit.errors), 0)
        record = audit.get_all_results()[0]
        self.assertIsInstance(record, workspace_sharing_audit_results.VerifiedNotShared)
        self.assertEqual(record.workspace, self.workspace_data.workspace)
        self.assertEqual(record.managed_group, self.dcc_writer_group)
        self.assertEqual(record.current_sharing_instance, None)
        self.assertEqual(
            record.note,
            dcc_processed_data_workspace_audit.DCCProcessedDataWorkspaceSharingAudit.DCC_WRITERS_AFTER_COMBINED_COMPLETE,  # noqa: E501
        )

    def test_dcc_writers_shared_as_writer_can_compute(self):
        sharing = WorkspaceGroupSharingFactory.create(
            workspace=self.workspace_data.workspace,
            group=self.dcc_writer_group,
            access=WorkspaceGroupSharing.WRITER,
            can_compute=True,
        )
        audit = dcc_processed_data_workspace_audit.DCCProcessedDataWorkspaceSharingAudit()
        audit.audit_workspace_and_group(self.workspace_data, self.dcc_writer_group)
        audit.completed = True
        self.assertEqual(len(audit.verified), 0)
        self.assertEqual(len(audit.needs_action), 1)
        self.assertEqual(len(audit.errors), 0)
        record = audit.get_all_results()[0]
        self.assertIsInstance(record, workspace_sharing_audit_results.StopSharing)
        self.assertEqual(record.workspace, self.workspace_data.workspace)
        self.assertEqual(record.managed_group, self.dcc_writer_group)
        self.assertEqual(record.current_sharing_instance, sharing)
        self.assertEqual(
            record.note,
            dcc_processed_data_workspace_audit.DCCProcessedDataWorkspaceSharingAudit.DCC_WRITERS_AFTER_COMBINED_COMPLETE,  # noqa: E501
        )

    def test_dcc_writers_shared_as_reader(self):
        sharing = WorkspaceGroupSharingFactory.create(
            workspace=self.workspace_data.workspace, group=self.dcc_writer_group, access=WorkspaceGroupSharing.READER
        )
        audit = dcc_processed_data_workspace_audit.DCCProcessedDataWorkspaceSharingAudit()
        audit.audit_workspace_and_group(self.workspace_data, self.dcc_writer_group)
        audit.completed = True
        self.assertEqual(len(audit.verified), 0)
        self.assertEqual(len(audit.needs_action), 1)
        self.assertEqual(len(audit.errors), 0)
        record = audit.get_all_results()[0]
        self.assertIsInstance(record, workspace_sharing_audit_results.StopSharing)
        self.assertEqual(record.workspace, self.workspace_data.workspace)
        self.assertEqual(record.managed_group, self.dcc_writer_group)
        self.assertEqual(record.current_sharing_instance, sharing)
        self.assertEqual(
            record.note,
            dcc_processed_data_workspace_audit.DCCProcessedDataWorkspaceSharingAudit.DCC_WRITERS_AFTER_COMBINED_COMPLETE,  # noqa: E501
        )

    def test_dcc_writers_shared_as_owner(self):
        sharing = WorkspaceGroupSharingFactory.create(
            workspace=self.workspace_data.workspace, group=self.dcc_writer_group, access=WorkspaceGroupSharing.OWNER
        )
        audit = dcc_processed_data_workspace_audit.DCCProcessedDataWorkspaceSharingAudit()
        audit.audit_workspace_and_group(self.workspace_data, self.dcc_writer_group)
        audit.completed = True
        self.assertEqual(len(audit.verified), 0)
        self.assertEqual(len(audit.needs_action), 0)
        self.assertEqual(len(audit.errors), 1)
        record = audit.get_all_results()[0]
        self.assertIsInstance(record, workspace_sharing_audit_results.StopSharing)
        self.assertEqual(record.workspace, self.workspace_data.workspace)
        self.assertEqual(record.managed_group, self.dcc_writer_group)
        self.assertEqual(record.current_sharing_instance, sharing)
        self.assertEqual(
            record.note,
            dcc_processed_data_workspace_audit.DCCProcessedDataWorkspaceSharingAudit.DCC_WRITERS_AFTER_COMBINED_COMPLETE,  # noqa: E501
        )

    def test_auth_domain_shared_as_writer_no_compute(self):
        # Share the workspace with the group.
        sharing = WorkspaceGroupSharingFactory.create(
            workspace=self.workspace_data.workspace, group=self.auth_domain, access=WorkspaceGroupSharing.WRITER
        )
        audit = dcc_processed_data_workspace_audit.DCCProcessedDataWorkspaceSharingAudit()
        audit.audit_workspace_and_group(self.workspace_data, self.auth_domain)
        audit.completed = True
        self.assertEqual(len(audit.verified), 0)
        self.assertEqual(len(audit.needs_action), 0)
        self.assertEqual(len(audit.errors), 1)
        record = audit.get_all_results()[0]
        self.assertIsInstance(record, workspace_sharing_audit_results.ShareAsReader)
        self.assertEqual(record.workspace, self.workspace_data.workspace)
        self.assertEqual(record.managed_group, self.auth_domain)
        self.assertEqual(record.current_sharing_instance, sharing)
        self.assertEqual(
            record.note, dcc_processed_data_workspace_audit.DCCProcessedDataWorkspaceSharingAudit.AUTH_DOMAIN_AS_READER
        )

    def test_auth_domain_not_shared(self):
        audit = dcc_processed_data_workspace_audit.DCCProcessedDataWorkspaceSharingAudit()
        audit.audit_workspace_and_group(self.workspace_data, self.auth_domain)
        audit.completed = True
        self.assertEqual(len(audit.verified), 0)
        self.assertEqual(len(audit.needs_action), 1)
        self.assertEqual(len(audit.errors), 0)
        record = audit.get_all_results()[0]
        self.assertIsInstance(record, workspace_sharing_audit_results.ShareAsReader)
        self.assertEqual(record.workspace, self.workspace_data.workspace)
        self.assertEqual(record.managed_group, self.auth_domain)
        self.assertEqual(record.current_sharing_instance, None)
        self.assertEqual(
            record.note, dcc_processed_data_workspace_audit.DCCProcessedDataWorkspaceSharingAudit.AUTH_DOMAIN_AS_READER
        )

    def test_auth_domain_shared_as_writer_can_compute(self):
        sharing = WorkspaceGroupSharingFactory.create(
            workspace=self.workspace_data.workspace,
            group=self.auth_domain,
            access=WorkspaceGroupSharing.WRITER,
            can_compute=True,
        )
        audit = dcc_processed_data_workspace_audit.DCCProcessedDataWorkspaceSharingAudit()
        audit.audit_workspace_and_group(self.workspace_data, self.auth_domain)
        audit.completed = True
        self.assertEqual(len(audit.verified), 0)
        self.assertEqual(len(audit.needs_action), 0)
        self.assertEqual(len(audit.errors), 1)
        record = audit.get_all_results()[0]
        self.assertIsInstance(record, workspace_sharing_audit_results.ShareAsReader)
        self.assertEqual(record.workspace, self.workspace_data.workspace)
        self.assertEqual(record.managed_group, self.auth_domain)
        self.assertEqual(record.current_sharing_instance, sharing)
        self.assertEqual(
            record.note, dcc_processed_data_workspace_audit.DCCProcessedDataWorkspaceSharingAudit.AUTH_DOMAIN_AS_READER
        )

    def test_auth_domain_shared_as_reader(self):
        sharing = WorkspaceGroupSharingFactory.create(
            workspace=self.workspace_data.workspace, group=self.auth_domain, access=WorkspaceGroupSharing.READER
        )
        audit = dcc_processed_data_workspace_audit.DCCProcessedDataWorkspaceSharingAudit()
        audit.audit_workspace_and_group(self.workspace_data, self.auth_domain)
        audit.completed = True
        self.assertEqual(len(audit.verified), 1)
        self.assertEqual(len(audit.needs_action), 0)
        self.assertEqual(len(audit.errors), 0)
        record = audit.get_all_results()[0]
        self.assertIsInstance(record, workspace_sharing_audit_results.VerifiedShared)
        self.assertEqual(record.workspace, self.workspace_data.workspace)
        self.assertEqual(record.managed_group, self.auth_domain)
        self.assertEqual(record.current_sharing_instance, sharing)
        self.assertEqual(
            record.note, dcc_processed_data_workspace_audit.DCCProcessedDataWorkspaceSharingAudit.AUTH_DOMAIN_AS_READER
        )

    def test_auth_domain_shared_as_owner(self):
        sharing = WorkspaceGroupSharingFactory.create(
            workspace=self.workspace_data.workspace, group=self.auth_domain, access=WorkspaceGroupSharing.OWNER
        )
        audit = dcc_processed_data_workspace_audit.DCCProcessedDataWorkspaceSharingAudit()
        audit.audit_workspace_and_group(self.workspace_data, self.auth_domain)
        audit.completed = True
        self.assertEqual(len(audit.verified), 0)
        self.assertEqual(len(audit.needs_action), 0)
        self.assertEqual(len(audit.errors), 1)
        record = audit.get_all_results()[0]
        self.assertIsInstance(record, workspace_sharing_audit_results.ShareAsReader)
        self.assertEqual(record.workspace, self.workspace_data.workspace)
        self.assertEqual(record.managed_group, self.auth_domain)
        self.assertEqual(record.current_sharing_instance, sharing)
        self.assertEqual(
            record.note, dcc_processed_data_workspace_audit.DCCProcessedDataWorkspaceSharingAudit.AUTH_DOMAIN_AS_READER
        )

    def test_anvil_admins_shared_as_writer_no_compute(self):
        # Share the workspace with the group.
        WorkspaceGroupSharingFactory.create(
            workspace=self.workspace_data.workspace, group=self.anvil_admins, access=WorkspaceGroupSharing.WRITER
        )
        audit = dcc_processed_data_workspace_audit.DCCProcessedDataWorkspaceSharingAudit()
        audit.audit_workspace_and_group(self.workspace_data, self.anvil_admins)
        self.assertEqual(len(audit.verified), 0)
        self.assertEqual(len(audit.needs_action), 0)
        self.assertEqual(len(audit.errors), 0)

    def test_anvil_admins_not_shared(self):
        audit = dcc_processed_data_workspace_audit.DCCProcessedDataWorkspaceSharingAudit()
        audit.audit_workspace_and_group(self.workspace_data, self.anvil_admins)
        self.assertEqual(len(audit.verified), 0)
        self.assertEqual(len(audit.needs_action), 0)
        self.assertEqual(len(audit.errors), 0)

    def test_anvil_admins_shared_as_writer_can_compute(self):
        WorkspaceGroupSharingFactory.create(
            workspace=self.workspace_data.workspace,
            group=self.anvil_admins,
            access=WorkspaceGroupSharing.WRITER,
            can_compute=True,
        )
        audit = dcc_processed_data_workspace_audit.DCCProcessedDataWorkspaceSharingAudit()
        audit.audit_workspace_and_group(self.workspace_data, self.anvil_admins)
        self.assertEqual(len(audit.verified), 0)
        self.assertEqual(len(audit.needs_action), 0)
        self.assertEqual(len(audit.errors), 0)

    def test_anvil_admins_shared_as_reader(self):
        WorkspaceGroupSharingFactory.create(
            workspace=self.workspace_data.workspace, group=self.anvil_admins, access=WorkspaceGroupSharing.READER
        )
        audit = dcc_processed_data_workspace_audit.DCCProcessedDataWorkspaceSharingAudit()
        audit.audit_workspace_and_group(self.workspace_data, self.anvil_admins)
        self.assertEqual(len(audit.verified), 0)
        self.assertEqual(len(audit.needs_action), 0)
        self.assertEqual(len(audit.errors), 0)

    def test_anvil_admins_shared_as_owner(self):
        WorkspaceGroupSharingFactory.create(
            workspace=self.workspace_data.workspace, group=self.anvil_admins, access=WorkspaceGroupSharing.OWNER
        )
        audit = dcc_processed_data_workspace_audit.DCCProcessedDataWorkspaceSharingAudit()
        audit.audit_workspace_and_group(self.workspace_data, self.anvil_admins)
        self.assertEqual(len(audit.verified), 0)
        self.assertEqual(len(audit.needs_action), 0)
        self.assertEqual(len(audit.errors), 0)

    def test_anvil_devs_shared_as_writer_no_compute(self):
        # Share the workspace with the group.
        WorkspaceGroupSharingFactory.create(
            workspace=self.workspace_data.workspace, group=self.anvil_devs, access=WorkspaceGroupSharing.WRITER
        )
        audit = dcc_processed_data_workspace_audit.DCCProcessedDataWorkspaceSharingAudit()
        audit.audit_workspace_and_group(self.workspace_data, self.anvil_devs)
        self.assertEqual(len(audit.verified), 0)
        self.assertEqual(len(audit.needs_action), 0)
        self.assertEqual(len(audit.errors), 0)

    def test_anvil_devs_not_shared(self):
        audit = dcc_processed_data_workspace_audit.DCCProcessedDataWorkspaceSharingAudit()
        audit.audit_workspace_and_group(self.workspace_data, self.anvil_devs)
        self.assertEqual(len(audit.verified), 0)
        self.assertEqual(len(audit.needs_action), 0)
        self.assertEqual(len(audit.errors), 0)

    def test_anvil_devs_shared_as_writer_can_compute(self):
        WorkspaceGroupSharingFactory.create(
            workspace=self.workspace_data.workspace,
            group=self.anvil_devs,
            access=WorkspaceGroupSharing.WRITER,
            can_compute=True,
        )
        audit = dcc_processed_data_workspace_audit.DCCProcessedDataWorkspaceSharingAudit()
        audit.audit_workspace_and_group(self.workspace_data, self.anvil_devs)
        self.assertEqual(len(audit.verified), 0)
        self.assertEqual(len(audit.needs_action), 0)
        self.assertEqual(len(audit.errors), 0)

    def test_anvil_devs_shared_as_reader(self):
        WorkspaceGroupSharingFactory.create(
            workspace=self.workspace_data.workspace, group=self.anvil_devs, access=WorkspaceGroupSharing.READER
        )
        audit = dcc_processed_data_workspace_audit.DCCProcessedDataWorkspaceSharingAudit()
        audit.audit_workspace_and_group(self.workspace_data, self.anvil_devs)
        self.assertEqual(len(audit.verified), 0)
        self.assertEqual(len(audit.needs_action), 0)
        self.assertEqual(len(audit.errors), 0)

    def test_anvil_devs_shared_as_owner(self):
        WorkspaceGroupSharingFactory.create(
            workspace=self.workspace_data.workspace, group=self.anvil_devs, access=WorkspaceGroupSharing.OWNER
        )
        audit = dcc_processed_data_workspace_audit.DCCProcessedDataWorkspaceSharingAudit()
        audit.audit_workspace_and_group(self.workspace_data, self.anvil_devs)
        self.assertEqual(len(audit.verified), 0)
        self.assertEqual(len(audit.needs_action), 0)
        self.assertEqual(len(audit.errors), 0)

    def test_other_group_shared_as_writer_no_compute(self):
        # Share the workspace with the group.
        sharing = WorkspaceGroupSharingFactory.create(
            workspace=self.workspace_data.workspace, group=self.other_group, access=WorkspaceGroupSharing.WRITER
        )
        audit = dcc_processed_data_workspace_audit.DCCProcessedDataWorkspaceSharingAudit()
        audit.audit_workspace_and_group(self.workspace_data, self.other_group)
        self.assertEqual(len(audit.verified), 0)
        self.assertEqual(len(audit.needs_action), 0)
        self.assertEqual(len(audit.errors), 1)
        record = audit.errors[0]
        self.assertIsInstance(record, workspace_sharing_audit_results.StopSharing)
        self.assertEqual(record.workspace, self.workspace_data.workspace)
        self.assertEqual(record.managed_group, self.other_group)
        self.assertEqual(record.current_sharing_instance, sharing)
        self.assertEqual(
            record.note, dcc_processed_data_workspace_audit.DCCProcessedDataWorkspaceSharingAudit.OTHER_GROUP
        )

    def test_other_group_not_shared(self):
        audit = dcc_processed_data_workspace_audit.DCCProcessedDataWorkspaceSharingAudit()
        audit.audit_workspace_and_group(self.workspace_data, self.other_group)
        self.assertEqual(len(audit.verified), 1)
        self.assertEqual(len(audit.needs_action), 0)
        self.assertEqual(len(audit.errors), 0)
        record = audit.verified[0]
        self.assertIsInstance(record, workspace_sharing_audit_results.VerifiedNotShared)
        self.assertEqual(record.workspace, self.workspace_data.workspace)
        self.assertEqual(record.managed_group, self.other_group)
        self.assertEqual(record.current_sharing_instance, None)
        self.assertEqual(
            record.note, dcc_processed_data_workspace_audit.DCCProcessedDataWorkspaceSharingAudit.OTHER_GROUP
        )

    def test_other_group_shared_as_writer_can_compute(self):
        sharing = WorkspaceGroupSharingFactory.create(
            workspace=self.workspace_data.workspace,
            group=self.other_group,
            access=WorkspaceGroupSharing.WRITER,
            can_compute=True,
        )
        audit = dcc_processed_data_workspace_audit.DCCProcessedDataWorkspaceSharingAudit()
        audit.audit_workspace_and_group(self.workspace_data, self.other_group)
        self.assertEqual(len(audit.verified), 0)
        self.assertEqual(len(audit.needs_action), 0)
        self.assertEqual(len(audit.errors), 1)
        record = audit.errors[0]
        self.assertIsInstance(record, workspace_sharing_audit_results.StopSharing)
        self.assertEqual(record.workspace, self.workspace_data.workspace)
        self.assertEqual(record.managed_group, self.other_group)
        self.assertEqual(record.current_sharing_instance, sharing)
        self.assertEqual(
            record.note, dcc_processed_data_workspace_audit.DCCProcessedDataWorkspaceSharingAudit.OTHER_GROUP
        )

    def test_other_group_shared_as_reader(self):
        sharing = WorkspaceGroupSharingFactory.create(
            workspace=self.workspace_data.workspace, group=self.other_group, access=WorkspaceGroupSharing.READER
        )
        audit = dcc_processed_data_workspace_audit.DCCProcessedDataWorkspaceSharingAudit()
        audit.audit_workspace_and_group(self.workspace_data, self.other_group)
        self.assertEqual(len(audit.verified), 0)
        self.assertEqual(len(audit.needs_action), 0)
        self.assertEqual(len(audit.errors), 1)
        record = audit.errors[0]
        self.assertIsInstance(record, workspace_sharing_audit_results.StopSharing)
        self.assertEqual(record.workspace, self.workspace_data.workspace)
        self.assertEqual(record.managed_group, self.other_group)
        self.assertEqual(record.current_sharing_instance, sharing)
        self.assertEqual(
            record.note, dcc_processed_data_workspace_audit.DCCProcessedDataWorkspaceSharingAudit.OTHER_GROUP
        )

    def test_other_group_shared_as_owner(self):
        sharing = WorkspaceGroupSharingFactory.create(
            workspace=self.workspace_data.workspace, group=self.other_group, access=WorkspaceGroupSharing.OWNER
        )
        audit = dcc_processed_data_workspace_audit.DCCProcessedDataWorkspaceSharingAudit()
        audit.audit_workspace_and_group(self.workspace_data, self.other_group)
        self.assertEqual(len(audit.verified), 0)
        self.assertEqual(len(audit.needs_action), 0)
        self.assertEqual(len(audit.errors), 1)
        record = audit.errors[0]
        self.assertIsInstance(record, workspace_sharing_audit_results.StopSharing)
        self.assertEqual(record.workspace, self.workspace_data.workspace)
        self.assertEqual(record.managed_group, self.other_group)
        self.assertEqual(record.current_sharing_instance, sharing)
        self.assertEqual(
            record.note, dcc_processed_data_workspace_audit.DCCProcessedDataWorkspaceSharingAudit.OTHER_GROUP
        )


class Test(TestCase):
    def test_completed(self):
        """The completed attribute is set appropriately."""
        # Instantiate the class.
        audit = dcc_processed_data_workspace_audit.DCCProcessedDataWorkspaceAuthDomainAudit()
        self.assertFalse(audit.completed)
        audit.run_audit()
        self.assertTrue(audit.completed)

    def test_no_workspaces(self):
        """The audit works if there are no combined workspaces."""
        audit = dcc_processed_data_workspace_audit.DCCProcessedDataWorkspaceAuthDomainAudit()
        audit.run_audit()
        self.assertEqual(len(audit.get_all_results()), 0)

    def test_one_workspace_no_groups(self):
        factories.DCCProcessedDataWorkspaceFactory.create()
        audit = dcc_processed_data_workspace_audit.DCCProcessedDataWorkspaceAuthDomainAudit()
        audit.run_audit()
        self.assertEqual(len(audit.get_all_results()), 0)

    def test_one_workspace_dcc_admin_group(self):
        group = ManagedGroupFactory.create(name=settings.ANVIL_DCC_ADMINS_GROUP_NAME)
        workspace_data = factories.DCCProcessedDataWorkspaceFactory.create()
        audit = dcc_processed_data_workspace_audit.DCCProcessedDataWorkspaceAuthDomainAudit()
        audit.run_audit()
        self.assertEqual(len(audit.get_all_results()), 1)
        record = audit.get_all_results()[0]
        self.assertIsInstance(record, workspace_auth_domain_audit_results.WorkspaceAuthDomainAuditResult)
        self.assertEqual(record.workspace, workspace_data.workspace)
        self.assertEqual(record.managed_group, group)
        self.assertNotEqual(record.note, audit.OTHER_GROUP)

    @override_settings(ANVIL_DCC_ADMINS_GROUP_NAME="foo")
    def test_one_workspace_dcc_admin_group_different_name(self):
        group = ManagedGroupFactory.create(name="foo")
        workspace_data = factories.DCCProcessedDataWorkspaceFactory.create()
        audit = dcc_processed_data_workspace_audit.DCCProcessedDataWorkspaceAuthDomainAudit()
        audit.run_audit()
        self.assertEqual(len(audit.get_all_results()), 1)
        record = audit.get_all_results()[0]
        self.assertIsInstance(record, workspace_auth_domain_audit_results.WorkspaceAuthDomainAuditResult)
        self.assertEqual(record.workspace, workspace_data.workspace)
        self.assertEqual(record.managed_group, group)
        self.assertNotEqual(record.note, audit.OTHER_GROUP)

    def test_one_workspace_dcc_writer_group(self):
        group = ManagedGroupFactory.create(name="GREGOR_DCC_WRITERS")
        workspace_data = factories.DCCProcessedDataWorkspaceFactory.create()
        audit = dcc_processed_data_workspace_audit.DCCProcessedDataWorkspaceAuthDomainAudit()
        audit.run_audit()
        self.assertEqual(len(audit.get_all_results()), 1)
        record = audit.get_all_results()[0]
        self.assertIsInstance(record, workspace_auth_domain_audit_results.WorkspaceAuthDomainAuditResult)
        self.assertEqual(record.workspace, workspace_data.workspace)
        self.assertEqual(record.managed_group, group)
        self.assertNotEqual(record.note, audit.OTHER_GROUP)

    def test_one_workspace_dcc_member_group(self):
        group = ManagedGroupFactory.create(name="GREGOR_DCC_MEMBERS")
        workspace_data = factories.DCCProcessedDataWorkspaceFactory.create()
        audit = dcc_processed_data_workspace_audit.DCCProcessedDataWorkspaceAuthDomainAudit()
        audit.run_audit()
        self.assertEqual(len(audit.get_all_results()), 1)
        record = audit.get_all_results()[0]
        self.assertIsInstance(record, workspace_auth_domain_audit_results.WorkspaceAuthDomainAuditResult)
        self.assertEqual(record.workspace, workspace_data.workspace)
        self.assertEqual(record.managed_group, group)
        self.assertNotEqual(record.note, audit.OTHER_GROUP)

    def test_one_workspace_anvil_admins(self):
        workspace_data = factories.DCCProcessedDataWorkspaceFactory.create()
        WorkspaceGroupSharingFactory.create(workspace=workspace_data.workspace, group__name="anvil-admins")
        factories.DCCProcessedDataWorkspaceFactory.create()
        audit = dcc_processed_data_workspace_audit.DCCProcessedDataWorkspaceAuthDomainAudit()
        audit.run_audit()
        self.assertEqual(len(audit.get_all_results()), 0)

    def test_one_workspace_anvil_devs(self):
        workspace_data = factories.DCCProcessedDataWorkspaceFactory.create()
        WorkspaceGroupSharingFactory.create(workspace=workspace_data.workspace, group__name="anvil_devs")
        factories.DCCProcessedDataWorkspaceFactory.create()
        audit = dcc_processed_data_workspace_audit.DCCProcessedDataWorkspaceAuthDomainAudit()
        audit.run_audit()
        self.assertEqual(len(audit.get_all_results()), 0)

    def test_one_workspace_other_group_shared(self):
        group = ManagedGroupFactory.create()
        workspace_data = factories.DCCProcessedDataWorkspaceFactory.create()
        GroupGroupMembershipFactory.create(
            parent_group=workspace_data.workspace.authorization_domains.first(), child_group=group
        )
        audit = dcc_processed_data_workspace_audit.DCCProcessedDataWorkspaceAuthDomainAudit()
        audit.run_audit()
        self.assertEqual(len(audit.get_all_results()), 1)
        record = audit.get_all_results()[0]
        self.assertIsInstance(record, workspace_auth_domain_audit_results.WorkspaceAuthDomainAuditResult)
        self.assertEqual(record.workspace, workspace_data.workspace)
        self.assertEqual(record.managed_group, group)
        self.assertEqual(record.note, audit.OTHER_GROUP)

    def test_one_workspace_other_group_not_shared(self):
        ManagedGroupFactory.create()
        factories.DCCProcessedDataWorkspaceFactory.create()
        audit = dcc_processed_data_workspace_audit.DCCProcessedDataWorkspaceAuthDomainAudit()
        audit.run_audit()
        self.assertEqual(len(audit.get_all_results()), 0)

    def test_two_workspaces(self):
        """Audit works with two workspaces."""
        group = ManagedGroupFactory.create()
        workspace_data_1 = factories.DCCProcessedDataWorkspaceFactory.create()
        workspace_data_2 = factories.DCCProcessedDataWorkspaceFactory.create()
        GroupGroupMembershipFactory.create(
            parent_group=workspace_data_1.workspace.authorization_domains.first(), child_group=group
        )
        GroupGroupMembershipFactory.create(
            parent_group=workspace_data_2.workspace.authorization_domains.first(), child_group=group
        )
        audit = dcc_processed_data_workspace_audit.DCCProcessedDataWorkspaceAuthDomainAudit()
        audit.run_audit()
        results = audit.get_all_results()
        self.assertEqual(len(results), 2)
        record = [x for x in results if x.workspace == workspace_data_1.workspace][0]
        self.assertIsInstance(record, workspace_auth_domain_audit_results.WorkspaceAuthDomainAuditResult)
        self.assertEqual(record.workspace, workspace_data_1.workspace)
        self.assertEqual(record.managed_group, group)
        record = [x for x in results if x.workspace == workspace_data_2.workspace][0]
        self.assertIsInstance(record, workspace_auth_domain_audit_results.WorkspaceAuthDomainAuditResult)
        self.assertEqual(record.workspace, workspace_data_2.workspace)
        self.assertEqual(record.managed_group, group)

    def test_queryset(self):
        """Audit only runs on the specified queryset."""
        group = ManagedGroupFactory.create(name=settings.ANVIL_DCC_ADMINS_GROUP_NAME)
        workspace_data_1 = factories.DCCProcessedDataWorkspaceFactory.create()
        workspace_data_2 = factories.DCCProcessedDataWorkspaceFactory.create()
        # First workspace
        audit = dcc_processed_data_workspace_audit.DCCProcessedDataWorkspaceAuthDomainAudit(
            queryset=models.DCCProcessedDataWorkspace.objects.filter(pk=workspace_data_1.pk)
        )
        audit.run_audit()
        self.assertEqual(len(audit.get_all_results()), 1)
        record = audit.get_all_results()[0]
        self.assertIsInstance(record, workspace_auth_domain_audit_results.WorkspaceAuthDomainAuditResult)
        self.assertEqual(record.workspace, workspace_data_1.workspace)
        self.assertEqual(record.managed_group, group)
        # Second workspace
        audit = dcc_processed_data_workspace_audit.DCCProcessedDataWorkspaceAuthDomainAudit(
            queryset=models.DCCProcessedDataWorkspace.objects.filter(pk=workspace_data_2.pk)
        )
        audit.run_audit()
        self.assertEqual(len(audit.get_all_results()), 1)
        record = audit.get_all_results()[0]
        self.assertIsInstance(record, workspace_auth_domain_audit_results.WorkspaceAuthDomainAuditResult)
        self.assertEqual(record.workspace, workspace_data_2.workspace)
        self.assertEqual(record.managed_group, group)

    def test_queryset_wrong_class(self):
        """Raises ValueError if queryset is not a QuerySet."""
        with self.assertRaises(ValueError):
            dcc_processed_data_workspace_audit.DCCProcessedDataWorkspaceAuthDomainAudit(queryset="foo")
        with self.assertRaises(ValueError):
            dcc_processed_data_workspace_audit.DCCProcessedDataWorkspaceAuthDomainAudit(
                # wrong model type.
                queryset=models.UploadWorkspace.objects.all()
            )


class DCCProcessedDataWorkspaceAuthDomainAuditBeforeCombinedTest(TestCase):
    """Tests for the `UploadWorkspaceAuthDomainAudit` class for future cycle UploadWorkspaces."""

    def setUp(self):
        super().setUp()
        self.dcc_member_group = ManagedGroupFactory.create(name="GREGOR_DCC_MEMBERS")
        self.dcc_writer_group = ManagedGroupFactory.create(name="GREGOR_DCC_WRITERS")
        self.dcc_admin_group = ManagedGroupFactory.create(name=settings.ANVIL_DCC_ADMINS_GROUP_NAME)
        self.gregor_all_group = ManagedGroupFactory.create(name="GREGOR_ALL")
        self.workspace_data = factories.DCCProcessedDataWorkspaceFactory.create(upload_cycle__is_current=True)
        self.auth_domain = self.workspace_data.workspace.authorization_domains.get()
        self.other_group = ManagedGroupFactory.create()
        self.anvil_admins = ManagedGroupFactory.create(name="anvil-admins")
        self.anvil_devs = ManagedGroupFactory.create(name="anvil_devs")
        # No combined workspace.

    def test_dcc_admins_not_member(self):
        audit = dcc_processed_data_workspace_audit.DCCProcessedDataWorkspaceAuthDomainAudit()
        audit.audit_workspace_and_group(self.workspace_data, self.dcc_admin_group)
        audit.completed = True
        self.assertEqual(len(audit.verified), 0)
        self.assertEqual(len(audit.needs_action), 1)
        self.assertEqual(len(audit.errors), 0)
        record = audit.get_all_results()[0]
        self.assertIsInstance(record, workspace_auth_domain_audit_results.AddAdmin)
        self.assertEqual(record.workspace, self.workspace_data.workspace)
        self.assertEqual(record.managed_group, self.dcc_admin_group)
        self.assertIsNone(record.current_membership_instance)
        self.assertEqual(
            record.note, dcc_processed_data_workspace_audit.DCCProcessedDataWorkspaceAuthDomainAudit.DCC_ADMINS
        )

    def test_dcc_admins_member(self):
        membership = GroupGroupMembershipFactory.create(
            parent_group=self.workspace_data.workspace.authorization_domains.first(),
            child_group=self.dcc_admin_group,
            role=GroupGroupMembership.MEMBER,
        )
        audit = dcc_processed_data_workspace_audit.DCCProcessedDataWorkspaceAuthDomainAudit()
        audit.audit_workspace_and_group(self.workspace_data, self.dcc_admin_group)
        audit.completed = True
        self.assertEqual(len(audit.verified), 0)
        self.assertEqual(len(audit.needs_action), 1)
        self.assertEqual(len(audit.errors), 0)
        record = audit.get_all_results()[0]
        self.assertIsInstance(record, workspace_auth_domain_audit_results.ChangeToAdmin)
        self.assertEqual(record.workspace, self.workspace_data.workspace)
        self.assertEqual(record.managed_group, self.dcc_admin_group)
        self.assertEqual(record.current_membership_instance, membership)
        self.assertEqual(
            record.note, dcc_processed_data_workspace_audit.DCCProcessedDataWorkspaceAuthDomainAudit.DCC_ADMINS
        )

    def test_dcc_admins_admin(self):
        membership = GroupGroupMembershipFactory.create(
            parent_group=self.workspace_data.workspace.authorization_domains.first(),
            child_group=self.dcc_admin_group,
            role=GroupGroupMembership.ADMIN,
        )
        audit = dcc_processed_data_workspace_audit.DCCProcessedDataWorkspaceAuthDomainAudit()
        audit.audit_workspace_and_group(self.workspace_data, self.dcc_admin_group)
        audit.completed = True
        self.assertEqual(len(audit.verified), 1)
        self.assertEqual(len(audit.needs_action), 0)
        self.assertEqual(len(audit.errors), 0)
        record = audit.get_all_results()[0]
        self.assertIsInstance(record, workspace_auth_domain_audit_results.VerifiedAdmin)
        self.assertEqual(record.workspace, self.workspace_data.workspace)
        self.assertEqual(record.managed_group, self.dcc_admin_group)
        self.assertEqual(record.current_membership_instance, membership)
        self.assertEqual(
            record.note, dcc_processed_data_workspace_audit.DCCProcessedDataWorkspaceAuthDomainAudit.DCC_ADMINS
        )

    @override_settings(ANVIL_DCC_ADMINS_GROUP_NAME="foobar")
    def test_dcc_admins_different_setting(self):
        group = ManagedGroupFactory.create(name="foobar")
        audit = dcc_processed_data_workspace_audit.DCCProcessedDataWorkspaceAuthDomainAudit()
        audit.audit_workspace_and_group(self.workspace_data, group)
        audit.completed = True
        self.assertEqual(len(audit.verified), 0)
        self.assertEqual(len(audit.needs_action), 1)
        self.assertEqual(len(audit.errors), 0)
        record = audit.get_all_results()[0]
        self.assertIsInstance(record, workspace_auth_domain_audit_results.AddAdmin)
        self.assertEqual(record.workspace, self.workspace_data.workspace)
        self.assertEqual(record.managed_group, group)
        self.assertIsNone(record.current_membership_instance)
        self.assertEqual(
            record.note, dcc_processed_data_workspace_audit.DCCProcessedDataWorkspaceAuthDomainAudit.DCC_ADMINS
        )

    def test_dcc_writers_not_member(self):
        audit = dcc_processed_data_workspace_audit.DCCProcessedDataWorkspaceAuthDomainAudit()
        audit.audit_workspace_and_group(self.workspace_data, self.dcc_writer_group)
        audit.completed = True
        self.assertEqual(len(audit.verified), 0)
        self.assertEqual(len(audit.needs_action), 1)
        self.assertEqual(len(audit.errors), 0)
        record = audit.get_all_results()[0]
        self.assertIsInstance(record, workspace_auth_domain_audit_results.AddMember)
        self.assertEqual(record.workspace, self.workspace_data.workspace)
        self.assertEqual(record.managed_group, self.dcc_writer_group)
        self.assertIsNone(record.current_membership_instance)
        self.assertEqual(
            record.note,
            dcc_processed_data_workspace_audit.DCCProcessedDataWorkspaceAuthDomainAudit.DCC_BEFORE_COMBINED_COMPLETE,
        )

    def test_dcc_writers_member(self):
        membership = GroupGroupMembershipFactory.create(
            parent_group=self.workspace_data.workspace.authorization_domains.first(),
            child_group=self.dcc_writer_group,
            role=GroupGroupMembership.MEMBER,
        )
        audit = dcc_processed_data_workspace_audit.DCCProcessedDataWorkspaceAuthDomainAudit()
        audit.audit_workspace_and_group(self.workspace_data, self.dcc_writer_group)
        audit.completed = True
        self.assertEqual(len(audit.verified), 1)
        self.assertEqual(len(audit.needs_action), 0)
        self.assertEqual(len(audit.errors), 0)
        record = audit.get_all_results()[0]
        self.assertIsInstance(record, workspace_auth_domain_audit_results.VerifiedMember)
        self.assertEqual(record.workspace, self.workspace_data.workspace)
        self.assertEqual(record.managed_group, self.dcc_writer_group)
        self.assertEqual(record.current_membership_instance, membership)
        self.assertEqual(
            record.note,
            dcc_processed_data_workspace_audit.DCCProcessedDataWorkspaceAuthDomainAudit.DCC_BEFORE_COMBINED_COMPLETE,
        )

    def test_dcc_writers_admin(self):
        membership = GroupGroupMembershipFactory.create(
            parent_group=self.workspace_data.workspace.authorization_domains.first(),
            child_group=self.dcc_writer_group,
            role=GroupGroupMembership.ADMIN,
        )
        audit = dcc_processed_data_workspace_audit.DCCProcessedDataWorkspaceAuthDomainAudit()
        audit.audit_workspace_and_group(self.workspace_data, self.dcc_writer_group)
        audit.completed = True
        self.assertEqual(len(audit.verified), 0)
        self.assertEqual(len(audit.needs_action), 0)
        self.assertEqual(len(audit.errors), 1)
        record = audit.get_all_results()[0]
        self.assertIsInstance(record, workspace_auth_domain_audit_results.ChangeToMember)
        self.assertEqual(record.workspace, self.workspace_data.workspace)
        self.assertEqual(record.managed_group, self.dcc_writer_group)
        self.assertEqual(record.current_membership_instance, membership)
        self.assertEqual(
            record.note,
            dcc_processed_data_workspace_audit.DCCProcessedDataWorkspaceAuthDomainAudit.DCC_BEFORE_COMBINED_COMPLETE,
        )

    def test_dcc_members_not_member(self):
        audit = dcc_processed_data_workspace_audit.DCCProcessedDataWorkspaceAuthDomainAudit()
        audit.audit_workspace_and_group(self.workspace_data, self.dcc_member_group)
        audit.completed = True
        self.assertEqual(len(audit.verified), 0)
        self.assertEqual(len(audit.needs_action), 1)
        self.assertEqual(len(audit.errors), 0)
        record = audit.get_all_results()[0]
        self.assertIsInstance(record, workspace_auth_domain_audit_results.AddMember)
        self.assertEqual(record.workspace, self.workspace_data.workspace)
        self.assertEqual(record.managed_group, self.dcc_member_group)
        self.assertIsNone(record.current_membership_instance)
        self.assertEqual(
            record.note,
            dcc_processed_data_workspace_audit.DCCProcessedDataWorkspaceAuthDomainAudit.DCC_BEFORE_COMBINED_COMPLETE,
        )

    def test_dcc_members_member(self):
        membership = GroupGroupMembershipFactory.create(
            parent_group=self.workspace_data.workspace.authorization_domains.first(),
            child_group=self.dcc_member_group,
            role=GroupGroupMembership.MEMBER,
        )
        audit = dcc_processed_data_workspace_audit.DCCProcessedDataWorkspaceAuthDomainAudit()
        audit.audit_workspace_and_group(self.workspace_data, self.dcc_member_group)
        audit.completed = True
        self.assertEqual(len(audit.verified), 1)
        self.assertEqual(len(audit.needs_action), 0)
        self.assertEqual(len(audit.errors), 0)
        record = audit.get_all_results()[0]
        self.assertIsInstance(record, workspace_auth_domain_audit_results.VerifiedMember)
        self.assertEqual(record.workspace, self.workspace_data.workspace)
        self.assertEqual(record.managed_group, self.dcc_member_group)
        self.assertEqual(record.current_membership_instance, membership)
        self.assertEqual(
            record.note,
            dcc_processed_data_workspace_audit.DCCProcessedDataWorkspaceAuthDomainAudit.DCC_BEFORE_COMBINED_COMPLETE,
        )

    def test_dcc_members_admin(self):
        membership = GroupGroupMembershipFactory.create(
            parent_group=self.workspace_data.workspace.authorization_domains.first(),
            child_group=self.dcc_member_group,
            role=GroupGroupMembership.ADMIN,
        )
        audit = dcc_processed_data_workspace_audit.DCCProcessedDataWorkspaceAuthDomainAudit()
        audit.audit_workspace_and_group(self.workspace_data, self.dcc_member_group)
        audit.completed = True
        self.assertEqual(len(audit.verified), 0)
        self.assertEqual(len(audit.needs_action), 0)
        self.assertEqual(len(audit.errors), 1)
        record = audit.get_all_results()[0]
        self.assertIsInstance(record, workspace_auth_domain_audit_results.ChangeToMember)
        self.assertEqual(record.workspace, self.workspace_data.workspace)
        self.assertEqual(record.managed_group, self.dcc_member_group)
        self.assertEqual(record.current_membership_instance, membership)
        self.assertEqual(
            record.note,
            dcc_processed_data_workspace_audit.DCCProcessedDataWorkspaceAuthDomainAudit.DCC_BEFORE_COMBINED_COMPLETE,
        )

    def test_anvil_admins_not_member(self):
        audit = dcc_processed_data_workspace_audit.DCCProcessedDataWorkspaceAuthDomainAudit()
        audit.audit_workspace_and_group(self.workspace_data, self.anvil_admins)
        self.assertEqual(len(audit.verified), 0)
        self.assertEqual(len(audit.needs_action), 0)
        self.assertEqual(len(audit.errors), 0)

    def test_anvil_admins_member(self):
        GroupGroupMembershipFactory.create(
            parent_group=self.workspace_data.workspace.authorization_domains.first(),
            child_group=self.anvil_admins,
            role=GroupGroupMembership.MEMBER,
        )
        audit = dcc_processed_data_workspace_audit.DCCProcessedDataWorkspaceAuthDomainAudit()
        audit.audit_workspace_and_group(self.workspace_data, self.anvil_admins)
        self.assertEqual(len(audit.verified), 0)
        self.assertEqual(len(audit.needs_action), 0)
        self.assertEqual(len(audit.errors), 0)

    def test_anvil_admins_admin(self):
        GroupGroupMembershipFactory.create(
            parent_group=self.workspace_data.workspace.authorization_domains.first(),
            child_group=self.anvil_admins,
            role=GroupGroupMembership.ADMIN,
        )
        audit = dcc_processed_data_workspace_audit.DCCProcessedDataWorkspaceAuthDomainAudit()
        audit.audit_workspace_and_group(self.workspace_data, self.anvil_admins)
        self.assertEqual(len(audit.verified), 0)
        self.assertEqual(len(audit.needs_action), 0)
        self.assertEqual(len(audit.errors), 0)

    def test_anvil_devs_not_member(self):
        audit = dcc_processed_data_workspace_audit.DCCProcessedDataWorkspaceAuthDomainAudit()
        audit.audit_workspace_and_group(self.workspace_data, self.anvil_devs)
        self.assertEqual(len(audit.verified), 0)
        self.assertEqual(len(audit.needs_action), 0)
        self.assertEqual(len(audit.errors), 0)

    def test_anvil_devs_member(self):
        GroupGroupMembershipFactory.create(
            parent_group=self.workspace_data.workspace.authorization_domains.first(),
            child_group=self.anvil_devs,
            role=GroupGroupMembership.MEMBER,
        )
        audit = dcc_processed_data_workspace_audit.DCCProcessedDataWorkspaceAuthDomainAudit()
        audit.audit_workspace_and_group(self.workspace_data, self.anvil_devs)
        self.assertEqual(len(audit.verified), 0)
        self.assertEqual(len(audit.needs_action), 0)
        self.assertEqual(len(audit.errors), 0)

    def test_anvil_devs_admin(self):
        GroupGroupMembershipFactory.create(
            parent_group=self.workspace_data.workspace.authorization_domains.first(),
            child_group=self.anvil_devs,
            role=GroupGroupMembership.ADMIN,
        )
        audit = dcc_processed_data_workspace_audit.DCCProcessedDataWorkspaceAuthDomainAudit()
        audit.audit_workspace_and_group(self.workspace_data, self.anvil_devs)
        self.assertEqual(len(audit.verified), 0)
        self.assertEqual(len(audit.needs_action), 0)
        self.assertEqual(len(audit.errors), 0)

    def test_gregor_all(self):
        self.fail()

    def test_other_group_not_member(self):
        audit = dcc_processed_data_workspace_audit.DCCProcessedDataWorkspaceAuthDomainAudit()
        audit.audit_workspace_and_group(self.workspace_data, self.other_group)
        audit.completed = True
        self.assertEqual(len(audit.verified), 1)
        self.assertEqual(len(audit.needs_action), 0)
        self.assertEqual(len(audit.errors), 0)
        record = audit.get_all_results()[0]
        self.assertIsInstance(record, workspace_auth_domain_audit_results.VerifiedNotMember)
        self.assertEqual(record.workspace, self.workspace_data.workspace)
        self.assertEqual(record.managed_group, self.other_group)
        self.assertIsNone(record.current_membership_instance)
        self.assertEqual(
            record.note, dcc_processed_data_workspace_audit.DCCProcessedDataWorkspaceAuthDomainAudit.OTHER_GROUP
        )

    def test_other_group_member(self):
        membership = GroupGroupMembershipFactory.create(
            parent_group=self.workspace_data.workspace.authorization_domains.first(),
            child_group=self.other_group,
            role=GroupGroupMembership.MEMBER,
        )
        audit = dcc_processed_data_workspace_audit.DCCProcessedDataWorkspaceAuthDomainAudit()
        audit.audit_workspace_and_group(self.workspace_data, self.other_group)
        audit.completed = True
        self.assertEqual(len(audit.verified), 0)
        self.assertEqual(len(audit.needs_action), 0)
        self.assertEqual(len(audit.errors), 1)
        record = audit.get_all_results()[0]
        self.assertIsInstance(record, workspace_auth_domain_audit_results.Remove)
        self.assertEqual(record.workspace, self.workspace_data.workspace)
        self.assertEqual(record.managed_group, self.other_group)
        self.assertEqual(record.current_membership_instance, membership)
        self.assertEqual(
            record.note, dcc_processed_data_workspace_audit.DCCProcessedDataWorkspaceAuthDomainAudit.OTHER_GROUP
        )

    def test_other_group_admin(self):
        membership = GroupGroupMembershipFactory.create(
            parent_group=self.workspace_data.workspace.authorization_domains.first(),
            child_group=self.other_group,
            role=GroupGroupMembership.ADMIN,
        )
        audit = dcc_processed_data_workspace_audit.DCCProcessedDataWorkspaceAuthDomainAudit()
        audit.audit_workspace_and_group(self.workspace_data, self.other_group)
        audit.completed = True
        self.assertEqual(len(audit.verified), 0)
        self.assertEqual(len(audit.needs_action), 0)
        self.assertEqual(len(audit.errors), 1)
        record = audit.get_all_results()[0]
        self.assertIsInstance(record, workspace_auth_domain_audit_results.Remove)
        self.assertEqual(record.workspace, self.workspace_data.workspace)
        self.assertEqual(record.managed_group, self.other_group)
        self.assertEqual(record.current_membership_instance, membership)
        self.assertEqual(
            record.note, dcc_processed_data_workspace_audit.DCCProcessedDataWorkspaceAuthDomainAudit.OTHER_GROUP
        )


class DCCProcessedDataWorkspaceAuthDomainAuditBeforeCombinedReadyTest(TestCase):
    def setUp(self):
        super().setUp()
        self.dcc_member_group = ManagedGroupFactory.create(name="GREGOR_DCC_MEMBERS")
        self.dcc_writer_group = ManagedGroupFactory.create(name="GREGOR_DCC_WRITERS")
        self.dcc_admin_group = ManagedGroupFactory.create(name=settings.ANVIL_DCC_ADMINS_GROUP_NAME)
        self.gregor_all_group = ManagedGroupFactory.create(name="GREGOR_ALL")
        self.workspace_data = factories.DCCProcessedDataWorkspaceFactory.create(upload_cycle__is_current=True)
        self.auth_domain = self.workspace_data.workspace.authorization_domains.get()
        self.other_group = ManagedGroupFactory.create()
        self.anvil_admins = ManagedGroupFactory.create(name="anvil-admins")
        self.anvil_devs = ManagedGroupFactory.create(name="anvil_devs")
        # Combined workspace that is not ready.
        factories.CombinedConsortiumDataWorkspaceFactory(upload_cycle=self.workspace_data.upload_cycle)

    def test_dcc_admins_not_member(self):
        audit = dcc_processed_data_workspace_audit.DCCProcessedDataWorkspaceAuthDomainAudit()
        audit.audit_workspace_and_group(self.workspace_data, self.dcc_admin_group)
        audit.completed = True
        self.assertEqual(len(audit.verified), 0)
        self.assertEqual(len(audit.needs_action), 1)
        self.assertEqual(len(audit.errors), 0)
        record = audit.get_all_results()[0]
        self.assertIsInstance(record, workspace_auth_domain_audit_results.AddAdmin)
        self.assertEqual(record.workspace, self.workspace_data.workspace)
        self.assertEqual(record.managed_group, self.dcc_admin_group)
        self.assertIsNone(record.current_membership_instance)
        self.assertEqual(
            record.note, dcc_processed_data_workspace_audit.DCCProcessedDataWorkspaceAuthDomainAudit.DCC_ADMINS
        )

    def test_dcc_admins_member(self):
        membership = GroupGroupMembershipFactory.create(
            parent_group=self.workspace_data.workspace.authorization_domains.first(),
            child_group=self.dcc_admin_group,
            role=GroupGroupMembership.MEMBER,
        )
        audit = dcc_processed_data_workspace_audit.DCCProcessedDataWorkspaceAuthDomainAudit()
        audit.audit_workspace_and_group(self.workspace_data, self.dcc_admin_group)
        audit.completed = True
        self.assertEqual(len(audit.verified), 0)
        self.assertEqual(len(audit.needs_action), 1)
        self.assertEqual(len(audit.errors), 0)
        record = audit.get_all_results()[0]
        self.assertIsInstance(record, workspace_auth_domain_audit_results.ChangeToAdmin)
        self.assertEqual(record.workspace, self.workspace_data.workspace)
        self.assertEqual(record.managed_group, self.dcc_admin_group)
        self.assertEqual(record.current_membership_instance, membership)
        self.assertEqual(
            record.note, dcc_processed_data_workspace_audit.DCCProcessedDataWorkspaceAuthDomainAudit.DCC_ADMINS
        )

    def test_dcc_admins_admin(self):
        membership = GroupGroupMembershipFactory.create(
            parent_group=self.workspace_data.workspace.authorization_domains.first(),
            child_group=self.dcc_admin_group,
            role=GroupGroupMembership.ADMIN,
        )
        audit = dcc_processed_data_workspace_audit.DCCProcessedDataWorkspaceAuthDomainAudit()
        audit.audit_workspace_and_group(self.workspace_data, self.dcc_admin_group)
        audit.completed = True
        self.assertEqual(len(audit.verified), 1)
        self.assertEqual(len(audit.needs_action), 0)
        self.assertEqual(len(audit.errors), 0)
        record = audit.get_all_results()[0]
        self.assertIsInstance(record, workspace_auth_domain_audit_results.VerifiedAdmin)
        self.assertEqual(record.workspace, self.workspace_data.workspace)
        self.assertEqual(record.managed_group, self.dcc_admin_group)
        self.assertEqual(record.current_membership_instance, membership)
        self.assertEqual(
            record.note, dcc_processed_data_workspace_audit.DCCProcessedDataWorkspaceAuthDomainAudit.DCC_ADMINS
        )

    @override_settings(ANVIL_DCC_ADMINS_GROUP_NAME="foobar")
    def test_dcc_admins_different_setting(self):
        group = ManagedGroupFactory.create(name="foobar")
        audit = dcc_processed_data_workspace_audit.DCCProcessedDataWorkspaceAuthDomainAudit()
        audit.audit_workspace_and_group(self.workspace_data, group)
        audit.completed = True
        self.assertEqual(len(audit.verified), 0)
        self.assertEqual(len(audit.needs_action), 1)
        self.assertEqual(len(audit.errors), 0)
        record = audit.get_all_results()[0]
        self.assertIsInstance(record, workspace_auth_domain_audit_results.AddAdmin)
        self.assertEqual(record.workspace, self.workspace_data.workspace)
        self.assertEqual(record.managed_group, group)
        self.assertIsNone(record.current_membership_instance)
        self.assertEqual(
            record.note, dcc_processed_data_workspace_audit.DCCProcessedDataWorkspaceAuthDomainAudit.DCC_ADMINS
        )

    def test_dcc_writers_not_member(self):
        audit = dcc_processed_data_workspace_audit.DCCProcessedDataWorkspaceAuthDomainAudit()
        audit.audit_workspace_and_group(self.workspace_data, self.dcc_writer_group)
        audit.completed = True
        self.assertEqual(len(audit.verified), 0)
        self.assertEqual(len(audit.needs_action), 1)
        self.assertEqual(len(audit.errors), 0)
        record = audit.get_all_results()[0]
        self.assertIsInstance(record, workspace_auth_domain_audit_results.AddMember)
        self.assertEqual(record.workspace, self.workspace_data.workspace)
        self.assertEqual(record.managed_group, self.dcc_writer_group)
        self.assertIsNone(record.current_membership_instance)
        self.assertEqual(
            record.note,
            dcc_processed_data_workspace_audit.DCCProcessedDataWorkspaceAuthDomainAudit.DCC_BEFORE_COMBINED_COMPLETE,
        )

    def test_dcc_writers_member(self):
        membership = GroupGroupMembershipFactory.create(
            parent_group=self.workspace_data.workspace.authorization_domains.first(),
            child_group=self.dcc_writer_group,
            role=GroupGroupMembership.MEMBER,
        )
        audit = dcc_processed_data_workspace_audit.DCCProcessedDataWorkspaceAuthDomainAudit()
        audit.audit_workspace_and_group(self.workspace_data, self.dcc_writer_group)
        audit.completed = True
        self.assertEqual(len(audit.verified), 1)
        self.assertEqual(len(audit.needs_action), 0)
        self.assertEqual(len(audit.errors), 0)
        record = audit.get_all_results()[0]
        self.assertIsInstance(record, workspace_auth_domain_audit_results.VerifiedMember)
        self.assertEqual(record.workspace, self.workspace_data.workspace)
        self.assertEqual(record.managed_group, self.dcc_writer_group)
        self.assertEqual(record.current_membership_instance, membership)
        self.assertEqual(
            record.note,
            dcc_processed_data_workspace_audit.DCCProcessedDataWorkspaceAuthDomainAudit.DCC_BEFORE_COMBINED_COMPLETE,
        )

    def test_dcc_writers_admin(self):
        membership = GroupGroupMembershipFactory.create(
            parent_group=self.workspace_data.workspace.authorization_domains.first(),
            child_group=self.dcc_writer_group,
            role=GroupGroupMembership.ADMIN,
        )
        audit = dcc_processed_data_workspace_audit.DCCProcessedDataWorkspaceAuthDomainAudit()
        audit.audit_workspace_and_group(self.workspace_data, self.dcc_writer_group)
        audit.completed = True
        self.assertEqual(len(audit.verified), 0)
        self.assertEqual(len(audit.needs_action), 0)
        self.assertEqual(len(audit.errors), 1)
        record = audit.get_all_results()[0]
        self.assertIsInstance(record, workspace_auth_domain_audit_results.ChangeToMember)
        self.assertEqual(record.workspace, self.workspace_data.workspace)
        self.assertEqual(record.managed_group, self.dcc_writer_group)
        self.assertEqual(record.current_membership_instance, membership)
        self.assertEqual(
            record.note,
            dcc_processed_data_workspace_audit.DCCProcessedDataWorkspaceAuthDomainAudit.DCC_BEFORE_COMBINED_COMPLETE,
        )

    def test_dcc_members_not_member(self):
        audit = dcc_processed_data_workspace_audit.DCCProcessedDataWorkspaceAuthDomainAudit()
        audit.audit_workspace_and_group(self.workspace_data, self.dcc_member_group)
        audit.completed = True
        self.assertEqual(len(audit.verified), 0)
        self.assertEqual(len(audit.needs_action), 1)
        self.assertEqual(len(audit.errors), 0)
        record = audit.get_all_results()[0]
        self.assertIsInstance(record, workspace_auth_domain_audit_results.AddMember)
        self.assertEqual(record.workspace, self.workspace_data.workspace)
        self.assertEqual(record.managed_group, self.dcc_member_group)
        self.assertIsNone(record.current_membership_instance)
        self.assertEqual(
            record.note,
            dcc_processed_data_workspace_audit.DCCProcessedDataWorkspaceAuthDomainAudit.DCC_BEFORE_COMBINED_COMPLETE,
        )

    def test_dcc_members_member(self):
        membership = GroupGroupMembershipFactory.create(
            parent_group=self.workspace_data.workspace.authorization_domains.first(),
            child_group=self.dcc_member_group,
            role=GroupGroupMembership.MEMBER,
        )
        audit = dcc_processed_data_workspace_audit.DCCProcessedDataWorkspaceAuthDomainAudit()
        audit.audit_workspace_and_group(self.workspace_data, self.dcc_member_group)
        audit.completed = True
        self.assertEqual(len(audit.verified), 1)
        self.assertEqual(len(audit.needs_action), 0)
        self.assertEqual(len(audit.errors), 0)
        record = audit.get_all_results()[0]
        self.assertIsInstance(record, workspace_auth_domain_audit_results.VerifiedMember)
        self.assertEqual(record.workspace, self.workspace_data.workspace)
        self.assertEqual(record.managed_group, self.dcc_member_group)
        self.assertEqual(record.current_membership_instance, membership)
        self.assertEqual(
            record.note,
            dcc_processed_data_workspace_audit.DCCProcessedDataWorkspaceAuthDomainAudit.DCC_BEFORE_COMBINED_COMPLETE,
        )

    def test_dcc_members_admin(self):
        membership = GroupGroupMembershipFactory.create(
            parent_group=self.workspace_data.workspace.authorization_domains.first(),
            child_group=self.dcc_member_group,
            role=GroupGroupMembership.ADMIN,
        )
        audit = dcc_processed_data_workspace_audit.DCCProcessedDataWorkspaceAuthDomainAudit()
        audit.audit_workspace_and_group(self.workspace_data, self.dcc_member_group)
        audit.completed = True
        self.assertEqual(len(audit.verified), 0)
        self.assertEqual(len(audit.needs_action), 0)
        self.assertEqual(len(audit.errors), 1)
        record = audit.get_all_results()[0]
        self.assertIsInstance(record, workspace_auth_domain_audit_results.ChangeToMember)
        self.assertEqual(record.workspace, self.workspace_data.workspace)
        self.assertEqual(record.managed_group, self.dcc_member_group)
        self.assertEqual(record.current_membership_instance, membership)
        self.assertEqual(
            record.note,
            dcc_processed_data_workspace_audit.DCCProcessedDataWorkspaceAuthDomainAudit.DCC_BEFORE_COMBINED_COMPLETE,
        )

    def test_anvil_admins_not_member(self):
        audit = dcc_processed_data_workspace_audit.DCCProcessedDataWorkspaceAuthDomainAudit()
        audit.audit_workspace_and_group(self.workspace_data, self.anvil_admins)
        self.assertEqual(len(audit.verified), 0)
        self.assertEqual(len(audit.needs_action), 0)
        self.assertEqual(len(audit.errors), 0)

    def test_anvil_admins_member(self):
        GroupGroupMembershipFactory.create(
            parent_group=self.workspace_data.workspace.authorization_domains.first(),
            child_group=self.anvil_admins,
            role=GroupGroupMembership.MEMBER,
        )
        audit = dcc_processed_data_workspace_audit.DCCProcessedDataWorkspaceAuthDomainAudit()
        audit.audit_workspace_and_group(self.workspace_data, self.anvil_admins)
        self.assertEqual(len(audit.verified), 0)
        self.assertEqual(len(audit.needs_action), 0)
        self.assertEqual(len(audit.errors), 0)

    def test_anvil_admins_admin(self):
        GroupGroupMembershipFactory.create(
            parent_group=self.workspace_data.workspace.authorization_domains.first(),
            child_group=self.anvil_admins,
            role=GroupGroupMembership.ADMIN,
        )
        audit = dcc_processed_data_workspace_audit.DCCProcessedDataWorkspaceAuthDomainAudit()
        audit.audit_workspace_and_group(self.workspace_data, self.anvil_admins)
        self.assertEqual(len(audit.verified), 0)
        self.assertEqual(len(audit.needs_action), 0)
        self.assertEqual(len(audit.errors), 0)

    def test_anvil_devs_not_member(self):
        audit = dcc_processed_data_workspace_audit.DCCProcessedDataWorkspaceAuthDomainAudit()
        audit.audit_workspace_and_group(self.workspace_data, self.anvil_devs)
        self.assertEqual(len(audit.verified), 0)
        self.assertEqual(len(audit.needs_action), 0)
        self.assertEqual(len(audit.errors), 0)

    def test_anvil_devs_member(self):
        GroupGroupMembershipFactory.create(
            parent_group=self.workspace_data.workspace.authorization_domains.first(),
            child_group=self.anvil_devs,
            role=GroupGroupMembership.MEMBER,
        )
        audit = dcc_processed_data_workspace_audit.DCCProcessedDataWorkspaceAuthDomainAudit()
        audit.audit_workspace_and_group(self.workspace_data, self.anvil_devs)
        self.assertEqual(len(audit.verified), 0)
        self.assertEqual(len(audit.needs_action), 0)
        self.assertEqual(len(audit.errors), 0)

    def test_anvil_devs_admin(self):
        GroupGroupMembershipFactory.create(
            parent_group=self.workspace_data.workspace.authorization_domains.first(),
            child_group=self.anvil_devs,
            role=GroupGroupMembership.ADMIN,
        )
        audit = dcc_processed_data_workspace_audit.DCCProcessedDataWorkspaceAuthDomainAudit()
        audit.audit_workspace_and_group(self.workspace_data, self.anvil_devs)
        self.assertEqual(len(audit.verified), 0)
        self.assertEqual(len(audit.needs_action), 0)
        self.assertEqual(len(audit.errors), 0)

    def test_gregor_all(self):
        self.fail()

    def test_other_group_not_member(self):
        audit = dcc_processed_data_workspace_audit.DCCProcessedDataWorkspaceAuthDomainAudit()
        audit.audit_workspace_and_group(self.workspace_data, self.other_group)
        audit.completed = True
        self.assertEqual(len(audit.verified), 1)
        self.assertEqual(len(audit.needs_action), 0)
        self.assertEqual(len(audit.errors), 0)
        record = audit.get_all_results()[0]
        self.assertIsInstance(record, workspace_auth_domain_audit_results.VerifiedNotMember)
        self.assertEqual(record.workspace, self.workspace_data.workspace)
        self.assertEqual(record.managed_group, self.other_group)
        self.assertIsNone(record.current_membership_instance)
        self.assertEqual(
            record.note, dcc_processed_data_workspace_audit.DCCProcessedDataWorkspaceAuthDomainAudit.OTHER_GROUP
        )

    def test_other_group_member(self):
        membership = GroupGroupMembershipFactory.create(
            parent_group=self.workspace_data.workspace.authorization_domains.first(),
            child_group=self.other_group,
            role=GroupGroupMembership.MEMBER,
        )
        audit = dcc_processed_data_workspace_audit.DCCProcessedDataWorkspaceAuthDomainAudit()
        audit.audit_workspace_and_group(self.workspace_data, self.other_group)
        audit.completed = True
        self.assertEqual(len(audit.verified), 0)
        self.assertEqual(len(audit.needs_action), 0)
        self.assertEqual(len(audit.errors), 1)
        record = audit.get_all_results()[0]
        self.assertIsInstance(record, workspace_auth_domain_audit_results.Remove)
        self.assertEqual(record.workspace, self.workspace_data.workspace)
        self.assertEqual(record.managed_group, self.other_group)
        self.assertEqual(record.current_membership_instance, membership)
        self.assertEqual(
            record.note, dcc_processed_data_workspace_audit.DCCProcessedDataWorkspaceAuthDomainAudit.OTHER_GROUP
        )

    def test_other_group_admin(self):
        membership = GroupGroupMembershipFactory.create(
            parent_group=self.workspace_data.workspace.authorization_domains.first(),
            child_group=self.other_group,
            role=GroupGroupMembership.ADMIN,
        )
        audit = dcc_processed_data_workspace_audit.DCCProcessedDataWorkspaceAuthDomainAudit()
        audit.audit_workspace_and_group(self.workspace_data, self.other_group)
        audit.completed = True
        self.assertEqual(len(audit.verified), 0)
        self.assertEqual(len(audit.needs_action), 0)
        self.assertEqual(len(audit.errors), 1)
        record = audit.get_all_results()[0]
        self.assertIsInstance(record, workspace_auth_domain_audit_results.Remove)
        self.assertEqual(record.workspace, self.workspace_data.workspace)
        self.assertEqual(record.managed_group, self.other_group)
        self.assertEqual(record.current_membership_instance, membership)
        self.assertEqual(
            record.note, dcc_processed_data_workspace_audit.DCCProcessedDataWorkspaceAuthDomainAudit.OTHER_GROUP
        )


class DCCProcessedDataWorkspaceAuthDomainAuditAfterCombinedReadyTest(TestCase):
    def setUp(self):
        super().setUp()
        self.dcc_member_group = ManagedGroupFactory.create(name="GREGOR_DCC_MEMBERS")
        self.dcc_writer_group = ManagedGroupFactory.create(name="GREGOR_DCC_WRITERS")
        self.dcc_admin_group = ManagedGroupFactory.create(name=settings.ANVIL_DCC_ADMINS_GROUP_NAME)
        self.gregor_all_group = ManagedGroupFactory.create(name="GREGOR_ALL")
        self.workspace_data = factories.DCCProcessedDataWorkspaceFactory.create(upload_cycle__is_current=True)
        self.auth_domain = self.workspace_data.workspace.authorization_domains.get()
        self.other_group = ManagedGroupFactory.create()
        self.anvil_admins = ManagedGroupFactory.create(name="anvil-admins")
        self.anvil_devs = ManagedGroupFactory.create(name="anvil_devs")
        # Combined workspace that is not ready.
        self.combined_workspace = factories.CombinedConsortiumDataWorkspaceFactory.create(
            upload_cycle=self.workspace_data.upload_cycle,
            date_completed=fake.date_this_year(
                before_today=True,
                after_today=False,
            ),
        )

    def test_dcc_admins_not_member(self):
        audit = dcc_processed_data_workspace_audit.DCCProcessedDataWorkspaceAuthDomainAudit()
        audit.audit_workspace_and_group(self.workspace_data, self.dcc_admin_group)
        audit.completed = True
        self.assertEqual(len(audit.verified), 0)
        self.assertEqual(len(audit.needs_action), 1)
        self.assertEqual(len(audit.errors), 0)
        record = audit.get_all_results()[0]
        self.assertIsInstance(record, workspace_auth_domain_audit_results.AddAdmin)
        self.assertEqual(record.workspace, self.workspace_data.workspace)
        self.assertEqual(record.managed_group, self.dcc_admin_group)
        self.assertIsNone(record.current_membership_instance)
        self.assertEqual(
            record.note, dcc_processed_data_workspace_audit.DCCProcessedDataWorkspaceAuthDomainAudit.DCC_ADMINS
        )

    def test_dcc_admins_member(self):
        membership = GroupGroupMembershipFactory.create(
            parent_group=self.workspace_data.workspace.authorization_domains.first(),
            child_group=self.dcc_admin_group,
            role=GroupGroupMembership.MEMBER,
        )
        audit = dcc_processed_data_workspace_audit.DCCProcessedDataWorkspaceAuthDomainAudit()
        audit.audit_workspace_and_group(self.workspace_data, self.dcc_admin_group)
        audit.completed = True
        self.assertEqual(len(audit.verified), 0)
        self.assertEqual(len(audit.needs_action), 1)
        self.assertEqual(len(audit.errors), 0)
        record = audit.get_all_results()[0]
        self.assertIsInstance(record, workspace_auth_domain_audit_results.ChangeToAdmin)
        self.assertEqual(record.workspace, self.workspace_data.workspace)
        self.assertEqual(record.managed_group, self.dcc_admin_group)
        self.assertEqual(record.current_membership_instance, membership)
        self.assertEqual(
            record.note, dcc_processed_data_workspace_audit.DCCProcessedDataWorkspaceAuthDomainAudit.DCC_ADMINS
        )

    def test_dcc_admins_admin(self):
        membership = GroupGroupMembershipFactory.create(
            parent_group=self.workspace_data.workspace.authorization_domains.first(),
            child_group=self.dcc_admin_group,
            role=GroupGroupMembership.ADMIN,
        )
        audit = dcc_processed_data_workspace_audit.DCCProcessedDataWorkspaceAuthDomainAudit()
        audit.audit_workspace_and_group(self.workspace_data, self.dcc_admin_group)
        audit.completed = True
        self.assertEqual(len(audit.verified), 1)
        self.assertEqual(len(audit.needs_action), 0)
        self.assertEqual(len(audit.errors), 0)
        record = audit.get_all_results()[0]
        self.assertIsInstance(record, workspace_auth_domain_audit_results.VerifiedAdmin)
        self.assertEqual(record.workspace, self.workspace_data.workspace)
        self.assertEqual(record.managed_group, self.dcc_admin_group)
        self.assertEqual(record.current_membership_instance, membership)
        self.assertEqual(
            record.note, dcc_processed_data_workspace_audit.DCCProcessedDataWorkspaceAuthDomainAudit.DCC_ADMINS
        )

    @override_settings(ANVIL_DCC_ADMINS_GROUP_NAME="foobar")
    def test_dcc_admins_different_setting(self):
        group = ManagedGroupFactory.create(name="foobar")
        audit = dcc_processed_data_workspace_audit.DCCProcessedDataWorkspaceAuthDomainAudit()
        audit.audit_workspace_and_group(self.workspace_data, group)
        audit.completed = True
        self.assertEqual(len(audit.verified), 0)
        self.assertEqual(len(audit.needs_action), 1)
        self.assertEqual(len(audit.errors), 0)
        record = audit.get_all_results()[0]
        self.assertIsInstance(record, workspace_auth_domain_audit_results.AddAdmin)
        self.assertEqual(record.workspace, self.workspace_data.workspace)
        self.assertEqual(record.managed_group, group)
        self.assertIsNone(record.current_membership_instance)
        self.assertEqual(
            record.note, dcc_processed_data_workspace_audit.DCCProcessedDataWorkspaceAuthDomainAudit.DCC_ADMINS
        )

    def test_dcc_writers_not_member(self):
        audit = dcc_processed_data_workspace_audit.DCCProcessedDataWorkspaceAuthDomainAudit()
        audit.audit_workspace_and_group(self.workspace_data, self.dcc_writer_group)
        audit.completed = True
        self.assertEqual(len(audit.verified), 1)
        self.assertEqual(len(audit.needs_action), 0)
        self.assertEqual(len(audit.errors), 0)
        record = audit.get_all_results()[0]
        self.assertIsInstance(record, workspace_auth_domain_audit_results.VerifiedNotMember)
        self.assertEqual(record.workspace, self.workspace_data.workspace)
        self.assertEqual(record.managed_group, self.dcc_writer_group)
        self.assertIsNone(record.current_membership_instance)
        self.assertEqual(
            record.note,
            dcc_processed_data_workspace_audit.DCCProcessedDataWorkspaceAuthDomainAudit.DCC_AFTER_COMBINED_COMPLETE,
        )

    def test_dcc_writers_member(self):
        membership = GroupGroupMembershipFactory.create(
            parent_group=self.workspace_data.workspace.authorization_domains.first(),
            child_group=self.dcc_writer_group,
            role=GroupGroupMembership.MEMBER,
        )
        audit = dcc_processed_data_workspace_audit.DCCProcessedDataWorkspaceAuthDomainAudit()
        audit.audit_workspace_and_group(self.workspace_data, self.dcc_writer_group)
        audit.completed = True
        self.assertEqual(len(audit.verified), 0)
        self.assertEqual(len(audit.needs_action), 1)
        self.assertEqual(len(audit.errors), 0)
        record = audit.get_all_results()[0]
        self.assertIsInstance(record, workspace_auth_domain_audit_results.Remove)
        self.assertEqual(record.workspace, self.workspace_data.workspace)
        self.assertEqual(record.managed_group, self.dcc_writer_group)
        self.assertEqual(record.current_membership_instance, membership)
        self.assertEqual(
            record.note,
            dcc_processed_data_workspace_audit.DCCProcessedDataWorkspaceAuthDomainAudit.DCC_AFTER_COMBINED_COMPLETE,
        )

    def test_dcc_writers_admin(self):
        membership = GroupGroupMembershipFactory.create(
            parent_group=self.workspace_data.workspace.authorization_domains.first(),
            child_group=self.dcc_writer_group,
            role=GroupGroupMembership.ADMIN,
        )
        audit = dcc_processed_data_workspace_audit.DCCProcessedDataWorkspaceAuthDomainAudit()
        audit.audit_workspace_and_group(self.workspace_data, self.dcc_writer_group)
        audit.completed = True
        self.assertEqual(len(audit.verified), 0)
        self.assertEqual(len(audit.needs_action), 0)
        self.assertEqual(len(audit.errors), 1)
        record = audit.get_all_results()[0]
        self.assertIsInstance(record, workspace_auth_domain_audit_results.Remove)
        self.assertEqual(record.workspace, self.workspace_data.workspace)
        self.assertEqual(record.managed_group, self.dcc_writer_group)
        self.assertEqual(record.current_membership_instance, membership)
        self.assertEqual(
            record.note,
            dcc_processed_data_workspace_audit.DCCProcessedDataWorkspaceAuthDomainAudit.DCC_AFTER_COMBINED_COMPLETE,
        )

    def test_dcc_members_not_member(self):
        audit = dcc_processed_data_workspace_audit.DCCProcessedDataWorkspaceAuthDomainAudit()
        audit.audit_workspace_and_group(self.workspace_data, self.dcc_member_group)
        audit.completed = True
        self.assertEqual(len(audit.verified), 1)
        self.assertEqual(len(audit.needs_action), 0)
        self.assertEqual(len(audit.errors), 0)
        record = audit.get_all_results()[0]
        self.assertIsInstance(record, workspace_auth_domain_audit_results.VerifiedNotMember)
        self.assertEqual(record.workspace, self.workspace_data.workspace)
        self.assertEqual(record.managed_group, self.dcc_member_group)
        self.assertIsNone(record.current_membership_instance)
        self.assertEqual(
            record.note,
            dcc_processed_data_workspace_audit.DCCProcessedDataWorkspaceAuthDomainAudit.DCC_AFTER_COMBINED_COMPLETE,
        )

    def test_dcc_members_member(self):
        membership = GroupGroupMembershipFactory.create(
            parent_group=self.workspace_data.workspace.authorization_domains.first(),
            child_group=self.dcc_member_group,
            role=GroupGroupMembership.MEMBER,
        )
        audit = dcc_processed_data_workspace_audit.DCCProcessedDataWorkspaceAuthDomainAudit()
        audit.audit_workspace_and_group(self.workspace_data, self.dcc_member_group)
        audit.completed = True
        self.assertEqual(len(audit.verified), 0)
        self.assertEqual(len(audit.needs_action), 1)
        self.assertEqual(len(audit.errors), 0)
        record = audit.get_all_results()[0]
        self.assertIsInstance(record, workspace_auth_domain_audit_results.Remove)
        self.assertEqual(record.workspace, self.workspace_data.workspace)
        self.assertEqual(record.managed_group, self.dcc_member_group)
        self.assertEqual(record.current_membership_instance, membership)
        self.assertEqual(
            record.note,
            dcc_processed_data_workspace_audit.DCCProcessedDataWorkspaceAuthDomainAudit.DCC_AFTER_COMBINED_COMPLETE,
        )

    def test_dcc_members_admin(self):
        membership = GroupGroupMembershipFactory.create(
            parent_group=self.workspace_data.workspace.authorization_domains.first(),
            child_group=self.dcc_member_group,
            role=GroupGroupMembership.ADMIN,
        )
        audit = dcc_processed_data_workspace_audit.DCCProcessedDataWorkspaceAuthDomainAudit()
        audit.audit_workspace_and_group(self.workspace_data, self.dcc_member_group)
        audit.completed = True
        self.assertEqual(len(audit.verified), 0)
        self.assertEqual(len(audit.needs_action), 0)
        self.assertEqual(len(audit.errors), 1)
        record = audit.get_all_results()[0]
        self.assertIsInstance(record, workspace_auth_domain_audit_results.Remove)
        self.assertEqual(record.workspace, self.workspace_data.workspace)
        self.assertEqual(record.managed_group, self.dcc_member_group)
        self.assertEqual(record.current_membership_instance, membership)
        self.assertEqual(
            record.note,
            dcc_processed_data_workspace_audit.DCCProcessedDataWorkspaceAuthDomainAudit.DCC_AFTER_COMBINED_COMPLETE,
        )

    def test_anvil_admins_not_member(self):
        audit = dcc_processed_data_workspace_audit.DCCProcessedDataWorkspaceAuthDomainAudit()
        audit.audit_workspace_and_group(self.workspace_data, self.anvil_admins)
        self.assertEqual(len(audit.verified), 0)
        self.assertEqual(len(audit.needs_action), 0)
        self.assertEqual(len(audit.errors), 0)

    def test_anvil_admins_member(self):
        GroupGroupMembershipFactory.create(
            parent_group=self.workspace_data.workspace.authorization_domains.first(),
            child_group=self.anvil_admins,
            role=GroupGroupMembership.MEMBER,
        )
        audit = dcc_processed_data_workspace_audit.DCCProcessedDataWorkspaceAuthDomainAudit()
        audit.audit_workspace_and_group(self.workspace_data, self.anvil_admins)
        self.assertEqual(len(audit.verified), 0)
        self.assertEqual(len(audit.needs_action), 0)
        self.assertEqual(len(audit.errors), 0)

    def test_anvil_admins_admin(self):
        GroupGroupMembershipFactory.create(
            parent_group=self.workspace_data.workspace.authorization_domains.first(),
            child_group=self.anvil_admins,
            role=GroupGroupMembership.ADMIN,
        )
        audit = dcc_processed_data_workspace_audit.DCCProcessedDataWorkspaceAuthDomainAudit()
        audit.audit_workspace_and_group(self.workspace_data, self.anvil_admins)
        self.assertEqual(len(audit.verified), 0)
        self.assertEqual(len(audit.needs_action), 0)
        self.assertEqual(len(audit.errors), 0)

    def test_anvil_devs_not_member(self):
        audit = dcc_processed_data_workspace_audit.DCCProcessedDataWorkspaceAuthDomainAudit()
        audit.audit_workspace_and_group(self.workspace_data, self.anvil_devs)
        self.assertEqual(len(audit.verified), 0)
        self.assertEqual(len(audit.needs_action), 0)
        self.assertEqual(len(audit.errors), 0)

    def test_anvil_devs_member(self):
        GroupGroupMembershipFactory.create(
            parent_group=self.workspace_data.workspace.authorization_domains.first(),
            child_group=self.anvil_devs,
            role=GroupGroupMembership.MEMBER,
        )
        audit = dcc_processed_data_workspace_audit.DCCProcessedDataWorkspaceAuthDomainAudit()
        audit.audit_workspace_and_group(self.workspace_data, self.anvil_devs)
        self.assertEqual(len(audit.verified), 0)
        self.assertEqual(len(audit.needs_action), 0)
        self.assertEqual(len(audit.errors), 0)

    def test_anvil_devs_admin(self):
        GroupGroupMembershipFactory.create(
            parent_group=self.workspace_data.workspace.authorization_domains.first(),
            child_group=self.anvil_devs,
            role=GroupGroupMembership.ADMIN,
        )
        audit = dcc_processed_data_workspace_audit.DCCProcessedDataWorkspaceAuthDomainAudit()
        audit.audit_workspace_and_group(self.workspace_data, self.anvil_devs)
        self.assertEqual(len(audit.verified), 0)
        self.assertEqual(len(audit.needs_action), 0)
        self.assertEqual(len(audit.errors), 0)

    def test_gregor_all(self):
        self.fail()

    def test_other_group_not_member(self):
        audit = dcc_processed_data_workspace_audit.DCCProcessedDataWorkspaceAuthDomainAudit()
        audit.audit_workspace_and_group(self.workspace_data, self.other_group)
        audit.completed = True
        self.assertEqual(len(audit.verified), 1)
        self.assertEqual(len(audit.needs_action), 0)
        self.assertEqual(len(audit.errors), 0)
        record = audit.get_all_results()[0]
        self.assertIsInstance(record, workspace_auth_domain_audit_results.VerifiedNotMember)
        self.assertEqual(record.workspace, self.workspace_data.workspace)
        self.assertEqual(record.managed_group, self.other_group)
        self.assertIsNone(record.current_membership_instance)
        self.assertEqual(
            record.note, dcc_processed_data_workspace_audit.DCCProcessedDataWorkspaceAuthDomainAudit.OTHER_GROUP
        )

    def test_other_group_member(self):
        membership = GroupGroupMembershipFactory.create(
            parent_group=self.workspace_data.workspace.authorization_domains.first(),
            child_group=self.other_group,
            role=GroupGroupMembership.MEMBER,
        )
        audit = dcc_processed_data_workspace_audit.DCCProcessedDataWorkspaceAuthDomainAudit()
        audit.audit_workspace_and_group(self.workspace_data, self.other_group)
        audit.completed = True
        self.assertEqual(len(audit.verified), 0)
        self.assertEqual(len(audit.needs_action), 0)
        self.assertEqual(len(audit.errors), 1)
        record = audit.get_all_results()[0]
        self.assertIsInstance(record, workspace_auth_domain_audit_results.Remove)
        self.assertEqual(record.workspace, self.workspace_data.workspace)
        self.assertEqual(record.managed_group, self.other_group)
        self.assertEqual(record.current_membership_instance, membership)
        self.assertEqual(
            record.note, dcc_processed_data_workspace_audit.DCCProcessedDataWorkspaceAuthDomainAudit.OTHER_GROUP
        )

    def test_other_group_admin(self):
        membership = GroupGroupMembershipFactory.create(
            parent_group=self.workspace_data.workspace.authorization_domains.first(),
            child_group=self.other_group,
            role=GroupGroupMembership.ADMIN,
        )
        audit = dcc_processed_data_workspace_audit.DCCProcessedDataWorkspaceAuthDomainAudit()
        audit.audit_workspace_and_group(self.workspace_data, self.other_group)
        audit.completed = True
        self.assertEqual(len(audit.verified), 0)
        self.assertEqual(len(audit.needs_action), 0)
        self.assertEqual(len(audit.errors), 1)
        record = audit.get_all_results()[0]
        self.assertIsInstance(record, workspace_auth_domain_audit_results.Remove)
        self.assertEqual(record.workspace, self.workspace_data.workspace)
        self.assertEqual(record.managed_group, self.other_group)
        self.assertEqual(record.current_membership_instance, membership)
        self.assertEqual(
            record.note, dcc_processed_data_workspace_audit.DCCProcessedDataWorkspaceAuthDomainAudit.OTHER_GROUP
        )
