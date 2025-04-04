import responses
from anvil_consortium_manager.adapters.default import DefaultWorkspaceAdapter
from anvil_consortium_manager.anvil_api import AnVILAPIError
from anvil_consortium_manager.models import (
    Account,
    GroupAccountMembership,
    GroupGroupMembership,
    WorkspaceGroupSharing,
)
from anvil_consortium_manager.tests.factories import (
    AccountFactory,
    GroupAccountMembershipFactory,
    ManagedGroupFactory,
    WorkspaceFactory,
    WorkspaceGroupSharingFactory,
)
from anvil_consortium_manager.tests.utils import AnVILAPIMockTestMixin
from django.core import mail
from django.test import TestCase, override_settings

from gregor_django.gregor_anvil.tests.factories import (
    PartnerGroupFactory,
    ResearchCenterFactory,
)
from gregor_django.users.tests.factories import UserFactory

from .. import adapters


class AccountAdapterTest(AnVILAPIMockTestMixin, TestCase):
    """Tests of the AccountAdapter, where not tested in other TestCases."""

    def test_get_autocomplete_label_linked_user(self):
        """get_autcomplete_label returns correct string when account has a linked user."""
        user = UserFactory.create(name="Test name")
        account = AccountFactory.create(email="foo@bar.com", user=user, verified=True)
        self.assertEqual(
            adapters.AccountAdapter().get_autocomplete_label(account),
            "Test name (foo@bar.com)",
        )

    def test_get_autocomplete_label_no_linked_user(self):
        """get_autcomplete_label returns correct string when account does not have a linked user."""
        account = AccountFactory.create(email="foo@bar.com")
        self.assertEqual(
            adapters.AccountAdapter().get_autocomplete_label(account),
            "--- (foo@bar.com)",
        )

    def test_autocomplete_queryset_matches_user_name(self):
        """get_autocomplete_label returns correct account when user name matches."""
        user_1 = UserFactory.create(name="First Last")
        account_1 = AccountFactory.create(email="test1@test.com", user=user_1, verified=True)
        user_2 = UserFactory.create(name="Foo Bar")
        account_2 = AccountFactory.create(email="test2@test.com", user=user_2, verified=True)
        queryset = adapters.AccountAdapter().get_autocomplete_queryset(Account.objects.all(), "last")
        self.assertEqual(len(queryset), 1)
        self.assertIn(account_1, queryset)
        self.assertNotIn(account_2, queryset)

    def test_autocomplete_queryset_matches_account_email(self):
        """get_autocomplete_label returns correct account when user email matches."""
        user_1 = UserFactory.create(name="First Last")
        account_1 = AccountFactory.create(email="test1@test.com", user=user_1, verified=True)
        user_2 = UserFactory.create(name="Foo Bar")
        account_2 = AccountFactory.create(email="username@domain.com", user=user_2, verified=True)
        queryset = adapters.AccountAdapter().get_autocomplete_queryset(Account.objects.all(), "test")
        self.assertEqual(len(queryset), 1)
        self.assertIn(account_1, queryset)
        self.assertNotIn(account_2, queryset)

    def test_autocomplete_queryset_no_linked_user(self):
        """get_autocomplete_label returns correct account when user name matches."""
        account_1 = AccountFactory.create(email="foo@bar.com")
        account_2 = AccountFactory.create(email="test@test.com")
        queryset = adapters.AccountAdapter().get_autocomplete_queryset(Account.objects.all(), "bar")
        self.assertEqual(len(queryset), 1)
        self.assertIn(account_1, queryset)
        self.assertNotIn(account_2, queryset)

    def test_after_account_verification_no_groups(self):
        ResearchCenterFactory.create(member_group=ManagedGroupFactory.create())
        PartnerGroupFactory.create(member_group=ManagedGroupFactory.create())
        # Create an account not linked to the above RC or group.
        account = AccountFactory.create(verified=True)
        adapters.AccountAdapter().after_account_verification(account)
        # Check for GroupGroupMembership.
        self.assertEqual(GroupAccountMembership.objects.count(), 0)

    def test_after_account_verification_one_rc(self):
        member_group = ManagedGroupFactory.create()
        research_center = ResearchCenterFactory.create(member_group=member_group)
        # Create an account whose user is linked to this RC.
        user = UserFactory.create()
        user.research_centers.add(research_center)
        account = AccountFactory.create(user=user, verified=True)
        # API response for RC membership.
        self.anvil_response_mock.add(
            responses.PUT,
            self.api_client.sam_entry_point + f"/api/groups/v1/{member_group.name}/member/{account.email}",
            status=204,
        )
        # Run the adapter method.
        adapters.AccountAdapter().after_account_verification(account)
        # Check for GroupGroupMembership.
        self.assertEqual(GroupAccountMembership.objects.count(), 1)
        membership = GroupAccountMembership.objects.first()
        self.assertEqual(membership.group, member_group)
        self.assertEqual(membership.account, account)
        self.assertEqual(membership.role, GroupGroupMembership.MEMBER)

    def test_after_account_verification_two_rcs(self):
        # Create an account whose user is linked to two RCs.
        user = UserFactory.create()
        member_group_1 = ManagedGroupFactory.create()
        research_center_1 = ResearchCenterFactory.create(member_group=member_group_1)
        user.research_centers.add(research_center_1)
        member_group_2 = ManagedGroupFactory.create()
        research_center_2 = ResearchCenterFactory.create(member_group=member_group_2)
        user.research_centers.add(research_center_2)
        account = AccountFactory.create(user=user, verified=True)
        # API response for RC membership.
        self.anvil_response_mock.add(
            responses.PUT,
            self.api_client.sam_entry_point + f"/api/groups/v1/{member_group_1.name}/member/{account.email}",
            status=204,
        )
        self.anvil_response_mock.add(
            responses.PUT,
            self.api_client.sam_entry_point + f"/api/groups/v1/{member_group_2.name}/member/{account.email}",
            status=204,
        )
        # Run the adapter method.
        adapters.AccountAdapter().after_account_verification(account)
        # Check for GroupGroupMembership.
        self.assertEqual(GroupAccountMembership.objects.count(), 2)
        membership = GroupAccountMembership.objects.get(group=member_group_1, account=account)
        self.assertEqual(membership.role, GroupGroupMembership.MEMBER)
        membership = GroupAccountMembership.objects.get(group=member_group_2, account=account)
        self.assertEqual(membership.role, GroupGroupMembership.MEMBER)

    def test_after_account_verification_one_rc_no_members_group(self):
        """A user is linked to an RC with no members group."""
        user = UserFactory.create()
        research_center = ResearchCenterFactory.create(member_group=None)
        user.research_centers.add(research_center)
        account = AccountFactory.create(user=user, verified=True)
        # No mocked API responses.
        # Run the adapter method.
        adapters.AccountAdapter().after_account_verification(account)
        # Check for GroupGroupMembership.
        self.assertEqual(GroupAccountMembership.objects.count(), 0)

    def test_after_account_verification_one_rc_api_error(self):
        member_group = ManagedGroupFactory.create()
        research_center = ResearchCenterFactory.create(member_group=member_group)
        # Create an account whose user is linked to this RC.
        user = UserFactory.create()
        user.research_centers.add(research_center)
        account = AccountFactory.create(user=user, verified=True)
        # API response for RC membership.
        self.anvil_response_mock.add(
            responses.PUT,
            self.api_client.sam_entry_point + f"/api/groups/v1/{member_group.name}/member/{account.email}",
            status=500,
            json={"message": "test error"},
        )
        # Run the adapter method.
        with self.assertRaises(AnVILAPIError):
            adapters.AccountAdapter().after_account_verification(account)
        # Check for GroupGroupMembership.
        # Saved but not created on AnVIL.
        self.assertEqual(GroupAccountMembership.objects.count(), 1)

    def test_after_account_verification_one_partner(self):
        member_group = ManagedGroupFactory.create()
        partner_group = PartnerGroupFactory.create(member_group=member_group)
        # Create an account whose user is linked to this partner group.
        user = UserFactory.create()
        user.partner_groups.add(partner_group)
        account = AccountFactory.create(user=user, verified=True)
        # API response for RC membership.
        self.anvil_response_mock.add(
            responses.PUT,
            self.api_client.sam_entry_point + f"/api/groups/v1/{member_group.name}/member/{account.email}",
            status=204,
        )
        # Run the adapter method.
        adapters.AccountAdapter().after_account_verification(account)
        # Check for GroupGroupMembership.
        self.assertEqual(GroupAccountMembership.objects.count(), 1)
        membership = GroupAccountMembership.objects.first()
        self.assertEqual(membership.group, member_group)
        self.assertEqual(membership.account, account)
        self.assertEqual(membership.role, GroupGroupMembership.MEMBER)

    def test_after_account_verification_two_partners(self):
        user = UserFactory.create()
        member_group_1 = ManagedGroupFactory.create()
        partner_group_1 = PartnerGroupFactory.create(member_group=member_group_1)
        user.partner_groups.add(partner_group_1)
        member_group_2 = ManagedGroupFactory.create()
        partner_group_2 = PartnerGroupFactory.create(member_group=member_group_2)
        user.partner_groups.add(partner_group_2)
        account = AccountFactory.create(user=user, verified=True)
        # API response for RC membership.
        self.anvil_response_mock.add(
            responses.PUT,
            self.api_client.sam_entry_point + f"/api/groups/v1/{member_group_1.name}/member/{account.email}",
            status=204,
        )
        self.anvil_response_mock.add(
            responses.PUT,
            self.api_client.sam_entry_point + f"/api/groups/v1/{member_group_2.name}/member/{account.email}",
            status=204,
        )
        # Run the adapter method.
        adapters.AccountAdapter().after_account_verification(account)
        # Check for GroupGroupMembership.
        self.assertEqual(GroupAccountMembership.objects.count(), 2)
        membership = GroupAccountMembership.objects.get(group=member_group_1, account=account)
        self.assertEqual(membership.role, GroupGroupMembership.MEMBER)
        membership = GroupAccountMembership.objects.get(group=member_group_2, account=account)
        self.assertEqual(membership.role, GroupGroupMembership.MEMBER)

    def test_after_account_verification_one_partner_no_members_group(self):
        """A user is linked to a PartnerGroup with no members group."""
        user = UserFactory.create()
        partner_group = PartnerGroupFactory.create(member_group=None)
        user.partner_groups.add(partner_group)
        account = AccountFactory.create(user=user, verified=True)
        # No mocked API responses.
        # Run the adapter method.
        adapters.AccountAdapter().after_account_verification(account)
        # Check for GroupGroupMembership.
        self.assertEqual(GroupAccountMembership.objects.count(), 0)

    def test_after_account_verification_one_partner_group_api_error(self):
        member_group = ManagedGroupFactory.create()
        partner_group = PartnerGroupFactory.create(member_group=member_group)
        # Create an account whose user is linked to this RC.
        user = UserFactory.create()
        user.partner_groups.add(partner_group)
        account = AccountFactory.create(user=user, verified=True)
        # API response for RC membership.
        self.anvil_response_mock.add(
            responses.PUT,
            self.api_client.sam_entry_point + f"/api/groups/v1/{member_group.name}/member/{account.email}",
            status=500,
            json={"message": "test error"},
        )
        # Run the adapter method.
        with self.assertRaises(AnVILAPIError):
            adapters.AccountAdapter().after_account_verification(account)
        # Check for GroupGroupMembership.
        # Saved but not created on AnVIL.
        self.assertEqual(GroupAccountMembership.objects.count(), 1)

    def test_after_account_verification_one_rc_and_one_partner_group(self):
        user = UserFactory.create()
        member_group_1 = ManagedGroupFactory.create()
        partner_group = PartnerGroupFactory.create(member_group=member_group_1)
        user.partner_groups.add(partner_group)
        member_group_2 = ManagedGroupFactory.create()
        research_center = ResearchCenterFactory.create(member_group=member_group_2)
        user.research_centers.add(research_center)
        account = AccountFactory.create(user=user, verified=True)
        # API response for RC membership.
        self.anvil_response_mock.add(
            responses.PUT,
            self.api_client.sam_entry_point + f"/api/groups/v1/{member_group_1.name}/member/{account.email}",
            status=204,
        )
        self.anvil_response_mock.add(
            responses.PUT,
            self.api_client.sam_entry_point + f"/api/groups/v1/{member_group_2.name}/member/{account.email}",
            status=204,
        )
        # Run the adapter method.
        adapters.AccountAdapter().after_account_verification(account)
        # Check for GroupGroupMembership.
        self.assertEqual(GroupAccountMembership.objects.count(), 2)
        membership = GroupAccountMembership.objects.get(group=member_group_1, account=account)
        self.assertEqual(membership.role, GroupGroupMembership.MEMBER)
        membership = GroupAccountMembership.objects.get(group=member_group_2, account=account)
        self.assertEqual(membership.role, GroupGroupMembership.MEMBER)

    def test_after_account_verification_group_account_membership_already_exists(self):
        member_group = ManagedGroupFactory.create()
        research_center = ResearchCenterFactory.create(member_group=member_group)
        # Create an account whose user is linked to this RC.
        user = UserFactory.create()
        user.research_centers.add(research_center)
        account = AccountFactory.create(user=user, verified=True)
        # Create the group-account membership already.
        GroupAccountMembershipFactory.create(
            group=member_group,
            account=account,
            role=GroupGroupMembership.ADMIN,
        )
        # No API response - group will not be changed.
        # Run the adapter method.
        adapters.AccountAdapter().after_account_verification(account)
        # Check for GroupGroupMembership.
        self.assertEqual(GroupAccountMembership.objects.count(), 1)
        membership = GroupAccountMembership.objects.first()
        self.assertEqual(membership.group, member_group)
        self.assertEqual(membership.account, account)
        self.assertEqual(membership.role, GroupGroupMembership.ADMIN)

    def test_get_account_verification_notification_context(self):
        account = AccountFactory.create(verified=True)
        context = adapters.AccountAdapter().get_account_verification_notification_context(account)
        self.assertEqual(context["email"], account.email)
        self.assertEqual(context["user"], account.user)
        self.assertIn("memberships", context)
        self.assertEqual(len(context["memberships"]), 0)
        # One membership
        membership_1 = GroupAccountMembershipFactory.create(account=account)
        context = adapters.AccountAdapter().get_account_verification_notification_context(account)
        self.assertEqual(len(context["memberships"]), 1)
        self.assertIn(membership_1, context["memberships"])
        # Two memberships
        membership_2 = GroupAccountMembershipFactory.create(account=account)
        context = adapters.AccountAdapter().get_account_verification_notification_context(account)
        self.assertEqual(len(context["memberships"]), 2)
        self.assertIn(membership_1, context["memberships"])
        self.assertIn(membership_2, context["memberships"])

    def test_send_account_verification_notification_email_includes_memberships(self):
        """The account verification notification email includes a list of the account memberships."""
        account = AccountFactory.create(verified=True)
        membership = GroupAccountMembershipFactory.create(account=account)
        with self.assertTemplateUsed("gregor_anvil/account_notification_email.html"):
            adapters.AccountAdapter().send_account_verification_notification_email(account)
        # Check that the email was sent.
        self.assertEqual(len(mail.outbox), 1)
        email = mail.outbox[0]
        # Check that the email contains the account email.
        self.assertIn(account.email, email.body)
        # Check that the email contains the username
        self.assertIn(account.user.username, email.body)
        # Check that the email contains the membership info.
        self.assertIn(str(membership), email.body)


