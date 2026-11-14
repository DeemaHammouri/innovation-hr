"""What quotations put on a person's My Work list."""
from django.utils import timezone

from core.mywork import provider
from core.roles import COMMERCIAL_HEAD, COMMERCIAL_MEMBER, HR_HEAD, HR_MEMBER, role_key

from .models import Quotation

CAP = 50


def item(kind, q, due=None, overdue=False):
    return {
        "kind": kind, "section": "quotations", "ref": q.ref, "title": q.lead.company_name,
        "link": f"/quotations/{q.pk}", "due": due.isoformat() if due else None, "overdue": overdue,
    }


@provider
def quotation_items(user):
    role = role_key(user)
    qs = Quotation.objects.select_related("lead")
    out = []
    if role in (HR_HEAD, HR_MEMBER):
        for q in qs.filter(status__in=["requested", "in_preparation", "changes_requested"]).order_by("created_at")[:CAP]:
            kind = {"requested": "quotation_prepare", "in_preparation": "quotation_continue", "changes_requested": "quotation_changes"}[q.status]
            out.append(item(kind, q))
    elif role in (COMMERCIAL_HEAD, COMMERCIAL_MEMBER):
        if role == COMMERCIAL_HEAD:
            for q in qs.filter(status="in_review").order_by("created_at")[:CAP]:
                out.append(item("quotation_sign", q))
        mine = qs.filter(lead__assigned_to=user) if role == COMMERCIAL_MEMBER else qs
        for q in mine.filter(status="signed").order_by("signed_at")[:CAP]:
            out.append(item("quotation_send", q))
        for q in mine.filter(status="sent").order_by("sent_at")[:CAP]:
            out.append(item("quotation_outcome", q))
        today = timezone.localdate()
        for q in mine.filter(status="waiting", next_follow_up__lte=today).order_by("next_follow_up")[:CAP]:
            late = q.next_follow_up < today
            out.append(item("quotation_followup", q, due=q.next_follow_up, overdue=late))
    return out
