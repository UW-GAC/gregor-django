"""Tests for management commands in the `gregor_anvil` app."""

from datetime import timedelta
from io import StringIO

from anvil_consortium_manager.models import GroupGroupMembership, WorkspaceGroupSharing
from anvil_consortium_manager.tests.factories import (
    GroupGroupMembershipFactory,
    ManagedGroupFactory,
    WorkspaceGroupSharingFactory,
)
from django.conf import settings
from django.contrib.sites.models import Site
from django.core import mail
from django.core.management import call_command
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from . import factories


class RunUploadWorkspaceAuditTest(TestCase):
    """Tests for the run_upload_workspace_audit command"""

    def test_no_upload_workspaces(self):
        """Test command output."""
        out = StringIO()
        call_command("run_upload_workspace_audit", "--no-color", stdout=out)
        expected_string = "\n".join(
            [
                "Running UploadWorkspace sharing audit... ok!",
                "* Verified: 0",
                "* Needs action: 0",
                "* Errors: 0",
            ]
        )
        self.assertIn(expected_string, out.getvalue())
        expected_string = "\n".join(
            [
                "Running UploadWorkspace auth domain audit... ok!",
                "* Verified: 0",
                "* Needs action: 0",
                "* Errors: 0",
            ]
        )
        self.assertIn(expected_string, out.getvalue())
        # Zero messages have been sent by default.
        self.assertEqual(len(mail.outbox), 0)

    def test_sharing_audit_one_instance_verified(self):
        """Test command output with one verified instance."""
        # Create a workspace and matching DAR.
        workspace = factories.UploadWorkspaceFactory.create()
        WorkspaceGroupSharingFactory.create(
            workspace=workspace.workspace,
            group=workspace.workspace.authorization_domains.first(),
        )
        out = StringIO()
        call_command("run_upload_workspace_audit", "--no-color", stdout=out)
        expected_string = "\n".join(
            [
                "Running UploadWorkspace sharing audit... ok!",
                "* Verified: 1",
                "* Needs action: 0",
                "* Errors: 0",
            ]
        )
        self.assertIn(expected_string, out.getvalue())
        # Zero messages have been sent by default.
        self.assertEqual(len(mail.outbox), 0)

    def test_sharing_audit_one_instance_needs_action(self):
        """Test command output with one needs_action instance."""
        # Create a workspace and matching DAR.
        factories.UploadWorkspaceFactory.create()
        out = StringIO()
        call_command("run_upload_workspace_audit", "--no-color", stdout=out)
        expected_string = "\n".join(
            [
                "Running UploadWorkspace sharing audit... problems found.",
                "* Verified: 0",
                "* Needs action: 1",
                "* Errors: 0",
            ]
        )
        self.assertIn(expected_string, out.getvalue())
        # Zero messages have been sent by default.
        self.assertEqual(len(mail.outbox), 0)

    def test_sharing_audit_one_instance_error(self):
        """Test command output with one error instance."""
        workspace = factories.UploadWorkspaceFactory.create()
        WorkspaceGroupSharingFactory.create(
            workspace=workspace.workspace,
            group=workspace.workspace.authorization_domains.first(),
            access=WorkspaceGroupSharing.OWNER,
        )
        out = StringIO()
        call_command("run_upload_workspace_audit", "--no-color", stdout=out)
        expected_string = "\n".join(
            [
                "Running UploadWorkspace sharing audit... problems found.",
                "* Verified: 0",
                "* Needs action: 0",
                "* Errors: 1",
            ]
        )
        self.assertIn(expected_string, out.getvalue())
        # Zero messages have been sent by default.
        self.assertEqual(len(mail.outbox), 0)

    def test_sharing_audit_one_instance_verified_email(self):
        """No email is sent when there are no errors."""
        workspace = factories.UploadWorkspaceFactory.create()
        WorkspaceGroupSharingFactory.create(
            workspace=workspace.workspace,
            group=workspace.workspace.authorization_domains.first(),
        )
        out = StringIO()
        call_command("run_upload_workspace_audit", "--no-color", email="test@example.com", stdout=out)
        self.assertIn("Running UploadWorkspace sharing audit... ok!", out.getvalue())
        # Zero messages have been sent by default.
        self.assertEqual(len(mail.outbox), 0)

    def test_sharing_audit_one_instance_needs_action_email(self):
        """Email is sent for one needs_action instance."""
        factories.UploadWorkspaceFactory.create()
        out = StringIO()
        call_command("run_upload_workspace_audit", "--no-color", email="test@example.com", stdout=out)
        expected_string = "\n".join(
            [
                "Running UploadWorkspace sharing audit... problems found.",
                "* Verified: 0",
                "* Needs action: 1",
                "* Errors: 0",
            ]
        )
        self.assertIn(expected_string, out.getvalue())
        # One message has been sent by default.
        self.assertEqual(len(mail.outbox), 1)
        email = mail.outbox[0]
        self.assertEqual(email.to, ["test@example.com"])
        self.assertEqual(email.subject, "UploadWorkspaceSharingAudit - problems found")

    def test_sharing_audit_one_instance_error_email(self):
        """Test command output with one error instance."""
        # Create a workspace and matching DAR.
        workspace = factories.UploadWorkspaceFactory.create()
        WorkspaceGroupSharingFactory.create(
            workspace=workspace.workspace,
            group=workspace.workspace.authorization_domains.first(),
            access=WorkspaceGroupSharing.OWNER,
        )
        out = StringIO()
        call_command("run_upload_workspace_audit", "--no-color", email="test@example.com", stdout=out)
        expected_string = "\n".join(
            [
                "Running UploadWorkspace sharing audit... problems found.",
                "* Verified: 0",
                "* Needs action: 0",
                "* Errors: 1",
            ]
        )
        self.assertIn(expected_string, out.getvalue())
        # One message has been sent by default.
        self.assertEqual(len(mail.outbox), 1)
        email = mail.outbox[0]
        self.assertEqual(email.to, ["test@example.com"])
        self.assertEqual(email.subject, "UploadWorkspaceSharingAudit - problems found")

    def test_sharing_audit_one_instance_needs_action_link_in_output(self):
        factories.UploadWorkspaceFactory.create()
        out = StringIO()
        call_command("run_upload_workspace_audit", "--no-color", stdout=out)
        url = reverse("gregor_anvil:audit:upload_workspaces:sharing:all")
        self.assertIn(url, out.getvalue())
        # Zero messages have been sent by default.
        self.assertEqual(len(mail.outbox), 0)

    def test_sharing_audit_different_domain(self):
        """Test command output when a different domain is specified."""
        site = Site.objects.create(domain="foobar.com", name="test")
        site.save()
        with self.settings(SITE_ID=site.id):
            factories.UploadWorkspaceFactory.create()
            out = StringIO()
            call_command("run_upload_workspace_audit", "--no-color", stdout=out)
            self.assertIn("Running UploadWorkspace sharing audit... problems found.", out.getvalue())
            self.assertIn("https://foobar.com", out.getvalue())

    def test_auth_domain_audit_one_instance_verified(self):
        """Test command output with one verified instance."""
        upload_workspace = factories.UploadWorkspaceFactory.create()
        GroupGroupMembershipFactory.create(
            parent_group=upload_workspace.workspace.authorization_domains.first(),
            child_group__name=settings.ANVIL_DCC_ADMINS_GROUP_NAME,
            role=GroupGroupMembership.ADMIN,
        )
        out = StringIO()
        call_command("run_upload_workspace_audit", "--no-color", stdout=out)
        expected_string = "\n".join(
            [
                "Running UploadWorkspace auth domain audit... ok!",
                "* Verified: 1",
                "* Needs action: 0",
                "* Errors: 0",
            ]
        )
        self.assertIn(expected_string, out.getvalue())
        # Zero messages have been sent by default.
        self.assertEqual(len(mail.outbox), 0)

    def test_auth_domain_audit_one_instance_needs_action(self):
        """Test command output with one needs_action instance."""
        factories.UploadWorkspaceFactory.create()
        ManagedGroupFactory.create(name=settings.ANVIL_DCC_ADMINS_GROUP_NAME)
        out = StringIO()
        call_command("run_upload_workspace_audit", "--no-color", stdout=out)
        expected_string = "\n".join(
            [
                "Running UploadWorkspace auth domain audit... problems found.",
                "* Verified: 0",
                "* Needs action: 1",
                "* Errors: 0",
            ]
        )
        self.assertIn(expected_string, out.getvalue())
        # Zero messages have been sent by default.
        self.assertEqual(len(mail.outbox), 0)

    def test_auth_domain_audit_one_instance_error(self):
        """Test command output with one error instance."""
        upload_workspace = factories.UploadWorkspaceFactory.create()
        # Share with the auth domain to prevent an error in the sharing audit.
        WorkspaceGroupSharingFactory.create(
            workspace=upload_workspace.workspace,
            group=upload_workspace.workspace.authorization_domains.first(),
        )
        GroupGroupMembershipFactory.create(
            parent_group=upload_workspace.workspace.authorization_domains.first(),
            role=GroupGroupMembership.ADMIN,
        )
        out = StringIO()
        call_command("run_upload_workspace_audit", "--no-color", stdout=out)
        expected_string = "\n".join(
            [
                "Running UploadWorkspace auth domain audit... problems found.",
                "* Verified: 0",
                "* Needs action: 0",
                "* Errors: 1",
            ]
        )
        self.assertIn(expected_string, out.getvalue())
        # Zero messages have been sent by default.
        self.assertEqual(len(mail.outbox), 0)

    def test_auth_domain_audit_one_instance_verified_email(self):
        """No email is sent when there are no errors."""
        upload_workspace = factories.UploadWorkspaceFactory.create()
        dcc_admins_group = ManagedGroupFactory.create(name=settings.ANVIL_DCC_ADMINS_GROUP_NAME)
        # Share with the auth domain to prevent a problem in the sharing audit.
        WorkspaceGroupSharingFactory.create(
            workspace=upload_workspace.workspace,
            group=upload_workspace.workspace.authorization_domains.first(),
            access=WorkspaceGroupSharing.READER,
        )
        # Share with the DCC admin group to prevent a problem in the sharing audit.
        WorkspaceGroupSharingFactory.create(
            workspace=upload_workspace.workspace,
            group=dcc_admins_group,
            access=WorkspaceGroupSharing.OWNER,
        )
        GroupGroupMembershipFactory.create(
            parent_group=upload_workspace.workspace.authorization_domains.first(),
            child_group=dcc_admins_group,
            role=GroupGroupMembership.ADMIN,
        )
        out = StringIO()
        call_command("run_upload_workspace_audit", "--no-color", email="test@example.com", stdout=out)
        self.assertIn("Running UploadWorkspace auth domain audit... ok!", out.getvalue())
        # Zero messages have been sent by default.
        self.assertEqual(len(mail.outbox), 0)

    def test_auth_domain_audit_one_instance_needs_action_email(self):
        """Email is sent for one needs_action instance."""
        # Create a workspace and matching DAR.
        upload_workspace = factories.UploadWorkspaceFactory.create()
        dcc_admins_group = ManagedGroupFactory.create(name=settings.ANVIL_DCC_ADMINS_GROUP_NAME)
        # Share with the auth domain to prevent a problem in the sharing audit.
        WorkspaceGroupSharingFactory.create(
            workspace=upload_workspace.workspace,
            group=upload_workspace.workspace.authorization_domains.first(),
            access=WorkspaceGroupSharing.READER,
        )
        # Share with the DCC admin group to prevent a problem in the sharing audit.
        WorkspaceGroupSharingFactory.create(
            workspace=upload_workspace.workspace,
            group=dcc_admins_group,
            access=WorkspaceGroupSharing.OWNER,
        )
        out = StringIO()
        call_command("run_upload_workspace_audit", "--no-color", email="test@example.com", stdout=out)
        # One message has been sent by default.
        self.assertEqual(len(mail.outbox), 1)
        email = mail.outbox[0]
        self.assertEqual(email.to, ["test@example.com"])
        self.assertEqual(email.subject, "UploadWorkspaceAuthDomainAudit - problems found")

    def test_auth_domain_audit_one_instance_error_email(self):
        """Test command output with one error instance."""
        upload_workspace = factories.UploadWorkspaceFactory.create()
        # Share with the auth domain to prevent a problem in the sharing audit.
        WorkspaceGroupSharingFactory.create(
            workspace=upload_workspace.workspace,
            group=upload_workspace.workspace.authorization_domains.first(),
            access=WorkspaceGroupSharing.READER,
        )
        GroupGroupMembershipFactory.create(
            parent_group=upload_workspace.workspace.authorization_domains.first(),
            role=GroupGroupMembership.ADMIN,
        )
        out = StringIO()
        call_command("run_upload_workspace_audit", "--no-color", email="test@example.com", stdout=out)
        expected_string = "\n".join(
            [
                "Running UploadWorkspace auth domain audit... problems found.",
                "* Verified: 0",
                "* Needs action: 0",
                "* Errors: 1",
            ]
        )
        self.assertIn(expected_string, out.getvalue())
        # One message has been sent by default.
        self.assertEqual(len(mail.outbox), 1)
        email = mail.outbox[0]
        self.assertEqual(email.to, ["test@example.com"])
        self.assertEqual(email.subject, "UploadWorkspaceAuthDomainAudit - problems found")

    def test_auth_domain_audit_different_domain(self):
        """Test command output when a different domain is specified."""
        site = Site.objects.create(domain="foobar.com", name="test")
        site.save()
        with self.settings(SITE_ID=site.id):
            factories.UploadWorkspaceFactory.create()
            ManagedGroupFactory.create(name=settings.ANVIL_DCC_ADMINS_GROUP_NAME)
            out = StringIO()
            call_command("run_upload_workspace_audit", "--no-color", stdout=out)
            self.assertIn("Running UploadWorkspace auth domain audit... problems found.", out.getvalue())
            self.assertIn("https://foobar.com", out.getvalue())

    def test_auth_domain_audit_one_instance_needs_action_link_in_output(self):
        upload_workspace = factories.UploadWorkspaceFactory.create()
        # Share with the auth domain to prevent an error in the sharing audit.
        WorkspaceGroupSharingFactory.create(
            workspace=upload_workspace.workspace,
            group=upload_workspace.workspace.authorization_domains.first(),
        )
        GroupGroupMembershipFactory.create(
            parent_group=upload_workspace.workspace.authorization_domains.first(),
            role=GroupGroupMembership.ADMIN,
        )
        out = StringIO()
        call_command("run_upload_workspace_audit", "--no-color", stdout=out)
        url = reverse("gregor_anvil:audit:upload_workspaces:auth_domains:all")
        self.assertIn(url, out.getvalue())
        # Zero messages have been sent by default.
        self.assertEqual(len(mail.outbox), 0)


