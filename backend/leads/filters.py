import django_filters
from django.db.models import Q
from django.utils import timezone

from .models import Lead


class CharInFilter(django_filters.BaseInFilter, django_filters.CharFilter):
    pass


class LeadFilter(django_filters.FilterSet):
    status = CharInFilter(field_name="status", lookup_expr="in")
    batch = django_filters.NumberFilter(field_name="batch_id")
    created_by = django_filters.NumberFilter(field_name="created_by_id")
    assigned_to = django_filters.CharFilter(method="filter_assigned")
    overdue = django_filters.CharFilter(method="filter_overdue")
    archived = django_filters.CharFilter(method="filter_archived")
    created_from = django_filters.DateFilter(field_name="created_at", lookup_expr="date__gte")
    created_to = django_filters.DateFilter(field_name="created_at", lookup_expr="date__lte")

    class Meta:
        model = Lead
        fields = []

    def filter_assigned(self, qs, name, value):
        if value == "none":
            return qs.filter(assigned_to__isnull=True)
        return qs.filter(assigned_to_id=value) if value.isdigit() else qs

    def filter_overdue(self, qs, name, value):
        if value not in ("1", "true", "True"):
            return qs
        return qs.filter(Q(status="waiting", next_follow_up__lt=timezone.localdate()))

    def filter_archived(self, qs, name, value):
        # By default archived leads are hidden. "1" shows them together with the rest, "only" shows just the archived ones.
        if value == "only":
            return qs.filter(archived_at__isnull=False)
        return qs if value == "1" else qs.filter(archived_at__isnull=True)

    @property
    def qs(self):
        qs = super().qs
        if not self.data.get("archived"):
            qs = qs.filter(archived_at__isnull=True)
        return qs


from rest_framework.filters import SearchFilter  # noqa: E402

from .normalize import normalize_phone  # noqa: E402


class LeadSearch(SearchFilter):
    """Search as usual, but a typed phone number (0797707154, 00962 79 770 7154) is compared in its stored E.164 form."""

    def get_search_terms(self, request):
        terms = super().get_search_terms(request)
        return [normalize_phone(t) or t if sum(c.isdigit() for c in t) >= 7 else t for t in terms]
