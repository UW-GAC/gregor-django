# Generated by Django 4.2.15 on 2024-08-22 21:30

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('gregor_anvil', '0031_uploadcycle_change_is_ready_to_compute_to_date_ready_for_compute'),
    ]

    operations = [
        migrations.AlterField(
            model_name='historicaluploadworkspace',
            name='date_qc_completed',
            field=models.DateField(blank=True, default=None, help_text='Date that QC was completed for this workspace. If null, QC is not complete.', null=True),
        ),
        migrations.AlterField(
            model_name='uploadworkspace',
            name='date_qc_completed',
            field=models.DateField(blank=True, default=None, help_text='Date that QC was completed for this workspace. If null, QC is not complete.', null=True),
        ),
    ]