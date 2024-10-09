import logging
from typing import Any, Dict

from allauth.account.adapter import DefaultAccountAdapter
from allauth.socialaccount.adapter import DefaultSocialAccountAdapter
from django.conf import settings
from django.contrib.auth.models import Group
from django.core.exceptions import ImproperlyConfigured, ObjectDoesNotExist
from django.core.mail import mail_admins
from django.http import HttpRequest

from gregor_django.gregor_anvil.models import PartnerGroup, ResearchCenter

logger = logging.getLogger(__name__)


class AccountAdapter(DefaultAccountAdapter):
    def is_open_for_signup(self, request: HttpRequest):
        return getattr(settings, "ACCOUNT_ALLOW_REGISTRATION", True)


class SocialAccountAdapter(DefaultSocialAccountAdapter):
    def is_open_for_signup(self, request: HttpRequest, sociallogin: Any):
        return getattr(settings, "ACCOUNT_ALLOW_REGISTRATION", True)

    def update_user_info(self, user, extra_data: Dict):
        import sys

        print(f"USER3: {user} {user.username} id: {user.id}", file=sys.stderr)
        logger.info(f"User {user} username {user.username}")
        drupal_username = extra_data.get("preferred_username")
        drupal_email = extra_data.get("email")
        first_name = extra_data.get("first_name")
        last_name = extra_data.get("last_name")
        full_name = " ".join(part for part in (first_name, last_name) if part)
        user_changed = False
        if user.name != full_name:
            logger.info(
                f"[SocialAccountAdatpter:update_user_info] user {user} " f"name updated from {user.name} to {full_name}"
            )
            user.name = full_name
            user_changed = True
        if user.username != drupal_username:
            logger.info(
                f"[SocialAccountAdatpter:update_user_info] user {user} "
                f"username updated from {user.username} to {drupal_username}"
            )
            user.username = drupal_username
            user_changed = True
        if user.email != drupal_email:
            logger.info(
                f"[SocialAccountAdatpter:update_user_info] user {user.username}"
                # f" email updated from {user.email} to {drupal_email}"
            )
            user.email = drupal_email
            user_changed = True

        if user_changed is True:
            user.save()

    def update_user_partner_groups(self, user, extra_data: Dict):
        partner_groups = extra_data.get("partner_group", [])
        logger.debug(f"partner groups: {partner_groups} for user {user}")
        partner_group_object_list = []
        if partner_groups:
            if not isinstance(partner_groups, list):
                raise ImproperlyConfigured("sociallogin.extra_data.partner_groups should be None or a list")

            for pg_name in partner_groups:
                try:
                    pg = PartnerGroup.objects.get(short_name=pg_name)
                except ObjectDoesNotExist:
                    try:
                        pg = PartnerGroup.objects.get(full_name=pg_name)
                    except ObjectDoesNotExist:
                        logger.debug(
                            f"[SocialAccountAdapter:update_user_partner_groups] Ignoring drupal "
                            f"partner_group {pg_name} - not in PartnerGroup domain"
                        )
                        mail_admins(
                            subject="Missing PartnerGroup",
                            message=f"Missing partner group ({pg_name}) passed from drupal for user {user}",
                        )
                    else:
                        partner_group_object_list.append(pg)
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
                    "[SocialAccountAdapter:update_user_partner_groups] " f"removing pg {existing_pg} for user {user}"
                )

    def update_user_research_centers(self, user, extra_data: Dict):
        # Get list of research centers in domain table

        research_center_or_site = extra_data.get("research_center_or_site", [])
        research_center_object_list = []
        if research_center_or_site:
            if not isinstance(research_center_or_site, list):
                raise ImproperlyConfigured("sociallogin.extra_data.research_center_or_site should be a list")

            for rc_name in research_center_or_site:
                try:
                    # For transition from passed full name to short name support both
                    rc = ResearchCenter.objects.get(short_name=rc_name)
                except ObjectDoesNotExist:
                    try:
                        rc = ResearchCenter.objects.get(full_name=rc_name)
                    except ObjectDoesNotExist:
                        logger.debug(
                            f"[SocialAccountAdapter:update_user_research_centers] Ignoring drupal "
                            f"research_center_or_site {rc_name} - not in ResearchCenter domain"
                        )
                        mail_admins(
                            subject="Missing ResearchCenter",
                            message=f"Missing research center {rc_name} passed from drupal for user {user}",
                        )
                    else:
                        research_center_object_list.append(rc)
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
                    "[SocialAccountAdatpter:update_user_research_centers] " f"removing rc {existing_rc} for user {user}"
                )

    def update_user_groups(self, user, extra_data: Dict):
        managed_scope_status = extra_data.get("managed_scope_status")
        if managed_scope_status:
            added_groups = []
            removed_groups = []
            if not isinstance(managed_scope_status, dict):
                raise ImproperlyConfigured("sociallogin.extra_data.managed_scope_status should be a dict")
            else:
                for group_name, user_has_group in managed_scope_status.items():
                    user_group, was_created = Group.objects.get_or_create(name=group_name)
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

        self.update_user_info(user, extra_data)
        self.update_user_research_centers(user, extra_data)
        self.update_user_partner_groups(user, extra_data)
        self.update_user_groups(user, extra_data)

    def on_authentication_error(self, request, provider_id, error, exception, extra_context):
        """
        Invoked when there is an error in auth cycle.
        Log so we know what is going on.
        """
        logger.error(
            f"[SocialAccountAdapter:on_authentication_error] Provider: {provider_id} "
            f"Error {error} Exception: {exception} extra {extra_context}"
        )
        super().on_authentication_error(request, provider_id, error, exception, extra_context)
