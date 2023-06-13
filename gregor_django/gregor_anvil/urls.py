from django.urls import include, path

from . import views

app_name = "gregor_anvil"


research_center_patterns = (
    [
        path("<int:pk>", views.ResearchCenterDetail.as_view(), name="detail"),
        path("", views.ResearchCenterList.as_view(), name="list"),
    ],
    "research_centers",
)

partner_group_patterns = (
    [
        path("<int:pk>", views.PartnerGroupDetail.as_view(), name="detail"),
        path("", views.PartnerGroupList.as_view(), name="list"),
    ],
    "partner_groups",
)

consent_group_patterns = (
    [
        path("<int:pk>", views.ConsentGroupDetail.as_view(), name="detail"),
        path("", views.ConsentGroupList.as_view(), name="list"),
    ],
    "consent_groups",
)

upload_cycle_patterns = (
    [
        path("<int:slug>/", views.UploadCycleDetail.as_view(), name="detail"),
        path("new/", views.UploadCycleCreate.as_view(), name="new"),
    ],
    "upload_cycles",
)

workspace_report_patterns = (
    [
        path("workspaces/", views.WorkspaceReport.as_view(), name="workspace"),
    ],
    "reports",
)
urlpatterns = [
    # path("", views.Index.as_view(), name="index"),
    path("research_centers/", include(research_center_patterns)),
    path("partner_groups", include(partner_group_patterns)),
    path("consent_groups/", include(consent_group_patterns)),
    path("upload_cycles/", include(upload_cycle_patterns)),
    path("reports/", include(workspace_report_patterns)),
]
