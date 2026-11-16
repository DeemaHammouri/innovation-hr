"""Seed for phase4.js (objectives 20-21). Run with: DJANGO_DB_PATH=<throwaway> SP=<scratch folder> SUF=<n> python manage.py shell -c "exec(open(r'<this file>').read())" """
import json, os
from datetime import date, timedelta
from django.core.files.base import ContentFile
from django.utils import timezone
from accounts.models import Role, User
from clients.models import Client
from core.access import content_type_for
from files.models import Attachment
from lookups.models import ChecklistTemplateItem
from operations import lifecycle
from operations.models import ChecklistItem, RecurringTask, TaskInstance
from operations.tests import PDF

today = timezone.localdate()
head = User.objects.get(email="operation.head@demo.test"); mem = User.objects.get(email="operation.member@demo.test")
out = {}
for lang in ("en", "ar"):
    SUF = os.environ.get("SUF", ""); name = "Proof Client " + lang.upper() + SUF
    c = Client.objects.create(company_name=name, contact_person="Proof", phone="0790009" + ("001" if lang == "en" else "002"), status="active", created_by=head)
    u = User.objects.create_user(email=f"proof-{lang}{SUF}@client.test", password="Demo-12345", full_name="Proof Portal " + lang, role_ref=Role.objects.get(key="client"))
    Client.objects.filter(pk=c.pk).update(portal_user=u)
    rule = RecurringTask.objects.create(client=c, title="Monthly VAT", frequency="monthly", start_date=date(2026, 1, 1), next_due=date(2027, 1, 1), created_by=head, assignee=mem)
    def mk(title, days, n):
        return TaskInstance.objects.create(recurring=rule, client=c, title=title, due_date=today + timedelta(days=days), assignee=mem, rule_version=n, period=date(2026, 1, 1) + timedelta(days=n))
    t1 = mk("Flow task", 5, 1); t2 = mk("Late task to escalate", -3, 2); t3 = mk("VAT return to deliver", 4, 3); t4 = mk("Blocked old task", -8, 4)
    lifecycle.start(mem, t3); lifecycle.submit(mem, t3, "Filed")
    lifecycle.start(mem, t4); lifecycle.block(mem, t4, "No access to the tax portal")
    att = Attachment.objects.create(file=ContentFile(PDF, name="vat-return.pdf"), original_name="vat-return.pdf", content_type_header="application/pdf", size=len(PDF), category="other", uploaded_by=mem, content_type=content_type_for(TaskInstance), object_id=t3.pk)
    out[lang] = dict(client=c.pk, company=name, email=u.email, tasks=dict(flow=t1.pk, late=t2.pk, deliver=t3.pk, blocked=t4.pk), att=att.pk)
json.dump(out, open(os.environ["SP"] + "/proof.json", "w"))
print(out)
