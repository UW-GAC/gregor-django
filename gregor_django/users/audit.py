import logging
from dataclasses import dataclass

import django_tables2 as tables
import jsonapi_requests
from allauth.socialaccount.models import SocialAccount
from anvil_consortium_manager.models import Account
from django.conf import settings
from django.contrib.auth import get_user_model
from django.core.exceptions import ObjectDoesNotExist
from django.db.models import Q
from django_tables2.export import TableExport
from oauthlib.oauth2 import BackendApplicationClient
from requests_oauthlib import OAuth2, OAuth2Session

from gregor_django.drupal_oauth_provider.provider import CustomProvider
from gregor_django.gregor_anvil.audit import GREGORAudit, GREGORAuditResult
from gregor_django.gregor_anvil.models import PartnerGroup, ResearchCenter

logger = logging.getLogger(__name__)


class TextTable(object):
    def render_to_text(self):
        return TableExport(export_format=TableExport.CSV, table=self).export()


class UserAuditResultsTable(tables.Table, TextTable):
    """A table to show results from a UserAudit instance."""

    result_type = tables.Column()
    local_user_id = tables.Column()
    local_username = tables.Column()
    remote_user_id = tables.Column()
    remote_username = tables.Column()
    remote_name = tables.Column()
    changes = tables.Column()
    note = tables.Column()
    anvil_groups = tables.Column()

    class Meta:
        orderable = False


@dataclass
class UserAuditResult(GREGORAuditResult):
    local_user: SocialAccount = None
    anvil_account: Account = None
    remote_user_data: jsonapi_requests.JsonApiObject = None
    note: str = None
    changes: dict = None
    anvil_groups: list = None

    def get_table_dictionary(self):
        """Return a dictionary that can be used to populate an instance of `UserAuditResultsTable`."""

        row = {
            "changes": self.changes,
            "anvil_groups": self.anvil_groups,
            "note": self.note,
            "result_type": type(self).__name__,
        }
        if self.local_user:
            row.update(
                {
                    "local_user_id": self.local_user.user.id,
                    "local_username": self.local_user.user.username,
                }
            )
        if self.remote_user_data:
            row.update(
                {
                    "remote_user_id": self.remote_user_data.attributes.get("drupal_internal__uid"),
                    "remote_username": self.remote_user_data.attributes.get("name"),
                    "remote_name": "{} {}".format(
                        self.remote_user_data.attributes.get("field_fname"),
                        self.remote_user_data.attributes.get("field_lname"),
                    ),
                }
            )
        if self.anvil_account:
            row.update(
                {
                    "anvil_account": self.anvil_account,
                    "local_user_id": self.anvil_account.user.id,
                }
            )
        return row


@dataclass
class VerifiedUser(UserAuditResult):
    pass


@dataclass
class NewUser(UserAuditResult):
    pass


@dataclass
class RemoveUser(UserAuditResult):
    pass


@dataclass
class InactiveAnvilUser(UserAuditResult):
    pass


@dataclass
class UpdateUser(UserAuditResult):
    pass


@dataclass
class OverDeactivateThresholdUser(UserAuditResult):
    pass


