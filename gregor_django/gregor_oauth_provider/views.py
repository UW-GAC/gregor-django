import logging

import requests
from allauth.socialaccount.providers.oauth2.views import (
    OAuth2Adapter,
    OAuth2CallbackView,
    OAuth2LoginView,
)
from django.conf import settings

from .provider import CustomProvider

logger = logging.getLogger(__name__)


class CustomAdapter(OAuth2Adapter):
    provider_id = CustomProvider.id

    # Fetched programmatically, must be reachable from container
    access_token_url = "{}/oauth/token".format(settings.GREGOR_OAUTH_SERVER_BASEURL)
    profile_url = "{}/oauth/userinfo".format(settings.GREGOR_OAUTH_SERVER_BASEURL)

    # Accessed by the user browser, must be reachable by the host
    authorize_url = "{}/oauth/authorize".format(settings.GREGOR_OAUTH_SERVER_BASEURL)

    debug_url = "{}/oauth/debug?_format=json".format(
        settings.GREGOR_OAUTH_SERVER_BASEURL
    )

    # NOTE: trailing slashes in URLs are important, don't miss it

    def complete_login(self, request, app, token, **kwargs):
        headers = {"Authorization": "Bearer {0}".format(token.token)}

        # import jwt
        # token_payload = jwt.decode(token.token, options={"verify_signature": False})
        # scopes granted will contain a list of roles the user has
        # at the drupal site plus any roles granted by the client itself 'oauth_client_user'
        # scopes_granted = token_payload.get('scopes')

        resp = requests.get(self.profile_url, headers=headers)
        resp.raise_for_status()
        extra_data = resp.json()
        logger.debug(
            f"[gregor_oauth_provider:complete_login] extra profile data {extra_data}"
        )

        # Another documented way I found to get roles is to access the oauth/debug
        # endpoint. to do this you need to grant debug oauth token role
        # to the client granted role "oauth_client_user"
        # dresp = None
        # try:
        #     dresp = requests.get(self.debug_url, headers=headers)
        #     logger.info(f"resp {dresp} cont {dresp.content}")
        # except Exception as e:
        #     logger.error(f'Failed to get oauth debug: {dresp} {e}')

        return self.get_provider().sociallogin_from_response(request, extra_data)


oauth2_login = OAuth2LoginView.adapter_view(CustomAdapter)
oauth2_callback = OAuth2CallbackView.adapter_view(CustomAdapter)
