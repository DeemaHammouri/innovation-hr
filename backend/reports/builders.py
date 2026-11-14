from collections import defaultdict
from datetime import timedelta
from decimal import Decimal

from django.db.models import Count

from clients.models import Client
from contracts import access as contract_access
from contracts.models import Contract
from hr import attendance
from hr.models import LeaveRequest
from leads import access as lead_access
from leads.models import Lead
from leads.sla import first_contact_overdue, follow_up_overdue, sla_now
from operations.models import QAMeeting, TaskInstance
from payments import services as pay
from payments.models import Instalment, Payment
from quotations import access as quote_access
from quotations.models import Quotation

from .series import avg_hours, pct, point, series

MIN_SAMPLE = 10  # a forecast based on fewer decided records than this is refused, not guessed
EARLY = ["requested", "in_preparation", "in_review", "changes_requested", "signed"]
LATE = ["sent", "waiting"]


def _span(start, end):
    """Datetimes covering the local days start..end inclusive."""
    return attendance.bounds(start, end)


def _durations(rows):
    """rows: (earlier, later) datetimes; pairs with a missing end or one that runs backwards are left out."""
    return [later - earlier for earlier, later in rows if earlier and later and later >= earlier]


def _stage(key, rows):
    value, n = avg_hours(_durations(rows))
    return point(key, value, n)


def _reason_points(qs):
    rows = qs.exclude(rejection_reason__isnull=True).values("rejection_reason__name_en", "rejection_reason__name_ar").annotate(n=Count("id")).order_by("-n")
    return [point(f"r{i}", r["n"], r["n"], r["rejection_reason__name_en"], r["rejection_reason__name_ar"]) for i, r in enumerate(rows)]


def funnel(user, start, end):
    t0, t1 = _span(start, end)
    leads = Lead.objects.filter(lead_access.visible_q(user), created_at__gte=t0, created_at__lt=t1)
    lead_ids = list(leads.values_list("id", flat=True))
    steps = [("created", len(lead_ids)), ("contacted", leads.filter(first_contacted_at__isnull=False).count()), ("qualified", leads.filter(qualified_at__isnull=False).count())]
    out = {"section": "funnel", "records": len(lead_ids), "series": []}
    with_contracts = contract_access.has_access(user)
    with_quotes = quote_access.has_access(user)
    contracts = Contract.objects.filter(contract_access.visible_q(user), lead_id__in=lead_ids) if with_contracts else Contract.objects.none()
    quotes = Quotation.objects.filter(quote_access.visible_q(user), lead_id__in=lead_ids) if with_quotes else Quotation.objects.none()
    if with_contracts:
        steps += [("contract_signed", contracts.filter(signed_at__isnull=False).count()), ("handed_over", contracts.filter(status="handed_over").count())]
    out["series"].append(series("funnel", "count", [point(k, v) for k, v in steps], kind="funnel"))
    out["series"].append(series("conversions", "percent", [point(f"{a[0]}_to_{b[0]}", pct(b[1], a[1]), a[1]) for a, b in zip(steps, steps[1:])]))
    by_status = {r["status"]: r["n"] for r in leads.values("status").annotate(n=Count("id"))}
    out["series"].append(series("lead_status", "count", [point(s, by_status.get(s, 0)) for s in ("new", "contacted", "waiting", "qualified", "rejected")]))
    out["series"].append(series("lead_rejections", "count", _reason_points(leads.filter(status="rejected"))))
    lrows = list(leads.values_list("assigned_at", "first_contacted_at", "qualified_at"))
    stages = [_stage("assigned_to_contact", [(a, b) for a, b, _ in lrows]), _stage("contact_to_qualified", [(b, c) for _, b, c in lrows])]
    if with_quotes:
        out["series"].append(series("quotations", "count", [
            point("requested", quotes.count()),
            point("sent", quotes.filter(sent_at__isnull=False).count()),
            point("confirmed", quotes.filter(status="confirmed").count()),
            point("rejected", quotes.filter(status="rejected").count()),
        ]))
        out["series"].append(series("quotation_rejections", "count", _reason_points(quotes.filter(status="rejected"))))
        q = list(quotes.values_list("created_at", "signed_at", "sent_at", "outcome_at"))
        stages += [_stage("quote_request_to_signed", [(a, b) for a, b, _, _ in q]), _stage("quote_signed_to_sent", [(b, c) for _, b, c, _ in q]), _stage("quote_sent_to_outcome", [(c, d) for _, _, c, d in q])]
    if with_contracts:
        c = list(contracts.values_list("created_at", "signed_at", "handed_over_at"))
        stages += [_stage("contract_request_to_signed", [(a, b) for a, b, _ in c]), _stage("contract_signed_to_handover", [(b, d) for _, b, d in c])]
    out["series"].append(series("stage_hours", "hours", stages))
    today, now, sla = sla_now()
    open_leads = list(Lead.objects.filter(lead_access.visible_q(user), archived_at__isnull=True, status__in=["new", "waiting"]))
    out["series"].append(series("sla_breaches", "count", [
        point("first_contact_overdue", sum(1 for lead in open_leads if first_contact_overdue(lead, now, sla))),
        point("follow_up_overdue", sum(1 for lead in open_leads if follow_up_overdue(lead, today))),
    ]))
    return out