class UserAudit(GREGORAudit):
    ISSUE_TYPE_USER_INACTIVE = "User is inactive in drupal"
    ISSUE_TYPE_USER_REMOVED_FROM_SITE = "User removed from site"
    USER_DEACTIVATE_THRESHOLD = 3
    results_table_class = UserAuditResultsTable

    def __init__(self, apply_changes=False, ignore_deactivate_threshold=False):
        """Initialize the audit.

        Args:
            apply_changes: Whether to make changes to align the audit
        """
        super().__init__()
        self.apply_changes = apply_changes
        self.ignore_deactivate_threshold = ignore_deactivate_threshold

    def _run_audit(self):
        """Run the audit on local and remote users."""
        user_endpoint_url = "user/user"
        drupal_uids = set()
        json_api = get_drupal_json_api()
        study_sites = get_study_sites(json_api)

        user_count = 0
        while user_endpoint_url is not None:
            users_endpoint = json_api.endpoint(user_endpoint_url)
            users_endpoint_response = users_endpoint.get()

            # If there are more, there will be a 'next' link

            user_endpoint_url = users_endpoint_response.content.links.get("next", {}).get("href")

            for user in users_endpoint_response.data:
                drupal_uid = user.attributes.get("drupal_internal__uid")
                drupal_username = user.attributes.get("name")
                drupal_email = user.attributes.get("mail")
                drupal_firstname = user.attributes.get("field_fname")
                drupal_lastname = user.attributes.get("field_lname")
                drupal_full_name = " ".join(part for part in (drupal_firstname, drupal_lastname) if part)
                drupal_study_sites_rel = user.relationships.get("field_research_center_or_site")
                # drupal_partner_groups_rel = user.relationships.get('field_partner_member_group')
                drupal_user_study_site_shortnames = []
                if drupal_study_sites_rel:
                    for dss in drupal_study_sites_rel.data:
                        study_site_uuid = dss.id
                        study_site_info = study_sites[study_site_uuid]

                        drupal_user_study_site_shortnames.append(study_site_info["short_name"])
                new_user_sites = ResearchCenter.objects.filter(short_name__in=drupal_user_study_site_shortnames)
                # no uid is blocked or anonymous
                if not drupal_uid:
                    # potential blocked user, but will no longer have a drupal uid
                    # so we cover these below
                    continue
                sa = None
                try:
                    sa = SocialAccount.objects.get(
                        uid=user.attributes["drupal_internal__uid"],
                        provider=CustomProvider.id,
                    )
                except ObjectDoesNotExist:
                    drupal_user = get_user_model()()
                    drupal_user.username = drupal_username
                    drupal_user.name = drupal_full_name
                    drupal_user.email = drupal_email
                    if self.apply_changes is True:
                        drupal_user.save()
                        drupal_user.research_centers.set(new_user_sites)
                    if self.apply_changes is True:
                        sa = SocialAccount.objects.create(
                            user=drupal_user,
                            uid=user.attributes["drupal_internal__uid"],
                            provider=CustomProvider.id,
                        )
                    self.needs_action.append(NewUser(local_user=sa, remote_user_data=user))

                if sa:
                    user_updates = {}
                    if sa.user.name != drupal_full_name:
                        user_updates.update({"name": {"old": sa.user.name, "new": drupal_full_name}})
                        sa.user.name = drupal_full_name
                    if sa.user.username != drupal_username:
                        user_updates.update(
                            {
                                "username": {
                                    "old": sa.user.username,
                                    "new": drupal_username,
                                }
                            }
                        )
                        sa.user.username = drupal_username
                    if sa.user.email != drupal_email:
                        user_updates.update({"email": {"old": sa.user.email, "new": drupal_email}})
                        sa.user.email = drupal_email

                    if sa.user.is_active is False:
                        user_updates.update({"is_active": {"old": False, "new": True}})
                        sa.user.is_active = True

                    prev_user_site_names = set(sa.user.research_centers.all().values_list("short_name", flat=True))
                    new_user_site_names = set(drupal_user_study_site_shortnames)
                    if prev_user_site_names != new_user_site_names:
                        user_updates.update(
                            {
                                "sites": {
                                    "old": prev_user_site_names,
                                    "new": new_user_site_names,
                                }
                            }
                        )
                        # do not remove from sites by default
                        removed_sites = prev_user_site_names.difference(new_user_site_names)
                        new_sites = new_user_site_names.difference(prev_user_site_names)

                        if settings.DRUPAL_DATA_AUDIT_REMOVE_USER_SITES is True:
                            if self.apply_changes is True:
                                sa.user.research_centers.set(new_user_sites)
                        else:
                            if removed_sites:
                                self.errors.append(
                                    UpdateUser(
                                        local_user=sa,
                                        remote_user_data=user,
                                        changes=user_updates,
                                    )
                                )
                            if new_sites:
                                for new_site in new_user_sites:
                                    if new_site.short_name in new_user_site_names:
                                        if self.apply_changes is True:
                                            sa.user.research_centers.add(new_site)

                    if user_updates:
                        if self.apply_changes is True:
                            sa.user.save()

                        self.needs_action.append(
                            UpdateUser(
                                local_user=sa,
                                remote_user_data=user,
                                changes=user_updates,
                            )
                        )
                    else:
                        self.verified.append(VerifiedUser(local_user=sa, remote_user_data=user))

                drupal_uids.add(drupal_uid)
                user_count += 1

        # find active django accounts that are drupal based
        # users that we did not get from drupal
        # these may include blocked users

        unaudited_drupal_accounts = SocialAccount.objects.filter(
            provider=CustomProvider.id, user__is_active=True
        ).exclude(uid__in=drupal_uids)
        user_ids_to_check = []
        count_inactive = unaudited_drupal_accounts.count()
        over_threshold = False
        if self.ignore_deactivate_threshold is False:
            if count_inactive > self.USER_DEACTIVATE_THRESHOLD:
                over_threshold = True

        for uda in unaudited_drupal_accounts:
            user_ids_to_check.append(uda.user.id)
            handled = False
            if settings.DRUPAL_DATA_AUDIT_DEACTIVATE_USERS is True:
                uda.user.is_active = False
                if over_threshold is False:
                    if self.apply_changes is True:
                        uda.user.save()
                    handled = True
                    self.needs_action.append(RemoveUser(local_user=uda))
            if handled is False:
                self.errors.append(RemoveUser(local_user=uda, note=f"Over Threshold {over_threshold}"))

        # Use distinct so this returns one row per Account
        # instead of row per groupaccountmembership
        inactive_anvil_users = Account.objects.filter(
            Q(user__is_active=False) | Q(user__id__in=user_ids_to_check),
            groupaccountmembership__isnull=False,
        ).distinct()

        for inactive_anvil_user in inactive_anvil_users:
            self.errors.append(
                InactiveAnvilUser(
                    anvil_account=inactive_anvil_user,
                    anvil_groups=list(
                        inactive_anvil_user.groupaccountmembership_set.all().values_list("group__name", flat=True)
                    ),
                )
            )


