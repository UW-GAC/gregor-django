import requests
from allauth.socialaccount.providers.oauth2.views import (
    OAuth2Adapter,
    OAuth2CallbackView,
    OAuth2LoginView,
)
from django.conf import settings

from .provider import CustomProvider


class CustomAdapter(OAuth2Adapter):
    provider_id = CustomProvider.id

    # Fetched programmatically, must be reachable from container
    access_token_url = "{}/o/token/".format(settings.GREGOR_OAUTH_SERVER_BASEURL)
    profile_url = "{}/profile/".format(settings.GREGOR_OAUTH_SERVER_BASEURL)

    # Accessed by the user browser, must be reachable by the host
    authorize_url = "{}/o/authorize/".format(settings.GREGOR_OAUTH_SERVER_BASEURL)

    # NOTE: trailing slashes in URLs are important, don't miss it

    def complete_login(self, request, app, token, **kwargs):
        headers = {"Authorization": "Bearer {0}".format(token.token)}
        resp = requests.get(self.profile_url, headers=headers)
        extra_data = resp.json()
        return self.get_provider().sociallogin_from_response(request, extra_data)


oauth2_login = OAuth2LoginView.adapter_view(CustomAdapter)
oauth2_callback = OAuth2CallbackView.adapter_view(CustomAdapter)
