# Generated by Django 4.2.15 on 2024-08-27 22:04

from datetime import timedelta

from django.db import migrations
from django.utils import timezone


def populate_uploadcycle_date_ready_for_compute(apps, schema_editor):
    UploadCycle = apps.get_model("gregor_anvil", "UploadCycle")
    # Create one UploadCycle for each unique version.
    for row in UploadCycle.objects.all():
        assumed_date_ready_for_compute = row.start_date + timedelta(days=7)
        if row.end_date <= timezone.localdate():
            row.date_ready_for_compute = assumed_date_ready_for_compute
            row.full_clean()
            row.save(update_fields=["date_ready_for_compute"])



class Migration(migrations.Migration):

    dependencies = [
        ("gregor_anvil", "0027_tracking_fields_for_custom_audits"),
    ]

    operations = [
        migrations.RunPython(populate_uploadcycle_date_ready_for_compute, reverse_code=migrations.RunPython.noop),
    ]
