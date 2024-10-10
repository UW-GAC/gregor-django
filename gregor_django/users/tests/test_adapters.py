# myapp/tests.py

import pytest
from allauth.account import app_settings as account_settings
from allauth.account import signals
from allauth.socialaccount.models import SocialAccount, SocialApp, SocialLogin
from django.contrib.auth import get_user_model
from django.contrib.auth.middleware import AuthenticationMiddleware
from django.contrib.auth.models import AnonymousUser
from django.contrib.sessions.middleware import SessionMiddleware
from django.contrib.sites.models import Site
from django.core.exceptions import ImproperlyConfigured
from django.test import TestCase
from django.test.client import RequestFactory
from django.test.utils import override_settings

from gregor_django.drupal_oauth_provider.provider import CustomProvider
from gregor_django.gregor_anvil.tests.factories import (
    PartnerGroupFactory,
    ResearchCenterFactory,
)
from gregor_django.users.adapters import AccountAdapter, SocialAccountAdapter

from .factories import GroupFactory, UserFactory

User = get_user_model()


class SocialAccountAdapterTest(TestCase):
    def setUp(self):
        self.factory = RequestFactory()
        # Setup a mock social app
        current_site = Site.objects.get_current()
        self.social_app = SocialApp.objects.create(
            provider=CustomProvider.id,
            name="DOA",
            client_id="test-client-id",
            secret="test-client-secret",
        )
        self.social_app.sites.add(current_site)

    def test_social_login_success(self):
        # Mock user
        request = self.factory.get("/")
        middleware = SessionMiddleware(lambda x: None)
        middleware.process_request(request)
        request.session.save()
        middleware = AuthenticationMiddleware(lambda x: None)
        middleware.process_request(request)
        request.user = AnonymousUser()
        user = User.objects.create(username="testuser", email="testuser@example.com")

        # # Mock social login
        # Create a mock SocialAccount and link it to the user
        new_first_name = "Bob"
        new_last_name = "Rob"
        social_account = SocialAccount.objects.create(
            user=user,
            provider="drupal_oauth_provider",
            uid="12345",
            extra_data={
                "preferred_username": "testuser",
                "first_name": new_first_name,
                "last_name": new_last_name,
                "email": "testuser@example.com",
            },
        )

        # Create a mock SocialLogin object and associate the user and social account
        sociallogin = SocialLogin(user=user, account=social_account)

        # Simulate social login
        from allauth.account.adapter import get_adapter

        # adapter = SocialAccountAdapter()
        adapter = get_adapter(request)

        adapter.login(request, user)

        signals.user_logged_in.send(
            sender=user.__class__,
            request=request,
            user=user,
            sociallogin=sociallogin,
        )
        # Check if the login completed successfully
        self.assertEqual(sociallogin.user, user)
        self.assertEqual(request.user, user)
        self.assertEqual(user.name, f"{new_first_name} {new_last_name}")

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

    def test_update_user_research_centers_short_name_add(self):
        adapter = SocialAccountAdapter()
        rc1 = ResearchCenterFactory(short_name="rc1")

        User = get_user_model()
        user = User()
        setattr(user, account_settings.USER_MODEL_USERNAME_FIELD, "test")
        setattr(user, account_settings.USER_MODEL_EMAIL_FIELD, "test@example.com")

        user.save()

        adapter.update_user_research_centers(user, dict(research_center_or_site=[rc1.short_name]))
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
