"""
Every notification text, in both languages. A module adds its kinds here.
Placeholders use str.format names: {name}, {ref}, {actor}, {who}.
"""

CATALOG = {
    "assigned": {
        "en": ("{actor} assigned you {ref}", "{name}"),
        "ar": ("قام {actor} بإسنادك إلى {ref}", "{name}"),
    },
    "mention": {
        "en": ("{actor} mentioned you in {ref}", "{name}"),
        "ar": ("أشار إليك {actor} في {ref}", "{name}"),
    },
    "comment": {
        "en": ("{actor} commented on {ref}", "{name}"),
        "ar": ("علّق {actor} على {ref}", "{name}"),
    },
    "request_received": {
        "en": ("New request: {ref}", "{name}"),
        "ar": ("طلب جديد: {ref}", "{name}"),
    },
    "returned": {
        "en": ("{ref} was returned with changes", "{name}"),
        "ar": ("أُعيد {ref} مع طلب تعديلات", "{name}"),
    },
    "approved": {
        "en": ("{ref} was approved", "{name}"),
        "ar": ("تمت الموافقة على {ref}", "{name}"),
    },
    "signed": {
        "en": ("{ref} was signed", "{name}"),
        "ar": ("تم توقيع {ref}", "{name}"),
    },
    "overdue": {
        "en": ("{ref} is overdue", "{name}"),
        "ar": ("{ref} متأخر عن موعده", "{name}"),
    },
    "payment_overdue": {
        "en": ("Payment overdue: {ref}", "{name}"),
        "ar": ("دفعة متأخرة: {ref}", "{name}"),
    },
}


def render(kind, lang, **params):
    entry = CATALOG.get(kind)
    if entry is None:
        return kind, ""
    title, body = entry.get(lang) or entry["en"]
    safe = {k: ("" if v is None else v) for k, v in params.items()}

    class _Blank(dict):
        def __missing__(self, key):
            return ""

    return title.format_map(_Blank(safe)).strip(), body.format_map(_Blank(safe)).strip()
