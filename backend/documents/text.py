"""Arabic needs two steps before a PDF library can print it: letters take their joined shapes, then the line is put in visual order.

`visual()` does both for one line. Mixed lines (Arabic with numbers and English names) come out in the right order too."""
import re

import arabic_reshaper
from bidi.algorithm import get_display

ARABIC = re.compile("[؀-ۿݐ-ݿࢠ-ࣿﭐ-﷿ﹰ-﻿]")
_reshaper = arabic_reshaper.ArabicReshaper(configuration={"delete_harakat": False, "support_ligatures": True})


def has_arabic(text):
    return bool(ARABIC.search(text or ""))


LATIN = re.compile("[A-Za-z]")


def is_rtl_text(text):
    """True when a paragraph is mostly Arabic: it is then laid out right to left, whatever the rest of the document does.

    A label such as "Quotation / عرض سعر" (more Latin letters) stays left to right; an Arabic sentence with an English name in it is right to left."""
    return len(ARABIC.findall(text or "")) > len(LATIN.findall(text or ""))


def visual(text, rtl):
    """The line as it must be drawn left to right on the page."""
    if not text:
        return ""
    if not has_arabic(text) and not rtl:
        return text
    return get_display(_reshaper.reshape(text), base_dir="R" if rtl else "L")


def pair_text(pair, lang):
    """A (English, Arabic) label in the chosen language. "both" prints the two together."""
    en, ar = pair
    if lang == "ar":
        return ar
    if lang == "both":
        return f"{en} / {ar}" if en != ar else en
    return en
