"""Who can see and change a contract. HR drafts, Commercial confirms, the CEO signs, HR marks it handed over. Operation never sees a contract: it gets a handover."""
from django.db.models import Q

from leads import access as lead_access

from .models import OPEN



def has_access(user):
    return user.has_capability("contract.access")


def is_hr(user):
    return user.has_capability("contract.draft")


def is_head(user):
    """The Commercial head: cancels contracts and runs the whole pipeline."""
    return lead_access.is_head(user)


def signs_contracts(user):
    return user.has_capability("contract.sign")


def visible_q(user):
    if user.has_capability("contract.view_all"):
        return Q()
    q = Q(pk__in=[])
    if user.has_capability("contract.view_assigned"):
        q |= Q(lead__assigned_to=user)
    return q


def can_view(user, c):
    return (
        user.has_capability("contract.view_all")
        or (user.has_capability("contract.view_assigned") and c.lead.assigned_to_id == user.pk)
    )


def on_pipeline(user, c):
    return is_head(user) or (user.has_capability("lead.work_assigned") and c.lead.assigned_to_id == user.pk)


def acts_on_lead(user, lead):
    return is_head(user) or (user.has_capability("lead.work_assigned") and lead.assigned_to_id == user.pk)


def lead_ready(lead):
    """A qualified lead whose quotation is confirmed or skipped, with no contract in progress."""
    if lead.archived_at or lead.status != "qualified":
        return False
    cleared = lead.skipped_quotation_at or any(q.status == "confirmed" for q in lead.quotations.all())
    return bool(cleared) and not any(c.status in OPEN for c in lead.contracts.all())


def can_request(user, lead):
    return lead_ready(lead) and lead_access.can_pipeline_write(user, lead)


def confirms(user):
    return user.has_capability("contract.confirm")


def flags(user, c):
    s = c.status
    return {
        "can_start": is_hr(user) and s in ("requested", "returned"),
        "can_edit": is_hr(user) and s == "drafting",
        "can_send": is_hr(user) and s == "drafting",
        "can_confirm": confirms(user) and s == "with_commercial",
        "can_return": confirms(user) and s == "with_commercial",
        "can_send_to_client": is_hr(user) and s == "confirmed",
        "can_upload_client_copy": (is_hr(user) or on_pipeline(user, c)) and s == "sent",
        "can_review": signs_contracts(user) and s == "ceo_review",
        "can_handover": is_hr(user) and s == "signed",
        "can_cancel": is_head(user) and s in OPEN,
    }


def can_write(user, c):
    return any(flags(user, c).values())


def can_attach(user, c, category=""):
    s = c.status
    if category == "draft":
        return is_hr(user) and s in ("requested", "drafting", "returned")
    if category == "client_signed_copy":
        return (is_hr(user) or on_pipeline(user, c)) and s == "sent"
    if category == "final_signed":
        return (is_hr(user) and s == "signed") or (signs_contracts(user) and s == "ceo_review")
    return (is_hr(user) or on_pipeline(user, c)) and s in OPEN
