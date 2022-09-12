from django.contrib import admin

from . import models


@admin.register(models.ConsentGroup)
class ConsentGroupAdmin(admin.ModelAdmin):
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
class ResearchCenterAdmin(admin.ModelAdmin):
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


@admin.register(models.UploadWorkspace)
class UploadWorkspaceAdmin(admin.ModelAdmin):
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