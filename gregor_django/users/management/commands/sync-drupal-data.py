import logging

from django.core.mail import send_mail
from django.core.management.base import BaseCommand
from django.http import HttpRequest
from django.template.loader import render_to_string
from django.utils.timezone import localtime

from gregor_django.users import audit

logger = logging.getLogger(__name__)


class Command(BaseCommand):
    help = "Sync drupal user and domain data"

    def add_arguments(self, parser):
        parser.add_argument(
            "--update",
            action="store_true",
            dest="update",
            default=False,
            help="Make updates to sync local data with remote. If not set, will just report.",
        )
        parser.add_argument(
            "--ignore-threshold",
            action="store_true",
            dest="ignore_threshold",
            default=False,
            help="Ignore user deactivation threshold",
        )

        parser.add_argument(
            "--email",
            help="""Email to which to send audit result details that need action or have errors.""",
        )

    def _send_email(self, user_audit, site_audit):
        # Send email if requested and there are problems.
        if user_audit.ok() is False or site_audit.ok() is False:
            # django-tables2 requires request context, so we create an empty one
            # if we wanted to linkify any of our data we would need to do more here
            request = HttpRequest()
            subject = "[command:sync-drupal-data] report"
            html_body = render_to_string(
                "users/drupal_data_audit_email.html",
                context={
                    "user_audit": user_audit,
                    "site_audit": site_audit,
                    "request": request,
                    "apply_changes": self.apply_changes,
                },
            )
            send_mail(
                subject,
                "Drupal data audit problems or changes found. Please see attached report.",
                None,
                [self.email],
                fail_silently=False,
                html_message=html_body,
            )

    def handle(self, *args, **options):
        self.apply_changes = options.get("update")
        self.email = options["email"]
        self.ignore_threshold = options["ignore_threshold"]

        notification_content = (
            f"[sync-drupal-data] start: Applying Changes: {self.apply_changes} "
            f"Ignoring Threshold: {self.ignore_threshold} Start time: {localtime()}\n"
        )
        site_audit = audit.SiteAudit(apply_changes=self.apply_changes)
        site_audit.run_audit()

        notification_content += (
            f"SiteAudit summary: status ok: {site_audit.ok()} verified: {len(site_audit.verified)} "
            f"needs_changes: {len(site_audit.needs_action)} errors: {len(site_audit.errors)}\n"
        )
        if site_audit.needs_action:
            notification_content += "Sites that need syncing:\n"
            notification_content += site_audit.get_needs_action_table().render_to_text()
        if site_audit.errors:
            notification_content += "Sites requiring intervention:\n"
            notification_content += site_audit.get_errors_table().render_to_text()

        user_audit = audit.UserAudit(
            apply_changes=self.apply_changes,
            ignore_deactivate_threshold=self.ignore_threshold,
        )
        user_audit.run_audit()
        notification_content += (
            "--------------------------------------\n"
            f"UserAudit summary: status ok: {user_audit.ok()} verified: {len(user_audit.verified)} "
            f"needs_changes: {len(user_audit.needs_action)} errors: {len(user_audit.errors)}\n"
        )
        if user_audit.needs_action:
            notification_content += "Users that need syncing (will be resolved by this script if in update mode):\n"
            notification_content += user_audit.get_needs_action_table().render_to_text()
        if user_audit.errors:
            notification_content += "Users that need intervention (cannot be resolved by script):\n"
            notification_content += user_audit.get_errors_table().render_to_text()

        self.stdout.write(notification_content)
        if self.email:
            self._send_email(user_audit, site_audit)
