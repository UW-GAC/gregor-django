# Generated by Django 3.2.19 on 2023-06-15 00:50

from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('gregor_anvil', '0012_populate_upload_cycle'),
    ]

    operations = [
        migrations.AddConstraint(
            model_name='releaseworkspace',
            constraint=models.UniqueConstraint(fields=('consent_group', 'upload_cycle'), name='unique_release_workspace_2'),
        ),
        migrations.AddConstraint(
            model_name='uploadworkspace',
            constraint=models.UniqueConstraint(fields=('research_center', 'consent_group', 'upload_cycle'), name='unique_workspace_data_2'),
        ),
        migrations.RemoveConstraint(
            model_name='releaseworkspace',
            name='unique_release_workspace',
        ),
        migrations.RemoveConstraint(
            model_name='uploadworkspace',
            name='unique_workspace_data',
        ),
        migrations.RemoveConstraint(
            model_name='uploadworkspace',
            name='positive_version',
        ),
        migrations.RemoveField(
            model_name='historicaluploadworkspace',
            name='version',
        ),
        migrations.RemoveField(
            model_name='uploadworkspace',
            name='version',
        ),
        migrations.AlterField(
            model_name='combinedconsortiumdataworkspace',
            name='upload_cycle',
            field=models.ForeignKey(default=None, on_delete=django.db.models.deletion.PROTECT, to='gregor_anvil.uploadcycle'),
            preserve_default=False,
        ),
        migrations.AlterField(
            model_name='releaseworkspace',
            name='upload_cycle',
            field=models.ForeignKey(default=None, on_delete=django.db.models.deletion.PROTECT, to='gregor_anvil.uploadcycle'),
            preserve_default=False,
        ),
        migrations.AlterField(
            model_name='uploadworkspace',
            name='upload_cycle',
            field=models.ForeignKey(default=None, on_delete=django.db.models.deletion.PROTECT, to='gregor_anvil.uploadcycle'),
            preserve_default=False,
        ),
    ]