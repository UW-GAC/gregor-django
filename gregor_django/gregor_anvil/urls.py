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

urlpatterns = [
    # path("", views.Index.as_view(), name="index"),
    path("research_centers/", include(research_center_patterns)),
]
