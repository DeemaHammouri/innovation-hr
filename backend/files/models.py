import uuid

from django.conf import settings
from django.contrib.contenttypes.models import ContentType
from django.core.files.storage import FileSystemStorage
from django.db import models
from django.utils import timezone

# Private storage: no URL is ever generated for these files. They are only served by the authenticated download view.
private_storage = FileSystemStorage(location=settings.PRIVATE_MEDIA_ROOT, base_url=None)


def stored_name(instance, filename):
    ext = filename.rsplit(".", 1)[-1].lower() if "." in filename else "bin"
    return f"{timezone.now():%Y/%m}/{uuid.uuid4().hex}.{ext}"  # never the user's file name


class Attachment(models.Model):
    file = models.FileField(storage=private_storage, upload_to=stored_name, max_length=255)
    original_name = models.CharField(max_length=200)
    content_type_header = models.CharField(max_length=100)
    size = models.PositiveIntegerField()
    category = models.CharField(max_length=40, blank=True)  # e.g. "visit_report", "client_signed_copy", "receipt"
    uploaded_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="+")
    content_type = models.ForeignKey(ContentType, on_delete=models.PROTECT, related_name="+")
    object_id = models.PositiveBigIntegerField()
    created_at = models.DateTimeField(default=timezone.now, db_index=True)
    archived_at = models.DateTimeField(null=True, blank=True, db_index=True)

    class Meta:
        ordering = ["-created_at", "-id"]
        indexes = [models.Index(fields=["content_type", "object_id", "archived_at"])]
