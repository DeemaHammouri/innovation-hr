from rest_framework import serializers, viewsets
from rest_framework.generics import RetrieveUpdateAPIView


from .models import ChecklistTemplateItem, RejectionReason, Service, SlaSetting, WorkHours


# Every signed-in person can read a lookup (forms need them). Only settings.manage can change one.
CAPS = {
    "list": [], "retrieve": [], "get": [],
    "create": ["settings.manage"], "update": ["settings.manage"], "partial_update": ["settings.manage"], "destroy": ["settings.manage"],
    "put": ["settings.manage"], "patch": ["settings.manage"],
}
DENIED = "Only the CEO can change these settings."


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

    required_capabilities = CAPS
    denied_message = DENIED
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


PRICE_FIELDS = ("default_unit_price", "currency")
PRICE_CAPABILITIES = ("settings.manage", "quotation.prepare")  # the CEO who sets the list and HR who prices a quotation with it


class ServiceSerializer(make_serializer(Service, PRICE_FIELDS)):
    """The names of the services are for everyone; the price list is not. Whoever may not price a quotation gets the names only."""

    def to_representation(self, instance):
        data = super().to_representation(instance)
        request = self.context.get("request")
        user = getattr(request, "user", None)
        if not (user and any(user.has_capability(c) for c in PRICE_CAPABILITIES)):
            for f in PRICE_FIELDS:
                data.pop(f, None)
        return data


class ServiceViewSet(LookupViewSet):
    queryset = Service.objects.all()
    serializer_class = ServiceSerializer


class ChecklistTemplateItemViewSet(LookupViewSet):
    queryset = ChecklistTemplateItem.objects.all()
    serializer_class = make_serializer(ChecklistTemplateItem, ("required", "has_expiry"))


def singleton_view(model, fields):
    meta = type("Meta", (), {"model": model, "fields": fields})
    ser = type(f"{model.__name__}Serializer", (serializers.ModelSerializer,), {"Meta": meta})

    class View(RetrieveUpdateAPIView):
        required_capabilities = CAPS
        denied_message = DENIED
        serializer_class = ser
        http_method_names = ["get", "patch", "head", "options"]

        def get_object(self):
            return model.get()

    return View


WorkHoursView = singleton_view(WorkHours, ["work_start", "work_end", "grace_minutes"])
SlaView = singleton_view(SlaSetting, ["first_contact_hours", "follow_up_days"])