class SiteAuditResultsTable(tables.Table, TextTable):
    """A table to show results from a SiteAudit instance."""

    result_type = tables.Column()
    local_site_name = tables.Column()
    remote_site_name = tables.Column()
    changes = tables.Column()
    note = tables.Column()

    def value_local_site_name(self, value):
        return value

    class Meta:
        orderable = False


@dataclass
class SiteAuditResult(GREGORAuditResult):
    local_site: ResearchCenter
    remote_site_data: jsonapi_requests.JsonApiObject = None
    changes: dict = None
    note: str = None

    def get_table_dictionary(self):
        """Return a dictionary that can be used to populate an instance of `SiteAuditResultsTable`."""
        row = {
            "changes": self.changes,
            "note": self.note,
            "result_type": type(self).__name__,
        }
        if self.local_site:
            row.update(
                {
                    "local_site_name": self.local_site.short_name,
                }
            )
        if self.remote_site_data:
            row.update(
                {
                    "remote_site_name": self.remote_site_data.get("short_name"),
                }
            )
        return row


@dataclass
class VerifiedSite(SiteAuditResult):
    pass


@dataclass
class NewSite(SiteAuditResult):
    pass


@dataclass
class RemoveSite(SiteAuditResult):
    pass


@dataclass
class UpdateSite(SiteAuditResult):
    changes: dict


