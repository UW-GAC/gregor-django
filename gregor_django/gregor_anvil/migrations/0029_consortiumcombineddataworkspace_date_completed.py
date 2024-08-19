# Generated by Django 4.2.15 on 2024-08-19 22:49

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('gregor_anvil', '0028_uploadworkspace_date_qc_complete'),
    ]

    operations = [
        migrations.AddField(
            model_name='combinedconsortiumdataworkspace',
            name='date_completed',
            field=models.DateTimeField(blank=True, default=None, help_text='Date that data preparation in this workspace was completed.', null=True),
        ),
        migrations.AddField(
            model_name='historicalcombinedconsortiumdataworkspace',
            name='date_completed',
            field=models.DateTimeField(blank=True, default=None, help_text='Date that data preparation in this workspace was completed.', null=True),
        ),
    ]
