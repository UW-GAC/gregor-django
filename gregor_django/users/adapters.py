import logging
from typing import Any, Dict

from allauth.account.adapter import DefaultAccountAdapter
from allauth.socialaccount.adapter import DefaultSocialAccountAdapter
from django.conf import settings
from django.contrib.auth.models import Group
from django.core.exceptions import ImproperlyConfigured, ObjectDoesNotExist
from django.http import HttpRequest

from gregor_django.gregor_anvil.models import ResearchCenter

logger = logging.getLogger(__name__)


class AccountAdapter(DefaultAccountAdapter):
    def is_open_for_signup(self, request: HttpRequest):
        return getattr(settings, "ACCOUNT_ALLOW_REGISTRATION", True)


class SocialAccountAdapter(DefaultSocialAccountAdapter):
    def is_open_for_signup(self, request: HttpRequest, sociallogin: Any):
        return getattr(settings, "ACCOUNT_ALLOW_REGISTRATION", True)

    def update_user_name(self, user, extra_data: Dict):
        first_name = extra_data.get("first_name")
        last_name = extra_data.get("last_name")
        full_name = " ".join(part for part in (first_name, last_name) if part)
        if user.name != full_name:
            logger.info(
                f"[SocialAccountAdatpter:update_user_name] user {user} name updated from {user.name} to {full_name}"
            )
            user.name = full_name
            user.save()

    def update_user_research_centers(self, user, extra_data: Dict):
        # Get list of research centers in domain table

        research_center_or_site = extra_data.get("research_center_or_site")
        if not isinstance(research_center_or_site, list):
            raise ImproperlyConfigured(
                "sociallogin.extra_data.research_center_or_site should be a list"
            )
        for rc_name in research_center_or_site:
            try:
                rc = ResearchCenter.objects.get(full_name=rc_name)
            except ObjectDoesNotExist:
                logger.debug(
                    f"[SocialAccountAdatpter:update_user_research_centers] Ignoring drupal "
                    f"research_center_or_site {rc_name} - not in ResearchCenter domain"
                )
                continue
            else:
                if not user.research_centers.filter(pk=rc.pk):
                    user.research_centers.add(rc)
                    logger.info(
                        f"[SocialAccountAdatpter:update_user_research_centers] adding user "
                        f"research_centers user: {user} rc: {rc}"
                    )

        for existing_rc in user.research_centers.all():
            if existing_rc.full_name not in research_center_or_site:
                user.research_centers.remove(existing_rc)
                logger.info(
                    f"[SocialAccountAdatpter:update_user_research_centers] removing rc {existing_rc} for user {user}"
                )

    def update_user_groups(self, user, extra_data: Dict):
        managed_scope_status = extra_data.get("managed_scope_status")
        if managed_scope_status:
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
                            f"[SocialAccountAdatpter:update_user_data] created mapped user group: {group_name}"
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
                    f"[SocialAccountAdatpter:update_user_data] user: {user} updated groups: "
                    f"added {added_groups} removed: {removed_groups} "
                    f"managed_scope_status: {managed_scope_status}"
                )

    def update_user_data(self, sociallogin: Any):

        logger.debug(
            f"[SocialAccountAdatpter:update_user_data] account: {sociallogin.account} "
            f"extra_data {sociallogin.account.extra_data} "
            f"provider: {sociallogin.account.provider}"
        )

        extra_data = sociallogin.account.extra_data
        user = sociallogin.user

        self.update_user_name(user, extra_data)
        self.update_user_research_centers(user, extra_data)
        self.update_user_groups(user, extra_data)
