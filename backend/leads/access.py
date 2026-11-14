"""Who can see and change a lead. One place, used by the API querysets, the record registry and the screen's permission flags."""
from django.db.models import Q

from core.roles import CEO, COMMERCIAL_HEAD, COMMERCIAL_MEMBER, MARKETING_USER, role_key

LEAD_ROLES = (CEO, MARKETING_USER, COMMERCIAL_HEAD, COMMERCIAL_MEMBER)


def has_lead_access(user):
    return role_key(user) in LEAD_ROLES


def visible_q(user):
    """CEO and the Commercial head see everything. A Commercial member sees what is assigned to them. Marketing sees what they added."""
    role = role_key(user)
    if role in (CEO, COMMERCIAL_HEAD):
        return Q()
    if role == COMMERCIAL_MEMBER:
        return Q(assigned_to=user)
    if role == MARKETING_USER:
        return Q(created_by=user)
    return Q(pk__in=[])


def can_view(user, lead):
    role = role_key(user)
    if role in (CEO, COMMERCIAL_HEAD):
        return True
    if role == COMMERCIAL_MEMBER:
        return lead.assigned_to_id == user.pk
    if role == MARKETING_USER:
        return lead.created_by_id == user.pk
    return False


def is_head(user):
    return role_key(user) == COMMERCIAL_HEAD


def can_pipeline_write(user, lead):
    """Log contacts and outcomes: the Commercial head, or the member the lead is assigned to. Never on an archived lead."""
    if lead.archived_at:
        return False
    return is_head(user) or (role_key(user) == COMMERCIAL_MEMBER and lead.assigned_to_id == user.pk)


def can_edit(user, lead):
    if lead.archived_at:
        return False
    if can_pipeline_write(user, lead):
        return True
    return role_key(user) == MARKETING_USER and lead.created_by_id == user.pk and lead.status == "new"


def can_archive(user, lead):
    if lead.archived_at:
        return False
    if is_head(user):
        return True
    return (
        role_key(user) == MARKETING_USER
        and lead.created_by_id == user.pk
        and lead.status == "new"
        and not lead.interactions.exists()
    )


def flags(user, lead):
    """What the screen may offer. The server checks each of these again on the action itself."""
    return {
        "can_edit": can_edit(user, lead),
        "can_assign": is_head(user) and not lead.archived_at,
        "can_log": can_pipeline_write(user, lead) and lead.status in ("new", "contacted", "waiting"),
        "can_reopen": is_head(user) and not lead.archived_at and lead.status == "rejected",
        "can_archive": can_archive(user, lead),
        "can_restore": is_head(user) and bool(lead.archived_at),
    }
