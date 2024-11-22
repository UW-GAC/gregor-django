import base64
import datetime
import hashlib
import json
from urllib.parse import parse_qs, urlparse

import jwt
import requests
from allauth.socialaccount import app_settings
from allauth.socialaccount.adapter import get_adapter
from allauth.socialaccount.models import SocialApp
from allauth.socialaccount.tests import OAuth2TestsMixin
from allauth.tests import MockedResponse, TestCase
from django.conf import settings
from django.contrib.auth import get_user_model
from django.contrib.sites.models import Site
from django.core.exceptions import ImproperlyConfigured
from django.test import RequestFactory
from django.test.utils import override_settings

from .provider import CustomProvider

# Generated on https://mkjwk.org/, used to sign and verify the fake drupal id_token
TESTING_JWT_KEYSET = {
    "p": (
        "1pbtdy7VdVkyRmhQw-OU9q3Ls_j7i-3fhBu71qcr60E43sXspV5iIXsesuUYmhLsPSgnXM_4EUQv8i2B51U5KpnGbZ"
        "_9UNHwzs8r9HVNHvhpmq0f8uUAD1Y8ExKR1aQp_4SlfM6paDdsOxIgDHYhdoaikWFj-q2E9cBt_fFC2g8"
    ),
    "kty": "RSA",
    "q": (
        "y6gIJ572rQKSehHqNJUkakui5qslvmjQcw-dp7IqiSLBe3nC6Q_FEYVxAS9m1HsB10TkVznePT9OP8iLJDtXmZu5c4Z"
        "FxGOf41edyLfc1u6IOM-bQcuPSpFJI3ULff437HhC64tpnE6UxAjxDnujUph7nlagoNFNH7LQxwGbyvM"
    ),
    "d": (
        "iq3Djdurye9T5MX3NfDlNRbmgzkByMhDmcdGFNMWp5O5NjEp9rVEFCIBtdz_MZ0In0tXX1BtZhhpQ2vLtiuNnuo93h"
        "EhtbSXt-E-86Yux1Y7Sib2VcfDRhSoAq0nG5E96YBx25-jKwMpbfNX0S0ucQ-ZK9rA6niuIzRYoSwL1XRNjLFZBiVM"
        "eEbMU9lDCceSngOFu-vdhbOWBIOSmnca_I_Nh9pEBdtInTwq_UqlW2Z6P0akdAV9vxE4W_tFdt_pbD6hBuavb6Di51f"
        "yYozrmkRfb9npi7q_VVgLmapwJ1vovjUPnE7xbs4u_m-dDPOUdtOoKujrxqFPTWOm2Eco5Q"
    ),
    "e": "AQAB",
    "use": "sig",
    "kid": "XQ9a8piY8PpxX1k0DyyVo6U_MEv_YbdTsjWbyplPPeY",
    "qi": (
        "TBvzQy7NaNOY0gTOAjMWkRYHnfQKY63d-yGL8EDxgXMAPDbecPgd0np5CN7_1QXzvPSw5lAbAf7fu5aC9p5iX0x3t"
        "_UpHukeLn50b1tNr9xYjkLTJtVusZWoJ5jcX7J8AhZqg2fxxBJqkl_CYq2Fi_nXExVj8Y5kL47RbrQ3fGc"
    ),
    "dp": (
        "Colqq5l_Hb39e_uPS68XF229PN8S6vIJMaFy_b1DqM-RDU9GqXAS_XXgMgSRyq73LqGUHTiRA7gHaqrVYBiNMAxQ8"
        "_0RITDN1DnT_LLt0IF-Hfw2P2UDNb2UQZN92bGv5j4LKi-zncxq4hOnwzThu8IspVrU3_A5QR_rxrZcA_0"
    ),
    "alg": "RS256",
    "dq": (
        "CsVGOSI1FY1PRdlws3s3w89gPCbNBjbw30TyJ45KpZoK9YbJAh5tY7HU-iURoScoP8RK9zn-QOr6LnFiunXQ-jS8"
        "KBnv0qUaLaHSnGzs5wkSdz6zjVVArMbmQVPNWcp6Fq19jIuA-F1HjN6UMRnk11dtIkCemiK3m3ePhxbUsHU"
    ),
    "n": (
        "qraIL0YD019xdQiVRlgY6ufV2WeVuK40URXQxXZKoZY57rXeNv74Tu1dxSDI35i5XB3JfnLDYbZ0pNc0jU8OPYAHu"
        "8qWB4We6yZwOaZaL55heGHTmhHdJa8VOfF6LsnW3Kxy-zaOaWxaJ7tJDGphq-i35NJsg73RlADYcp5oF5aDxQUkDM"
        "kaXpeqWNaPEIWfOSev4KwIRcHT53w06yFT4O5E6qV46ulISYFcWeH8O4B2ojjx-GktMr0fDhi1O8doK45IQsK7Jb8"
        "tbt3nj5wialUE9BIHtFORPbgtlt9DzcFqF248sAYv9Ry3cVgMJr89Fd3vZLOSreL-ttBn2JnSPQ"
    ),
}


