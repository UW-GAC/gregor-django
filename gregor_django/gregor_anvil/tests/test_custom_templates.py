from anvil_consortium_manager.tests.factories import UserEmailEntryFactory
from django.core import mail
from django.test import TestCase

from gregor_django.users.tests.factories import UserFactory


class VerificationEmailTemplateTest(TestCase):
    """Tests of the verification email template."""

    def test_verification_email_template(self):
        """Verification email is correct."""
        user = UserFactory.create()
        email_entry = UserEmailEntryFactory.create(user=user)
        email_entry.send_verification_email("www.test.com")
        # One message has been sent.
        self.assertEqual(len(mail.outbox), 1)
        # The correct template is used.
        email_body = mail.outbox[0].body
        self.assertIn("GREGoR consortium", email_body)