def revenue(user, start, end):
    today = sla_now()[0]
    insts = list(pay.with_paid(Instalment.objects.filter(cancelled_at__isnull=True).select_related("client")))
    out = {"section": "revenue", "records": len(insts), "series": [], "kpis": {}}
    for cur in sorted({i.currency for i in insts}):
        mine = [i for i in insts if i.currency == cur]
        expected, counts, received = defaultdict(Decimal), defaultdict(int), defaultdict(Decimal)
        for i in mine:
            if start <= i.due_date <= end:
                month = i.due_date.strftime("%Y-%m")
                expected[month] += i.amount
                counts[month] += 1
        for p in Payment.objects.filter(instalment__currency=cur, received_on__gte=start, received_on__lte=end):
            received[p.received_on.strftime("%Y-%m")] += p.amount if p.kind == "payment" else -p.amount
        months = sorted(set(expected) | set(received))
        out["series"].append(series(f"expected_{cur}", "money", [point(m, float(expected[m]), counts[m]) for m in months], currency=cur, kind="line"))
        out["series"].append(series(f"received_{cur}", "money", [point(m, float(received[m]), None) for m in months], currency=cur, kind="line"))
        per_client, n_over = defaultdict(Decimal), 0
        for i in mine:
            if pay.status_of(i, i.paid, today) == "overdue":
                per_client[i.client.company_name] += i.amount - i.paid
                n_over += 1
        top = sorted(per_client.items(), key=lambda kv: -kv[1])[:10]
        out["series"].append(series(f"overdue_{cur}", "money", [point(f"c{k}", float(v), None, name, name) for k, (name, v) in enumerate(top)], currency=cur))
        out["kpis"][cur] = {"overdue_total": float(sum(per_client.values())), "overdue_instalments": n_over}
    return out


def forecast(user, start, end):
    """Expected new revenue = value of quotations still open x how often quotations like them were confirmed in the past.

    P(sent) = of quotations that left the early stages, the share that reached the client. P(confirmed) = of quotations the client
    decided, the share confirmed. Both come from quotations created in start..end; either one resting on fewer than MIN_SAMPLE
    records makes the forecast refuse. Unpaid instalments are shown by month separately: that is contracted money, not an estimate.
    """
    today = sla_now()[0]
    t0, t1 = _span(start, end)
    hist = Quotation.objects.filter(created_at__gte=t0, created_at__lt=t1)
    confirmed = hist.filter(status="confirmed").count()
    rejected = hist.filter(status="rejected").count()
    reached = hist.filter(sent_at__isnull=False).count()
    dropped = hist.filter(status="cancelled", sent_at__isnull=True).count()
    decided, left_early = confirmed + rejected, reached + dropped
    out = {"section": "forecast", "records": decided, "series": [], "method": {"window_from": str(start), "window_to": str(end), "decided": decided, "left_early": left_early, "min_sample": MIN_SAMPLE}}
    unpaid, n_unpaid = defaultdict(lambda: defaultdict(Decimal)), 0
    for i in pay.with_paid(Instalment.objects.filter(cancelled_at__isnull=True)):
        left = i.amount - i.paid
        if left > 0:
            unpaid[i.currency]["overdue" if i.due_date < today else i.due_date.strftime("%Y-%m")] += left
            n_unpaid += 1
    for cur, months in unpaid.items():
        order = sorted(months, key=lambda m: "" if m == "overdue" else m)
        out["series"].append(series(f"unpaid_{cur}", "money", [point(m, float(months[m]), None) for m in order], currency=cur))
    out["unpaid_records"] = n_unpaid
    if decided < MIN_SAMPLE or left_early < MIN_SAMPLE:
        out["refused"] = True
        return out
    p_sent, p_conf = Decimal(reached) / left_early, Decimal(confirmed) / decided
    rows = defaultdict(list)
    open_qs = Quotation.objects.filter(status__in=EARLY + LATE).prefetch_related("versions")
    for q in open_qs:
        versions = list(q.versions.all())
        if versions:
            last = max(versions, key=lambda v: v.number)
            rows[last.currency].append((q.status, last.total))
    out["refused"] = False
    out["method"].update({"p_sent": float(round(p_sent, 3)), "p_confirmed": float(round(p_conf, 3)), "open_quotations": sum(len(v) for v in rows.values())})
    for cur, items in rows.items():
        total = sum(t for _, t in items)
        weighted = sum(t * p_conf * (p_sent if s in EARLY else 1) for s, t in items)
        out["series"].append(series(f"pipeline_{cur}", "money", [point("open_value", float(total), len(items)), point("expected", float(round(weighted, 2)), len(items))], currency=cur))
    return out