def sign_id_token(payload):
    """
    Sign a payload as drupal normally would for the id_token.
    """
    signing_key = jwt.algorithms.RSAAlgorithm.from_jwk(json.dumps(TESTING_JWT_KEYSET))
    return jwt.encode(
        payload,
        signing_key,
        algorithm="RS256",
        headers={"kid": TESTING_JWT_KEYSET["kid"]},
    )


# Mocked version of the test data from /oauth/jwks
KEY_SERVER_RESP_JSON = json.dumps(
    {
        "keys": [
            {
                "kty": TESTING_JWT_KEYSET["kty"],
                "n": TESTING_JWT_KEYSET["n"],
                "e": TESTING_JWT_KEYSET["e"],
            }
        ]
    }
)


# disable token storing for testing as it conflicts with drupals use
# of tokens for user info
@override_settings(SOCIALACCOUNT_STORE_TOKENS=True)
class CustomProviderTests(OAuth2TestsMixin, TestCase):
    provider_id = CustomProvider.id

    def setUp(self):
        super(CustomProviderTests, self).setUp()
        # workaround to create a session. see:
        # https://code.djangoproject.com/ticket/11475
        User = get_user_model()
        User.objects.create_user("testuser", "testuser@testuser.com", "testpw")
        self.client.login(username="testuser", password="testpw")
        self.setup_time = datetime.datetime.now(datetime.timezone.utc)

    # Provide two mocked responses, first is to the public key request
    # second is used for the profile request for extra data
    def get_mocked_response(self):
        return [
            MockedResponse(200, KEY_SERVER_RESP_JSON),
            MockedResponse(
                200,
                """
        {
            "name": "testmaster",
            "email": "test@testmaster.net",
            "email_verified": "True",
            "sub": "20122"
        }""",
            ),
        ]

    def login(self, resp_mock=None, process="login", with_refresh_token=True):
        """
        Unfortunately due to how our provider works we need to alter
        this test login function as the default one fails.
        """
        with self.mocked_response():
            resp = self.client.post(self.provider.get_login_url(self.request, process=process))
        p = urlparse(resp["location"])
        q = parse_qs(p.query)
        pkce_enabled = app_settings.PROVIDERS.get(self.app.provider, {}).get(
            "OAUTH_PKCE_ENABLED", self.provider.pkce_enabled_default
        )

        self.assertEqual("code_challenge" in q, pkce_enabled)
        self.assertEqual("code_challenge_method" in q, pkce_enabled)
        if pkce_enabled:
            code_challenge = q["code_challenge"][0]
            self.assertEqual(q["code_challenge_method"][0], "S256")

        complete_url = self.provider.get_callback_url()
        self.assertGreater(q["redirect_uri"][0].find(complete_url), 0)
        response_json = self.get_login_response_json(with_refresh_token=with_refresh_token)

        resp_mocks = resp_mock if isinstance(resp_mock, list) else ([resp_mock] if resp_mock is not None else [])

        with self.mocked_response(
            MockedResponse(200, response_json, {"content-type": "application/json"}),
            *resp_mocks,
        ):
            resp = self.client.get(complete_url, self.get_complete_parameters(q))

            # Find the access token POST request, and assert that it contains
            # the correct code_verifier if and only if PKCE is enabled
            request_calls = requests.Session.request.call_args_list

            for args, kwargs in request_calls:
                data = kwargs.get("data", {})
                if (
                    args
                    and args[0] == "POST"
                    and isinstance(data, dict)
                    and data.get("redirect_uri", "").endswith(complete_url)
                ):
                    self.assertEqual("code_verifier" in data, pkce_enabled)

                    if pkce_enabled:
                        hashed_code_verifier = hashlib.sha256(data["code_verifier"].encode("ascii"))
                        expected_code_challenge = (
                            base64.urlsafe_b64encode(hashed_code_verifier.digest()).rstrip(b"=").decode()
                        )
                        self.assertEqual(code_challenge, expected_code_challenge)

        return resp

    def get_id_token(self):
        app = get_adapter().get_app(request=None, provider=self.provider_id)
        allowed_audience = app.client_id
        return sign_id_token(
            {
                "exp": self.setup_time + datetime.timedelta(hours=1),
                "iat": self.setup_time,
                "aud": allowed_audience,
                "scope": ["authenticated", "oauth_client_user"],
                "sub": "20122",
            }
        )

    def get_access_token(self) -> str:
        return self.get_id_token()

    def get_expected_to_str(self):
        return "test@testmaster.net"

    # This login response mimics drupals in that it contains a set of scopes
    # and the uid which has the name sub
    def get_login_response_json(self, with_refresh_token=True):
        id_token = self.get_id_token()
        response_data = {
            "access_token": id_token,
            "expires_in": 3600,
            "id_token": id_token,
            "token_type": "Bearer",
        }
        if with_refresh_token:
            response_data["refresh_token"] = "testrf"
        return json.dumps(response_data)


