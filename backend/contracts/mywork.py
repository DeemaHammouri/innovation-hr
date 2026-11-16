"""What contracts put on a person's My Work list."""
from core.mywork import provider

from .models import Contract

CAP = 50


def item(kind, c):
    return {"kind": kind, "section": "contracts", "ref": c.ref, "title": c.lead.company_name, "link": f"/contracts/{c.pk}", "due": None, "overdue": False}


@provider
def contract_items(user):
    head = user.has_capability("lead.manage")
    member = user.has_capability("lead.work_assigned")
    qs = Contract.objects.select_related("lead")
    out = []
    if user.has_capability("contract.sign"):
        out += [item("contract_review", c) for c in qs.filter(status="ceo_review").order_by("submitted_to_ceo_at")[:CAP]]
    elif user.has_capability("contract.draft"):
        kinds = {"requested": "contract_draft", "drafting": "contract_continue", "returned": "contract_redraft", "signed": "contract_handover"}
        out += [item(kinds[c.status], c) for c in qs.filter(status__in=list(kinds)).order_by("created_at")[:CAP]]
    elif head or member:
        mine = qs if head else qs.filter(lead__assigned_to=user)
        kinds = {"with_commercial": "contract_meeting", "returned": "contract_meeting", "meeting_logged": "contract_submit"}
        out += [item(kinds[c.status], c) for c in mine.filter(status__in=list(kinds)).order_by("created_at")[:CAP]]
    return out
