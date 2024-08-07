from django.contrib import admin
from simple_history.admin import SimpleHistoryAdmin

from . import models


@admin.register(models.ConsentGroup)
class ConsentGroupAdmin(SimpleHistoryAdmin):
    """Admin class for the ConsentGroup model."""

    list_display = (
        "code",
        "consent",
    )
    search_fields = (
        "code",
        "consent",
        "data_use_limitations",
    )
    sortable_by = (
        "code",
        "consent",
    )


@admin.register(models.ResearchCenter)
class ResearchCenterAdmin(SimpleHistoryAdmin):
    """Admin class for the ResearchCenter model."""

    list_display = (
        "short_name",
        "full_name",
    )
    search_fields = (
        "short_name",
        "full_name",
    )
    sortable_by = (
        "short_name",
        "full_name",
    )


@admin.register(models.PartnerGroup)
class PartnerGroupAdmin(SimpleHistoryAdmin):
    """Admin class for the PartnerGroup model."""

    list_display = (
        "short_name",
        "full_name",
    )
    search_fields = (
        "short_name",
        "full_name",
    )
    sortable_by = (
        "short_name",
        "full_name",
    )


@admin.register(models.UploadCycle)
class UploadCycleAdmin(SimpleHistoryAdmin):
    """Admin class for the UploadCycle model."""

    list_display = (
        "cycle",
        "start_date",
        "end_date",
    )
    sortable_by = (
        "cycle",
        "start_date",
        "end_date",
    )


@admin.register(models.UploadWorkspace)
class UploadWorkspaceAdmin(SimpleHistoryAdmin):
    """Admin class for the UploadWorkspace model."""

    list_display = (
        "id",
        "workspace",
        "research_center",
        "consent_group",
        "upload_cycle",
    )
    list_filter = (
        "research_center",
        "consent_group",
        "upload_cycle",
    )
    sortable_by = (
        "id",
        "workspace",
        "upload_cycle",
    )


@admin.register(models.PartnerUploadWorkspace)
class PartnerUploadWorkspaceAdmin(SimpleHistoryAdmin):
    """Admin class for the PartnerUploadWorkspace model."""

    list_display = (
        "id",
        "workspace",
        "partner_group",
        "consent_group",
        "version",
    )
    list_filter = (
        "partner_group",
        "consent_group",
        "version",
    )
    sortable_by = (
        "id",
        "workspace",
        "partner_group",
        "version",
    )


@admin.register(models.ResourceWorkspace)
class ResourceWorkspaceAdmin(SimpleHistoryAdmin):
    """Admin class for the ResourceWorkspace model."""

    list_display = (
        "id",
        "workspace",
    )
    sortable_by = (
        "id",
        "workspace",
    )


@admin.register(models.TemplateWorkspace)
class TemplateWorkspaceAdmin(SimpleHistoryAdmin):
    """Admin class for the TemplateWorkspace model."""

    list_display = (
        "id",
        "workspace",
    )
    sortable_by = (
        "id",
        "workspace",
    )


@admin.register(models.CombinedConsortiumDataWorkspace)
class CombinedConsortiumDataWorkspaceAdmin(SimpleHistoryAdmin):
    """Admin class for the CombinedConsortiumDataWorkspace model."""

    list_display = (
        "id",
        "workspace",
        "upload_cycle",
    )
    list_filter = ("upload_cycle",)
    sortable_by = (
        "id",
        "workspace",
        "upload_cycle",
    )


@admin.register(models.ReleaseWorkspace)
class ReleaseWorkspaceAdmin(SimpleHistoryAdmin):
    """Admin class for the ReleaseWorkspace model."""

    list_display = (
        "id",
        "workspace",
        "upload_cycle",
        "consent_group",
    )
    list_filter = (
        "upload_cycle",
        "consent_group",
    )
    sortable_by = (
        "id",
        "workspace",
        "upload_cycle",
        "consent_group",
    )


@admin.register(models.ExchangeWorkspace)
class ExchangeWorkspaceAdmin(SimpleHistoryAdmin):
    """Admin class for the ExchangeWorkspace model."""

    list_display = (
        "id",
        "workspace",
        "research_center",
    )
