import django_filters
from django.utils import timezone

from .models import Quotation


class QuotationFilter(django_filters.FilterSet):
    status = django_filters.BaseInFilter(field_name="status", lookup_expr="in")
    lead = django_filters.NumberFilter(field_name="lead_id")
    overdue = django_filters.CharFilter(method="filter_overdue")
    open = django_filters.CharFilter(method="filter_open")

    class Meta:
        model = Quotation
        fields = ["status", "lead"]

    def filter_overdue(self, qs, name, value):
        if value not in ("1", "true", "True"):
            return qs
        return qs.filter(status="waiting", next_follow_up__lt=timezone.localdate())

    def filter_open(self, qs, name, value):
        if value not in ("1", "true", "True"):
            return qs
        return qs.exclude(status__in=["confirmed", "rejected", "cancelled"])
