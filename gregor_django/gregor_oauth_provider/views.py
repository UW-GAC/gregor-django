import json
import logging

import jwt
import requests
from allauth.socialaccount import app_settings
from allauth.socialaccount.adapter import get_adapter
from allauth.socialaccount.providers.oauth2.client import OAuth2Error
from allauth.socialaccount.providers.oauth2.views import (
    OAuth2Adapter,
    OAuth2CallbackView,
    OAuth2LoginView,
)

from .provider import CustomProvider

logger = logging.getLogger(__name__)


class CustomAdapter(OAuth2Adapter):
    provider_id = CustomProvider.id

    provider_settings = app_settings.PROVIDERS.get(provider_id, {})

    api_url = provider_settings.get("API_URL")

    # Fetched programmatically, must be reachable from container
    access_token_url = "{}/oauth/token".format(api_url)
    profile_url = "{}/oauth/userinfo".format(api_url)
    public_key_url = "{}/oauth/jwks".format(api_url)

    # Accessed by the user browser, must be reachable by the host
    authorize_url = "{}/oauth/authorize".format(api_url)

    # debug_url is not currently in use. Left here as documenation of available
    # endpoint sometimes used with drupal oauth.
    # requires additional debug permissions for users
    debug_url = "{}/oauth/debug?_format=json".format(api_url)

    def _get_public_key_jwk(self, headers):
        response = requests.get(self.public_key_url, headers=headers)
        response.raise_for_status()

        try:
            data = response.json()
        except json.JSONDecodeError as e:
            raise OAuth2Error("Error retrieving drupal public key.") from e
        else:
            keys = data.get("keys")
            return keys[0]

    def get_public_key(self, headers):

        provider_settings = app_settings.PROVIDERS.get(self.provider_id, {})

        config_public_key = provider_settings.get("PUBLIC_KEY")
        if False and config_public_key:
            return config_public_key

        public_key_jwk = self._get_public_key_jwk(headers)
        try:
            public_key = jwt.algorithms.RSAAlgorithm.from_jwk(
                json.dumps(public_key_jwk)
            )
        except Exception as e:
            logger.error(f"[get_public_key] failed to convert jwk to public key {e}")
        else:
            return public_key

    def get_client_id(self):
        app = get_adapter().get_app(request=None, provider=self.provider_id)
        return app.client_id

    def get_scopes_from_token(self, id_token, headers):
        allowed_audience = self.get_client_id()
        public_key = self.get_public_key(headers)
        scopes = []

        try:
            unverified_header = jwt.get_unverified_header(id_token.token)
            token_payload = jwt.decode(
                id_token.token,
                public_key,
                algorithms=["RS256"],
                leeway=5,  # allow for times to be slightly out of sync pyjwt._verify_nbf
                audience=allowed_audience,
            )
        except jwt.PyJWTError as e:
            logger.error(f"Invalid id_token {e} {id_token.token}")
            raise OAuth2Error("Invalid id_token") from e
        except Exception as e:
            logger.error(
                f"Other exception parsing token {e} header {unverified_header} token {id_token}"
            )
            raise OAuth2Error("Error when decoding token {e}")
        else:
            scopes = token_payload.get("scope")

        return scopes

    def complete_login(self, request, app, token, **kwargs):
        headers = {"Authorization": "Bearer {0}".format(token.token)}

        scopes_granted = self.get_scopes_from_token(token, headers)
        managed_scope_status = self.get_provider().get_provider_managed_scope_status(
            scopes_granted
        )

        resp = requests.get(self.profile_url, headers=headers)
        resp.raise_for_status()
        extra_data = resp.json()
        logger.debug(
            f"[gregor_oauth_provider:complete_login] extra profile data {resp} "
            f"ed: {extra_data} scopes granted {scopes_granted}"
            f" managed_scope_status {managed_scope_status}"
        )
        extra_data["scopes_granted"] = scopes_granted
        extra_data["managed_scope_status"] = managed_scope_status
        social_login = self.get_provider().sociallogin_from_response(
            request, extra_data
        )

        return social_login


oauth2_login = OAuth2LoginView.adapter_view(CustomAdapter)
oauth2_callback = OAuth2CallbackView.adapter_view(CustomAdapter)
