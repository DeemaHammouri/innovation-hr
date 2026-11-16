"""Write a SecurityEvent. The only door into that table: it checks the detail for secrets first."""
import re

from .models import FORBIDDEN_DETAIL_WORDS, SecurityEvent

JWT_SHAPE = re.compile(r"^[A-Za-z0-9_-]{8,}\.[A-Za-z0-9_-]{8,}\.[A-Za-z0-9_-]{8,}$")
LONG_OPAQUE = re.compile(r"^[A-Za-z0-9+/_=-]{40,}$")


class SecretInAuditError(ValueError):
    pass


def _check(value, path="detail"):
    if isinstance(value, dict):
        for k, v in value.items():
            if any(w in str(k).lower() for w in FORBIDDEN_DETAIL_WORDS):
                raise SecretInAuditError(f"{path}.{k} looks like a secret and cannot be written to the audit trail")
            _check(v, f"{path}.{k}")
    elif isinstance(value, (list, tuple)):
        for v in value:
            _check(v, path)
    elif isinstance(value, str):
        if JWT_SHAPE.match(value) or LONG_OPAQUE.match(value):
            raise SecretInAuditError(f"{path} looks like a token and cannot be written to the audit trail")


def client_ip(request):
    from django.conf import settings

    forwarded = request.META.get("HTTP_X_FORWARDED_FOR")
    if forwarded and getattr(settings, "TRUST_X_FORWARDED_FOR", False):
        return forwarded.split(",")[0].strip()
    return request.META.get("REMOTE_ADDR")


def record_event(request, event, actor=None, target=None, identifier="", **detail):
    _check(detail)
    actor = actor if getattr(actor, "pk", None) else (request.user if getattr(getattr(request, "user", None), "pk", None) else None)
    return SecurityEvent.objects.create(
        event=event, actor=actor, target=target, identifier=identifier[:254],
        ip_address=client_ip(request) or None, user_agent=request.META.get("HTTP_USER_AGENT", "")[:300], detail=detail,
    )
