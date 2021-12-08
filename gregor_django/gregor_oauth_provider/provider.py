import logging

from allauth.socialaccount import providers
from allauth.socialaccount.providers.base import ProviderAccount
from allauth.socialaccount.providers.oauth2.provider import OAuth2Provider
from django.conf import settings

logger = logging.getLogger(__name__)


class CustomAccount(ProviderAccount):
    pass


class CustomProvider(OAuth2Provider):

    id = "gregor_oauth_provider"
    name = "Gregor Drupal OAuth2 Provider"
    account_class = CustomAccount

    def extract_uid(self, data):
        return str(data["sub"])

    def extract_common_fields(self, data):
        return dict(
            username=data["name"],
            email=data["email"],
        )

    def get_default_scope(self):
        scope = []
        if hasattr(settings, "GREGOR_OAUTH_REQUESTED_SCOPES"):
            scope = settings.GREGOR_OAUTH_REQUESTED_SCOPES
        return scope


providers.registry.register(CustomProvider)
