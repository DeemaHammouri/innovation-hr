"""One error shape for the whole API: {"error": {"code", "message", "fields"?}}.

Views keep raising and returning errors the way DRF does. The renderer below wraps every response with a status of 400 or more on
its way out, so no endpoint can answer in another shape, and `response.data` stays the plain DRF data for in-process callers.
"""
from django.http import JsonResponse
from rest_framework.renderers import JSONRenderer

GENERIC = "Something went wrong on our side. Try again, and tell your administrator if it keeps happening."
STATUS_CODES = {
    400: "validation_error", 401: "not_authenticated", 403: "permission_denied", 404: "not_found", 405: "method_not_allowed",
    406: "not_acceptable", 409: "conflict", 415: "unsupported_media_type", 429: "rate_limited", 500: "server_error", 503: "unavailable",
}


def _text(value):
    if isinstance(value, (list, tuple)):
        return _text(value[0]) if value else ""
    if isinstance(value, dict):
        return _text(next(iter(value.values()), ""))
    return str(value)


def envelope(status_code, data):
    """Turn whatever a view sent into {"error": {...}}."""
    if isinstance(data, dict) and set(data) == {"error"}:
        return data
    code = STATUS_CODES.get(status_code, "error" if status_code < 500 else "server_error")
    fields = None
    if isinstance(data, dict):
        detail = data.get("detail")
        if detail is not None:
            message = _text(detail)
            code = getattr(detail, "code", None) or code
            if code == "authentication_failed":
                code = "not_authenticated"
        else:
            fields = {k: v if isinstance(v, (list, dict)) else [v] for k, v in data.items()}
            non_field = fields.get("non_field_errors")
            message = _text(non_field) if non_field else "Check the highlighted fields and try again."
        extra = {k: v for k, v in data.items() if k not in ("detail",)} if detail is not None else {}
        if extra:  # a message plus field errors, e.g. {"detail": "...", "field": [...]}
            fields = {k: v if isinstance(v, (list, dict)) else [v] for k, v in extra.items()}
    elif isinstance(data, list):
        message = _text(data) or "Check what you entered and try again."
        fields = {"non_field_errors": [str(x) for x in data]}
    else:
        message = _text(data) if data else GENERIC
    if status_code >= 500:
        message, fields = GENERIC, None  # never leak internals
    body = {"code": str(code), "message": message}
    if fields:
        body["fields"] = fields
    return {"error": body}


class EnvelopeJSONRenderer(JSONRenderer):
    def render(self, data, accepted_media_type=None, renderer_context=None):
        response = (renderer_context or {}).get("response")
        if response is not None and response.status_code >= 400:
            data = envelope(response.status_code, data)
        return super().render(data, accepted_media_type, renderer_context)


def error_response(status_code, message=None, code=None):
    body = envelope(status_code, {"detail": message} if message else None)
    if code:
        body["error"]["code"] = code
    return JsonResponse(body, status=status_code)


def json_404(request, exception=None):
    return error_response(404, "Not found.")


def json_405(request, *args, **kwargs):
    return error_response(405, "That method is not allowed here.")


def json_500(request):
    return error_response(500, GENERIC)


def csrf_failure(request, reason=""):
    return error_response(403, "Your session check failed. Reload the page and try again.", code="csrf_failed")