class WorkspaceAdminSharingAdapterMixin(AnVILAPIMockTestMixin, TestCase):
    def setUp(self):
        super().setUp()

        class TestAdapter(adapters.WorkspaceAdminSharingAdapterMixin, DefaultWorkspaceAdapter):
            pass

        self.adapter = TestAdapter()

    def test_after_anvil_create(self):
        admins_group = ManagedGroupFactory.create(name="TEST_GREGOR_DCC_ADMINS")
        workspace = WorkspaceFactory.create(
            billing_project__name="bar", name="foo", workspace_type=self.adapter.get_type()
        )
        # API response for admin group workspace owner.
        acls = [
            {
                "email": "TEST_GREGOR_DCC_ADMINS@firecloud.org",
                "accessLevel": "OWNER",
                "canShare": False,
                "canCompute": True,
            }
        ]
        self.anvil_response_mock.add(
            responses.PATCH,
            self.api_client.rawls_entry_point + "/api/workspaces/bar/foo/acl?inviteUsersNotFound=false",
            status=200,
            match=[responses.matchers.json_params_matcher(acls)],
            json={"invitesSent": {}, "usersNotFound": {}, "usersUpdated": acls},
        )
        # Run the adapter method.
        self.adapter.after_anvil_create(workspace)
        # Check for WorkspaceGroupSharing.
        self.assertEqual(WorkspaceGroupSharing.objects.count(), 1)
        sharing = WorkspaceGroupSharing.objects.first()
        self.assertEqual(sharing.workspace, workspace)
        self.assertEqual(sharing.group, admins_group)
        self.assertEqual(sharing.access, WorkspaceGroupSharing.OWNER)
        self.assertTrue(sharing.can_compute)

    @override_settings(ANVIL_DCC_ADMINS_GROUP_NAME="foobar")
    def test_after_anvil_create_different_admins_group(self):
        admins_group = ManagedGroupFactory.create(name="foobar")
        workspace = WorkspaceFactory.create(
            billing_project__name="bar", name="foo", workspace_type=self.adapter.get_type()
        )
        # API response for admin group workspace owner.
        acls = [
            {
                "email": "foobar@firecloud.org",
                "accessLevel": "OWNER",
                "canShare": False,
                "canCompute": True,
            }
        ]
        self.anvil_response_mock.add(
            responses.PATCH,
            self.api_client.rawls_entry_point + "/api/workspaces/bar/foo/acl?inviteUsersNotFound=false",
            status=200,
            match=[responses.matchers.json_params_matcher(acls)],
            json={"invitesSent": {}, "usersNotFound": {}, "usersUpdated": acls},
        )
        # Run the adapter method.
        self.adapter.after_anvil_create(workspace)
        # Check for WorkspaceGroupSharing.
        self.assertEqual(WorkspaceGroupSharing.objects.count(), 1)
        sharing = WorkspaceGroupSharing.objects.first()
        self.assertEqual(sharing.workspace, workspace)
        self.assertEqual(sharing.group, admins_group)
        self.assertEqual(sharing.access, WorkspaceGroupSharing.OWNER)
        self.assertTrue(sharing.can_compute)

    def test_after_anvil_create_no_admins_group(self):
        workspace = WorkspaceFactory.create(
            billing_project__name="bar", name="foo", workspace_type=self.adapter.get_type()
        )
        # Run the adapter method.
        self.adapter.after_anvil_create(workspace)
        # No WorkspaceGroupSharing objects were created.
        self.assertEqual(WorkspaceGroupSharing.objects.count(), 0)

    def test_after_anvil_import(self):
        admins_group = ManagedGroupFactory.create(name="TEST_GREGOR_DCC_ADMINS")
        workspace = WorkspaceFactory.create(
            billing_project__name="bar", name="foo", workspace_type=self.adapter.get_type()
        )
        # API response for admin group workspace owner.
        acls = [
            {
                "email": "TEST_GREGOR_DCC_ADMINS@firecloud.org",
                "accessLevel": "OWNER",
                "canShare": False,
                "canCompute": True,
            }
        ]
        self.anvil_response_mock.add(
            responses.PATCH,
            self.api_client.rawls_entry_point + "/api/workspaces/bar/foo/acl?inviteUsersNotFound=false",
            status=200,
            match=[responses.matchers.json_params_matcher(acls)],
            json={"invitesSent": {}, "usersNotFound": {}, "usersUpdated": acls},
        )
        # Run the adapter method.
        self.adapter.after_anvil_import(workspace)
        # Check for WorkspaceGroupSharing.
        self.assertEqual(WorkspaceGroupSharing.objects.count(), 1)
        sharing = WorkspaceGroupSharing.objects.first()
        self.assertEqual(sharing.workspace, workspace)
        self.assertEqual(sharing.group, admins_group)
        self.assertEqual(sharing.access, WorkspaceGroupSharing.OWNER)
        self.assertTrue(sharing.can_compute)

    @override_settings(ANVIL_DCC_ADMINS_GROUP_NAME="foobar")
    def test_after_anvil_import_different_admins_group(self):
        admins_group = ManagedGroupFactory.create(name="foobar")
        workspace = WorkspaceFactory.create(
            billing_project__name="bar", name="foo", workspace_type=self.adapter.get_type()
        )
        # API response for admin group workspace owner.
        acls = [
            {
                "email": "foobar@firecloud.org",
                "accessLevel": "OWNER",
                "canShare": False,
                "canCompute": True,
            }
        ]
        self.anvil_response_mock.add(
            responses.PATCH,
            self.api_client.rawls_entry_point + "/api/workspaces/bar/foo/acl?inviteUsersNotFound=false",
            status=200,
            match=[responses.matchers.json_params_matcher(acls)],
            json={"invitesSent": {}, "usersNotFound": {}, "usersUpdated": acls},
        )
        # Run the adapter method.
        self.adapter.after_anvil_import(workspace)
        # Check for WorkspaceGroupSharing.
        self.assertEqual(WorkspaceGroupSharing.objects.count(), 1)
        sharing = WorkspaceGroupSharing.objects.first()
        self.assertEqual(sharing.workspace, workspace)
        self.assertEqual(sharing.group, admins_group)
        self.assertEqual(sharing.access, WorkspaceGroupSharing.OWNER)
        self.assertTrue(sharing.can_compute)

    def test_after_anvil_import_no_admins_group(self):
        workspace = WorkspaceFactory.create(
            billing_project__name="bar", name="foo", workspace_type=self.adapter.get_type()
        )
        # Run the adapter method.
        self.adapter.after_anvil_import(workspace)
        # No WorkspaceGroupSharing objects were created.
        self.assertEqual(WorkspaceGroupSharing.objects.count(), 0)

    def test_after_anvil_import_already_shared(self):
        admins_group = ManagedGroupFactory.create(name="TEST_GREGOR_DCC_ADMINS")
        workspace = WorkspaceFactory.create(workspace_type=self.adapter.get_type())
        WorkspaceGroupSharingFactory.create(
            workspace=workspace,
            group=admins_group,
            access=WorkspaceGroupSharing.OWNER,
            can_compute=True,
        )
        # No API call - record already exists.
        # Run the adapter method.
        self.adapter.after_anvil_import(workspace)
        # Check for WorkspaceGroupSharing.
        self.assertEqual(WorkspaceGroupSharing.objects.count(), 1)
        sharing = WorkspaceGroupSharing.objects.first()
        self.assertEqual(sharing.workspace, workspace)
        self.assertEqual(sharing.group, admins_group)
        self.assertEqual(sharing.access, WorkspaceGroupSharing.OWNER)
        self.assertTrue(sharing.can_compute)

    def test_after_anvil_import_already_shared_wrong_access(self):
        admins_group = ManagedGroupFactory.create(name="TEST_GREGOR_DCC_ADMINS")
        workspace = WorkspaceFactory.create(
            billing_project__name="bar", name="foo", workspace_type=self.adapter.get_type()
        )
        sharing = WorkspaceGroupSharingFactory.create(
            workspace=workspace,
            group=admins_group,
            access=WorkspaceGroupSharing.READER,
            can_compute=True,
        )
        # API response to update sharing.
        acls = [
            {
                "email": "TEST_GREGOR_DCC_ADMINS@firecloud.org",
                "accessLevel": "OWNER",
                "canShare": False,
                "canCompute": True,
            }
        ]
        self.anvil_response_mock.add(
            responses.PATCH,
            self.api_client.rawls_entry_point + "/api/workspaces/bar/foo/acl?inviteUsersNotFound=false",
            status=200,
            match=[responses.matchers.json_params_matcher(acls)],
            json={"invitesSent": {}, "usersNotFound": {}, "usersUpdated": acls},
        )
        # Run the adapter method.
        self.adapter.after_anvil_import(workspace)
        # Check for WorkspaceGroupSharing.
        self.assertEqual(WorkspaceGroupSharing.objects.count(), 1)
        sharing.refresh_from_db()
        self.assertEqual(sharing.workspace, workspace)
        self.assertEqual(sharing.group, admins_group)
        self.assertEqual(sharing.access, WorkspaceGroupSharing.OWNER)
        self.assertTrue(sharing.can_compute)

    def test_after_anvil_import_already_shared_wrong_can_compute(self):
        admins_group = ManagedGroupFactory.create(name="TEST_GREGOR_DCC_ADMINS")
        workspace = WorkspaceFactory.create(
            billing_project__name="bar", name="foo", workspace_type=self.adapter.get_type()
        )
        sharing = WorkspaceGroupSharingFactory.create(
            workspace=workspace,
            group=admins_group,
            access=WorkspaceGroupSharing.OWNER,
            can_compute=False,
        )
        # API response to update sharing.
        acls = [
            {
                "email": "TEST_GREGOR_DCC_ADMINS@firecloud.org",
                "accessLevel": "OWNER",
                "canShare": False,
                "canCompute": True,
            }
        ]
        self.anvil_response_mock.add(
            responses.PATCH,
            self.api_client.rawls_entry_point + "/api/workspaces/bar/foo/acl?inviteUsersNotFound=false",
            status=200,
            match=[responses.matchers.json_params_matcher(acls)],
            json={"invitesSent": {}, "usersNotFound": {}, "usersUpdated": acls},
        )
        # Run the adapter method.
        self.adapter.after_anvil_import(workspace)
        # Check for WorkspaceGroupSharing.
        self.assertEqual(WorkspaceGroupSharing.objects.count(), 1)
        sharing.refresh_from_db()
        self.assertEqual(sharing.workspace, workspace)
        self.assertEqual(sharing.group, admins_group)
        self.assertEqual(sharing.access, WorkspaceGroupSharing.OWNER)
        self.assertTrue(sharing.can_compute)


