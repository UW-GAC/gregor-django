# Generated by Django 3.2.19 on 2023-06-14 00:08

from datetime import date

from django.db import migrations
from django.db.models import Max

def populate_uploadworkspace_uploadcycle(apps, schema_editor):
    """Populate the UploadCycle model using versions in UploadWorkspace, and set UploadWorkspace.upload_cycle."""
    UploadWorkspace = apps.get_model("gregor_anvil", "UploadWorkspace")
    UploadCycle = apps.get_model("gregor_anvil", "UploadCycle")
    # Create one UploadCycle for each unique version.
    for row in UploadWorkspace.objects.all():
        # Get or create the upload cycle object.
        try:
            upload_cycle = UploadCycle.objects.get(cycle=row.version)
        except UploadCycle.DoesNotExist:
            upload_cycle = UploadCycle(
                cycle=row.version,
                start_date=date.fromtimestamp(0),
                end_date=date.fromtimestamp(0),
                note="Automatically generated by migration."
            )
            upload_cycle.full_clean()
            upload_cycle.save()
        # Set the upload cycle for the upload workspace.
        row.upload_cycle = upload_cycle
        row.save(update_fields=["upload_cycle"])

def populate_combinedconsortiumdataworkspace_uploadcycle(apps, schema_editor):
    """Populate the CombinedConsortiumDataWorkspace.upload_cycle field using versions in UploadWorkspace."""
    CombinedConsortiumDataWorkspace = apps.get_model("gregor_anvil", "CombinedConsortiumDataWorkspace")
    UploadCycle = apps.get_model("gregor_anvil", "UploadCycle")
    # Create one UploadCycle for each unique version.
    for row in CombinedConsortiumDataWorkspace.objects.all():
        # Find the latest version of upload workspace associated with this workspace.
        max_version = row.upload_workspaces.aggregate(Max("version"))["version__max"]
        upload_cycle = UploadCycle.objects.get(cycle=max_version)
        # Set the upload cycle for the upload workspace.
        row.upload_cycle = upload_cycle
        row.save(update_fields=["upload_cycle"])

def populate_releaseworkspace_uploadcycle(apps, schema_editor):
    """Populate the ReleaseWorkspace.upload_cycle field using versions in UploadWorkspace."""
    ReleaseWorkspace = apps.get_model("gregor_anvil", "ReleaseWorkspace")
    UploadCycle = apps.get_model("gregor_anvil", "UploadCycle")
    # Create one UploadCycle for each unique version.
    for row in ReleaseWorkspace.objects.all():
        # Find the latest version of upload workspace associated with this workspace.
        max_version = row.upload_workspaces.aggregate(Max("version"))["version__max"]
        upload_cycle = UploadCycle.objects.get(cycle=max_version)
        # Set the upload cycle for the upload workspace.
        row.upload_cycle = upload_cycle
        row.save(update_fields=["upload_cycle"])


class Migration(migrations.Migration):

    dependencies = [
        ('gregor_anvil', '0011_add_uploadcycle_fields'),
    ]

    operations = [
        migrations.RunPython(populate_uploadworkspace_uploadcycle, reverse_code=migrations.RunPython.noop),
        migrations.RunPython(populate_combinedconsortiumdataworkspace_uploadcycle, reverse_code=migrations.RunPython.noop),
        migrations.RunPython(populate_releaseworkspace_uploadcycle, reverse_code=migrations.RunPython.noop),
    ]