def operations(user, start, end):
    t0, t1 = _span(start, end)
    today = sla_now()[0]
    out = {"section": "operations", "series": []}
    clients = {r["status"]: r["n"] for r in Client.objects.values("status").annotate(n=Count("id"))}
    out["series"].append(series("clients", "count", [point(s, clients.get(s, 0)) for s in ("onboarding", "active", "inactive")]))
    out["series"].append(series("onboarding_hours", "hours", [_stage("created_to_active", list(Client.objects.filter(activated_at__gte=t0, activated_at__lt=t1).values_list("created_at", "activated_at")))]))
    tasks = TaskInstance.objects.filter(due_date__gte=start, due_date__lte=end)
    done = list(tasks.filter(status="done").values_list("due_date", "closed_at"))
    on_time = sum(1 for d, c in done if c and timezone_date(c) <= d)
    out["series"].append(series("tasks", "count", [
        point("done", len(done)), point("skipped", tasks.filter(status="skipped").count()),
        point("open", tasks.filter(status="open", due_date__gte=today).count()), point("overdue", tasks.filter(status="open", due_date__lt=today).count()),
    ]))
    out["series"].append(series("tasks_on_time", "percent", [point("done_on_time", pct(on_time, len(done)), len(done))]))
    overdue = 0
    for c in Client.objects.filter(status="active").prefetch_related("qa_meetings"):
        held = [m.held_on for m in c.qa_meetings.all()]
        if held and max(held) + timedelta(days=c.qa_cadence_days) < today:
            overdue += 1
    out["series"].append(series("qa", "count", [point("meetings_held", QAMeeting.objects.filter(held_on__gte=start, held_on__lte=end).count()), point("clients_overdue", overdue)]))
    out["records"] = tasks.count()
    return out


def timezone_date(moment):
    from django.utils import timezone
    return timezone.localtime(moment).date()


def hr(user, start, end):
    users = list(attendance.employees())
    rows = attendance.rows_for(users, start, end)
    s = attendance.summary(rows)
    closed = s["days"] - s["open_days"]
    out = {"section": "hr", "records": len(rows), "series": []}
    out["series"].append(series("headcount", "count", [point("people", len(users))]))
    out["series"].append(series("attendance", "count", [point("present_days", s["days"]), point("late_days", s["late_days"]), point("open_days", s["open_days"])]))
    out["series"].append(series("attendance_rates", "percent", [point("late_rate", pct(s["late_days"], s["days"]), s["days"])]))
    out["series"].append(series("hours", "hours", [point("avg_hours_per_day", round(s["hours"] / closed, 1) if closed > 0 else None, closed)]))
    by_type = defaultdict(int)
    for r in LeaveRequest.objects.filter(status="approved", start_date__lte=end, end_date__gte=start).select_related("leave_type"):
        by_type[(r.leave_type.name_en, r.leave_type.name_ar)] += r.days
    out["series"].append(series("leave_days", "count", [point(f"t{i}", d, None, en, ar) for i, ((en, ar), d) in enumerate(sorted(by_type.items()))]))
    out["series"].append(series("leave_pending", "count", [point("pending", LeaveRequest.objects.filter(status="pending").count())]))
    return out


BUILDERS = {"funnel": funnel, "revenue": revenue, "forecast": forecast, "operations": operations, "hr": hr}
