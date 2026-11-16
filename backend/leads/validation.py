"""Field rules shared by the manual form and the CSV import, so a row is judged the same way in both."""
import re

from django.core.exceptions import ValidationError as DjangoValidationError
from django.core.validators import validate_email

from .normalize import ascii_digits

MSG_COMPANY = "Enter the company name."
MSG_COMPANY_LONG = "Keep the company name under 200 characters."
MSG_PHONE = "Enter a phone number with at least 7 digits (numbers, spaces, + and - only)."
MSG_EMAIL = "Enter a valid email address."
MSG_CONTACT_REQUIRED = "Add a phone number or an email so someone can reach this lead."
MSG_CONTACT_LONG = "Keep the contact name under 150 characters."
MSG_SOURCE_LONG = "Keep the source under 150 characters."
MSG_POSITION_LONG = "Keep the position under 150 characters."
MSG_LOCATION_LONG = "Keep the location under 200 characters."

PHONE_CHARS = re.compile(r"^[+0-9٠-٩۰-۹()\-\s.]{1,30}$")


FIELDS = ("company_name", "contact_name", "position", "phone", "email", "location", "source", "notes")


def clean_lead_fields(data):
    """Returns (cleaned values, {field: message}). Missing fields count as empty."""
    out = {k: str(data.get(k) or "").strip() for k in FIELDS}
    errors = {}
    if not out["company_name"]:
        errors["company_name"] = MSG_COMPANY
    elif len(out["company_name"]) > 200:
        errors["company_name"] = MSG_COMPANY_LONG
    if len(out["contact_name"]) > 150:
        errors["contact_name"] = MSG_CONTACT_LONG
    if len(out["position"]) > 150:
        errors["position"] = MSG_POSITION_LONG
    if len(out["location"]) > 200:
        errors["location"] = MSG_LOCATION_LONG
    if len(out["source"]) > 150:
        errors["source"] = MSG_SOURCE_LONG
    if out["phone"]:
        digits = re.sub(r"\D", "", ascii_digits(out["phone"]))
        if not PHONE_CHARS.match(out["phone"]) or len(digits) < 7:
            errors["phone"] = MSG_PHONE
    if out["email"]:
        try:
            validate_email(out["email"])
        except DjangoValidationError:
            errors["email"] = MSG_EMAIL
        if len(out["email"]) > 254:
            errors["email"] = MSG_EMAIL
    if not out["phone"] and not out["email"] and "phone" not in errors and "email" not in errors:
        errors["phone"] = MSG_CONTACT_REQUIRED
    return out, errors
