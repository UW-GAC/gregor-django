# Generated by Django 4.2.20 on 2025-04-30 20:57

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('gregor_anvil', '0031_historicalpartnergroup_status_partnergroup_status'),
    ]

    operations = [
        migrations.AlterField(
            model_name='historicalpartnergroup',
            name='status',
            field=models.CharField(choices=[('Active', 'Active'), ('Inactive', 'Inactive')], default='Active', max_length=20),
        ),
        migrations.AlterField(
            model_name='partnergroup',
            name='status',
            field=models.CharField(choices=[('Active', 'Active'), ('Inactive', 'Inactive')], default='Active', max_length=20),
        ),
    ]
