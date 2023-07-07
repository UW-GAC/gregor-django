from anvil_consortium_manager.forms import Bootstrap5MediaFormMixin
from dal import autocomplete
from django import forms
from django.contrib.auth import forms as admin_forms
from django.contrib.auth import get_user_model
from django.utils.translation import gettext_lazy as _

User = get_user_model()


class UserChangeForm(admin_forms.UserChangeForm):
    class Meta(admin_forms.UserChangeForm.Meta):
        model = User


class UserCreationForm(admin_forms.UserCreationForm):
    class Meta(admin_forms.UserCreationForm.Meta):
        model = User

        error_messages = {
            "username": {"unique": _("This username has already been taken.")}
        }


class UserLookupForm(Bootstrap5MediaFormMixin, forms.Form):
    """Form for the user lookup."""

    user = forms.ModelChoiceField(
        queryset=User.objects.all(),
        widget=autocomplete.ListSelect2(
            url="users:autocomplete",
            attrs={"data-theme": "bootstrap-5"},
        ),
        required=True,
        help_text="Enter either the name or username to search.",
    )
