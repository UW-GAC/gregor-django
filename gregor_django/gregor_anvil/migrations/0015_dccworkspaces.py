# Generated by Django 3.2.19 on 2023-07-10 22:20

from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion
import django_extensions.db.fields
import simple_history.models


class Migration(migrations.Migration):

    dependencies = [
        ('anvil_consortium_manager', '0012_managedgroup_email_unique'),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
        ('gregor_anvil', '0014_alter_uploadcycle_options'),
    ]

    operations = [
        migrations.CreateModel(
            name='HistoricalDCCProcessingWorkspace',
            fields=[
                ('id', models.BigIntegerField(auto_created=True, blank=True, db_index=True, verbose_name='ID')),
                ('created', django_extensions.db.fields.CreationDateTimeField(auto_now_add=True, verbose_name='created')),
                ('modified', django_extensions.db.fields.ModificationDateTimeField(auto_now=True, verbose_name='modified')),
                ('purpose', models.TextField(help_text='The type of processing that is done in this workspace.')),
                ('history_id', models.AutoField(primary_key=True, serialize=False)),
                ('history_date', models.DateTimeField(db_index=True)),
                ('history_change_reason', models.CharField(max_length=100, null=True)),
                ('history_type', models.CharField(choices=[('+', 'Created'), ('~', 'Changed'), ('-', 'Deleted')], max_length=1)),
                ('history_user', models.ForeignKey(null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='+', to=settings.AUTH_USER_MODEL)),
                ('upload_cycle', models.ForeignKey(blank=True, db_constraint=False, help_text='Upload cycle associated with this workspace.', null=True, on_delete=django.db.models.deletion.DO_NOTHING, related_name='+', to='gregor_anvil.uploadcycle')),
                ('workspace', models.ForeignKey(blank=True, db_constraint=False, null=True, on_delete=django.db.models.deletion.DO_NOTHING, related_name='+', to='anvil_consortium_manager.workspace')),
            ],
            options={
                'verbose_name': 'historical dcc processing workspace',
                'verbose_name_plural': 'historical dcc processing workspaces',
                'ordering': ('-history_date', '-history_id'),
                'get_latest_by': ('history_date', 'history_id'),
            },
            bases=(simple_history.models.HistoricalChanges, models.Model),
        ),
        migrations.CreateModel(
            name='HistoricalDCCProcessedDataWorkspace',
            fields=[
                ('id', models.BigIntegerField(auto_created=True, blank=True, db_index=True, verbose_name='ID')),
                ('created', django_extensions.db.fields.CreationDateTimeField(auto_now_add=True, verbose_name='created')),
                ('modified', django_extensions.db.fields.ModificationDateTimeField(auto_now=True, verbose_name='modified')),
                ('history_id', models.AutoField(primary_key=True, serialize=False)),
                ('history_date', models.DateTimeField(db_index=True)),
                ('history_change_reason', models.CharField(max_length=100, null=True)),
                ('history_type', models.CharField(choices=[('+', 'Created'), ('~', 'Changed'), ('-', 'Deleted')], max_length=1)),
                ('consent_group', models.ForeignKey(blank=True, db_constraint=False, help_text='Consent group associated with this data.', null=True, on_delete=django.db.models.deletion.DO_NOTHING, related_name='+', to='gregor_anvil.consentgroup')),
                ('history_user', models.ForeignKey(null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='+', to=settings.AUTH_USER_MODEL)),
                ('upload_cycle', models.ForeignKey(blank=True, db_constraint=False, help_text='Upload cycle associated with this workspace.', null=True, on_delete=django.db.models.deletion.DO_NOTHING, related_name='+', to='gregor_anvil.uploadcycle')),
                ('workspace', models.ForeignKey(blank=True, db_constraint=False, null=True, on_delete=django.db.models.deletion.DO_NOTHING, related_name='+', to='anvil_consortium_manager.workspace')),
            ],
            options={
                'verbose_name': 'historical dcc processed data workspace',
                'verbose_name_plural': 'historical dcc processed data workspaces',
                'ordering': ('-history_date', '-history_id'),
                'get_latest_by': ('history_date', 'history_id'),
            },
            bases=(simple_history.models.HistoricalChanges, models.Model),
        ),
        migrations.CreateModel(
            name='DCCProcessingWorkspace',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('created', django_extensions.db.fields.CreationDateTimeField(auto_now_add=True, verbose_name='created')),
                ('modified', django_extensions.db.fields.ModificationDateTimeField(auto_now=True, verbose_name='modified')),
                ('purpose', models.TextField(help_text='The type of processing that is done in this workspace.')),
                ('upload_cycle', models.ForeignKey(help_text='Upload cycle associated with this workspace.', on_delete=django.db.models.deletion.PROTECT, to='gregor_anvil.uploadcycle')),
                ('workspace', models.OneToOneField(on_delete=django.db.models.deletion.CASCADE, to='anvil_consortium_manager.workspace')),
            ],
            options={
                'get_latest_by': 'modified',
                'abstract': False,
            },
        ),
        migrations.CreateModel(
            name='DCCProcessedDataWorkspace',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('created', django_extensions.db.fields.CreationDateTimeField(auto_now_add=True, verbose_name='created')),
                ('modified', django_extensions.db.fields.ModificationDateTimeField(auto_now=True, verbose_name='modified')),
                ('consent_group', models.ForeignKey(help_text='Consent group associated with this data.', on_delete=django.db.models.deletion.PROTECT, to='gregor_anvil.consentgroup')),
                ('upload_cycle', models.ForeignKey(help_text='Upload cycle associated with this workspace.', on_delete=django.db.models.deletion.PROTECT, to='gregor_anvil.uploadcycle')),
                ('workspace', models.OneToOneField(on_delete=django.db.models.deletion.CASCADE, to='anvil_consortium_manager.workspace')),
            ],
        ),
        migrations.AddConstraint(
            model_name='dccprocesseddataworkspace',
            constraint=models.UniqueConstraint(fields=('upload_cycle', 'consent_group'), name='unique_dcc_processed_data_workspace'),
        ),
    ]