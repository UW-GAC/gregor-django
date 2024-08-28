# Generated by Django 4.2.15 on 2024-08-27 22:04

from datetime import timedelta

from django.db import migrations
from django.utils import timezone

def populate_uploadworkspace_date_qc_complete(apps, schema_editor):
    UploadWorkspace = apps.get_model("gregor_anvil", "UploadWorkspace")
    # Create one UploadWorkspace for each unique version.
    for row in UploadWorkspace.objects.all():
        assumed_date_qc_completed = row.upload_cycle.end_date + timedelta(days=7)
        if assumed_date_qc_completed <= timezone.localdate():
            row.date_qc_completed = assumed_date_qc_completed
            row.full_clean()
            row.save(update_fields=["date_qc_completed"])


class Migration(migrations.Migration):

    dependencies = [
        ("gregor_anvil", "0028_populate_uploadcycle_date_ready_for_compute"),
    ]

    operations = [
        migrations.RunPython(populate_uploadworkspace_date_qc_complete, reverse_code=migrations.RunPython.noop),
    ]