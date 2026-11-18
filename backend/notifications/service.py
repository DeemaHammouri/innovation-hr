import json

from django.db import IntegrityError, transaction

from .messages import render
from .models import Notification


def json_safe(params):
    """The placeholder values as plain JSON (dates and the like become text), so they can be stored and rendered again later."""
    return json.loads(json.dumps(params, default=str))


def notify(user, kind, link="", dedupe_key="", **params):
    """Create one notification for one person, in their language. Returns None if it is a duplicate or the person is inactive.

    With a dedupe_key the database has the last word (unique constraint), so two workers sending the same reminder at the same time
    still produce one notification.
    """
    if user is None or not user.is_active:
        return None
    if dedupe_key and Notification.objects.filter(user=user, dedupe_key=dedupe_key).exists():
        return None
    title, body = render(kind, user.preferred_language, **params)
    try:
        with transaction.atomic():  # a savepoint: losing the race must not poison the caller's transaction
            return Notification.objects.create(user=user, kind=kind, title=title, body=body[:400], link=link, dedupe_key=dedupe_key, params=json_safe(params))
    except IntegrityError:
        if dedupe_key:
            return None  # another caller created it between our check and our insert
        raise


def notify_many(users, kind, exclude=None, **kwargs):
    """Notify several people, never the person who caused it."""
    seen = set()
    for u in users:
        if u is None or u.pk in seen or (exclude is not None and u.pk == exclude.pk):
            continue
        seen.add(u.pk)
        notify(u, kind, **kwargs)
