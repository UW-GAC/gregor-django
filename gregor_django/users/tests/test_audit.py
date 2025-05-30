import json
import time
from io import StringIO

import responses
from allauth.socialaccount.models import SocialAccount
from anvil_consortium_manager.models import Account, GroupAccountMembership, GroupGroupMembership, ManagedGroup
from anvil_consortium_manager.tests.factories import (
    GroupGroupMembershipFactory,
    ManagedGroupFactory,
)
from django.conf import settings
from django.contrib.auth import get_user_model
from django.core import mail
from django.core.management import call_command
from django.test import TestCase
from marshmallow_jsonapi import Schema, fields

from gregor_django.drupal_oauth_provider.provider import CustomProvider
from gregor_django.users import audit
from gregor_django.users.models import PartnerGroup, ResearchCenter


class ResearchCenterMockObject:
    def __init__(self, id, title, field_short_name, drupal_internal__nid) -> None:
        self.id = id
        self.title = title
        self.field_short_name = field_short_name
        self.drupal_internal__nid = drupal_internal__nid


class PartnerGroupMockObject:
    def __init__(self, id, title, drupal_internal__nid, field_status):
        self.id = id
        self.title = title
        self.full_name = title
        self.drupal_internal__nid = drupal_internal__nid
        self.field_status = field_status


class UserMockObject:
    def __init__(
        self,
        id,
        display_name,
        drupal_internal__uid,
        name,
        mail,
        field_fname,
        field_lname,
        field_research_center_or_site,
    ) -> None:
        self.id = id
        self.display_name = display_name
        self.drupal_internal__uid = drupal_internal__uid
        self.name = name
        self.mail = mail
        self.field_fname = field_fname
        self.field_lname = field_lname
        self.field_research_center_or_site = field_research_center_or_site


class ResearchCenterSchema(Schema):
    id = fields.Str(dump_only=True)
    field_short_name = fields.Str()
    title = fields.Str()
    drupal_internal__nid = fields.Str()
    # document_meta = fields.DocumentMeta()

    class Meta:
        type_ = "node--research_center"


class PartnerGroupSchema(Schema):
    id = fields.Str(dump_only=True)
    title = fields.Str()
    drupal_internal__nid = fields.Str()
    field_status = fields.Str()

    class Meta:
        type_ = "node--partner_group"


class UserSchema(Schema):
    id = fields.Str(dump_only=True)
    display_name = fields.Str()
    drupal_internal__uid = fields.Str()
    name = fields.Str()
    mail = fields.Str()
    field_fname = fields.Str()
    field_lname = fields.Str()
    field_research_center_or_site = fields.Relationship(
        many=True, schema="ResearchCenterSchema", type_="node--research_center"
    )
    field_partner_member_group = fields.Relationship(
        many=True, schema="PartnerGroupSchema", type_="node--partner_group"
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
            "field_short_name": "SS1",
            "title": "S S 1",
            # "document_meta": {"page": {"offset": 10}},
        }
    ),
    ResearchCenterMockObject(
        **{
            "id": "2",
            "drupal_internal__nid": "2",
            "field_short_name": "SS2",
            "title": "S S 2",
            # "document_meta": {"page": {"offset": 10}},
        }
    ),
]

