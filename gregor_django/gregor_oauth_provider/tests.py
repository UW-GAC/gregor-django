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
            "name": "testmaster",
            "email": "test@testmaster.net",
            "sub": 20122
        }""",
        )
