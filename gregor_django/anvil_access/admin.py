from django.contrib import admin

from . import models


@admin.register(models.ConsentGroup)
class ConsentGroupAdmin(admin.ModelAdmin):
    """Admin class for the ConsentGroup model."""

    list_display = ("code",)
    search_fields = (
        "code",
        "data_use_limitations",
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


@admin.register(models.WorkspaceData)
class WorkspaceDataAdmin(admin.ModelAdmin):
    """Admin class for the WorkspaceData model."""

    list_display = (
        "workspace",
        "research_center",
        "consent_group",
        "version",
    )
    list_filter = ("research_center", "consent_group")
