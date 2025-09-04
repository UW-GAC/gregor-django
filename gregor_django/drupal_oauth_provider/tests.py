import datetime
import json
from unittest.mock import Mock, patch

import jwt
import responses
from allauth.socialaccount.adapter import get_adapter
from allauth.socialaccount.models import SocialAccount, SocialApp
from django.conf import settings
from django.contrib.auth import get_user_model
from django.contrib.sites.models import Site
from django.core.exceptions import ImproperlyConfigured
from django.test import Client, RequestFactory, TestCase
from django.test.utils import override_settings
from django.urls import reverse

from .provider import CustomProvider
from .views import CustomAdapter

User = get_user_model()

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

KEY_SERVER_RESP_JSON = {
    "keys": [
        {
            "kty": TESTING_JWT_KEYSET["kty"],
            "n": TESTING_JWT_KEYSET["n"],
            "e": TESTING_JWT_KEYSET["e"],
        }
    ]
}

INVALID_KEY_RESP_JSON = {"keys": [{"kty": "TEST", "n": "TEST", "e": "TEST"}]}

USER_INFO_RESP_JSON = {
    "name": "testmaster",
    "preferred_username": "testmaster",
    "email": "test@testmaster.net",
    "email_verified": "True",
    "sub": "20122",
}
EXISTING_USER_RESP_JSON = {
    "name": "existinguser",
    "preferred_username": "existinguser",
    "email": "testuser@example.com",
    "email_verified": "True",
    "sub": "99999",
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


class CustomProviderLoginTest(TestCase):
    def setUp(self):
        """Set up test fixtures"""
        self.client = Client()
        self.setup_time = datetime.datetime.now(datetime.timezone.utc)
        # Create a SocialApp for your custom provider
        self.social_app = SocialApp.objects.create(
            provider=CustomProvider.id,  # Replace with your provider ID
            name=CustomProvider.name,
            client_id="test_client_id",
            secret="test_client_secret",
        )
        self.social_app.sites.add(1)  # Add to default site

        # Mock token data
        self.mock_token_data = {
            "access_token": "mock_access_token_12345",
            "refresh_token": "mock_refresh_token_67890",
            "token_type": "Bearer",
            "expires_in": 3600,
            "scope": "read:user user:email",
        }

        # Mock user data from provider API
        self.mock_user_data = {
            "id": "123456789",
            "email": "testuser@example.com",
            "name": "Test User",
            "username": "testuser",
            "verified": True,
        }

    def get_id_token(self):
        app = get_adapter().get_app(request=None, provider=CustomProvider.id)
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
        return response_data

    @responses.activate
    def test_invalid_public_key(self):
        """Test invalid key formatting"""
        responses.add(responses.GET, CustomAdapter.public_key_url, json=INVALID_KEY_RESP_JSON, status=200)
        rf = RequestFactory()
        request = rf.get("/fake-url/", HTTP_HOST="testserver")
        adapter = CustomAdapter(request)

        pub_key = adapter.get_public_key(headers={"HTTP_HOST": "foo"})
        self.assertEqual(pub_key, None)

    @responses.activate
    def test_complete_oauth_login_flow(self):
        """Test the complete OAuth login flow with mocked responses"""

        # Start the OAuth flow by visiting the login URL
        login_url = reverse(f"{CustomProvider.id}_login")
        responses.add(responses.POST, login_url, json=self.mock_token_data, status=200)

        # This should redirect to the provider's authorization URL
        response = self.client.post(login_url)
        self.assertEqual(response.status_code, 302)

        # Simulate the callback from the provider with an authorization code
        callback_url = reverse(f"{CustomProvider.id}_callback")
        responses.add(responses.GET, callback_url, json=self.mock_user_data, status=200)

        responses.add(responses.POST, CustomAdapter.access_token_url, json=self.get_login_response_json(), status=200)
        responses.add(responses.GET, CustomAdapter.public_key_url, json=KEY_SERVER_RESP_JSON, status=200)
        responses.add(responses.GET, CustomAdapter.profile_url, json=USER_INFO_RESP_JSON, status=200)
        callback_response = self.client.get(
            callback_url,
            {
                "code": "mock_authorization_code",
                "state": "mock_state_value",  # You might need to handle state properly
            },
        )
        self.assertEqual(callback_response.status_code, 302)

        # Verify user was created
        user = User.objects.get(email="test@testmaster.net")

        # Verify social account was created
        social_account = SocialAccount.objects.get(user=user)
        self.assertEqual(social_account.provider, CustomProvider.id)
        self.assertEqual(social_account.uid, "20122")

        # Verify user is logged in
        self.assertTrue("_auth_user_id" in self.client.session, f"session: {self.client.session}")
        self.assertEqual(int(self.client.session["_auth_user_id"]), user.id)
        responses.mock.assert_all_requests_are_fired

    @responses.activate
    def test_login_existing_user(self):
        """Test login flow for existing user"""
        uid = "99999"
        # Create existing user and social account
        existing_user = User.objects.create_user(username="existinguser", email="testuser@example.com")
        SocialAccount.objects.create(
            user=existing_user, provider=CustomProvider.id, uid=uid, extra_data=self.mock_user_data
        )
        # Start the OAuth flow by visiting the login URL
        login_url = reverse(f"{CustomProvider.id}_login")
        responses.add(responses.POST, login_url, json=self.mock_token_data, status=200)

        response = self.client.post(login_url)
        self.assertEqual(response.status_code, 302)

        # Simulate the callback from the provider with an authorization code
        callback_url = reverse(f"{CustomProvider.id}_callback")
        responses.add(
            responses.GET,
            callback_url,
            json={"id": uid, "email": "testuser@example.com", "name": "Existing User", "username": "existinguser"},
            status=200,
        )
        responses.add(responses.POST, CustomAdapter.access_token_url, json=self.get_login_response_json(), status=200)
        responses.add(responses.GET, CustomAdapter.public_key_url, json=KEY_SERVER_RESP_JSON, status=200)
        responses.add(responses.GET, CustomAdapter.profile_url, json=EXISTING_USER_RESP_JSON, status=200)
        callback_response = self.client.get(
            callback_url,
            {
                "code": "mock_authorization_code",
                "state": "mock_state_value",  # You might need to handle state properly
            },
        )
        self.assertEqual(callback_response.status_code, 302)
        # Verify user is logged in
        self.assertTrue("_auth_user_id" in self.client.session, f"session: {self.client.session.__dict__}")
        self.assertEqual(int(self.client.session["_auth_user_id"]), existing_user.id)
        responses.mock.assert_all_requests_are_fired

    @patch("requests.post")
    def test_token_exchange_failure(self, mock_post):
        """Test handling of token exchange failure"""

        # Mock failed token response
        mock_token_response = Mock()
        mock_token_response.status_code = 400
        mock_token_response.json.return_value = {
            "error": "invalid_grant",
            "error_description": "The authorization code is invalid",
        }
        mock_post.return_value = mock_token_response

        callback_url = reverse(f"{CustomProvider.id}_callback")

        response = self.client.get(callback_url, {"code": "invalid_code", "state": "mock_state_value"})

        # Should redirect to login page or show error
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "An error occurred")

        # Verify no user was created
        self.assertEqual(User.objects.count(), 0)

    @patch("requests.post")
    @patch("requests.get")
    def test_user_info_failure(self, mock_get, mock_post):
        """Test handling of user info API failure"""

        # Mock successful token response
        mock_token_response = Mock()
        mock_token_response.status_code = 200
        mock_token_response.json.return_value = self.mock_token_data
        mock_post.return_value = mock_token_response

        # Mock failed user info response
        mock_user_response = Mock()
        mock_user_response.status_code = 403
        mock_user_response.json.return_value = {"error": "insufficient_scope"}
        mock_get.return_value = mock_user_response

        callback_url = reverse(f"{CustomProvider.id}_callback")

        response = self.client.get(callback_url, {"code": "mock_authorization_code", "state": "mock_state_value"})

        # Should handle the error gracefully
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "An error occurred")

        # Verify no user was created
        self.assertEqual(User.objects.count(), 0)

    def test_provider_settings(self):
        """Test that provider settings are configured correctly"""

        # Verify social app exists
        self.assertTrue(SocialApp.objects.filter(provider=CustomProvider.id).exists())

        # Verify provider is in INSTALLED_APPS or configured properly
        # This depends on how you've set up your custom provider
        from allauth.socialaccount import providers

        # Your custom provider should be registered
        provider_classes = providers.registry.get_class_list()
        provider_ids = [p.id for p in provider_classes]
        self.assertIn(CustomProvider.id, provider_ids)


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
