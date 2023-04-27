import logging
from typing import Any, Dict

from allauth.account.adapter import DefaultAccountAdapter
from allauth.socialaccount.adapter import DefaultSocialAccountAdapter
from django.conf import settings
from django.contrib.auth.models import Group
from django.core.exceptions import ImproperlyConfigured, ObjectDoesNotExist
from django.core.mail import mail_admins
from django.db.models import Q
from django.http import HttpRequest

from gregor_django.gregor_anvil.models import PartnerGroup, ResearchCenter

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

    def update_user_partner_groups(self, user, extra_data: Dict):
        partner_groups = extra_data.get("partner_group", [])
        logger.debug(f"partner groups: {partner_groups} for user {user}")
        if partner_groups:
            if not isinstance(partner_groups, list):
                raise ImproperlyConfigured(
                    "sociallogin.extra_data.partner_groups should be None or a list"
                )
            partner_group_object_list = []
            for pg_name in partner_groups:
                try:
                    pg = PartnerGroup.objects.get(
                        Q(full_name=pg_name) | Q(short_name=pg_name)
                    )
                except ObjectDoesNotExist:
                    logger.debug(
                        f"[SocialAccountAdapter:update_user_partner_groups] Ignoring drupal "
                        f"partner_group {pg_name} - not in PartnerGroup domain"
                    )
                    mail_admins(
                        subject="Missing PartnerGroup",
                        message=f"Missing partner group ({pg_name}) passed from drupal for user {user}",
                    )
                    continue
                else:
                    partner_group_object_list.append(pg)

            for pg in partner_group_object_list:
                if not user.partner_groups.filter(pk=pg.pk):
                    user.partner_groups.add(pg)
                    logger.info(
                        f"[SocialAccountAdatpter:update_user_partner_groups] adding user "
                        f"partner_groups user: {user} rc: {pg}"
                    )

            for existing_pg in user.partner_groups.all():
                if existing_pg not in partner_group_object_list:
                    user.partner_groups.remove(existing_pg)
                    logger.info(
                        "[SocialAccountAdapter:update_user_partner_groups] "
                        f"removing pg {existing_pg} for user {user}"
                    )

    def update_user_research_centers(self, user, extra_data: Dict):
        # Get list of research centers in domain table

        research_center_or_site = extra_data.get("research_center_or_site", [])
        if research_center_or_site:
            if not isinstance(research_center_or_site, list):
                raise ImproperlyConfigured(
                    "sociallogin.extra_data.research_center_or_site should be a list"
                )
            research_center_object_list = []
            for rc_name in research_center_or_site:
                try:
                    # For transition from passed full name to short name
                    # support both
                    rc = ResearchCenter.objects.get(
                        Q(full_name=rc_name) | Q(short_name=rc_name)
                    )
                except ObjectDoesNotExist:
                    logger.debug(
                        f"[SocialAccountAdapter:update_user_research_centers] Ignoring drupal "
                        f"research_center_or_site {rc_name} - not in ResearchCenter domain"
                    )
                    mail_admins(
                        subject="Missing ResearchCenter",
                        message=f"Missing research center {rc_name} passed from drupal for user {user}",
                    )
                    continue
                else:
                    research_center_object_list.append(rc)

            for rc in research_center_object_list:
                if not user.research_centers.filter(pk=rc.pk):
                    user.research_centers.add(rc)
                    logger.info(
                        f"[SocialAccountAdatpter:update_user_research_centers] adding user "
                        f"research_centers user: {user} rc: {rc}"
                    )

            for existing_rc in user.research_centers.all():
                if existing_rc not in research_center_object_list:
                    user.research_centers.remove(existing_rc)
                    logger.info(
                        "[SocialAccountAdatpter:update_user_research_centers] "
                        f"removing rc {existing_rc} for user {user}"
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
        self.update_user_partner_groups(user, extra_data)
        self.update_user_groups(user, extra_data)
