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
    """The caller's address, for the audit trail and the sign-in throttle.

    `X-Forwarded-For` is a list every proxy appends to, and a caller can start it with anything. So it is read from the right:
    TRUSTED_PROXY_COUNT is how many hops between the caller and this app are yours (each one adds the address it saw), and the
    caller is the entry just before them in the chain `X-Forwarded-For + REMOTE_ADDR`. Anything further left is ignored, so
    rotating the header gains an attacker nothing. With 0 (the default) the header is not used at all.
    """
    from django.conf import settings

    remote = request.META.get("REMOTE_ADDR")
    trusted = getattr(settings, "TRUSTED_PROXY_COUNT", 0)
    forwarded = request.META.get("HTTP_X_FORWARDED_FOR", "")
    if trusted <= 0 or not forwarded:
        return remote
    chain = [part.strip() for part in forwarded.split(",") if part.strip()] + [remote]
    if len(chain) <= trusted:  # fewer hops than promised: the header is not what the deployment says it is
        return remote
    return chain[-(trusted + 1)]


def record_event(request, event, actor=None, target=None, identifier="", **detail):
    _check(detail)
    actor = actor if getattr(actor, "pk", None) else (request.user if getattr(getattr(request, "user", None), "pk", None) else None)
    return SecurityEvent.objects.create(
        event=event, actor=actor, target=target, identifier=identifier[:254],
        ip_address=client_ip(request) or None, user_agent=request.META.get("HTTP_USER_AGENT", "")[:300], detail=detail,
    )
