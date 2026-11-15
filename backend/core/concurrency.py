"""Optimistic concurrency for edit forms. The form sends back the `updated_at` it loaded; if someone saved since, refuse with 409."""
from django.utils.dateparse import parse_datetime
from rest_framework.exceptions import APIException

MSG_CONFLICT = "Someone else changed this record while you were editing. Reload to see their changes, then make your edit again."


class EditConflict(APIException):
    status_code = 409
    default_detail = MSG_CONFLICT
    default_code = "conflict"


def check_fresh(instance, data):
    """No `expected_updated_at` in the request means no check (API clients that never read first keep working)."""
    token = data.get("expected_updated_at") if hasattr(data, "get") else None
    if not token:
        return
    sent = parse_datetime(str(token))
    if sent is None or sent != instance.updated_at:
        raise EditConflict()
