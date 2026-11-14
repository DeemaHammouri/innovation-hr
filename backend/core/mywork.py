"""
"My Work": what needs a person's action today. Each module registers a provider that returns plain
dicts; this file only gathers them. An item looks like:
  {"kind": "followup_overdue", "section": "pipeline", "ref": "LD-0004", "title": "Al Noor",
   "link": "/leads/4", "due": "2026-11-14" or None, "overdue": True}
`kind` is translated by the screen (my_work.kind.<kind>). `section` is the nav key that gets the badge.
"""
from collections import Counter

_PROVIDERS = []


def provider(fn):
    _PROVIDERS.append(fn)
    return fn


def collect(user):
    items = []
    for fn in _PROVIDERS:
        items.extend(fn(user))
    items.sort(key=lambda i: (not i.get("overdue", False), i.get("due") or "9999", i.get("ref", "")))
    return items


def badges(items):
    return dict(Counter(i["section"] for i in items if i.get("section")))
