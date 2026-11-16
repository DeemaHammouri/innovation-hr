"""Who can see and change a lead. One place, used by the API querysets, the record registry and the screen's permission flags."""
from django.db.models import Q

def has_lead_access(user):
    return user.has_capability("lead.access")


def visible_q(user):
    """Everything with lead.view_all; plus what is assigned to you (lead.view_assigned); plus what you added (lead.view_created)."""
    if user.has_capability("lead.view_all"):
        return Q()
    q = Q(pk__in=[])
    if user.has_capability("lead.view_assigned"):
        q |= Q(assigned_to=user)
    if user.has_capability("lead.view_created"):
        q |= Q(created_by=user)
    return q


def can_view(user, lead):
    return (
        user.has_capability("lead.view_all")
        or (user.has_capability("lead.view_assigned") and lead.assigned_to_id == user.pk)
        or (user.has_capability("lead.view_created") and lead.created_by_id == user.pk)
    )


def is_head(user):
    """Runs the whole pipeline: assign, reopen, restore, work any lead."""
    return user.has_capability("lead.manage")


def can_pipeline_write(user, lead):
    """Log contacts and outcomes: whoever manages the pipeline, or the person the lead is assigned to. Never on an archived lead."""
    if lead.archived_at:
        return False
    return is_head(user) or (user.has_capability("lead.work_assigned") and lead.assigned_to_id == user.pk)


def can_edit(user, lead):
    if lead.archived_at:
        return False
    if can_pipeline_write(user, lead):
        return True
    return user.has_capability("lead.edit_created") and lead.created_by_id == user.pk and lead.status == "new"


def can_archive(user, lead):
    if lead.archived_at:
        return False
    if is_head(user):
        return True
    return (
        user.has_capability("lead.edit_created")
        and lead.created_by_id == user.pk
        and lead.status == "new"
        and not lead.interactions.exists()
    )


def quotation_ready(user, lead):
    """A qualified lead with no quotation in progress and no skip recorded, for the head or the assigned member."""
    if not can_pipeline_write(user, lead) or lead.status != "qualified" or lead.skipped_quotation_at:
        return False
    return not any(q.status in OPEN_QUOTATION for q in lead.quotations.all())


def contract_ready(user, lead):
    """Quotation confirmed or skipped, and no contract in progress, for the head or the assigned member."""
    if not can_pipeline_write(user, lead) or lead.archived_at or lead.status != "qualified":
        return False
    cleared = lead.skipped_quotation_at or any(q.status == "confirmed" for q in lead.quotations.all())
    return bool(cleared) and not any(c.status in OPEN_CONTRACT for c in lead.contracts.all())


OPEN_CONTRACT = ("requested", "drafting", "with_commercial", "confirmed", "sent", "ceo_review", "returned", "signed")
OPEN_QUOTATION = ("requested", "in_preparation", "in_review", "changes_requested", "signed", "sent", "waiting")


def flags(user, lead):
    """What the screen may offer. The server checks each of these again on the action itself."""
    return {
        "can_edit": can_edit(user, lead),
        "can_assign": is_head(user) and not lead.archived_at,
        "can_log": can_pipeline_write(user, lead) and lead.status in ("new", "contacted", "waiting"),
        "can_decide": user.has_capability("client.decide") and can_pipeline_write(user, lead) and hasattr(lead, "client"),
        "can_reopen": is_head(user) and not lead.archived_at and lead.status == "rejected",
        "can_archive": can_archive(user, lead),
        "can_restore": is_head(user) and bool(lead.archived_at),
        "can_request_quotation": quotation_ready(user, lead),
        "can_skip_quotation": quotation_ready(user, lead),
        "can_request_contract": contract_ready(user, lead),
    }