class SiteAudit(GREGORAudit):
    ISSUE_TYPE_LOCAL_SITE_INVALID = "Local site is invalid"
    results_table_class = SiteAuditResultsTable

    def __init__(self, apply_changes=False):
        """Initialize the audit.

        Args:
            apply_changes: Whether to make changes to align the audit
        """
        super().__init__()
        self.apply_changes = apply_changes

    def _run_audit(self):
        """Run the audit on local and remote users."""
        valid_nodes = set()
        json_api = get_drupal_json_api()
        study_sites = get_study_sites(json_api=json_api)
        for study_site_info in study_sites.values():
            short_name = study_site_info["short_name"]
            full_name = study_site_info["full_name"]
            node_id = study_site_info["node_id"]
            valid_nodes.add(node_id)

            try:
                study_site = ResearchCenter.objects.get(drupal_node_id=node_id)
            except ObjectDoesNotExist:
                study_site = None
                if self.apply_changes is True:
                    study_site = ResearchCenter.objects.create(
                        drupal_node_id=node_id,
                        short_name=short_name,
                        full_name=full_name,
                    )
                self.needs_action.append(NewSite(remote_site_data=study_site_info, local_site=study_site))
            else:
                study_site_updates = {}

                if study_site.full_name != full_name:
                    study_site_updates.update({"full_name": {"old": study_site.full_name, "new": full_name}})
                    study_site.full_name = full_name

                if study_site.short_name != short_name:
                    study_site_updates.update(
                        {
                            "short_name": {
                                "old": study_site.short_name,
                                "new": short_name,
                            }
                        }
                    )
                    study_site.short_name = short_name

                if study_site_updates:
                    if self.apply_changes is True:
                        study_site.save()
                    self.needs_action.append(
                        UpdateSite(
                            local_site=study_site,
                            remote_site_data=study_site_info,
                            changes=study_site_updates,
                        )
                    )
                else:
                    self.verified.append(VerifiedSite(local_site=study_site, remote_site_data=study_site_info))

        invalid_study_sites = ResearchCenter.objects.exclude(drupal_node_id__in=valid_nodes)

        for iss in invalid_study_sites:
            self.errors.append(RemoveSite(local_site=iss, note=self.ISSUE_TYPE_LOCAL_SITE_INVALID))


class PartnerGroupAuditResultsTable(tables.Table, TextTable):
    """A table to show results from a PartnerGroupAudit instance."""

    result_type = tables.Column()
    local_partner_group_name = tables.Column()
    remote_partner_group_name = tables.Column()
    changes = tables.Column()
    note = tables.Column()

    def value_local_partner_group_name(self, value):
        return value

    class Meta:
        orderable = False


@dataclass
class PartnerGroupAuditResult(GREGORAuditResult):
    local_partner_group: ResearchCenter
    remote_partner_group_data: jsonapi_requests.JsonApiObject = None
    changes: dict = None
    note: str = None

    def get_table_dictionary(self):
        """Return a dictionary that can be used to populate an instance of `PartnerGroupAuditResultsTable`."""
        row = {
            "changes": self.changes,
            "note": self.note,
            "result_type": type(self).__name__,
        }
        if self.local_partner_group:
            row.update(
                {
                    "local_partner_group_name": self.local_partner_group.short_name,
                }
            )
        if self.remote_partner_group_data:
            row.update(
                {
                    "remote_partner_group_name": self.remote_partner_group_data.get("short_name"),
                }
            )
        return row


@dataclass
class VerifiedPartnerGroup(PartnerGroupAuditResult):
    pass


@dataclass
class NewPartnerGroup(PartnerGroupAuditResult):
    pass


@dataclass
class RemovePartnerGroup(PartnerGroupAuditResult):
    pass


@dataclass
class UpdatePartnerGroup(PartnerGroupAuditResult):
    changes: dict


