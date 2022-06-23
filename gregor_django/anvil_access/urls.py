from django.urls import include, path

from . import views

app_name = "anvil_access"


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

workspace_patterns = (
    [
        path("<int:pk>", views.WorkspaceDataDetail.as_view(), name="detail"),
        path("", views.WorkspaceDataList.as_view(), name="list"),
    ],
    "workspaces",
)

urlpatterns = [
    # path("", views.Index.as_view(), name="index"),
    path("research_centers/", include(research_center_patterns)),
    path("consent_groups/", include(consent_group_patterns)),
    path("workspaces/", include(workspace_patterns)),
]
