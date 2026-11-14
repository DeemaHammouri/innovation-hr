"""Who can see and change a quotation. HR prepares, the Commercial head signs, the Commercial pipeline sends and records the outcome."""
from django.db.models import Q

from core.roles import CEO, COMMERCIAL_HEAD, COMMERCIAL_MEMBER, HR_HEAD, HR_MEMBER, role_key
from leads import access as lead_access

from .models import OPEN

QUOTATION_ROLES = (CEO, COMMERCIAL_HEAD, COMMERCIAL_MEMBER, HR_HEAD, HR_MEMBER)


def has_access(user):
    return role_key(user) in QUOTATION_ROLES


def is_hr(user):
    return role_key(user) in (HR_HEAD, HR_MEMBER)


def is_head(user):
    return role_key(user) == COMMERCIAL_HEAD


def visible_q(user):
    role = role_key(user)
    if role in (CEO, COMMERCIAL_HEAD, HR_HEAD, HR_MEMBER):
        return Q()
    if role == COMMERCIAL_MEMBER:
        return Q(lead__assigned_to=user)
    return Q(pk__in=[])


def can_view(user, q):
    role = role_key(user)
    if role in (CEO, COMMERCIAL_HEAD, HR_HEAD, HR_MEMBER):
        return True
    return role == COMMERCIAL_MEMBER and q.lead.assigned_to_id == user.pk


def on_pipeline(user, q):
    """The Commercial head, or the member the lead is assigned to."""
    return is_head(user) or (role_key(user) == COMMERCIAL_MEMBER and q.lead.assigned_to_id == user.pk)


def acts_on_lead(user, lead):
    """The Commercial head, or the member the lead is assigned to (whatever state the lead is in)."""
    return is_head(user) or (role_key(user) == COMMERCIAL_MEMBER and lead.assigned_to_id == user.pk)


def can_request(user, lead):
    return (
        not lead.archived_at
        and lead.status == "qualified"
        and not lead.skipped_quotation_at
        and lead_access.can_pipeline_write(user, lead)
        and not any(q.status in OPEN for q in lead.quotations.all())
    )


def flags(user, q):
    return {
        "can_start": is_hr(user) and q.status in ("requested", "changes_requested"),
        "can_edit": is_hr(user) and q.status == "in_preparation",
        "can_review": is_head(user) and q.status == "in_review",
        "can_send": on_pipeline(user, q) and q.status == "signed",
        "can_outcome": on_pipeline(user, q) and q.status in ("sent", "waiting"),
        "can_cancel": is_head(user) and q.status in OPEN,
        "can_print": bool(q.signed_by_id) and can_view(user, q),
    }


def can_write(user, q):
    f = flags(user, q)
    return any(v for k, v in f.items() if k != "can_print")


def can_attach(user, q, category=""):
    return (is_hr(user) or on_pipeline(user, q)) and q.status in OPEN
