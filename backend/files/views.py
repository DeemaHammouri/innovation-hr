import os

from django.http import FileResponse
from django.utils import timezone
from rest_framework import serializers, status
from rest_framework.exceptions import NotFound, PermissionDenied
from rest_framework.generics import ListAPIView
from rest_framework.parsers import FormParser, MultiPartParser
from rest_framework.response import Response
from rest_framework.views import APIView

from audit.models import record
from core import access
from core.pagination import StandardPagination

from .models import Attachment

ALLOWED = {
    # extension: (leading bytes the real file must start with, content type served back)
    "pdf": (b"%PDF", "application/pdf"),
    "png": (b"\x89PNG", "image/png"),
    "jpg": (b"\xff\xd8\xff", "image/jpeg"),
    "jpeg": (b"\xff\xd8\xff", "image/jpeg"),
    "docx": (b"PK\x03\x04", "application/vnd.openxmlformats-officedocument.wordprocessingml.document"),
    "xlsx": (b"PK\x03\x04", "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"),
}
MAX_BYTES = 10 * 1024 * 1024


class AttachmentSerializer(serializers.ModelSerializer):
    uploaded_by_name = serializers.CharField(source="uploaded_by.full_name", read_only=True)

    class Meta:
        model = Attachment
        fields = ["id", "original_name", "size", "category", "uploaded_by", "uploaded_by_name", "created_at", "archived_at"]
        read_only_fields = fields


def clean_name(name):
    name = os.path.basename(str(name or "file")).replace("\x00", "").strip()
    return name[:200] or "file"


def validate_upload(upload):
    ext = clean_name(upload.name).rsplit(".", 1)[-1].lower() if "." in clean_name(upload.name) else ""
    if ext not in ALLOWED:
        raise serializers.ValidationError({"file": "Upload a PDF, PNG, JPG, DOCX or XLSX file."})
    if upload.size > MAX_BYTES:
        raise serializers.ValidationError({"file": "This file is over 10 MB. Upload a smaller one."})
    if upload.size == 0:
        raise serializers.ValidationError({"file": "This file is empty."})
    head = upload.read(8)
    upload.seek(0)
    if not head.startswith(ALLOWED[ext][0]):
        raise serializers.ValidationError({"file": "This file doesn't look like a real %s file." % ext.upper()})
    return ext


class AttachmentListCreateView(ListAPIView):
    """GET or POST /api/files/?target=contract:3 (multipart: file, category). Access always follows the parent record."""

    serializer_class = AttachmentSerializer
    pagination_class = StandardPagination
    parser_classes = [MultiPartParser, FormParser]

    def get_queryset(self):
        _, obj = access.resolve(self.request.user, self.request.query_params.get("target"))
        qs = Attachment.objects.filter(content_type=access.content_type_for(obj), object_id=obj.pk).select_related("uploaded_by")
        if self.request.query_params.get("archived") != "1":
            qs = qs.filter(archived_at__isnull=True)
        return qs

    def post(self, request):
        target, obj = access.resolve(request.user, request.query_params.get("target") or request.data.get("target"))
        category = str(request.data.get("category", ""))[:40]
        if not target.may_attach(request.user, obj, category):
            raise PermissionDenied("You can't add files to this record.")
        upload = request.FILES.get("file")
        if upload is None:
            raise serializers.ValidationError({"file": "Choose a file to upload."})
        validate_upload(upload)
        att = Attachment.objects.create(
            file=upload, original_name=clean_name(upload.name), content_type_header=ALLOWED[clean_name(upload.name).rsplit(".", 1)[-1].lower()][1],
            size=upload.size, category=category, uploaded_by=request.user,
            content_type=access.content_type_for(obj), object_id=obj.pk,
        )
        record(request.user, obj, "file_added", to_value=att.original_name)
        if target.after_attach:
            target.after_attach(request.user, obj, att)
        return Response(AttachmentSerializer(att).data, status=status.HTTP_201_CREATED)


def load_attachment(user, pk):
    att = Attachment.objects.select_related("content_type").filter(pk=pk).first()
    if att is None:
        raise NotFound("File not found.")
    target = access.target_for_model(att.content_type.model_class())
    obj = target.model.objects.filter(pk=att.object_id).first()
    if obj is None or not target.can_view(user, obj):
        raise NotFound("File not found.")
    return att, target, obj


class AttachmentDownloadView(APIView):
    def get(self, request, pk):
        att, _, _ = load_attachment(request.user, pk)
        res = FileResponse(att.file.open("rb"), as_attachment=True, filename=att.original_name, content_type=att.content_type_header)
        res["X-Content-Type-Options"] = "nosniff"
        res["Cache-Control"] = "private, no-store"
        return res


class AttachmentArchiveView(APIView):
    """Files are archived, not deleted. Whoever may attach to the record (or uploaded it) may archive it."""

    def post(self, request, pk):
        att, target, obj = load_attachment(request.user, pk)
        if att.uploaded_by_id != request.user.pk and not target.may_attach(request.user, obj, att.category):
            raise PermissionDenied("You can't archive this file.")
        if att.archived_at is None:
            att.archived_at = timezone.now()
            att.save(update_fields=["archived_at"])
            record(request.user, obj, "file_archived", from_value=att.original_name, comment=str(request.data.get("reason", ""))[:300])
        return Response(AttachmentSerializer(att).data)
