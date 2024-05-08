import json
import time
from io import StringIO

import responses
from allauth.socialaccount.models import SocialAccount
from anvil_consortium_manager.models import (
    Account,
    GroupAccountMembership,
    ManagedGroup,
)
from django.conf import settings
from django.contrib.auth import get_user_model
from django.core import mail
from django.core.management import call_command
from django.test import TestCase
from marshmallow_jsonapi import Schema, fields

from gregor_django.drupal_oauth_provider.provider import CustomProvider
from gregor_django.users import audit
from gregor_django.users.models import ResearchCenter


class ResearchCenterMockObject:
    def __init__(self, id, title, field_long_name, drupal_internal__nid) -> None:
        self.id = id
        self.title = title
        self.field_long_name = field_long_name
        self.drupal_internal__nid = drupal_internal__nid


class UserMockObject:
    def __init__(
        self,
        id,
        display_name,
        drupal_internal__uid,
        name,
        mail,
        field_given_first_name_s_,
        field_examples_family_last_name_,
        field_study_site_or_center,
    ) -> None:
        self.id = id
        self.display_name = display_name
        self.drupal_internal__uid = drupal_internal__uid
        self.name = name
        self.mail = mail
        self.field_given_first_name_s_ = field_given_first_name_s_
        self.field_examples_family_last_name_ = field_examples_family_last_name_
        self.field_study_site_or_center = field_study_site_or_center


class ResearchCenterSchema(Schema):
    id = fields.Str(dump_only=True)
    title = fields.Str()
    field_long_name = fields.Str()
    drupal_internal__nid = fields.Str()
    # document_meta = fields.DocumentMeta()

    class Meta:
        type_ = "node--study_site_or_center"


class UserSchema(Schema):
    id = fields.Str(dump_only=True)
    display_name = fields.Str()
    drupal_internal__uid = fields.Str()
    name = fields.Str()
    mail = fields.Str()
    field_given_first_name_s_ = fields.Str()
    field_examples_family_last_name_ = fields.Str()
    field_study_site_or_center = fields.Relationship(
        many=True, schema="ResearchCenterSchema", type_="node--study_site_or_center"
    )

    class Meta:
        type_ = "users"


# def debug_requests_on():
#     """Switches on logging of the requests module."""
#     HTTPConnection.debuglevel = 1

#     logging.basicConfig()
#     logging.getLogger().setLevel(logging.DEBUG)
#     requests_log = logging.getLogger("requests.packages.urllib3")
#     requests_log.setLevel(logging.DEBUG)
#     requests_log.propagate = True


TEST_STUDY_SITE_DATA = [
    ResearchCenterMockObject(
        **{
            "id": "1",
            "drupal_internal__nid": "1",
            "title": "SS1",
            "field_long_name": "S S 1",
            # "document_meta": {"page": {"offset": 10}},
        }
    ),
    ResearchCenterMockObject(
        **{
            "id": "2",
            "drupal_internal__nid": "2",
            "title": "SS2",
            "field_long_name": "S S 2",
            # "document_meta": {"page": {"offset": 10}},
        }
    ),
]

TEST_USER_DATA = [
    UserMockObject(
        **{
            "id": "usr1",
            "display_name": "dnusr1",
            "drupal_internal__uid": "usr1",
            "name": "testuser1",
            "mail": "testuser1@test.com",
            "field_given_first_name_s_": "test1",
            "field_examples_family_last_name_": "user1",
            "field_study_site_or_center": [],
        }
    ),
    # second mock object is deactivated user (no drupal uid)
    UserMockObject(
        **{
            "id": "usr2",
            "display_name": "dnusr2",
            "drupal_internal__uid": "",
            "name": "testuser2",
            "mail": "testuser2@test.com",
            "field_given_first_name_s_": "test2",
            "field_examples_family_last_name_": "user2",
            "field_study_site_or_center": [],
        }
    ),
]


