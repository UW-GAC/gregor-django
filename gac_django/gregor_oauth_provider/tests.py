from allauth.socialaccount.models import SocialAccount
from allauth.socialaccount.tests import OAuth2TestsMixin
from allauth.tests import MockedResponse, TestCase

from .provider import CustomProvider


class CustomProviderTests(OAuth2TestsMixin, TestCase):
    provider_id = CustomProvider.id

    def get_mocked_response(self):
        return MockedResponse(
            200,
            """
        {
            "username": "testmaster",
            "email": "test@testmaster.net",
            "id": 20122,
            "first_name":"Test",
            "last_name": "Master"
        }""",
        )

