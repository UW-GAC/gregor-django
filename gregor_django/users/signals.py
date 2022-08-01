from allauth.account.signals import user_logged_in
from allauth.socialaccount.adapter import get_adapter
from django.dispatch import receiver

from gregor_django.drupal_oauth_provider.provider import (
    CustomProvider as DrupalProvider,
)


@receiver(user_logged_in)
def custom_user_logged_in_processing(sender, **kwargs):
    # After a successful social login
    # If the user logged in with the gregor oauth provider
    # update additional user info
    sociallogin = kwargs.get("sociallogin")
    if sociallogin:
        user_provider_id = sociallogin.account.provider
        if user_provider_id == DrupalProvider.id:
            get_adapter().update_gregor_user_data(sociallogin)
