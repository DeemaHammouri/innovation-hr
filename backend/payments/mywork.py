"""The Commercial head's My Work: instalments that are overdue."""
from core.mywork import provider
from core.roles import COMMERCIAL_HEAD, role_key
from leads.sla import sla_now

from . import services
from .models import Instalment

CAP = 50


@provider
def payment_items(user):
    if role_key(user) != COMMERCIAL_HEAD:
        return []
    today = sla_now()[0]
    qs = services.with_paid(Instalment.objects.filter(cancelled_at__isnull=True, due_date__lt=today).select_related("client")).order_by("due_date")
    out = []
    for i in qs:
        if i.paid >= i.amount:
            continue
        out.append({"kind": "payment_overdue", "section": "payments", "ref": f"#{i.number}", "title": i.client.company_name, "link": f"/payments/{i.client_id}", "due": i.due_date.isoformat(), "overdue": True})
        if len(out) >= CAP:
            break
    return out
