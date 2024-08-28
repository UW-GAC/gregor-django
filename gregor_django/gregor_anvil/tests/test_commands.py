"""Tests for management commands in the `gregor_anvil` app."""

from io import StringIO

from anvil_consortium_manager.models import WorkspaceGroupSharing
from anvil_consortium_manager.tests.factories import (
    WorkspaceGroupSharingFactory,
)
from django.contrib.sites.models import Site
from django.core import mail
from django.core.management import call_command
from django.test import TestCase
from django.urls import reverse

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

    # def test_collaborator_audit_one_instance_verified(self):
    #     """Test command output with one verified instance."""
    #     # Create a workspace and matching DAR.
    #     factories.dbGaPApplicationFactory.create()
    #     # Verified no access for PI.
    #     out = StringIO()
    #     call_command("run_upload_workspace_audit", "--no-color", stdout=out)
    #     expected_string = "\n".join(
    #         [
    #             "Running dbGaP collaborator audit... ok!",
    #             "* Verified: 1",
    #             "* Needs action: 0",
    #             "* Errors: 0",
    #         ]
    #     )
    #     self.assertIn(expected_string, out.getvalue())
    #     # Zero messages have been sent by default.
    #     self.assertEqual(len(mail.outbox), 0)

    # def test_collaborator_audit_one_instance_needs_action(self):
    #     """Test command output with one needs_action instance."""
    #     application = factories.dbGaPApplicationFactory.create()
    #     AccountFactory.create(user=application.principal_investigator)
    #     out = StringIO()
    #     call_command("run_upload_workspace_audit", "--no-color", stdout=out)
    #     expected_string = "\n".join(
    #         [
    #             "Running dbGaP collaborator audit... problems found.",
    #             "* Verified: 0",
    #             "* Needs action: 1",
    #             "* Errors: 0",
    #         ]
    #     )
    #     self.assertIn(expected_string, out.getvalue())
    #     # Zero messages have been sent by default.
    #     self.assertEqual(len(mail.outbox), 0)

    # def test_collaborator_audit_one_instance_error(self):
    #     """Test command output with one error instance."""
    #     application = factories.dbGaPApplicationFactory.create()
    #     GroupGroupMembershipFactory(
    #         parent_group=application.anvil_access_group,
    #     )
    #     out = StringIO()
    #     call_command("run_upload_workspace_audit", "--no-color", stdout=out)
    #     expected_string = "\n".join(
    #         [
    #             "Running dbGaP collaborator audit... problems found.",
    #             "* Verified: 1",  # PI - no linked account, verified no access.
    #             "* Needs action: 0",
    #             "* Errors: 1",
    #         ]
    #     )
    #     self.assertIn(expected_string, out.getvalue())
    #     # Zero messages have been sent by default.
    #     self.assertEqual(len(mail.outbox), 0)

    # def test_collaborator_audit_one_instance_verified_email(self):
    #     """No email is sent when there are no errors."""
    #     factories.dbGaPApplicationFactory.create()
    #     # Verified no access for PI.
    #     out = StringIO()
    #     call_command("run_upload_workspace_audit", "--no-color", email="test@example.com", stdout=out)
    #     self.assertIn("Running dbGaP collaborator audit... ok!", out.getvalue())
    #     # Zero messages have been sent by default.
    #     self.assertEqual(len(mail.outbox), 0)

    # def test_collaborator_audit_one_instance_needs_action_email(self):
    #     """Email is sent for one needs_action instance."""
    #     # Create a workspace and matching DAR.
    #     application = factories.dbGaPApplicationFactory.create()
    #     AccountFactory.create(user=application.principal_investigator)
    #     out = StringIO()
    #     call_command("run_upload_workspace_audit", "--no-color", email="test@example.com", stdout=out)
    #     expected_string = "\n".join(
    #         [
    #             "Running dbGaP collaborator audit... problems found.",
    #             "* Verified: 0",
    #             "* Needs action: 1",
    #             "* Errors: 0",
    #         ]
    #     )
    #     self.assertIn(expected_string, out.getvalue())
    #     # One message has been sent by default.
    #     self.assertEqual(len(mail.outbox), 1)
    #     email = mail.outbox[0]
    #     self.assertEqual(email.to, ["test@example.com"])
    #     self.assertEqual(email.subject, "dbGaPCollaboratorAudit - problems found")

    # def test_collaborator_audit_one_instance_error_email(self):
    #     """Test command output with one error instance."""
    #     application = factories.dbGaPApplicationFactory.create()
    #     GroupGroupMembershipFactory(
    #         parent_group=application.anvil_access_group,
    #     )
    #     out = StringIO()
    #     call_command("run_upload_workspace_audit", "--no-color", email="test@example.com", stdout=out)
    #     expected_string = "\n".join(
    #         [
    #             "Running dbGaP collaborator audit... problems found.",
    #             "* Verified: 1",  # PI - no linked account, verified no access.
    #             "* Needs action: 0",
    #             "* Errors: 1",
    #         ]
    #     )
    #     self.assertIn(expected_string, out.getvalue())
    #     # One message has been sent by default.
    #     self.assertEqual(len(mail.outbox), 1)
    #     email = mail.outbox[0]
    #     self.assertEqual(email.to, ["test@example.com"])
    #     self.assertEqual(email.subject, "dbGaPCollaboratorAudit - problems found")

    # def test_collaborator_audit_different_domain(self):
    #     """Test command output when a different domain is specified."""
    #     site = Site.objects.create(domain="foobar.com", name="test")
    #     site.save()
    #     with self.settings(SITE_ID=site.id):
    #         application = factories.dbGaPApplicationFactory.create()
    #         AccountFactory.create(user=application.principal_investigator)
    #         out = StringIO()
    #         call_command("run_upload_workspace_audit", "--no-color", stdout=out)
    #         self.assertIn("Running dbGaP collaborator audit... problems found.", out.getvalue())
    #         self.assertIn("https://foobar.com", out.getvalue())
