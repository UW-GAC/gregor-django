# Generated by Django 3.2.16 on 2023-04-27 19:41

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('gregor_anvil', '0008_historicalpartnergroup_partnergroup'),
    ]

    operations = [
        migrations.AlterField(
            model_name='historicalpartnergroup',
            name='full_name',
            field=models.CharField(db_index=True, max_length=255),
        ),
        migrations.AlterField(
            model_name='historicalresearchcenter',
            name='full_name',
            field=models.CharField(db_index=True, max_length=255),
        ),
        migrations.AlterField(
            model_name='partnergroup',
            name='full_name',
            field=models.CharField(max_length=255, unique=True),
        ),
        migrations.AlterField(
            model_name='researchcenter',
            name='full_name',
            field=models.CharField(max_length=255, unique=True),
        ),
    ]
