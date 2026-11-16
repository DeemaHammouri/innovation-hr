"""One way to hand a document to a person: always through a view that has already checked access, never a public URL."""
from django.http import FileResponse, HttpResponse
from rest_framework.exceptions import ValidationError

from .pdf import build_pdf
from .word import build_docx

TYPES = {"pdf": "application/pdf", "docx": "application/vnd.openxmlformats-officedocument.wordprocessingml.document"}
LANGS = ("en", "ar", "both")


def options(request):
    """fmt (pdf or docx) and lang from the query string; the language defaults to the person's own. (Not "format": DRF reads that one itself.)"""
    fmt = str(request.query_params.get("fmt", "pdf")).lower()
    if fmt not in TYPES:
        raise ValidationError({"fmt": ["Choose pdf or docx."]})
    lang = str(request.query_params.get("lang") or getattr(request.user, "preferred_language", "") or "en").lower()
    if lang not in LANGS:
        raise ValidationError({"lang": ["Choose en, ar or both."]})
    return fmt, lang


def respond(doc, fmt, lang, override=None):
    """`override` is an Attachment (an uploaded signed copy). For PDF it replaces the generated file, because it is the document of record."""
    if override is not None and fmt == "pdf":
        res = FileResponse(override.file.open("rb"), as_attachment=True, filename=override.original_name, content_type=override.content_type_header)
        res["X-Document-Source"] = "signed-copy"
    else:
        data = build_pdf(doc, lang) if fmt == "pdf" else build_docx(doc, lang)
        res = HttpResponse(data, content_type=TYPES[fmt])
        res["Content-Disposition"] = f'attachment; filename="{doc.filename}-{lang}.{fmt}"'
        res["X-Document-Source"] = "generated"
    res["X-Content-Type-Options"] = "nosniff"
    res["Cache-Control"] = "private, no-store"
    return res
