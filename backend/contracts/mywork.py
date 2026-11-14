"""What contracts put on a person's My Work list."""
from core.mywork import provider
from core.roles import CEO, COMMERCIAL_HEAD, COMMERCIAL_MEMBER, HR_HEAD, HR_MEMBER, role_key

from .models import Contract

CAP = 50


def item(kind, c):
    return {"kind": kind, "section": "contracts", "ref": c.ref, "title": c.lead.company_name, "link": f"/contracts/{c.pk}", "due": None, "overdue": False}


@provider
def contract_items(user):
    role = role_key(user)
    qs = Contract.objects.select_related("lead")
    out = []
    if role == CEO:
        out += [item("contract_review", c) for c in qs.filter(status="ceo_review").order_by("submitted_to_ceo_at")[:CAP]]
    elif role in (HR_HEAD, HR_MEMBER):
        kinds = {"requested": "contract_draft", "drafting": "contract_continue", "returned": "contract_redraft", "signed": "contract_handover"}
        out += [item(kinds[c.status], c) for c in qs.filter(status__in=list(kinds)).order_by("created_at")[:CAP]]
    elif role in (COMMERCIAL_HEAD, COMMERCIAL_MEMBER):
        mine = qs.filter(lead__assigned_to=user) if role == COMMERCIAL_MEMBER else qs
        kinds = {"with_commercial": "contract_meeting", "returned": "contract_meeting", "meeting_logged": "contract_submit"}
        out += [item(kinds[c.status], c) for c in mine.filter(status__in=list(kinds)).order_by("created_at")[:CAP]]
    return out
