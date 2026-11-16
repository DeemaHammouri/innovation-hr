"""Seed for phase4a.js (objectives 18-19). Same way of running as phase4_obj20_21.py."""
import json, os
from django.core.files.base import ContentFile
from django.utils import timezone
from accounts.models import User
from clients.models import Client
from contracts import services as cs
from contracts.models import Contract
from core.access import content_type_for
from files.models import Attachment
from leads.models import Lead
from lookups.models import ChecklistTemplateItem
from operations.models import ChecklistItem
from operations.tests import PDF

SUF = os.environ.get("SUF", "")
U = lambda k: User.objects.get(email=f"{k}@demo.test")
mkt, cmem, hr, ceo = U("marketing"), U("commercial.member"), U("hr.head"), User.objects.get(email="ceo@innovation.test")
out = {}
n0 = Lead.objects.count() + 100
for lang in ("en", "ar"):
    ho = []
    for i, label in enumerate(("Handover A", "Handover B")):
        n = n0 + len(out) * 10 + i
        name = f"{label} {lang.upper()}{SUF}"
        lead = Lead.objects.create(ref=f"LD-9{n:04d}", company_name=name, contact_name="Sam", phone=f"07600{n:05d}", email=f"s{n}@x.com", created_by=mkt, status="qualified", assigned_to=cmem, skipped_quotation_at=timezone.now())
        c = cs.request_contract(cmem, lead)
        Contract.objects.filter(pk=c.pk).update(status="signed", signed_by=ceo, signed_at=timezone.now())
        Attachment.objects.create(file=ContentFile(PDF, name="f.pdf"), original_name="f.pdf", content_type_header="application/pdf", size=len(PDF), category="final_signed", uploaded_by=hr, content_type=content_type_for(Contract), object_id=c.pk)
        h = cs.hand_over(hr, Contract.objects.get(pk=c.pk)).handover
        ho.append(dict(id=h.pk, ref=h.ref, company=name))
    kyc = Client.objects.create(company_name=f"KYC Client {lang.upper()}{SUF}", contact_person="Kay", phone="0790008" + ("001" if lang == "en" else "002"), status="onboarding", created_by=U("operation.head"))
    for pos, t in enumerate(ChecklistTemplateItem.objects.filter(is_active=True)):
        ChecklistItem.objects.create(client=kyc, template_item=t, name_en=t.name_en, name_ar=t.name_ar, required=t.required, position=pos, expires_required=(pos == 0))
    first = ChecklistItem.objects.filter(client=kyc).order_by("position").first()
    out[lang] = dict(handovers=ho, kyc=kyc.pk, kyc_item_en=first.name_en, kyc_item_ar=first.name_ar)
json.dump(out, open(os.environ["SP"] + "/proof2.json", "w"))
print(out)