TEST_PARTNER_GROUP_DATA = [
    PartnerGroupMockObject(
        **{
            "id": "11",
            "title": "Partner Group 11",
            "drupal_internal__nid": "11",
            "field_status": PartnerGroup.StatusTypes.ACTIVE,
        }
    ),
    PartnerGroupMockObject(
        **{
            "id": "22",
            "title": "Partner Group 22",
            "drupal_internal__nid": "22",
            "field_status": PartnerGroup.StatusTypes.INACTIVE,
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
            "field_fname": "test1",
            "field_lname": "user1",
            "field_research_center_or_site": [],
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
            "field_fname": "test2",
            "field_lname": "user2",
            "field_research_center_or_site": [],
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
        url_path = f"{settings.DRUPAL_SITE_URL}/{settings.DRUPAL_API_REL_PATH}/node/research_center/"
        responses.get(
            url=url_path,
            body=json.dumps(ResearchCenterSchema(many=True).dump(TEST_STUDY_SITE_DATA)),
        )

    def add_fake_partner_groups_response(self):
        url_path = f"{settings.DRUPAL_SITE_URL}/{settings.DRUPAL_API_REL_PATH}/node/partner_group/"
        responses.get(
            url=url_path,
            body=json.dumps(PartnerGroupSchema(many=True).dump(TEST_PARTNER_GROUP_DATA)),
        )

    def add_fake_users_response(self):
        url_path = f"{settings.DRUPAL_SITE_URL}/{settings.DRUPAL_API_REL_PATH}/user/user/"
        TEST_USER_DATA[0].field_research_center_or_site = [TEST_STUDY_SITE_DATA[0]]
        user_data = UserSchema(include_data=("field_research_center_or_site",), many=True).dump(TEST_USER_DATA)

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
            assert test_study_site.title == study_sites[test_study_site.drupal_internal__nid]["full_name"]
            assert test_study_site.field_short_name == study_sites[test_study_site.drupal_internal__nid]["short_name"]
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
                    TEST_STUDY_SITE_DATA[0].field_short_name,
                    TEST_STUDY_SITE_DATA[1].field_short_name,
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
            short_name=TEST_STUDY_SITE_DATA[1].field_short_name,
            full_name=TEST_STUDY_SITE_DATA[1].title,
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

        first_test_ss = ResearchCenter.objects.get(short_name=TEST_STUDY_SITE_DATA[0].field_short_name)
        # did we update the long name
        assert first_test_ss.full_name == TEST_STUDY_SITE_DATA[0].title
        assert first_test_ss.short_name == TEST_STUDY_SITE_DATA[0].field_short_name

    @responses.activate
    def test_audit_partner_groups_with_group_update(self):
        PartnerGroup.objects.create(
            drupal_node_id=TEST_PARTNER_GROUP_DATA[0].drupal_internal__nid,
            short_name="WrongShortName",
            full_name="WrongTitle",
            status=PartnerGroup.StatusTypes.INACTIVE,
        )
        PartnerGroup.objects.create(
            drupal_node_id=TEST_PARTNER_GROUP_DATA[1].drupal_internal__nid,
            short_name=audit.partner_group_short_name_from_full_name(TEST_PARTNER_GROUP_DATA[1].title),
            full_name=TEST_PARTNER_GROUP_DATA[1].title,
            status=TEST_PARTNER_GROUP_DATA[1].field_status,
        )
        self.get_fake_json_api()
        self.add_fake_partner_groups_response()
        pg_audit = audit.PartnerGroupAudit(apply_changes=True)
        pg_audit.run_audit()
        self.assertFalse(pg_audit.ok())
        self.assertEqual(len(pg_audit.needs_action), 1)
        self.assertEqual(len(pg_audit.verified), 1)
        self.assertEqual(len(pg_audit.errors), 0)
        self.assertEqual(PartnerGroup.objects.all().count(), 2)

        needs_action_table = pg_audit.get_needs_action_table()
        self.assertIn("UpdatePartnerGroup", needs_action_table.render_to_text())

        first_test_pg = PartnerGroup.objects.get(drupal_node_id=TEST_PARTNER_GROUP_DATA[0].drupal_internal__nid)

        # did we update the long name
        assert first_test_pg.full_name == TEST_PARTNER_GROUP_DATA[0].title
        assert first_test_pg.status == TEST_PARTNER_GROUP_DATA[0].field_status

    @responses.activate
    def test_audit_inactive_partner_groups_in_gregor_all(self):
        PartnerGroup.objects.create(
            drupal_node_id=TEST_PARTNER_GROUP_DATA[0].drupal_internal__nid,
            short_name=audit.partner_group_short_name_from_full_name(TEST_PARTNER_GROUP_DATA[0].title),
            full_name=TEST_PARTNER_GROUP_DATA[0].title,
            status=TEST_PARTNER_GROUP_DATA[0].field_status,
        )
        pg2_nid_id = TEST_PARTNER_GROUP_DATA[1].drupal_internal__nid

        gregor_all_group = ManagedGroupFactory(name="GREGOR_ALL")
        pg_member_group = ManagedGroupFactory(name=f"PG_{pg2_nid_id}_MEMBER_GROUP")
        GroupGroupMembershipFactory.create(
            parent_group=gregor_all_group,
            child_group=pg_member_group,
            role=GroupGroupMembership.MEMBER,
        )
        pg2 = PartnerGroup.objects.create(
            drupal_node_id=pg2_nid_id,
            short_name=audit.partner_group_short_name_from_full_name(TEST_PARTNER_GROUP_DATA[1].title),
            full_name=TEST_PARTNER_GROUP_DATA[1].title,
            status=PartnerGroup.StatusTypes.ACTIVE,
            member_group=pg_member_group,
        )

        self.get_fake_json_api()
        self.add_fake_partner_groups_response()
        pg_audit = audit.PartnerGroupAudit(apply_changes=True)
        pg_audit.run_audit()

        pg2.refresh_from_db()

        self.assertFalse(pg_audit.ok())
        self.assertEqual(len(pg_audit.errors), 1)
        self.assertEqual(PartnerGroup.objects.all().count(), 2)

        # Verify that status was updated by the audit
        self.assertEqual(pg2.status, PartnerGroup.StatusTypes.INACTIVE)
        # Verify our partner group that is inactive and a member of GREGOR_ALL
        # is reported as an error in our audit.
        errors_table = pg_audit.get_errors_table()
        self.assertIn("MembershipIssuePartnerGroup", errors_table.render_to_text())

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
    def test_audit_partner_groups_with_extra_group(self):
        PartnerGroup.objects.create(drupal_node_id=99, short_name="ExtraPG", full_name="ExtraPartnerGroupLong")
        self.get_fake_json_api()
        self.add_fake_partner_groups_response()
        pg_audit = audit.PartnerGroupAudit(apply_changes=True)
        pg_audit.run_audit()
        self.assertFalse(pg_audit.ok())
        self.assertEqual(len(pg_audit.errors), 1)
        self.assertEqual(PartnerGroup.objects.all().count(), 3)
        assert len(pg_audit.get_errors_table().rows) == 1

    @responses.activate
    def test_full_user_audit(self):
        self.add_fake_token_response()
        self.add_fake_study_sites_response()
        self.add_fake_partner_groups_response()
        self.add_fake_users_response()
        ResearchCenter.objects.create(
            drupal_node_id=TEST_STUDY_SITE_DATA[0].drupal_internal__nid,
            short_name=TEST_STUDY_SITE_DATA[0].field_short_name,
            full_name=TEST_STUDY_SITE_DATA[0].title,
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
        assert users.first().research_centers.first().short_name == TEST_STUDY_SITE_DATA[0].field_short_name

    @responses.activate
    def test_full_user_audit_check_only(self):
        self.add_fake_token_response()
        self.add_fake_study_sites_response()
        self.add_fake_users_response()
        ResearchCenter.objects.create(
            drupal_node_id=TEST_STUDY_SITE_DATA[0].drupal_internal__nid,
            short_name=TEST_STUDY_SITE_DATA[0].field_short_name,
            full_name=TEST_STUDY_SITE_DATA[0].title,
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
            short_name=TEST_STUDY_SITE_DATA[1].field_short_name,
            full_name=TEST_STUDY_SITE_DATA[1].title,
        )
        drupal_fullname = "{} {}".format(
            TEST_USER_DATA[0].field_fname,
            TEST_USER_DATA[0].field_lname,
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
            short_name=TEST_STUDY_SITE_DATA[1].field_short_name,
            full_name=TEST_STUDY_SITE_DATA[1].title,
        )
        drupal_fullname = "{} {}".format(
            TEST_USER_DATA[0].field_fname,
            TEST_USER_DATA[0].field_lname,
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
            short_name=TEST_STUDY_SITE_DATA[0].field_short_name,
            full_name=TEST_STUDY_SITE_DATA[0].title,
        )
        drupal_fullname = "{} {}".format(
            TEST_USER_DATA[0].field_fname,
            TEST_USER_DATA[0].field_lname,
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
            short_name=TEST_STUDY_SITE_DATA[0].field_short_name,
            full_name=TEST_STUDY_SITE_DATA[0].title,
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
            short_name=TEST_STUDY_SITE_DATA[0].field_short_name,
            full_name=TEST_STUDY_SITE_DATA[0].title,
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
            short_name=TEST_STUDY_SITE_DATA[0].field_short_name,
            full_name=TEST_STUDY_SITE_DATA[0].title,
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
        with self.settings(DRUPAL_DATA_AUDIT_DEACTIVATE_USERS=True, DRUPAL_DATA_AUDIT_DEACTIVATE_USER_THRESHOLD=3):
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
        self.add_fake_partner_groups_response()
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
            short_name=TEST_STUDY_SITE_DATA[0].field_short_name,
            full_name=TEST_STUDY_SITE_DATA[0].title,
        )
        PartnerGroup.objects.create(
            drupal_node_id="999999",
            short_name=audit.partner_group_short_name_from_full_name(TEST_PARTNER_GROUP_DATA[0].title),
            full_name=TEST_PARTNER_GROUP_DATA[0].title,
        )
        new_user = get_user_model().objects.create(username="username2", email="useremail2", name="user fullname2")
        SocialAccount.objects.create(
            user=new_user,
            uid=999,
            provider=CustomProvider.id,
        )
        self.add_fake_token_response()
        self.add_fake_study_sites_response()
        self.add_fake_partner_groups_response()
        self.add_fake_users_response()
        out = StringIO()
        call_command("sync-drupal-data", "--email=test@example.com", stdout=out)
        self.assertIn("SiteAudit summary: status ok: False", out.getvalue())
        self.assertIn("UserAudit summary: status ok: False", out.getvalue())
        self.assertIn("PartnerGroupAudit summary: status ok: False", out.getvalue())

        self.assertEqual(len(mail.outbox), 1)
        email = mail.outbox[0]
        self.assertEqual(email.to, ["test@example.com"])
        self.assertEqual(email.subject, "[command:sync-drupal-data] report")