class RunCombinedWorkspaceAuditTestCase(TestCase):
    def test_no_workspaces(self):
        """Test command output."""
        out = StringIO()
        call_command("run_combined_workspace_audit", "--no-color", stdout=out)
        expected_string = "\n".join(
            [
                "Running CombinedConsortiumDataWorkspace sharing audit... ok!",
                "* Verified: 0",
                "* Needs action: 0",
                "* Errors: 0",
            ]
        )
        self.assertIn(expected_string, out.getvalue())
        expected_string = "\n".join(
            [
                "Running CombinedConsortiumDataWorkspace auth domain audit... ok!",
                "* Verified: 0",
                "* Needs action: 0",
                "* Errors: 0",
            ]
        )
        self.assertIn(expected_string, out.getvalue())
        # Zero messages have been sent by default.
        self.assertEqual(len(mail.outbox), 0)

    def test_sharing_audit_one_instance_verified(self):
        """Test command output with one verified instance."""
        factories.CombinedConsortiumDataWorkspaceFactory.create()
        # Verified not shared with auth domain.
        out = StringIO()
        call_command("run_combined_workspace_audit", "--no-color", stdout=out)
        expected_string = "\n".join(
            [
                "Running CombinedConsortiumDataWorkspace sharing audit... ok!",
                "* Verified: 1",
                "* Needs action: 0",
                "* Errors: 0",
            ]
        )
        self.assertIn(expected_string, out.getvalue())
        # Zero messages have been sent by default.
        self.assertEqual(len(mail.outbox), 0)

    def test_sharing_audit_one_instance_needs_action(self):
        """Test command output with one needs_action instance."""
        # Create a workspace and matching DAR.
        factories.CombinedConsortiumDataWorkspaceFactory.create(date_completed=timezone.now() - timedelta(days=1))
        out = StringIO()
        call_command("run_combined_workspace_audit", "--no-color", stdout=out)
        expected_string = "\n".join(
            [
                "Running CombinedConsortiumDataWorkspace sharing audit... problems found.",
                "* Verified: 0",
                "* Needs action: 1",
                "* Errors: 0",
            ]
        )
        self.assertIn(expected_string, out.getvalue())
        # Zero messages have been sent by default.
        self.assertEqual(len(mail.outbox), 0)

    def test_sharing_audit_one_instance_error(self):
        """Test command output with one error instance."""
        workspace = factories.CombinedConsortiumDataWorkspaceFactory.create()
        WorkspaceGroupSharingFactory.create(
            workspace=workspace.workspace,
            group=workspace.workspace.authorization_domains.first(),
            access=WorkspaceGroupSharing.OWNER,
        )
        out = StringIO()
        call_command("run_combined_workspace_audit", "--no-color", stdout=out)
        expected_string = "\n".join(
            [
                "Running CombinedConsortiumDataWorkspace sharing audit... problems found.",
                "* Verified: 0",
                "* Needs action: 0",
                "* Errors: 1",
            ]
        )
        self.assertIn(expected_string, out.getvalue())
        # Zero messages have been sent by default.
        self.assertEqual(len(mail.outbox), 0)

    def test_sharing_audit_one_instance_verified_email(self):
        """No email is sent when there are no errors."""
        factories.CombinedConsortiumDataWorkspaceFactory.create()
        # Verified not shared with auth domain.
        out = StringIO()
        call_command("run_combined_workspace_audit", "--no-color", email="test@example.com", stdout=out)
        self.assertIn("Running CombinedConsortiumDataWorkspace sharing audit... ok!", out.getvalue())
        # Zero messages have been sent by default.
        self.assertEqual(len(mail.outbox), 0)

    def test_sharing_audit_one_instance_needs_action_email(self):
        """Email is sent for one needs_action instance."""
        # Create a workspace and matching DAR.
        factories.CombinedConsortiumDataWorkspaceFactory.create(date_completed=timezone.now() - timedelta(days=1))
        out = StringIO()
        call_command("run_combined_workspace_audit", "--no-color", email="test@example.com", stdout=out)
        expected_string = "\n".join(
            [
                "Running CombinedConsortiumDataWorkspace sharing audit... problems found.",
                "* Verified: 0",
                "* Needs action: 1",
                "* Errors: 0",
            ]
        )
        self.assertIn(expected_string, out.getvalue())
        # One message has been sent by default.
        self.assertEqual(len(mail.outbox), 1)
        email = mail.outbox[0]
        self.assertEqual(email.to, ["test@example.com"])
        self.assertEqual(email.subject, "CombinedConsortiumDataWorkspaceSharingAudit - problems found")

    def test_sharing_audit_one_instance_error_email(self):
        """Test command output with one error instance."""
        # Create a workspace and matching DAR.
        workspace = factories.CombinedConsortiumDataWorkspaceFactory.create()
        WorkspaceGroupSharingFactory.create(
            workspace=workspace.workspace,
            group=workspace.workspace.authorization_domains.first(),
            access=WorkspaceGroupSharing.OWNER,
        )
        out = StringIO()
        call_command("run_combined_workspace_audit", "--no-color", email="test@example.com", stdout=out)
        expected_string = "\n".join(
            [
                "Running CombinedConsortiumDataWorkspace sharing audit... problems found.",
                "* Verified: 0",
                "* Needs action: 0",
                "* Errors: 1",
            ]
        )
        self.assertIn(expected_string, out.getvalue())
        # One message has been sent by default.
        self.assertEqual(len(mail.outbox), 1)
        email = mail.outbox[0]
        self.assertEqual(email.to, ["test@example.com"])
        self.assertEqual(email.subject, "CombinedConsortiumDataWorkspaceSharingAudit - problems found")

    def test_sharing_audit_one_instance_needs_action_link_in_output(self):
        factories.CombinedConsortiumDataWorkspaceFactory.create(date_completed=timezone.now() - timedelta(days=1))
        out = StringIO()
        call_command("run_combined_workspace_audit", "--no-color", stdout=out)
        url = reverse("gregor_anvil:audit:combined_workspaces:sharing:all")
        self.assertIn(url, out.getvalue())
        # Zero messages have been sent by default.
        self.assertEqual(len(mail.outbox), 0)

    def test_sharing_audit_different_domain(self):
        """Test command output when a different domain is specified."""
        site = Site.objects.create(domain="foobar.com", name="test")
        site.save()
        with self.settings(SITE_ID=site.id):
            factories.CombinedConsortiumDataWorkspaceFactory.create(date_completed=timezone.now() - timedelta(days=1))
            out = StringIO()
            call_command("run_combined_workspace_audit", "--no-color", stdout=out)
            self.assertIn("Running CombinedConsortiumDataWorkspace sharing audit... problems found.", out.getvalue())
            self.assertIn("https://foobar.com", out.getvalue())

    def test_auth_domain_audit_one_instance_verified(self):
        """Test command output with one verified instance."""
        workspace = factories.CombinedConsortiumDataWorkspaceFactory.create()
        GroupGroupMembershipFactory.create(
            parent_group=workspace.workspace.authorization_domains.first(),
            child_group__name=settings.ANVIL_DCC_ADMINS_GROUP_NAME,
            role=GroupGroupMembership.ADMIN,
        )
        out = StringIO()
        call_command("run_combined_workspace_audit", "--no-color", stdout=out)
        expected_string = "\n".join(
            [
                "Running CombinedConsortiumDataWorkspace auth domain audit... ok!",
                "* Verified: 1",
                "* Needs action: 0",
                "* Errors: 0",
            ]
        )
        self.assertIn(expected_string, out.getvalue())
        # Zero messages have been sent by default.
        self.assertEqual(len(mail.outbox), 0)

    def test_auth_domain_audit_one_instance_needs_action(self):
        """Test command output with one needs_action instance."""
        factories.CombinedConsortiumDataWorkspaceFactory.create()
        ManagedGroupFactory.create(name=settings.ANVIL_DCC_ADMINS_GROUP_NAME)
        out = StringIO()
        call_command("run_combined_workspace_audit", "--no-color", stdout=out)
        expected_string = "\n".join(
            [
                "Running CombinedConsortiumDataWorkspace auth domain audit... problems found.",
                "* Verified: 0",
                "* Needs action: 1",
                "* Errors: 0",
            ]
        )
        self.assertIn(expected_string, out.getvalue())
        # Zero messages have been sent by default.
        self.assertEqual(len(mail.outbox), 0)

    def test_auth_domain_audit_one_instance_error(self):
        """Test command output with one error instance."""
        workspace = factories.CombinedConsortiumDataWorkspaceFactory.create()
        GroupGroupMembershipFactory.create(
            parent_group=workspace.workspace.authorization_domains.first(),
            role=GroupGroupMembership.ADMIN,
        )
        out = StringIO()
        call_command("run_combined_workspace_audit", "--no-color", stdout=out)
        expected_string = "\n".join(
            [
                "Running CombinedConsortiumDataWorkspace auth domain audit... problems found.",
                "* Verified: 0",
                "* Needs action: 0",
                "* Errors: 1",
            ]
        )
        self.assertIn(expected_string, out.getvalue())
        # Zero messages have been sent by default.
        self.assertEqual(len(mail.outbox), 0)

    def test_auth_domain_audit_one_instance_verified_email(self):
        """No email is sent when there are no errors."""
        workspace = factories.CombinedConsortiumDataWorkspaceFactory.create()
        GroupGroupMembershipFactory.create(
            parent_group=workspace.workspace.authorization_domains.first(),
            child_group__name="GREGOR_ALL",
            role=GroupGroupMembership.MEMBER,
        )
        out = StringIO()
        call_command("run_combined_workspace_audit", "--no-color", email="test@example.com", stdout=out)
        self.assertIn("Running CombinedConsortiumDataWorkspace auth domain audit... ok!", out.getvalue())
        # Zero messages have been sent by default.
        self.assertEqual(len(mail.outbox), 0)

    def test_auth_domain_audit_one_instance_needs_action_email(self):
        """Email is sent for one needs_action instance."""
        # Create a workspace and matching DAR.
        factories.CombinedConsortiumDataWorkspaceFactory.create()
        factories.ManagedGroupFactory.create(name="GREGOR_ALL")
        out = StringIO()
        call_command("run_combined_workspace_audit", "--no-color", email="test@example.com", stdout=out)
        # One message has been sent by default.
        self.assertEqual(len(mail.outbox), 1)
        email = mail.outbox[0]
        self.assertEqual(email.to, ["test@example.com"])
        self.assertEqual(email.subject, "CombinedConsortiumDataWorkspaceAuthDomainAudit - problems found")

    def test_auth_domain_audit_one_instance_error_email(self):
        """Test command output with one error instance."""
        workspace = factories.CombinedConsortiumDataWorkspaceFactory.create()
        GroupGroupMembershipFactory.create(
            parent_group=workspace.workspace.authorization_domains.first(),
            role=GroupGroupMembership.ADMIN,
        )
        out = StringIO()
        call_command("run_combined_workspace_audit", "--no-color", email="test@example.com", stdout=out)
        expected_string = "\n".join(
            [
                "Running CombinedConsortiumDataWorkspace auth domain audit... problems found.",
                "* Verified: 0",
                "* Needs action: 0",
                "* Errors: 1",
            ]
        )
        self.assertIn(expected_string, out.getvalue())
        # One message has been sent by default.
        self.assertEqual(len(mail.outbox), 1)
        email = mail.outbox[0]
        self.assertEqual(email.to, ["test@example.com"])
        self.assertEqual(email.subject, "CombinedConsortiumDataWorkspaceAuthDomainAudit - problems found")

    def test_auth_domain_audit_different_domain(self):
        """Test command output when a different domain is specified."""
        site = Site.objects.create(domain="foobar.com", name="test")
        site.save()
        with self.settings(SITE_ID=site.id):
            factories.CombinedConsortiumDataWorkspaceFactory.create()
            ManagedGroupFactory.create(name=settings.ANVIL_DCC_ADMINS_GROUP_NAME)
            out = StringIO()
            call_command("run_combined_workspace_audit", "--no-color", stdout=out)
            self.assertIn(
                "Running CombinedConsortiumDataWorkspace auth domain audit... problems found.", out.getvalue()
            )
            self.assertIn("https://foobar.com", out.getvalue())

    def test_auth_domain_audit_one_instance_needs_action_link_in_output(self):
        factories.CombinedConsortiumDataWorkspaceFactory.create()
        ManagedGroupFactory.create(name="GREGOR_ALL")
        out = StringIO()
        call_command("run_combined_workspace_audit", "--no-color", stdout=out)
        url = reverse("gregor_anvil:audit:combined_workspaces:auth_domains:all")
        self.assertIn(url, out.getvalue())
        # Zero messages have been sent by default.
        self.assertEqual(len(mail.outbox), 0)


