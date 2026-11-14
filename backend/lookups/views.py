from rest_framework import serializers, viewsets
from rest_framework.generics import RetrieveUpdateAPIView
from rest_framework.permissions import SAFE_METHODS, BasePermission

from accounts.permissions import PasswordChangeNotPending
from core.roles import CEO, role_key

from .models import ChecklistTemplateItem, RejectionReason, Service, SlaSetting, WorkHours


class CEOWritesEveryoneReads(BasePermission):
    """Every signed-in person can read a lookup (forms need them). Only the CEO can change one."""

    message = "Only the CEO can change these settings."

    def has_permission(self, request, view):
        if not (request.user and request.user.is_authenticated):
            return False
        return request.method in SAFE_METHODS or role_key(request.user) == CEO


PERMS = [CEOWritesEveryoneReads, PasswordChangeNotPending]


def bilingual_fields(extra=()):
    return ["id", "name_en", "name_ar", "is_active", "sort_order", *extra]


class BilingualSerializer(serializers.ModelSerializer):
    def validate(self, attrs):
        for key in ("name_en", "name_ar"):
            if key in attrs:
                attrs[key] = attrs[key].strip()
                if not attrs[key]:
                    label = "English" if key == "name_en" else "Arabic"
                    raise serializers.ValidationError({key: f"Enter the {label} name."})
                same = self.Meta.model.objects.filter(**{f"{key}__iexact": attrs[key]})
                if self.instance:
                    same = same.exclude(pk=self.instance.pk)
                if same.exists():
                    raise serializers.ValidationError({key: "This name is already in the list."})
        return attrs


def make_serializer(model, extra=()):
    meta = type("Meta", (), {"model": model, "fields": bilingual_fields(extra)})
    return type(f"{model.__name__}Serializer", (BilingualSerializer,), {"Meta": meta})


class LookupViewSet(viewsets.ModelViewSet):
    """List, create, edit. No delete: switch a value off with is_active=false."""

    permission_classes = PERMS
    pagination_class = None
    http_method_names = ["get", "post", "patch", "head", "options"]

    def get_queryset(self):
        qs = self.queryset.all()
        if self.request.query_params.get("active") == "1":
            qs = qs.filter(is_active=True)
        return qs


class RejectionReasonViewSet(LookupViewSet):
    queryset = RejectionReason.objects.all()
    serializer_class = make_serializer(RejectionReason)


class ServiceViewSet(LookupViewSet):
    queryset = Service.objects.all()
    serializer_class = make_serializer(Service, ("default_unit_price", "currency"))


class ChecklistTemplateItemViewSet(LookupViewSet):
    queryset = ChecklistTemplateItem.objects.all()
    serializer_class = make_serializer(ChecklistTemplateItem, ("required",))


def singleton_view(model, fields):
    meta = type("Meta", (), {"model": model, "fields": fields})
    ser = type(f"{model.__name__}Serializer", (serializers.ModelSerializer,), {"Meta": meta})

    class View(RetrieveUpdateAPIView):
        permission_classes = PERMS
        serializer_class = ser
        http_method_names = ["get", "patch", "head", "options"]

        def get_object(self):
            return model.get()

    return View


WorkHoursView = singleton_view(WorkHours, ["work_start", "work_end", "grace_minutes"])
SlaView = singleton_view(SlaSetting, ["first_contact_hours", "follow_up_days"])
