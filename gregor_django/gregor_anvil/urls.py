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

consent_group_patterns = (
    [
        path("<int:pk>", views.ConsentGroupDetail.as_view(), name="detail"),
        path("", views.ConsentGroupList.as_view(), name="list"),
    ],
    "consent_groups",
)

upload_workspace_patterns = (
    [
        path(
            "autocomplete/",
            views.UploadWorkspaceAutocomplete.as_view(),
            name="autocomplete",
        ),
    ],
    "upload_workspaces",
)
workspace_report_patterns = (
    [
        path("", views.WorkspaceReport.as_view(), name="report"),
    ],
    "workspace_report",
)
urlpatterns = [
    # path("", views.Index.as_view(), name="index"),
    path("research_centers/", include(research_center_patterns)),
    path("consent_groups/", include(consent_group_patterns)),
    path("upload_workspaces/", include(upload_workspace_patterns)),
    path("workspace_report/", include(workspace_report_patterns)),
]
