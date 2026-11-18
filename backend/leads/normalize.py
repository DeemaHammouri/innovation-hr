"""One place that decides what a phone number or an email "is", so the form, the import, the duplicate check and the database agree.

Phones become E.164 (+9627...). The default country is the DEFAULT_PHONE_REGION setting (Jordan, "JO", unless changed): with it 07xxxxxxxx -> +9627xxxxxxxx.
00 means "+". Arabic-Indic digits are read as digits.
"""
import re

import phonenumbers
from django.conf import settings

_ARABIC_DIGITS = str.maketrans("٠١٢٣٤٥٦٧٨٩۰۱۲۳۴۵۶۷۸۹", "01234567890123456789")


def ascii_digits(text):
    return str(text or "").translate(_ARABIC_DIGITS)


def default_region():
    region = str(getattr(settings, "DEFAULT_PHONE_REGION", "JO")).upper()
    return region if phonenumbers.country_code_for_region(region) else "JO"  # an unknown code must not break every phone number


def normalize_phone(raw):
    """E.164 string, or "" when the text has fewer than 7 digits."""
    region = default_region()
    dial = str(phonenumbers.country_code_for_region(region) or 962)
    text = ascii_digits(raw).strip()
    digits = re.sub(r"\D", "", text)
    if len(digits) < 7:
        return ""
    candidate = text
    if digits.startswith("00"):
        candidate = "+" + digits[2:]
    elif text.startswith("+"):
        candidate = "+" + digits
    elif digits.startswith(dial):
        candidate = "+" + digits
    try:
        number = phonenumbers.parse(candidate, region)
        if phonenumbers.is_possible_number(number):
            return phonenumbers.format_number(number, phonenumbers.PhoneNumberFormat.E164)
    except phonenumbers.NumberParseException:
        pass
    # Not a number the library knows: still give a stable form, so the same digits always match each other.
    if candidate.startswith("+"):
        return "+" + digits.lstrip("0") if candidate.startswith("+") else ""
    return f"+{dial}" + digits.lstrip("0") if digits.startswith("0") else "+" + digits


def normalize_email(raw):
    return str(raw or "").strip().lower()