class TestProviderConfig(TestCase):
    def setUp(self):
        # workaround to create a session. see:
        # https://code.djangoproject.com/ticket/11475
        current_site = Site.objects.get_current()
        app = SocialApp.objects.create(
            provider=CustomProvider.id,
            name=CustomProvider.id,
            client_id="app123id",
            key=CustomProvider.id,
            secret="dummy",
        )
        self.app = app
        self.app.sites.add(current_site)

    def test_custom_provider_no_app(self):
        rf = RequestFactory()
        request = rf.get("/fake-url/")
        provider = CustomProvider(request)
        assert provider.app is not None

    def test_custom_provider_scope_config(self):
        custom_provider_settings = settings.SOCIALACCOUNT_PROVIDERS
        rf = RequestFactory()
        request = rf.get("/fake-url/")
        custom_provider_settings["drupal_oauth_provider"]["SCOPES"] = None
        with override_settings(SOCIALACCOUNT_PROVIDERS=custom_provider_settings):
            with self.assertRaises(ImproperlyConfigured):
                CustomProvider(request, app=self.app).get_provider_scope_config()

    def test_custom_provider_scope_detail_config(self):
        custom_provider_settings = settings.SOCIALACCOUNT_PROVIDERS
        rf = RequestFactory()
        request = rf.get("/fake-url/")
        custom_provider_settings["drupal_oauth_provider"]["SCOPES"] = [
            {
                "z_drupal_machine_name": "X",
                "request_scope": True,
                "django_group_name": "Z",
            }
        ]
        with override_settings(SOCIALACCOUNT_PROVIDERS=custom_provider_settings):
            with self.assertRaises(ImproperlyConfigured):
                CustomProvider(request, app=self.app).get_provider_managed_scope_status()

    def test_custom_provider_has_scope(self):
        custom_provider_settings = settings.SOCIALACCOUNT_PROVIDERS
        rf = RequestFactory()
        request = rf.get("/fake-url/")
        custom_provider_settings["drupal_oauth_provider"]["SCOPES"] = [
            {
                "drupal_machine_name": "X",
                "request_scope": True,
                "django_group_name": "Z",
            }
        ]
        with override_settings(SOCIALACCOUNT_PROVIDERS=custom_provider_settings):
            CustomProvider(request, app=self.app).get_provider_managed_scope_status(scopes_granted=["X"])
