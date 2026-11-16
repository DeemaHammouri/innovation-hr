from django.db.models import Q


def visible_q(user):
    if user.has_capability("meeting_report.view_all"):
        return Q()
    if not user.has_capability("meeting_report.write"):
        return Q(pk__in=[])
    q = Q(author=user)
    if user.has_capability("lead.view_assigned"):
        q |= Q(lead__assigned_to=user)
    return q


def flags(user, r):
    s = r.status
    mine = r.author_id == user.pk
    return {
        "can_edit": s in ("draft", "returned") and (mine or user.has_capability("meeting_report.sign")),
        "can_sign": user.has_capability("meeting_report.sign") and s in ("draft", "returned"),
        "can_approve": user.has_capability("meeting_report.approve") and s == "signed",
        "can_return": user.has_capability("meeting_report.approve") and s == "signed",
    }
