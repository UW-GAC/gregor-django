import logging
from typing import Any

from allauth.account.adapter import DefaultAccountAdapter
from allauth.socialaccount.adapter import DefaultSocialAccountAdapter
from django.conf import settings
from django.contrib.auth.models import Group
from django.core.exceptions import ImproperlyConfigured
from django.http import HttpRequest

logger = logging.getLogger(__name__)


class AccountAdapter(DefaultAccountAdapter):
    def is_open_for_signup(self, request: HttpRequest):
        return getattr(settings, "ACCOUNT_ALLOW_REGISTRATION", True)


class SocialAccountAdapter(DefaultSocialAccountAdapter):
    def is_open_for_signup(self, request: HttpRequest, sociallogin: Any):
        return getattr(settings, "ACCOUNT_ALLOW_REGISTRATION", True)

    def update_gregor_user_data(self, sociallogin: Any):

        logger.debug(
            f"[SocialAccountAdatpter:update_gregor_user_data] account: {sociallogin.account} "
            f"extra_data {sociallogin.account.extra_data} "
            f"provider: {sociallogin.account.provider}"
        )

        extra_data = sociallogin.account.extra_data

        managed_scope_status = extra_data.get("managed_scope_status")
        if managed_scope_status:
            user = sociallogin.user
            added_groups = []
            removed_groups = []
            if not isinstance(managed_scope_status, dict):
                raise ImproperlyConfigured(
                    "sociallogin.extra_data.managed_scope_status should be a dict"
                )
            else:
                for group_name, user_has_group in managed_scope_status.items():
                    user_group, was_created = Group.objects.get_or_create(
                        name=group_name
                    )
                    if was_created:
                        logger.debug(
                            f"[SocialAccountAdatpter:update_gregor_user_data] created mapped user group: {group_name}"
                        )
                    if user_has_group is True:
                        if user_group not in user.groups.all():
                            user.groups.add(user_group)
                            added_groups.append(user_group.name)
                    else:
                        if user_group in user.groups.all():
                            user.groups.remove(user_group)
                            removed_groups.append(user_group.name)
            if added_groups or removed_groups:
                logger.info(
                    f"[SocialAccountAdatpter:update_gregor_user_data] user: {sociallogin.account} updated groups: "
                    f"added {added_groups} removed: {removed_groups} "
                    f"managed_scope_status: {managed_scope_status}"
                )
                user.save()
