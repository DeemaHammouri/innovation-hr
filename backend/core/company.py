"""The company details documents are built from: names, number prefixes and the stamp. Only people with company.manage change them."""
import re

from django.core.files.base import ContentFile
from django.http import FileResponse
from rest_framework import serializers
from rest_framework.exceptions import NotFound
from rest_framework.parsers import FormParser, JSONParser, MultiPartParser
from rest_framework.response import Response
from rest_framework.views import APIView

from audit.models import record

from .models import CompanyProfile

PREFIX = re.compile(r"^[A-Za-z0-9]{1,12}$")
MAX_STAMP = 500_000


def as_json(p):
    return {
        "name_en": p.name_en, "name_ar": p.name_ar, "quotation_prefix": p.quotation_prefix, "contract_prefix": p.contract_prefix,
        "has_stamp": bool(p.stamp), "updated_at": p.updated_at,
    }


class CompanyView(APIView):
    required_capabilities = {"get": ["company.manage"], "patch": ["company.manage"]}
    parser_classes = [MultiPartParser, FormParser, JSONParser]

    def get(self, request):
        return Response(as_json(CompanyProfile.get()))

    def patch(self, request):
        p = CompanyProfile.get()
        errors = {}
        for field, limit in (("name_en", 120), ("name_ar", 120)):
            if field in request.data:
                value = str(request.data[field]).strip()
                if not value or len(value) > limit:
                    errors[field] = ["Enter the company name (up to 120 characters)."]
                else:
                    setattr(p, field, value)
        for field in ("quotation_prefix", "contract_prefix"):
            if field in request.data:
                value = str(request.data[field]).strip().upper()
                if not PREFIX.match(value):
                    errors[field] = ["Use 1 to 12 letters or digits."]
                else:
                    setattr(p, field, value)
        upload = request.FILES.get("stamp")
        if upload is not None:
            head = upload.read(8)
            upload.seek(0)
            if not head.startswith(b"\x89PNG") or upload.size > MAX_STAMP or upload.size == 0:
                errors["stamp"] = ["Upload the stamp as a PNG image under 500 KB."]
            else:
                p.stamp.save("stamp.png", ContentFile(upload.read()), save=False)
        if errors:
            raise serializers.ValidationError(errors)
        p.save()
        record(request.user, p, "company_changed")
        return Response(as_json(p))


class CompanyStampView(APIView):
    required_capabilities = ["company.manage"]

    def get(self, request):
        p = CompanyProfile.get()
        if not p.stamp:
            raise NotFound("No stamp yet.")
        res = FileResponse(p.stamp.open("rb"), content_type="image/png")
        res["Cache-Control"] = "private, no-store"
        res["X-Content-Type-Options"] = "nosniff"
        return res
