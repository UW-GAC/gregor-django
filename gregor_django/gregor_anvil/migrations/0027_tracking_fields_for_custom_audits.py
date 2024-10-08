# Generated by Django 4.2.15 on 2024-08-27 21:58

from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ("anvil_consortium_manager", "0019_accountuserarchive"),
        ("gregor_anvil", "0026_historicalpartnergroup_drupal_node_id_and_more"),
    ]

    operations = [
        migrations.AddField(
            model_name="combinedconsortiumdataworkspace",
            name="date_completed",
            field=models.DateField(
                blank=True,
                default=None,
                help_text="Date that data preparation in this workspace was completed.",
                null=True,
            ),
        ),
        migrations.AddField(
            model_name="historicalcombinedconsortiumdataworkspace",
            name="date_completed",
            field=models.DateField(
                blank=True,
                default=None,
                help_text="Date that data preparation in this workspace was completed.",
                null=True,
            ),
        ),
        migrations.AddField(
            model_name="historicalresearchcenter",
            name="non_member_group",
            field=models.ForeignKey(
                blank=True,
                db_constraint=False,
                help_text="The AnVIL group containing non-members from this Research Center.",
                null=True,
                on_delete=django.db.models.deletion.DO_NOTHING,
                related_name="+",
                to="anvil_consortium_manager.managedgroup",
            ),
        ),
        migrations.AddField(
            model_name="historicaluploadcycle",
            name="date_ready_for_compute",
            field=models.DateField(
                blank=True,
                default=None,
                help_text="Date that this workspace was ready for RC uploaders to run compute.",
                null=True,
            ),
        ),
        migrations.AddField(
            model_name="historicaluploadworkspace",
            name="date_qc_completed",
            field=models.DateField(
                blank=True,
                default=None,
                help_text="Date that QC was completed for this workspace. If null, QC is not complete.",
                null=True,
            ),
        ),
        migrations.AddField(
            model_name="researchcenter",
            name="non_member_group",
            field=models.OneToOneField(
                blank=True,
                help_text="The AnVIL group containing non-members from this Research Center.",
                null=True,
                on_delete=django.db.models.deletion.PROTECT,
                related_name="research_center_of_non_members",
                to="anvil_consortium_manager.managedgroup",
            ),
        ),
        migrations.AddField(
            model_name="uploadcycle",
            name="date_ready_for_compute",
            field=models.DateField(
                blank=True,
                default=None,
                help_text="Date that this workspace was ready for RC uploaders to run compute.",
                null=True,
            ),
        ),
        migrations.AddField(
            model_name="uploadworkspace",
            name="date_qc_completed",
            field=models.DateField(
                blank=True,
                default=None,
                help_text="Date that QC was completed for this workspace. If null, QC is not complete.",
                null=True,
            ),
        ),
    ]
