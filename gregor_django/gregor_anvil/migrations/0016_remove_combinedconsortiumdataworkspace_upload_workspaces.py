# Generated by Django 3.2.19 on 2023-08-04 22:36

from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ('gregor_anvil', '0015_dccworkspaces'),
    ]

    operations = [
        migrations.RemoveField(
            model_name='combinedconsortiumdataworkspace',
            name='upload_workspaces',
        ),
    ]