class RunDCCProcessedDataWorkspaceAuditTest(TestCase):
    """Tests for the run_dcc_processed_data_workspace_audit command"""

    def test_no_dcc_processed_data_workspaces(self):
        """Test command output."""
        out = StringIO()
        call_command("run_dcc_processed_data_workspace_audit", "--no-color", stdout=out)
        expected_string = "\n".join(
            [
                "Running DCCProcessedDataWorkspace sharing audit... ok!",
                "* Verified: 0",
                "* Needs action: 0",
                "* Errors: 0",
            ]
        )
        self.assertIn(expected_string, out.getvalue())
        expected_string = "\n".join(
            [
                "Running DCCProcessedDataWorkspace auth domain audit... ok!",
                "* Verified: 0",
                "* Needs action: 0",
                "* Errors: 0",
            ]
        )
        self.assertIn(expected_string, out.getvalue())
        # Zero messages have been sent by default.
        self.assertEqual(len(mail.outbox), 0)

    def test_sharing_audit_one_instance_verified(self):
        """Test command output with one verified instance."""
        # Create a workspace and matching DAR.
        workspace = factories.DCCProcessedDataWorkspaceFactory.create()
        WorkspaceGroupSharingFactory.create(
            workspace=workspace.workspace,
            group=workspace.workspace.authorization_domains.first(),
        )
        out = StringIO()
        call_command("run_dcc_processed_data_workspace_audit", "--no-color", stdout=out)
        expected_string = "\n".join(
            [
                "Running DCCProcessedDataWorkspace sharing audit... ok!",
                "* Verified: 1",
                "* Needs action: 0",
                "* Errors: 0",
            ]
        )
        self.assertIn(expected_string, out.getvalue())
        # Zero messages have been sent by default.
        self.assertEqual(len(mail.outbox), 0)

    def test_sharing_audit_one_instance_needs_action(self):
        """Test command output with one needs_action instance."""
        # Create a workspace and matching DAR.
        factories.DCCProcessedDataWorkspaceFactory.create()
        out = StringIO()
        call_command("run_dcc_processed_data_workspace_audit", "--no-color", stdout=out)
        expected_string = "\n".join(
            [
                "Running DCCProcessedDataWorkspace sharing audit... problems found.",
                "* Verified: 0",
                "* Needs action: 1",
                "* Errors: 0",
            ]
        )
        self.assertIn(expected_string, out.getvalue())
        # Zero messages have been sent by default.
        self.assertEqual(len(mail.outbox), 0)

    def test_sharing_audit_one_instance_error(self):
        """Test command output with one error instance."""
        workspace = factories.DCCProcessedDataWorkspaceFactory.create()
        WorkspaceGroupSharingFactory.create(
            workspace=workspace.workspace,
            group=workspace.workspace.authorization_domains.first(),
            access=WorkspaceGroupSharing.OWNER,
        )
        out = StringIO()
        call_command("run_dcc_processed_data_workspace_audit", "--no-color", stdout=out)
        expected_string = "\n".join(
            [
                "Running DCCProcessedDataWorkspace sharing audit... problems found.",
                "* Verified: 0",
                "* Needs action: 0",
                "* Errors: 1",
            ]
        )
        self.assertIn(expected_string, out.getvalue())
        # Zero messages have been sent by default.
        self.assertEqual(len(mail.outbox), 0)

    def test_sharing_audit_one_instance_verified_email(self):
        """No email is sent when there are no errors."""
        workspace = factories.DCCProcessedDataWorkspaceFactory.create()
        WorkspaceGroupSharingFactory.create(
            workspace=workspace.workspace,
            group=workspace.workspace.authorization_domains.first(),
        )
        out = StringIO()
        call_command("run_dcc_processed_data_workspace_audit", "--no-color", email="test@example.com", stdout=out)
        self.assertIn("Running DCCProcessedDataWorkspace sharing audit... ok!", out.getvalue())
        # Zero messages have been sent by default.
        self.assertEqual(len(mail.outbox), 0)

    def test_sharing_audit_one_instance_needs_action_email(self):
        """Email is sent for one needs_action instance."""
        factories.DCCProcessedDataWorkspaceFactory.create()
        out = StringIO()
        call_command("run_dcc_processed_data_workspace_audit", "--no-color", email="test@example.com", stdout=out)
        expected_string = "\n".join(
            [
                "Running DCCProcessedDataWorkspace sharing audit... problems found.",
                "* Verified: 0",
                "* Needs action: 1",
                "* Errors: 0",
            ]
        )
        self.assertIn(expected_string, out.getvalue())
        # One message has been sent by default.
        self.assertEqual(len(mail.outbox), 1)
        email = mail.outbox[0]
        self.assertEqual(email.to, ["test@example.com"])
        self.assertEqual(email.subject, "DCCProcessedDataWorkspaceSharingAudit - problems found")

    def test_sharing_audit_one_instance_error_email(self):
        """Test command output with one error instance."""
        # Create a workspace and matching DAR.
        workspace = factories.DCCProcessedDataWorkspaceFactory.create()
        WorkspaceGroupSharingFactory.create(
            workspace=workspace.workspace,
            group=workspace.workspace.authorization_domains.first(),
            access=WorkspaceGroupSharing.OWNER,
        )
        out = StringIO()
        call_command("run_dcc_processed_data_workspace_audit", "--no-color", email="test@example.com", stdout=out)
        expected_string = "\n".join(
            [
                "Running DCCProcessedDataWorkspace sharing audit... problems found.",
                "* Verified: 0",
                "* Needs action: 0",
                "* Errors: 1",
            ]
        )
        self.assertIn(expected_string, out.getvalue())
        # One message has been sent by default.
        self.assertEqual(len(mail.outbox), 1)
        email = mail.outbox[0]
        self.assertEqual(email.to, ["test@example.com"])
        self.assertEqual(email.subject, "DCCProcessedDataWorkspaceSharingAudit - problems found")

    def test_sharing_audit_one_instance_needs_action_link_in_output(self):
        factories.DCCProcessedDataWorkspaceFactory.create()
        out = StringIO()
        call_command("run_dcc_processed_data_workspace_audit", "--no-color", stdout=out)
        url = reverse("gregor_anvil:audit:dcc_processed_data_workspaces:sharing:all")
        self.assertIn(url, out.getvalue())
        # Zero messages have been sent by default.
        self.assertEqual(len(mail.outbox), 0)

    def test_sharing_audit_different_domain(self):
        """Test command output when a different domain is specified."""
        site = Site.objects.create(domain="foobar.com", name="test")
        site.save()
        with self.settings(SITE_ID=site.id):
            factories.DCCProcessedDataWorkspaceFactory.create()
            out = StringIO()
            call_command("run_dcc_processed_data_workspace_audit", "--no-color", stdout=out)
            self.assertIn("Running DCCProcessedDataWorkspace sharing audit... problems found.", out.getvalue())
            self.assertIn("https://foobar.com", out.getvalue())

    def test_auth_domain_audit_one_instance_verified(self):
        """Test command output with one verified instance."""
        dcc_processed_data_workspace = factories.DCCProcessedDataWorkspaceFactory.create()
        GroupGroupMembershipFactory.create(
            parent_group=dcc_processed_data_workspace.workspace.authorization_domains.first(),
            child_group__name=settings.ANVIL_DCC_ADMINS_GROUP_NAME,
            role=GroupGroupMembership.ADMIN,
        )
        out = StringIO()
        call_command("run_dcc_processed_data_workspace_audit", "--no-color", stdout=out)
        expected_string = "\n".join(
            [
                "Running DCCProcessedDataWorkspace auth domain audit... ok!",
                "* Verified: 1",
                "* Needs action: 0",
                "* Errors: 0",
            ]
        )
        self.assertIn(expected_string, out.getvalue())
        # Zero messages have been sent by default.
        self.assertEqual(len(mail.outbox), 0)

    def test_auth_domain_audit_one_instance_needs_action(self):
        """Test command output with one needs_action instance."""
        factories.DCCProcessedDataWorkspaceFactory.create()
        ManagedGroupFactory.create(name=settings.ANVIL_DCC_ADMINS_GROUP_NAME)
        out = StringIO()
        call_command("run_dcc_processed_data_workspace_audit", "--no-color", stdout=out)
        expected_string = "\n".join(
            [
                "Running DCCProcessedDataWorkspace auth domain audit... problems found.",
                "* Verified: 0",
                "* Needs action: 1",
                "* Errors: 0",
            ]
        )
        self.assertIn(expected_string, out.getvalue())
        # Zero messages have been sent by default.
        self.assertEqual(len(mail.outbox), 0)

    def test_auth_domain_audit_one_instance_error(self):
        """Test command output with one error instance."""
        dcc_processed_data_workspace = factories.DCCProcessedDataWorkspaceFactory.create()
        # Share with the auth domain to prevent an error in the sharing audit.
        WorkspaceGroupSharingFactory.create(
            workspace=dcc_processed_data_workspace.workspace,
            group=dcc_processed_data_workspace.workspace.authorization_domains.first(),
        )
        GroupGroupMembershipFactory.create(
            parent_group=dcc_processed_data_workspace.workspace.authorization_domains.first(),
            role=GroupGroupMembership.ADMIN,
        )
        out = StringIO()
        call_command("run_dcc_processed_data_workspace_audit", "--no-color", stdout=out)
        expected_string = "\n".join(
            [
                "Running DCCProcessedDataWorkspace auth domain audit... problems found.",
                "* Verified: 0",
                "* Needs action: 0",
                "* Errors: 1",
            ]
        )
        self.assertIn(expected_string, out.getvalue())
        # Zero messages have been sent by default.
        self.assertEqual(len(mail.outbox), 0)

    def test_auth_domain_audit_one_instance_verified_email(self):
        """No email is sent when there are no errors."""
        dcc_processed_data_workspace = factories.DCCProcessedDataWorkspaceFactory.create()
        dcc_admins_group = ManagedGroupFactory.create(name=settings.ANVIL_DCC_ADMINS_GROUP_NAME)
        # Share with the auth domain to prevent a problem in the sharing audit.
        WorkspaceGroupSharingFactory.create(
            workspace=dcc_processed_data_workspace.workspace,
            group=dcc_processed_data_workspace.workspace.authorization_domains.first(),
            access=WorkspaceGroupSharing.READER,
        )
        # Share with the DCC admin group to prevent a problem in the sharing audit.
        WorkspaceGroupSharingFactory.create(
            workspace=dcc_processed_data_workspace.workspace,
            group=dcc_admins_group,
            access=WorkspaceGroupSharing.OWNER,
        )
        GroupGroupMembershipFactory.create(
            parent_group=dcc_processed_data_workspace.workspace.authorization_domains.first(),
            child_group=dcc_admins_group,
            role=GroupGroupMembership.ADMIN,
        )
        out = StringIO()
        call_command("run_dcc_processed_data_workspace_audit", "--no-color", email="test@example.com", stdout=out)
        self.assertIn("Running DCCProcessedDataWorkspace auth domain audit... ok!", out.getvalue())
        # Zero messages have been sent by default.
        self.assertEqual(len(mail.outbox), 0)

    def test_auth_domain_audit_one_instance_needs_action_email(self):
        """Email is sent for one needs_action instance."""
        # Create a workspace and matching DAR.
        dcc_processed_data_workspace = factories.DCCProcessedDataWorkspaceFactory.create()
        dcc_admins_group = ManagedGroupFactory.create(name=settings.ANVIL_DCC_ADMINS_GROUP_NAME)
        # Share with the auth domain to prevent a problem in the sharing audit.
        WorkspaceGroupSharingFactory.create(
            workspace=dcc_processed_data_workspace.workspace,
            group=dcc_processed_data_workspace.workspace.authorization_domains.first(),
            access=WorkspaceGroupSharing.READER,
        )
        # Share with the DCC admin group to prevent a problem in the sharing audit.
        WorkspaceGroupSharingFactory.create(
            workspace=dcc_processed_data_workspace.workspace,
            group=dcc_admins_group,
            access=WorkspaceGroupSharing.OWNER,
        )
        out = StringIO()
        call_command("run_dcc_processed_data_workspace_audit", "--no-color", email="test@example.com", stdout=out)
        # One message has been sent by default.
        self.assertEqual(len(mail.outbox), 1)
        email = mail.outbox[0]
        self.assertEqual(email.to, ["test@example.com"])
        self.assertEqual(email.subject, "DCCProcessedDataWorkspaceAuthDomainAudit - problems found")

    def test_auth_domain_audit_one_instance_error_email(self):
        """Test command output with one error instance."""
        dcc_processed_data_workspace = factories.DCCProcessedDataWorkspaceFactory.create()
        # Share with the auth domain to prevent a problem in the sharing audit.
        WorkspaceGroupSharingFactory.create(
            workspace=dcc_processed_data_workspace.workspace,
            group=dcc_processed_data_workspace.workspace.authorization_domains.first(),
            access=WorkspaceGroupSharing.READER,
        )
        GroupGroupMembershipFactory.create(
            parent_group=dcc_processed_data_workspace.workspace.authorization_domains.first(),
            role=GroupGroupMembership.ADMIN,
        )
        out = StringIO()
        call_command("run_dcc_processed_data_workspace_audit", "--no-color", email="test@example.com", stdout=out)
        expected_string = "\n".join(
            [
                "Running DCCProcessedDataWorkspace auth domain audit... problems found.",
                "* Verified: 0",
                "* Needs action: 0",
                "* Errors: 1",
            ]
        )
        self.assertIn(expected_string, out.getvalue())
        # One message has been sent by default.
        self.assertEqual(len(mail.outbox), 1)
        email = mail.outbox[0]
        self.assertEqual(email.to, ["test@example.com"])
        self.assertEqual(email.subject, "DCCProcessedDataWorkspaceAuthDomainAudit - problems found")

    def test_auth_domain_audit_different_domain(self):
        """Test command output when a different domain is specified."""
        site = Site.objects.create(domain="foobar.com", name="test")
        site.save()
        with self.settings(SITE_ID=site.id):
            factories.DCCProcessedDataWorkspaceFactory.create()
            ManagedGroupFactory.create(name=settings.ANVIL_DCC_ADMINS_GROUP_NAME)
            out = StringIO()
            call_command("run_dcc_processed_data_workspace_audit", "--no-color", stdout=out)
            self.assertIn("Running DCCProcessedDataWorkspace auth domain audit... problems found.", out.getvalue())
            self.assertIn("https://foobar.com", out.getvalue())

    def test_auth_domain_audit_one_instance_needs_action_link_in_output(self):
        dcc_processed_data_workspace = factories.DCCProcessedDataWorkspaceFactory.create()
        # Share with the auth domain to prevent an error in the sharing audit.
        WorkspaceGroupSharingFactory.create(
            workspace=dcc_processed_data_workspace.workspace,
            group=dcc_processed_data_workspace.workspace.authorization_domains.first(),
        )
        GroupGroupMembershipFactory.create(
            parent_group=dcc_processed_data_workspace.workspace.authorization_domains.first(),
            role=GroupGroupMembership.ADMIN,
        )
        out = StringIO()
        call_command("run_dcc_processed_data_workspace_audit", "--no-color", stdout=out)
        url = reverse("gregor_anvil:audit:dcc_processed_data_workspaces:auth_domains:all")
        self.assertIn(url, out.getvalue())
        # Zero messages have been sent by default.
        self.assertEqual(len(mail.outbox), 0)
