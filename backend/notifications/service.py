from .messages import render
from .models import Notification


def notify(user, kind, link="", dedupe_key="", **params):
    """Create one notification for one person, in their language. Returns None if it is a duplicate or the person is inactive."""
    if user is None or not user.is_active:
        return None
    if dedupe_key and Notification.objects.filter(user=user, dedupe_key=dedupe_key).exists():
        return None
    title, body = render(kind, user.preferred_language, **params)
    return Notification.objects.create(user=user, kind=kind, title=title, body=body[:400], link=link, dedupe_key=dedupe_key)


def notify_many(users, kind, exclude=None, **kwargs):
    """Notify several people, never the person who caused it."""
    seen = set()
    for u in users:
        if u is None or u.pk in seen or (exclude is not None and u.pk == exclude.pk):
            continue
        seen.add(u.pk)
        notify(u, kind, **kwargs)
