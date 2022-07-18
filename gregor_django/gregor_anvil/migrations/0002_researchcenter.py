# Generated by Django 3.2.13 on 2022-07-18 23:12

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('gregor_anvil', '0001_initial'),
    ]

    operations = [
        migrations.CreateModel(
            name='ResearchCenter',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('short_name', models.CharField(max_length=15, unique=True)),
                ('full_name', models.CharField(max_length=255)),
            ],
        ),
    ]