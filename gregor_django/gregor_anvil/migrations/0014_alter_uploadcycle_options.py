# Generated by Django 3.2.19 on 2023-06-20 23:37

from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ('gregor_anvil', '0013_remove_version_fields'),
    ]

    operations = [
        migrations.AlterModelOptions(
            name='uploadcycle',
            options={'ordering': ['cycle']},
        ),
    ]
