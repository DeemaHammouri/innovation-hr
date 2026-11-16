"""Who can see and change a quotation. HR prepares, the Commercial head signs, the Commercial pipeline sends and records the outcome."""
from django.db.models import Q

from leads import access as lead_access

from .models import OPEN


def has_access(user):
    return user.has_capability("quotation.access")


def is_hr(user):
    return user.has_capability("quotation.prepare")


def is_head(user):
    return user.has_capability("quotation.sign")


def visible_q(user):
    if user.has_capability("quotation.view_all"):
        return Q()
    if user.has_capability("quotation.view_assigned"):
        return Q(lead__assigned_to=user)
    return Q(pk__in=[])


def can_view(user, q):
    return user.has_capability("quotation.view_all") or (user.has_capability("quotation.view_assigned") and q.lead.assigned_to_id == user.pk)


def on_pipeline(user, q):
    """Whoever manages the lead pipeline, or the person the lead is assigned to."""
    return lead_access.is_head(user) or (user.has_capability("lead.work_assigned") and q.lead.assigned_to_id == user.pk)


def acts_on_lead(user, lead):
    """Whoever manages the pipeline, or the person the lead is assigned to (whatever state the lead is in)."""
    return lead_access.is_head(user) or (user.has_capability("lead.work_assigned") and lead.assigned_to_id == user.pk)


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
        "can_start": is_hr(user) and q.status in ("requested", "changes_requested") and (not q.assigned_to_id or q.assigned_to_id == user.pk or user.has_capability("quotation.assign")),
        "can_assign": user.has_capability("quotation.assign") and q.status in ("requested", "changes_requested"),
        "can_edit": is_hr(user) and q.status == "in_preparation",
        "can_review": is_head(user) and q.status == "in_review",
        "can_send": on_pipeline(user, q) and q.status == "signed",
        "can_outcome": on_pipeline(user, q) and q.status in ("sent", "waiting"),
        "can_upload_copy": on_pipeline(user, q) and q.status in ("sent", "waiting", "confirmed") and q.client_signed_via != "portal",
        "can_cancel": is_head(user) and q.status in OPEN,
        "can_print": bool(q.signed_by_id) and can_view(user, q),
    }


def can_write(user, q):
    f = flags(user, q)
    return any(v for k, v in f.items() if k != "can_print")


def can_attach(user, q, category=""):
    return (is_hr(user) or on_pipeline(user, q)) and q.status in OPEN
