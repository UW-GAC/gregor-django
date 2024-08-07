import pytest
from allauth.account import app_settings as account_settings
from allauth.socialaccount.helpers import complete_social_login
from allauth.socialaccount.models import SocialAccount, SocialLogin
from allauth.utils import get_user_model
from django.contrib.auth.models import AnonymousUser
from django.contrib.messages.middleware import MessageMiddleware
from django.contrib.sessions.middleware import SessionMiddleware
from django.core.exceptions import ImproperlyConfigured
from django.test.client import RequestFactory
from django.test.utils import override_settings

from gregor_django.gregor_anvil.tests.factories import (
    PartnerGroupFactory,
    ResearchCenterFactory,
)
from gregor_django.users.adapters import AccountAdapter, SocialAccountAdapter

from .factories import GroupFactory, UserFactory


@pytest.mark.django_db
class TestsUserSocialLoginAdapter(object):
    @override_settings(
        SOCIALACCOUNT_AUTO_SIGNUP=True,
        ACCOUNT_SIGNUP_FORM_CLASS=None,
        ACCOUNT_EMAIL_VERIFICATION=account_settings.EmailVerificationMethod.NONE,  # noqa
    )
    def test_drupal_social_login_adapter(self):
        factory = RequestFactory()
        request = factory.get("/accounts/login/callback/")
        request.user = AnonymousUser()
        SessionMiddleware(lambda request: None).process_request(request)
        MessageMiddleware(lambda request: None).process_request(request)

        User = get_user_model()
        user = User()
        old_name = "Old Name"
        old_username = "test"
        old_email = "test@example.com"
        setattr(user, account_settings.USER_MODEL_USERNAME_FIELD, "test")
        setattr(user, "name", "Old Name")
        setattr(user, account_settings.USER_MODEL_EMAIL_FIELD, "test@example.com")

        account = SocialAccount(
            provider="drupal_oauth_provider",
            uid="123",
            extra_data=dict(
                first_name="Old",
                last_name="Name",
                email=old_email,
                preferred_username=old_username,
            ),
        )
        sociallogin = SocialLogin(user=user, account=account)
        complete_social_login(request, sociallogin)

        user = User.objects.get(**{account_settings.USER_MODEL_USERNAME_FIELD: "test"})
        assert SocialAccount.objects.filter(user=user, uid=account.uid).exists() is True
        assert user.name == old_name
        assert user.username == old_username
        assert user.email == old_email

    def test_update_user_info(self):
        adapter = SocialAccountAdapter()

        User = get_user_model()
        user = User()
        new_first_name = "New"
        new_last_name = "Name"
        new_name = f"{new_first_name} {new_last_name}"
        new_email = "newemail@example.com"
        new_username = "newusername"
        setattr(user, account_settings.USER_MODEL_USERNAME_FIELD, "test")
        setattr(user, "name", "Old Name")
        setattr(user, account_settings.USER_MODEL_EMAIL_FIELD, "test@example.com")

        user.save()

        adapter.update_user_info(
            user,
            dict(
                first_name=new_first_name,
                last_name=new_last_name,
                email=new_email,
                preferred_username=new_username,
            ),
        )
        assert user.name == new_name
        assert user.email == new_email
        assert user.username == new_username

    def test_update_user_research_centers_add(self):
        adapter = SocialAccountAdapter()
        rc1 = ResearchCenterFactory(short_name="rc1")

        User = get_user_model()
        user = User()
        setattr(user, account_settings.USER_MODEL_USERNAME_FIELD, "test")
        setattr(user, account_settings.USER_MODEL_EMAIL_FIELD, "test@example.com")

        user.save()

        adapter.update_user_research_centers(user, dict(research_center_or_site=[rc1.full_name]))
        assert user.research_centers.filter(pk=rc1.pk).exists()
        assert user.research_centers.all().count() == 1

    def test_update_user_research_centers_remove(self):
        adapter = SocialAccountAdapter()
        rc1 = ResearchCenterFactory(short_name="rc1")
        rc2 = ResearchCenterFactory(short_name="rc2")

        User = get_user_model()
        user = User()
        setattr(user, account_settings.USER_MODEL_USERNAME_FIELD, "test")
        setattr(user, account_settings.USER_MODEL_EMAIL_FIELD, "test@example.com")

        user.save()
        user.research_centers.add(rc1, rc2)
        assert user.research_centers.all().count() == 2

        adapter.update_user_research_centers(user, dict(research_center_or_site=[rc1.full_name]))
        assert user.research_centers.filter(pk=rc1.pk).exists()
        assert user.research_centers.all().count() == 1

        adapter.update_user_research_centers(user, dict(research_center_or_site=None))
        assert user.research_centers.all().count() == 0

    def test_update_research_centers_malformed(self):
        adapter = SocialAccountAdapter()
        user = UserFactory()
        with pytest.raises(ImproperlyConfigured):
            adapter.update_user_research_centers(user, dict(research_center_or_site="FOO"))

    def test_update_user_research_centers_unknown(self):
        adapter = SocialAccountAdapter()
        user = UserFactory()
        adapter.update_user_research_centers(user, dict(research_center_or_site=["UNKNOWN"]))
        assert user.research_centers.all().count() == 0

    def test_update_user_groups_add(self):
        adapter = SocialAccountAdapter()
        g1 = GroupFactory(name="g1")

        User = get_user_model()
        user = User()
        setattr(user, account_settings.USER_MODEL_USERNAME_FIELD, "test")
        setattr(user, account_settings.USER_MODEL_EMAIL_FIELD, "test@example.com")

        user.save()

        adapter.update_user_groups(user, extra_data=dict(managed_scope_status={g1.name: True}))
        assert user.groups.filter(pk=g1.pk).exists()
        assert user.groups.all().count() == 1

    # Partner Groups

    def test_update_user_partner_groups_add(self):
        adapter = SocialAccountAdapter()
        pg1 = PartnerGroupFactory(short_name="pg1")
        pg2 = PartnerGroupFactory(short_name="pg2")

        User = get_user_model()
        user = User()
        setattr(user, account_settings.USER_MODEL_USERNAME_FIELD, "test")
        setattr(user, account_settings.USER_MODEL_EMAIL_FIELD, "test@example.com")

        user.save()

        adapter.update_user_partner_groups(user, dict(partner_group=[pg1.short_name]))
        assert user.partner_groups.filter(pk=pg1.pk).exists()
        assert user.partner_groups.all().count() == 1

        # test full_name as well
        adapter.update_user_partner_groups(user, dict(partner_group=[pg2.full_name]))
        assert user.partner_groups.filter(pk=pg2.pk).exists()
        assert user.partner_groups.all().count() == 1

    def test_update_user_partner_groups_remove(self):
        adapter = SocialAccountAdapter()
        pg1 = PartnerGroupFactory(short_name="pg1")
        pg2 = PartnerGroupFactory(short_name="pg2")

        User = get_user_model()
        user = User()
        setattr(user, account_settings.USER_MODEL_USERNAME_FIELD, "test")
        setattr(user, account_settings.USER_MODEL_EMAIL_FIELD, "test@example.com")

        user.save()
        user.partner_groups.add(pg1, pg2)
        assert user.partner_groups.all().count() == 2

        adapter.update_user_partner_groups(user, dict(partner_group=[pg1.short_name]))
        assert user.partner_groups.filter(pk=pg1.pk).exists()
        assert user.partner_groups.all().count() == 1

        adapter.update_user_partner_groups(user, dict(partner_group=None))
        assert user.partner_groups.all().count() == 0

    def test_update_partner_groups_malformed(self):
        adapter = SocialAccountAdapter()
        user = UserFactory()
        with pytest.raises(ImproperlyConfigured):
            adapter.update_user_partner_groups(user, dict(partner_group="FOO"))

    def test_update_user_partner_groups_unknown(self):
        adapter = SocialAccountAdapter()
        user = UserFactory()
        adapter.update_user_partner_groups(user, dict(partner_group=["UNKNOWN"]))
        assert user.partner_groups.all().count() == 0

    def test_update_user_groups_create(self):
        adapter = SocialAccountAdapter()

        User = get_user_model()
        user = User()
        setattr(user, account_settings.USER_MODEL_USERNAME_FIELD, "test")
        setattr(user, account_settings.USER_MODEL_EMAIL_FIELD, "test@example.com")

        user.save()

        adapter.update_user_groups(user, extra_data=dict(managed_scope_status={"CREATE_GROUP": True}))
        assert user.groups.filter(name="CREATE_GROUP").exists()
        assert user.groups.all().count() == 1

    def test_update_user_groups_remove(self):
        adapter = SocialAccountAdapter()
        rc1 = GroupFactory(name="g1")
        rc2 = GroupFactory(name="g2")

        User = get_user_model()
        user = User()
        setattr(user, account_settings.USER_MODEL_USERNAME_FIELD, "test")
        setattr(user, account_settings.USER_MODEL_EMAIL_FIELD, "test@example.com")

        user.save()
        user.groups.add(rc1, rc2)
        assert user.groups.all().count() == 2

        adapter.update_user_groups(
            user,
            extra_data=dict(managed_scope_status={rc1.name: True, rc2.name: False}),
        )
        assert user.groups.filter(pk=rc1.pk).exists()
        assert not user.groups.filter(pk=rc2.pk).exists()
        assert user.groups.all().count() == 1

    def test_update_user_groups_malformed(self):
        adapter = SocialAccountAdapter()
        user = UserFactory()
        with pytest.raises(ImproperlyConfigured):
            adapter.update_user_groups(user, dict(managed_scope_status="FOO"))

    @override_settings(ACCOUNT_ALLOW_REGISTRATION=True)
    def test_account_is_open_for_signup(self):
        request = RequestFactory()
        adapter = AccountAdapter()
        assert adapter.is_open_for_signup(request) is True

    @override_settings(ACCOUNT_ALLOW_REGISTRATION=False)
    def test_account_is_not_open_for_signup(self):
        request = RequestFactory()
        adapter = AccountAdapter()
        assert adapter.is_open_for_signup(request) is False
