from anvil_consortium_manager.forms import FilterForm
from anvil_consortium_manager.models import Account
from django_filters import FilterSet


class AccountListFilter(FilterSet):
    class Meta:
        model = Account
        fields = {"email": ["icontains"], "user__name": ["icontains"]}
        form = FilterForm
