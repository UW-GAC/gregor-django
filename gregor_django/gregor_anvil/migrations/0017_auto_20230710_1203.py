# Generated by Django 3.2.19 on 2023-07-10 19:03

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('gregor_anvil', '0016_dccprocesseddataworkspace_historicaldccprocesseddataworkspace'),
    ]

    operations = [
        migrations.AddField(
            model_name='dccprocessingworkspace',
            name='purpose',
            field=models.TextField(default=None, help_text='The type of processing that is done in this workspace.'),
            preserve_default=False,
        ),
        migrations.AddField(
            model_name='historicaldccprocessingworkspace',
            name='purpose',
            field=models.TextField(default=None, help_text='The type of processing that is done in this workspace.'),
            preserve_default=False,
        ),
    ]