class TestUserDataAudit(TestCase):
    """General tests of the user audit"""

    def setUp(self):
        # debug_requests_on()
        super().setUp()
        fake_time = time.time()
        self.token = {
            "token_type": "Bearer",
            "access_token": "asdfoiw37850234lkjsdfsdfTEST",  # gitleaks:allow
            "refresh_token": "sldvafkjw34509s8dfsdfTEST",  # gitleaks:allow
            "expires_in": 3600,
            "expires_at": fake_time + 3600,
        }

    def add_fake_study_sites_response(self):
        url_path = f"{settings.DRUPAL_SITE_URL}/{settings.DRUPAL_API_REL_PATH}/node/study_site_or_center/"
        responses.get(
            url=url_path,
            body=json.dumps(ResearchCenterSchema(many=True).dump(TEST_STUDY_SITE_DATA)),
        )

    def add_fake_users_response(self):
        url_path = f"{settings.DRUPAL_SITE_URL}/{settings.DRUPAL_API_REL_PATH}/user/user/"
        TEST_USER_DATA[0].field_study_site_or_center = [TEST_STUDY_SITE_DATA[0]]
        user_data = UserSchema(include_data=("field_study_site_or_center",), many=True).dump(TEST_USER_DATA)

        responses.get(
            url=url_path,
            body=json.dumps(user_data),
        )

    def add_fake_token_response(self):
        token_url = f"{settings.DRUPAL_SITE_URL}/oauth/token"
        responses.post(url=token_url, body=json.dumps(self.token))

    def get_fake_json_api(self):
        self.add_fake_token_response()
        return audit.get_drupal_json_api()

    @responses.activate
    def test_get_json_api(self):
        json_api = self.get_fake_json_api()
        assert json_api.requests.config.AUTH._client.token["access_token"] == self.token["access_token"]

    @responses.activate
    def test_get_study_sites(self):
        json_api = self.get_fake_json_api()
        self.add_fake_study_sites_response()
        study_sites = audit.get_study_sites(json_api=json_api)

        for test_study_site in TEST_STUDY_SITE_DATA:
            assert test_study_site.field_long_name == study_sites[test_study_site.drupal_internal__nid]["full_name"]
            assert test_study_site.title == study_sites[test_study_site.drupal_internal__nid]["short_name"]
            assert test_study_site.drupal_internal__nid == study_sites[test_study_site.drupal_internal__nid]["node_id"]

    @responses.activate
    def test_audit_study_sites_no_update(self):
        self.get_fake_json_api()
        self.add_fake_study_sites_response()
        site_audit = audit.SiteAudit(apply_changes=False)
        site_audit.run_audit()
        self.assertFalse(site_audit.ok())
        self.assertEqual(len(site_audit.errors), 0)
        self.assertEqual(len(site_audit.needs_action), 2)
        self.assertEqual(ResearchCenter.objects.all().count(), 0)

    @responses.activate
    def test_audit_study_sites_with_new_sites(self):
        self.get_fake_json_api()
        self.add_fake_study_sites_response()
        site_audit = audit.SiteAudit(apply_changes=True)
        site_audit.run_audit()
        self.assertFalse(site_audit.ok())
        self.assertEqual(len(site_audit.needs_action), 2)
        self.assertEqual(ResearchCenter.objects.all().count(), 2)

        assert (
            ResearchCenter.objects.filter(
                short_name__in=[
                    TEST_STUDY_SITE_DATA[0].title,
                    TEST_STUDY_SITE_DATA[1].title,
                ]
            ).count()
            == 2
        )
        assert len(site_audit.get_needs_action_table().rows) == 2

    @responses.activate
    def test_audit_study_sites_with_site_update(self):
        ResearchCenter.objects.create(
            drupal_node_id=TEST_STUDY_SITE_DATA[0].drupal_internal__nid,
            short_name="WrongShortName",
            full_name="WrongTitle",
        )
        ResearchCenter.objects.create(
            drupal_node_id=TEST_STUDY_SITE_DATA[1].drupal_internal__nid,
            short_name=TEST_STUDY_SITE_DATA[1].title,
            full_name=TEST_STUDY_SITE_DATA[1].field_long_name,
        )
        self.get_fake_json_api()
        self.add_fake_study_sites_response()
        site_audit = audit.SiteAudit(apply_changes=True)
        site_audit.run_audit()
        self.assertFalse(site_audit.ok())
        self.assertEqual(len(site_audit.needs_action), 1)
        self.assertEqual(len(site_audit.verified), 1)
        self.assertEqual(len(site_audit.errors), 0)
        self.assertEqual(ResearchCenter.objects.all().count(), 2)

        first_test_ss = ResearchCenter.objects.get(short_name=TEST_STUDY_SITE_DATA[0].title)
        # did we update the long name
        assert first_test_ss.full_name == TEST_STUDY_SITE_DATA[0].field_long_name
        assert first_test_ss.short_name == TEST_STUDY_SITE_DATA[0].title

    @responses.activate
    def test_audit_study_sites_with_extra_site(self):
        ResearchCenter.objects.create(drupal_node_id=99, short_name="ExtraSite", full_name="ExtraSiteLong")
        self.get_fake_json_api()
        self.add_fake_study_sites_response()
        site_audit = audit.SiteAudit(apply_changes=True)
        site_audit.run_audit()
        self.assertFalse(site_audit.ok())
        self.assertEqual(len(site_audit.errors), 1)
        self.assertEqual(ResearchCenter.objects.all().count(), 3)
        assert len(site_audit.get_errors_table().rows) == 1

    @responses.activate
    def test_full_user_audit(self):
        self.add_fake_token_response()
        self.add_fake_study_sites_response()
        self.add_fake_users_response()
        ResearchCenter.objects.create(
            drupal_node_id=TEST_STUDY_SITE_DATA[0].drupal_internal__nid,
            short_name=TEST_STUDY_SITE_DATA[0].title,
            full_name=TEST_STUDY_SITE_DATA[0].field_long_name,
        )
        user_audit = audit.UserAudit(apply_changes=True)
        user_audit.run_audit()

        self.assertFalse(user_audit.ok())
        self.assertEqual(len(user_audit.needs_action), 1)

        users = get_user_model().objects.all()
        assert users.count() == 1

        assert users.first().email == TEST_USER_DATA[0].mail
        assert users.first().username == TEST_USER_DATA[0].name
        assert users.first().research_centers.count() == 1
        assert users.first().research_centers.first().short_name == TEST_STUDY_SITE_DATA[0].title

    @responses.activate
    def test_full_user_audit_check_only(self):
        self.add_fake_token_response()
        self.add_fake_study_sites_response()
        self.add_fake_users_response()
        ResearchCenter.objects.create(
            drupal_node_id=TEST_STUDY_SITE_DATA[0].drupal_internal__nid,
            short_name=TEST_STUDY_SITE_DATA[0].title,
            full_name=TEST_STUDY_SITE_DATA[0].field_long_name,
        )
        user_audit = audit.UserAudit(apply_changes=False)
        user_audit.run_audit()
        self.assertFalse(user_audit.ok())
        self.assertEqual(len(user_audit.needs_action), 1)

        # verify we did not actually create a user
        users = get_user_model().objects.all()
        assert users.count() == 0

    @responses.activate
    def test_user_audit_remove_site_inform(self):
        self.add_fake_token_response()
        self.add_fake_study_sites_response()
        self.add_fake_users_response()
        ss1 = ResearchCenter.objects.create(
            drupal_node_id=TEST_STUDY_SITE_DATA[1].drupal_internal__nid,
            short_name=TEST_STUDY_SITE_DATA[1].title,
            full_name=TEST_STUDY_SITE_DATA[1].field_long_name,
        )
        drupal_fullname = "{} {}".format(
            TEST_USER_DATA[0].field_given_first_name_s_,
            TEST_USER_DATA[0].field_examples_family_last_name_,
        )
        drupal_username = TEST_USER_DATA[0].name
        drupal_email = TEST_USER_DATA[0].mail
        new_user = get_user_model().objects.create(
            username=drupal_username + "UPDATE",
            email=drupal_email + "UPDATE",
            name=drupal_fullname + "UPDATE",
        )
        new_user.research_centers.add(ss1)
        SocialAccount.objects.create(
            user=new_user,
            uid=TEST_USER_DATA[0].drupal_internal__uid,
            provider=CustomProvider.id,
        )
        user_audit = audit.UserAudit(apply_changes=False)
        user_audit.run_audit()
        self.assertFalse(user_audit.ok())
        self.assertEqual(len(user_audit.errors), 1)

        new_user.refresh_from_db()
        # assert we did not remove the site
        assert ss1 in new_user.research_centers.all()

    @responses.activate
    def test_user_audit_remove_site_act(self):
        self.add_fake_token_response()
        self.add_fake_study_sites_response()
        self.add_fake_users_response()
        ss1 = ResearchCenter.objects.create(
            drupal_node_id=TEST_STUDY_SITE_DATA[1].drupal_internal__nid,
            short_name=TEST_STUDY_SITE_DATA[1].title,
            full_name=TEST_STUDY_SITE_DATA[1].field_long_name,
        )
        drupal_fullname = "{} {}".format(
            TEST_USER_DATA[0].field_given_first_name_s_,
            TEST_USER_DATA[0].field_examples_family_last_name_,
        )
        drupal_username = TEST_USER_DATA[0].name
        drupal_email = TEST_USER_DATA[0].mail
        new_user = get_user_model().objects.create(
            username=drupal_username + "UPDATE",
            email=drupal_email + "UPDATE",
            name=drupal_fullname + "UPDATE",
        )
        new_user.research_centers.add(ss1)
        SocialAccount.objects.create(
            user=new_user,
            uid=TEST_USER_DATA[0].drupal_internal__uid,
            provider=CustomProvider.id,
        )
        with self.settings(DRUPAL_DATA_AUDIT_REMOVE_USER_SITES=True):
            user_audit = audit.UserAudit(apply_changes=True)
            user_audit.run_audit()
            self.assertFalse(user_audit.ok())
            new_user.refresh_from_db()
            # assert we did remove the site
            assert ss1 not in new_user.research_centers.all()

    @responses.activate
    def test_user_audit_change_user(self):
        self.add_fake_token_response()
        self.add_fake_study_sites_response()
        self.add_fake_users_response()
        ResearchCenter.objects.create(
            drupal_node_id=TEST_STUDY_SITE_DATA[0].drupal_internal__nid,
            short_name=TEST_STUDY_SITE_DATA[0].title,
            full_name=TEST_STUDY_SITE_DATA[0].field_long_name,
        )
        drupal_fullname = "{} {}".format(
            TEST_USER_DATA[0].field_given_first_name_s_,
            TEST_USER_DATA[0].field_examples_family_last_name_,
        )
        drupal_username = TEST_USER_DATA[0].name
        drupal_email = TEST_USER_DATA[0].mail
        new_user = get_user_model().objects.create(
            username=drupal_username + "UPDATE",
            email=drupal_email + "UPDATE",
            name=drupal_fullname + "UPDATE",
            is_active=False,
        )
        SocialAccount.objects.create(
            user=new_user,
            uid=TEST_USER_DATA[0].drupal_internal__uid,
            provider=CustomProvider.id,
        )
        user_audit = audit.UserAudit(apply_changes=True)
        user_audit.run_audit()
        self.assertFalse(user_audit.ok())
        new_user.refresh_from_db()

        self.assertEqual(new_user.name, drupal_fullname)
        self.assertEqual(len(user_audit.needs_action), 1)

    # test user removal
    @responses.activate
    def test_user_audit_remove_user_only_inform(self):
        self.add_fake_token_response()
        self.add_fake_study_sites_response()
        self.add_fake_users_response()
        ResearchCenter.objects.create(
            drupal_node_id=TEST_STUDY_SITE_DATA[0].drupal_internal__nid,
            short_name=TEST_STUDY_SITE_DATA[0].title,
            full_name=TEST_STUDY_SITE_DATA[0].field_long_name,
        )

        new_user = get_user_model().objects.create(username="username2", email="useremail2", name="user fullname2")
        SocialAccount.objects.create(
            user=new_user,
            uid=999,
            provider=CustomProvider.id,
        )
        user_audit = audit.UserAudit(apply_changes=True)
        user_audit.run_audit()
        self.assertFalse(user_audit.ok())

        new_user.refresh_from_db()
        self.assertTrue(new_user.is_active)

    # test user removal
    @responses.activate
    def test_user_audit_remove_user(self):
        self.add_fake_token_response()
        self.add_fake_study_sites_response()
        self.add_fake_users_response()
        ResearchCenter.objects.create(
            drupal_node_id=TEST_STUDY_SITE_DATA[0].drupal_internal__nid,
            short_name=TEST_STUDY_SITE_DATA[0].title,
            full_name=TEST_STUDY_SITE_DATA[0].field_long_name,
        )

        new_user = get_user_model().objects.create(username="username2", email="useremail2", name="user fullname2")
        SocialAccount.objects.create(
            user=new_user,
            uid=999,
            provider=CustomProvider.id,
        )
        new_anvil_account = Account.objects.create(
            user=new_user,
            is_service_account=False,
        )
        new_anvil_managed_group = ManagedGroup.objects.create(
            name="testgroup",
            email="testgroup@testgroup.org",
        )
        GroupAccountMembership.objects.create(
            group=new_anvil_managed_group,
            account=new_anvil_account,
            role=GroupAccountMembership.MEMBER,
        )

        with self.settings(DRUPAL_DATA_AUDIT_DEACTIVATE_USERS=True):
            user_audit = audit.UserAudit(apply_changes=True)
            user_audit.run_audit()
            self.assertFalse(user_audit.ok())
            self.assertEqual(len(user_audit.errors), 1)
            self.assertEqual(user_audit.errors[0].anvil_account, new_anvil_account)
            self.assertIn("InactiveAnvilUser", user_audit.get_errors_table().render_to_text())
            self.assertEqual(len(user_audit.needs_action), 2)
            new_user.refresh_from_db()
            self.assertFalse(new_user.is_active)

    # test user removal
    @responses.activate
    def test_user_audit_remove_user_threshold(self):
        self.add_fake_token_response()
        self.add_fake_study_sites_response()
        self.add_fake_users_response()
        ResearchCenter.objects.create(
            drupal_node_id=TEST_STUDY_SITE_DATA[0].drupal_internal__nid,
            short_name=TEST_STUDY_SITE_DATA[0].title,
            full_name=TEST_STUDY_SITE_DATA[0].field_long_name,
        )

        SocialAccount.objects.create(
            user=get_user_model().objects.create(username="username2", email="useremail2", name="user fullname2"),
            uid=996,
            provider=CustomProvider.id,
        )

        SocialAccount.objects.create(
            user=get_user_model().objects.create(username="username3", email="useremail3", name="user fullname3"),
            uid=997,
            provider=CustomProvider.id,
        )

        SocialAccount.objects.create(
            user=get_user_model().objects.create(username="username4", email="useremail4", name="user fullname4"),
            uid=998,
            provider=CustomProvider.id,
        )
        SocialAccount.objects.create(
            user=get_user_model().objects.create(username="username5", email="useremail5", name="user fullname5"),
            uid=999,
            provider=CustomProvider.id,
        )
        with self.settings(DRUPAL_DATA_AUDIT_DEACTIVATE_USERS=True):
            user_audit = audit.UserAudit(apply_changes=False)
            user_audit.run_audit()
            self.assertFalse(user_audit.ok())
            self.assertEqual(len(user_audit.errors), 4)
            self.assertEqual(len(user_audit.needs_action), 1)
            self.assertEqual(user_audit.errors[0].note, "Over Threshold True")
            # Run again with ignore threshold, should move from error to needs action
            user_audit = audit.UserAudit(apply_changes=False, ignore_deactivate_threshold=True)
            user_audit.run_audit()
            self.assertFalse(user_audit.ok())
            self.assertEqual(len(user_audit.errors), 0)
            self.assertEqual(len(user_audit.needs_action), 5)

    @responses.activate
    def test_sync_drupal_data_command(self):
        self.add_fake_token_response()
        self.add_fake_study_sites_response()
        self.add_fake_users_response()
        out = StringIO()
        call_command("sync-drupal-data", stdout=out)
        self.assertIn(
            "SiteAudit summary: status ok: False verified: 0 needs_changes: 2",
            out.getvalue(),
        )

    @responses.activate
    def test_sync_drupal_data_command_with_issues(self):
        ResearchCenter.objects.create(
            drupal_node_id="999999",
            short_name=TEST_STUDY_SITE_DATA[0].title,
            full_name=TEST_STUDY_SITE_DATA[0].field_long_name,
        )

        new_user = get_user_model().objects.create(username="username2", email="useremail2", name="user fullname2")
        SocialAccount.objects.create(
            user=new_user,
            uid=999,
            provider=CustomProvider.id,
        )
        self.add_fake_token_response()
        self.add_fake_study_sites_response()
        self.add_fake_users_response()
        out = StringIO()
        call_command("sync-drupal-data", "--email=test@example.com", stdout=out)
        self.assertIn("SiteAudit summary: status ok: False", out.getvalue())
        self.assertIn("UserAudit summary: status ok: False", out.getvalue())

        self.assertEqual(len(mail.outbox), 1)
        email = mail.outbox[0]
        self.assertEqual(email.to, ["test@example.com"])
        self.assertEqual(email.subject, "[command:sync-drupal-data] report")
