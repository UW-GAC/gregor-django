from dal import autocomplete
from django.contrib.auth import get_user_model
from django.contrib.auth.mixins import LoginRequiredMixin
from django.contrib.messages.views import SuccessMessageMixin
from django.db.models import Q
from django.urls import reverse
from django.utils.translation import gettext_lazy as _
from django.views.generic import DetailView, FormView, RedirectView, UpdateView

from .forms import UserSearchForm

User = get_user_model()


class UserDetailView(LoginRequiredMixin, DetailView):

    model = User
    slug_field = "username"
    slug_url_kwarg = "username"


user_detail_view = UserDetailView.as_view()


class UserUpdateView(LoginRequiredMixin, SuccessMessageMixin, UpdateView):

    model = User
    fields = ["name"]
    success_message = _("Information successfully updated")

    def get_success_url(self):
        return self.request.user.get_absolute_url()  # type: ignore [union-attr]

    def get_object(self):
        return self.request.user


user_update_view = UserUpdateView.as_view()


class UserRedirectView(LoginRequiredMixin, RedirectView):

    permanent = False

    def get_redirect_url(self):
        return reverse("users:detail", kwargs={"username": self.request.user.username})


user_redirect_view = UserRedirectView.as_view()


class UserAutocompleteView(LoginRequiredMixin, autocomplete.Select2QuerySetView):
    """View to provide autocompletion for User."""

    def get_result_label(self, item):
        return "{} ({})".format(item.name, item.username)

    def get_result_value(self, item):
        """Return the value of a result."""
        return item.username

    def get_queryset(self):
        qs = User.objects.all().order_by("username")

        if self.q:
            qs = qs.filter(Q(name__icontains=self.q) | Q(username__icontains=self.q))
        return qs


user_autocomplete_view = UserAutocompleteView.as_view()


class UserSearchFormView(LoginRequiredMixin, FormView):
    template_name = "users/usersearch_form.html"
    form_class = UserSearchForm

    def get_success_url(self):
        """Redirect to the user profile page after processing a valid form."""

        return reverse(
            "users:detail", kwargs={"username": self.request.POST.get("user")}
        )


user_search_form_view = UserSearchFormView.as_view()
