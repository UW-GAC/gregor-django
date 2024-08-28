from django.contrib.sites.models import Site
from django.core.mail import send_mail
from django.core.management.base import BaseCommand
from django.template.loader import render_to_string
from django.urls import reverse

from ...audit import upload_workspace_auth_domain_audit, upload_workspace_sharing_audit


class Command(BaseCommand):
    help = "Run access audits on UploadWorkspace."

    def add_arguments(self, parser):
        email_group = parser.add_argument_group(title="Email reports")
        email_group.add_argument(
            "--email",
            help="""Email to which to send audit reports that need action or have errors.""",
        )

    def run_sharing_audit(self, *args, **options):
        self.stdout.write("Running UploadWorkspace sharing audit... ", ending="")
        audit = upload_workspace_sharing_audit.UploadWorkspaceSharingAudit()
        audit.run_audit()
        self._handle_audit_results(audit, reverse("gregor_anvil:audit:upload_workspaces:sharing:all"), **options)

    def run_auth_domain_audit(self, *args, **options):
        self.stdout.write("Running UploadWorkspace auth domain audit... ", ending="")
        audit = upload_workspace_auth_domain_audit.UploadWorkspaceAuthDomainAudit()
        audit.run_audit()
        self._handle_audit_results(audit, reverse("gregor_anvil:audit:upload_workspaces:auth_domains:all"), **options)

    def _handle_audit_results(self, audit, url, **options):
        # Report errors and needs access.
        audit_ok = audit.ok()
        # Construct the url for handling errors.
        url = "https://" + Site.objects.get_current().domain + url
        if audit_ok:
            self.stdout.write(self.style.SUCCESS("ok!"))
        else:
            self.stdout.write(self.style.ERROR("problems found."))

        # Print results
        self.stdout.write("* Verified: {}".format(len(audit.verified)))
        self.stdout.write("* Needs action: {}".format(len(audit.needs_action)))
        self.stdout.write("* Errors: {}".format(len(audit.errors)))

        if not audit_ok:
            self.stdout.write(self.style.ERROR(f"Please visit {url} to resolve these issues."))

            # Send email if requested and there are problems.
            email = options["email"]
            subject = "{} - problems found".format(audit.__class__.__name__)
            html_body = render_to_string(
                "gregor_anvil/email_audit_report.html",
                context={
                    "title": "Upload workspace audit",
                    "audit_results": audit,
                    "url": url,
                },
            )
            send_mail(
                subject,
                "Audit problems found. Please see attached report.",
                None,
                [email],
                fail_silently=False,
                html_message=html_body,
            )

    def handle(self, *args, **options):
        self.run_sharing_audit(*args, **options)
        self.run_auth_domain_audit(*args, **options)
