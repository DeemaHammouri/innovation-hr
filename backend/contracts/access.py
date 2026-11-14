"""Who can see and change a contract. HR drafts, Commercial runs the meeting, the CEO signs, HR hands over to Operation."""
from django.db.models import Q

from core.roles import CEO, COMMERCIAL_HEAD, COMMERCIAL_MEMBER, HR_HEAD, HR_MEMBER, OPERATION_HEAD, OPERATION_MEMBER, role_key
from leads import access as lead_access

from .models import OPEN

CONTRACT_ROLES = (CEO, COMMERCIAL_HEAD, COMMERCIAL_MEMBER, HR_HEAD, HR_MEMBER, OPERATION_HEAD, OPERATION_MEMBER)
OPERATION = (OPERATION_HEAD, OPERATION_MEMBER)
MEETING_CATS = ("visit_report", "client_signed_copy")


def has_access(user):
    return role_key(user) in CONTRACT_ROLES


def is_hr(user):
    return role_key(user) in (HR_HEAD, HR_MEMBER)


def is_head(user):
    return role_key(user) == COMMERCIAL_HEAD


def is_ceo(user):
    return role_key(user) == CEO


def visible_q(user):
    role = role_key(user)
    if role in (CEO, COMMERCIAL_HEAD, HR_HEAD, HR_MEMBER):
        return Q()
    if role == COMMERCIAL_MEMBER:
        return Q(lead__assigned_to=user)
    if role in OPERATION:
        return Q(status="handed_over")  # Operation sees a contract once it has been handed over
    return Q(pk__in=[])


def can_view(user, c):
    role = role_key(user)
    if role in (CEO, COMMERCIAL_HEAD, HR_HEAD, HR_MEMBER):
        return True
    if role == COMMERCIAL_MEMBER:
        return c.lead.assigned_to_id == user.pk
    return role in OPERATION and c.status == "handed_over"


def on_pipeline(user, c):
    return is_head(user) or (role_key(user) == COMMERCIAL_MEMBER and c.lead.assigned_to_id == user.pk)


def acts_on_lead(user, lead):
    return is_head(user) or (role_key(user) == COMMERCIAL_MEMBER and lead.assigned_to_id == user.pk)


def lead_ready(lead):
    """A qualified lead whose quotation is confirmed or skipped, with no contract in progress."""
    if lead.archived_at or lead.status != "qualified":
        return False
    cleared = lead.skipped_quotation_at or any(q.status == "confirmed" for q in lead.quotations.all())
    return bool(cleared) and not any(c.status in OPEN for c in lead.contracts.all())


def can_request(user, lead):
    return lead_ready(lead) and lead_access.can_pipeline_write(user, lead)


def flags(user, c):
    s = c.status
    return {
        "can_start": is_hr(user) and s in ("requested", "returned"),
        "can_send": is_hr(user) and s == "drafting",
        "can_log_meeting": on_pipeline(user, c) and s in ("with_commercial", "returned"),
        "can_submit": on_pipeline(user, c) and s == "meeting_logged",
        "can_review": is_ceo(user) and s == "ceo_review",
        "can_handover": is_hr(user) and s == "signed",
        "can_cancel": is_head(user) and s in OPEN,
    }


def can_write(user, c):
    return any(flags(user, c).values())


def can_attach(user, c, category=""):
    s = c.status
    if category == "draft":
        return is_hr(user) and s in ("requested", "drafting", "returned")
    if category in MEETING_CATS:
        return on_pipeline(user, c) and s in ("with_commercial", "meeting_logged", "returned")
    if category == "final_signed":
        return is_hr(user) and s == "signed"
    return (is_hr(user) or on_pipeline(user, c)) and s in OPEN