class PartnerGroupAudit(GREGORAudit):
    ISSUE_TYPE_LOCAL_PARTNER_GROUP_INVALID = "Local PartnerGroup is invalid"
    results_table_class = PartnerGroupAuditResultsTable

    def __init__(self, apply_changes=False):
        """Initialize the audit.

        Args:
            apply_changes: Whether to make changes to align the audit
        """
        super().__init__()
        self.apply_changes = apply_changes

    def _run_audit(self):
        """Run the audit on local and remote users."""
        valid_nodes = set()
        json_api = get_drupal_json_api()
        study_partner_groups = get_partner_groups(json_api=json_api)
        for study_partner_group_info in study_partner_groups.values():
            short_name = study_partner_group_info["short_name"]
            full_name = study_partner_group_info["full_name"]
            node_id = study_partner_group_info["node_id"]
            valid_nodes.add(node_id)

            try:
                study_partner_group = PartnerGroup.objects.get(drupal_node_id=node_id)
            except ObjectDoesNotExist:
                study_partner_group = None
                if self.apply_changes is True:
                    study_partner_group = PartnerGroup.objects.create(
                        drupal_node_id=node_id,
                        short_name=short_name,
                        full_name=full_name,
                    )
                self.needs_action.append(
                    NewPartnerGroup(
                        remote_partner_group_data=study_partner_group_info, local_partner_group=study_partner_group
                    )
                )
            else:
                study_partner_group_updates = {}

                if study_partner_group.full_name != full_name:
                    study_partner_group_updates.update(
                        {"full_name": {"old": study_partner_group.full_name, "new": full_name}}
                    )
                    study_partner_group.full_name = full_name

                # Short name not currently maintained in drupal
                # if study_partner_group.short_name != short_name:
                #     study_partner_group_updates.update(
                #         {
                #             "short_name": {
                #                 "old": study_partner_group.short_name,
                #                 "new": short_name,
                #             }
                #         }
                #     )
                #     study_partner_group.short_name = short_name

                if study_partner_group_updates:
                    if self.apply_changes is True:
                        study_partner_group.save()
                    self.needs_action.append(
                        UpdatePartnerGroup(
                            local_partner_group=study_partner_group,
                            remote_partner_group_data=study_partner_group_info,
                            changes=study_partner_group_updates,
                        )
                    )
                else:
                    self.verified.append(
                        VerifiedPartnerGroup(
                            local_partner_group=study_partner_group, remote_partner_group_data=study_partner_group_info
                        )
                    )

        invalid_study_partner_groups = PartnerGroup.objects.exclude(drupal_node_id__in=valid_nodes)

        for iss in invalid_study_partner_groups:
            self.errors.append(
                RemovePartnerGroup(local_partner_group=iss, note=self.ISSUE_TYPE_LOCAL_PARTNER_GROUP_INVALID)
            )


def get_drupal_json_api():
    json_api_client_id = settings.DRUPAL_API_CLIENT_ID
    json_api_client_secret = settings.DRUPAL_API_CLIENT_SECRET

    token_url = f"{settings.DRUPAL_SITE_URL}/oauth/token"
    client = BackendApplicationClient(client_id=json_api_client_id)
    oauth = OAuth2Session(client=client)
    api_root = f"{settings.DRUPAL_SITE_URL}/{settings.DRUPAL_API_REL_PATH}"

    token = oauth.fetch_token(
        token_url=token_url,
        client_id=json_api_client_id,
        client_secret=json_api_client_secret,
    )

    drupal_api = jsonapi_requests.Api.config(
        {
            "API_ROOT": api_root,
            "AUTH": OAuth2(client=client, client_id=json_api_client_id, token=token),
            "VALIDATE_SSL": True,
        }
    )
    return drupal_api


def get_study_sites(json_api):
    study_sites_endpoint = json_api.endpoint("node/research_center")
    study_sites_response = study_sites_endpoint.get()
    study_sites_info = dict()

    for ss in study_sites_response.data:
        short_name = ss.attributes["field_short_name"]
        full_name = ss.attributes["title"]
        node_id = ss.attributes["drupal_internal__nid"]

        study_sites_info[ss.id] = {
            "node_id": node_id,
            "short_name": short_name,
            "full_name": full_name,
        }
    return study_sites_info


def get_partner_groups(json_api):
    partner_groups_endpoint = json_api.endpoint("node/partner_group")
    partner_groups_response = partner_groups_endpoint.get()
    partner_groups_info = dict()

    for ss in partner_groups_response.data:
        full_name = ss.attributes["title"]
        # try to figure out short name - try to split on dash
        # or just truncate

        short_name = ss.attributes["title"]

        node_id = ss.attributes["drupal_internal__nid"]

        partner_groups_info[ss.id] = {
            "node_id": node_id,
            "short_name": short_name,
            "full_name": full_name,
        }
    return partner_groups_info
