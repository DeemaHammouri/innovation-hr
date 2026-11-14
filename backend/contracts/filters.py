import django_filters

from .models import OPEN, Contract


class ContractFilter(django_filters.FilterSet):
    status = django_filters.BaseInFilter(field_name="status", lookup_expr="in")
    lead = django_filters.NumberFilter(field_name="lead_id")
    open = django_filters.CharFilter(method="filter_open")

    class Meta:
        model = Contract
        fields = ["status", "lead"]

    def filter_open(self, qs, name, value):
        return qs.filter(status__in=OPEN) if value in ("1", "true", "True") else qs
