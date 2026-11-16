"""Seed for phase5.js (objective 22). Same way of running as phase4_obj20_21.py."""
import json, os
from datetime import timedelta
from django.utils import timezone
from accounts.models import User
from generaltasks import services
from generaltasks.models import GeneralTask

SUF = os.environ.get("SUF", "")
U = lambda k: User.objects.get(email=f"{k}@demo.test")
head, mem, chead, cmem = U("operation.head"), U("operation.member"), U("commercial.head"), U("commercial.member")
today = timezone.localdate()
out = {}
for lang in ("en", "ar"):
    t = dict(open=f"Open task {lang.upper()}{SUF}", late=f"Late task {lang.upper()}{SUF}", other=f"Commercial task {lang.upper()}{SUF}", today=f"Due today task {lang.upper()}{SUF}")
    def give(giver, who, title, days):
        task = services.create(giver, {"title": title, "assignee": who.pk, "deadline": (today + timedelta(days=days)).isoformat()})
        return task
    a = give(head, mem, t["open"], 5)
    b = give(head, mem, t["late"], 3)
    GeneralTask.objects.filter(pk=b.pk).update(deadline=today - timedelta(days=2))  # the past cannot be chosen in the form
    c = give(chead, cmem, t["other"], 4)
    d = give(head, mem, t["today"], 0)
    out[lang] = dict(titles=t, ids=dict(open=a.pk, late=b.pk, other=c.pk))
json.dump(out, open(os.environ["SP"] + "/proof3.json", "w"))
