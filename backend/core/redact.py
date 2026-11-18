"""P29: free text that Commercial writes must not carry a price to Operation.

Rule (the simplest safe one): when the reader belongs to the Operation department, anything in a free-text field that looks like an
amount of money is replaced with a marker at the moment it is sent. The stored text is never changed, so Commercial, HR and the CEO
still read exactly what was written. "Looks like money" errs on the side of hiding:

  1. a number next to a currency word or symbol (JD, JOD, USD, $, €, دينار, دولار ...), with k / m / ألف / مليون after it
  2. a number written like money: grouped thousands (1,500 / 1.500,00) or exactly two decimals (12.50)
  3. a plain whole number of 4 to 7 digits (5000), except a year (1900 to 2099)

Left alone: phone numbers (8 or more digits, or starting with +), short counts and dates, and the digits inside references such as
QT/2026/11/0001 (a digit run that follows / - . or +). Arabic-Indic digits count as digits.
"""
import re

from accounts.catalog import OPERATION

D = "[0-9٠-٩۰-۹]"
NUM = rf"{D}+(?:[,.٫٬، ]{D}+)*(?:\s?(?:[kKmM]\b|ألف|مليون))?"
CURRENCY = r"(?:JOD|JD|USD|US\$|AED|SAR|EUR|GBP|\$|€|£|دينار|دنانير|دولار|ريال|درهم|د\.أ|ر\.س)"
MONEY_PATTERNS = [
    re.compile(rf"{CURRENCY}\s*{NUM}", re.I),
    re.compile(rf"{NUM}\s*{CURRENCY}", re.I),
    re.compile(rf"(?<![\w/+.\-]){D}{{1,3}}(?:[,٬]{D}{{3}})+(?:[.٫]{D}+)?(?!{D})"),
    re.compile(rf"(?<![\w/+.\-]){D}+[.٫]{D}{{2}}(?!{D})"),
    re.compile(rf"(?<![\w/+.\-]){D}{{4,7}}(?!{D})(?![.,]{D})"),
]
YEAR = re.compile(r"^(19|20)\d\d$")
MARKER = {"en": "[amount hidden]", "ar": "[مبلغ مخفي]"}


def _is_year(match):
    digits = match.group(0).translate(str.maketrans("٠١٢٣٤٥٦٧٨٩", "0123456789"))
    return bool(YEAR.match(digits))


def mask_money(text, language="en"):
    """The text with every money-like amount replaced by a marker."""
    if not text:
        return text
    marker = MARKER.get(language, MARKER["en"])
    for pattern in MONEY_PATTERNS:
        text = pattern.sub(lambda m: m.group(0) if _is_year(m) else marker, text)
    return text


def reader_is_operation(user):
    department = getattr(user, "department", None)
    return bool(user and getattr(user, "is_authenticated", False) and department and department.name == OPERATION)


def redact_for(user, text):
    """What `user` may read of a free-text value: unchanged for everyone except Operation, which gets the amounts masked."""
    return mask_money(text, getattr(user, "preferred_language", "en")) if reader_is_operation(user) else text


class RedactFreeText:
    """Serializer mixin: list the free-text fields in `redacted_fields`; Operation readers get them masked."""

    redacted_fields = ()

    def to_representation(self, instance):
        data = super().to_representation(instance)
        user = getattr(self.context.get("request"), "user", None)
        if reader_is_operation(user):
            for name in self.redacted_fields:
                if isinstance(data.get(name), str):
                    data[name] = redact_for(user, data[name])
        return data
