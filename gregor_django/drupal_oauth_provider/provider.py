import logging

from allauth.account.models import EmailAddress
from allauth.socialaccount import app_settings, providers
from allauth.socialaccount.providers.base import ProviderAccount
from allauth.socialaccount.providers.oauth2.provider import OAuth2Provider
from django.conf import settings
from django.core.exceptions import ImproperlyConfigured

logger = logging.getLogger(__name__)

DRUPAL_PROVIDER_ID = "drupal_oauth_provider"
DRUPAL_DEFAULT_NAME = "Drupal Simple Oauth"

OVERRIDE_NAME = (
    getattr(settings, "SOCIALACCOUNT_PROVIDERS", {})
    .get(DRUPAL_PROVIDER_ID, {})
    .get("OVERRIDE_NAME", DRUPAL_DEFAULT_NAME)
)


class CustomAccount(ProviderAccount):
    pass


class CustomProvider(OAuth2Provider):

    id = DRUPAL_PROVIDER_ID
    name = OVERRIDE_NAME
    account_class = CustomAccount

    def extract_uid(self, data):
        return str(data["sub"])

    def extract_common_fields(self, data):
        extra_common = super(CustomProvider, self).extract_common_fields(data)

        first_name = data.get("first_name")
        last_name = data.get("last_name")
        full_name = " ".join(part for part in (first_name, last_name) if part)

        extra_common.update(
            username=data["name"],
            email=data["email"],
            first_name=first_name,
            last_name=last_name,
            full_name=full_name,
        )
        return extra_common

    def extract_email_addresses(self, data):
        ret = []
        email = data.get("email")
        verified = data.get("email_verified")
        if isinstance(verified, str):
            verified = verified == "True"
        if email:
            ret.append(
                EmailAddress(
                    email=email,
                    verified=verified,
                    primary=True,
                )
            )
        return ret

    def get_provider_scope_config(self):
        provider_settings = app_settings.PROVIDERS.get(self.id, {})
        gregor_oauth_scopes = provider_settings.get("SCOPES")

        if not gregor_oauth_scopes:
            raise ImproperlyConfigured(
                f"[get_provider_scope_config] missing provider setting SCOPES {provider_settings}"
            )

        if not isinstance(gregor_oauth_scopes, list):
            raise ImproperlyConfigured(
                "[get_provider_scope_config] provider setting SCOPES should be a list"
            )

        return gregor_oauth_scopes

    def get_provider_managed_scope_status(self, scopes_granted=[]):
        provider_managed_django_group_status = {}

        gregor_oauth_scopes = self.get_provider_scope_config()

        for scope_settings in gregor_oauth_scopes:
            drupal_scope_name = scope_settings.get("drupal_machine_name")
            django_group_name = scope_settings.get("django_group_name")
            has_scope = False

            if not drupal_scope_name and django_group_name:
                raise ImproperlyConfigured(
                    f"[get_provider_managed_group_status] GREGOR_OAUTH_SCOPE entry {scope_settings} misconfigured"
                )

            if drupal_scope_name in scopes_granted:
                has_scope = True

            provider_managed_django_group_status[django_group_name] = has_scope

        return provider_managed_django_group_status

    def get_default_scope(self):
        requested_scopes = []
        gregor_oauth_scopes = self.get_provider_scope_config()
        for scope_settings in gregor_oauth_scopes:
            if scope_settings.get("request_scope", False):
                requested_scopes.append(scope_settings.get("drupal_machine_name"))

        return requested_scopes


providers.registry.register(CustomProvider)
