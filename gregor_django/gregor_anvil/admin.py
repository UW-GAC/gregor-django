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


@admin.register(models.UploadWorkspace)
class UploadWorkspaceAdmin(SimpleHistoryAdmin):
    """Admin class for the UploadWorkspace model."""

    list_display = (
        "id",
        "workspace",
        "research_center",
        "consent_group",
        "version",
    )
    list_filter = (
        "research_center",
        "consent_group",
    )
    sortable_by = (
        "id",
        "workspace",
        "version",
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