class ManagedGroupAdapterTest(AnVILAPIMockTestMixin, TestCase):
    """Tests for the custom PRIMED ManagedGroupAdapter."""

    def setUp(self):
        super().setUp()
        self.adapter = adapters.ManagedGroupAdapter()

    def test_after_anvil_create(self):
        admins_group = ManagedGroupFactory.create(name="TEST_GREGOR_DCC_ADMINS")
        managed_group = ManagedGroupFactory.create(name="test-group")
        # API response for PRIMED_ADMINS membership.
        self.anvil_response_mock.add(
            responses.PUT,
            self.api_client.sam_entry_point + "/api/groups/v1/test-group/admin/TEST_GREGOR_DCC_ADMINS@firecloud.org",
            status=204,
        )
        # Run the adapter method.
        self.adapter.after_anvil_create(managed_group)
        # Check for GroupGroupMembership.
        self.assertEqual(GroupGroupMembership.objects.count(), 1)
        membership = GroupGroupMembership.objects.first()
        self.assertEqual(membership.parent_group, managed_group)
        self.assertEqual(membership.child_group, admins_group)
        self.assertEqual(membership.role, GroupGroupMembership.ADMIN)

    @override_settings(ANVIL_DCC_ADMINS_GROUP_NAME="foobar")
    def test_after_anvil_create_different_admins_group(self):
        admins_group = ManagedGroupFactory.create(name="foobar")
        managed_group = ManagedGroupFactory.create(name="test-group")
        # API response for PRIMED_ADMINS membership.
        self.anvil_response_mock.add(
            responses.PUT,
            self.api_client.sam_entry_point + "/api/groups/v1/test-group/admin/foobar@firecloud.org",
            status=204,
        )
        # Run the adapter method.
        self.adapter.after_anvil_create(managed_group)
        # Check for GroupGroupMembership.
        self.assertEqual(GroupGroupMembership.objects.count(), 1)
        membership = GroupGroupMembership.objects.first()
        self.assertEqual(membership.parent_group, managed_group)
        self.assertEqual(membership.child_group, admins_group)
        self.assertEqual(membership.role, GroupGroupMembership.ADMIN)

    def test_after_anvil_create_no_admins_group(self):
        managed_group = ManagedGroupFactory.create(name="test-group")
        # Run the adapter method.
        self.adapter.after_anvil_create(managed_group)
        # No WorkspaceGroupSharing objects were created.
        self.assertEqual(GroupGroupMembership.objects.count(), 0)
