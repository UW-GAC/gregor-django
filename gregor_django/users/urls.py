from django.urls import path

from gregor_django.users.views import (
    user_autocomplete_view,
    user_detail_view,
    user_redirect_view,
    user_search_form_view,
    user_update_view,
)

app_name = "users"
urlpatterns = [
    path("search/", view=user_search_form_view, name="search"),
    path("autocomplete/", view=user_autocomplete_view, name="autocomplete"),
    path("~redirect/", view=user_redirect_view, name="redirect"),
    path("~update/", view=user_update_view, name="update"),
    path("<str:username>/", view=user_detail_view, name="detail"),
]
