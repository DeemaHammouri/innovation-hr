"""
Operation: onboarding a client, the KYC checklist, recurring tasks and follow-up QA meetings.

A client created by a contract handover starts "onboarding" and becomes "active" the moment every required checklist item is
verified (or marked not applicable with a reason). If a required item stops being satisfied later, it goes back to "onboarding".
"""
from datetime import date, timedelta

from django.conf import settings
from django.db import transaction
from django.utils import timezone
from rest_framework.exceptions import ValidationError

from accounts.models import User
from audit.models import record
from clients.models import Client
from core.access import content_type_for
from files.models import Attachment
from lookups.models import ChecklistTemplateItem, Holiday
from notifications.service import notify, notify_many

from . import recurrence
from .models import ChecklistItem, ChecklistItemVersion, QAMeeting, RecurringTask, TaskInstance

MSG_STATE = "That can't be done in the current state."
MSG_NO_FILE = "Upload the document first."
MSG_REASON = "Write why this item does not apply."
MSG_NAME = "Enter the document name in both languages."
MSG_NOTE_LONG = "Keep this under 1000 characters."
MSG_TITLE = "Enter a title for the task."
MSG_FREQUENCY = "Choose how often it repeats."
MSG_INTERVAL = "Enter a number of days from 1 to 365."
MSG_DAY_RULE = "Choose which day of the month it falls on."
MSG_DAY_RULE_FREQUENCY = "A first or last working day, or a weekday of the month, only works for monthly, quarterly, every 6 months and yearly tasks."
MSG_NTH = "Choose the 1st, 2nd, 3rd, 4th or last."
MSG_WEEKDAY = "Choose the day of the week."
MSG_POLICY = "Choose what happens when the date is a weekend day or a holiday."
MSG_START = "Choose the first due date."
MSG_START_OLD = "Choose today or a later date."
MSG_ASSIGNEE = "Choose someone from Operation."
MSG_SKIP = "Write why you are skipping this task."
MSG_HELD = "Choose the date the meeting took place."
MSG_HELD_FUTURE = "The meeting date can't be in the future."
MSG_MEETING_NOTES = "Write what was discussed in the meeting."
MSG_NEXT = "Choose a date after the meeting."
MSG_CADENCE = "Enter a number of days from 7 to 365."
MSG_TASK_CLOSED = "This task is already closed."
MSG_EXPIRY = "Enter the date this document stops being valid."
MSG_EXPIRY_PAST = "The expiry date must be after today."

Item = ChecklistItem.Status
Task = TaskInstance.Status
FREQUENCIES = set(recurrence.FREQUENCIES)


def operation_users():
    return User.objects.filter(is_active=True, department__name="Operation")


def operation_head():
    return operation_users().filter(is_dept_head=True).first()


# ---------- onboarding ----------
def onboard(actor, contract):
    """On handover: create the client (or link the existing one with the same name) and copy the CEO's checklist template."""
    lead = contract.lead
    with transaction.atomic():
        client = Client.objects.filter(lead=lead).first() or Client.objects.filter(company_name__iexact=lead.company_name).first()
        created = client is None
        if created:
            client = Client.objects.create(
                company_name=lead.company_name, contact_person=lead.contact_name, phone=lead.phone, email=lead.email or "",
                status="onboarding", created_by=actor, notes=f"Created from contract {contract.ref}",
            )
            record(actor, client, "created", comment=f"From contract {contract.ref}")
        contract.client = client
        contract.save(update_fields=["client", "updated_at"])
        if not client.checklist.exists():
            for pos, t in enumerate(ChecklistTemplateItem.objects.filter(is_active=True).order_by("sort_order", "id")):
                ChecklistItem.objects.create(client=client, template_item=t, name_en=t.name_en, name_ar=t.name_ar, required=t.required, expires_required=t.has_expiry, position=pos)
        if client.status == "prospect":  # converted from a lead earlier; the handover is what starts onboarding
            client.status = "onboarding"
            client.save(update_fields=["status", "updated_at"])
        record(actor, client, "contract_linked", to_value=contract.ref)
        if client.status == "onboarding":
            recompute_status(actor, client)
    return client


def _satisfied(item, today=None):
    """Not applicable, or verified and not past its expiry date. An expired document never counts, even before the daily job has marked it."""
    if item.status == Item.NOT_APPLICABLE:
        return True
    if item.status != Item.VERIFIED:
        return False
    return item.expires_on is None or item.expires_on >= (today or timezone.localdate())


def recompute_status(actor, client):
    """Active exactly when every required, non-archived item is satisfied. Clients with no checklist at all are left alone."""
    items = list(client.checklist.filter(archived_at__isnull=True))
    if not items or client.status == "inactive":
        return client
    ok = all(_satisfied(i) for i in items if i.required)
    if ok and client.status == "onboarding":
        client.status, client.activated_at = "active", timezone.now()
        client.save(update_fields=["status", "activated_at", "updated_at"])
        record(actor, client, "activated", from_value="onboarding", to_value="active")
        notify_many(operation_users(), "client_active", exclude=actor, link=f"/operation/{client.pk}", ref=client.company_name, name="")
    elif not ok and client.status == "active":
        client.status = "onboarding"
        client.save(update_fields=["status", "updated_at"])
        record(actor, client, "back_to_onboarding", from_value="active", to_value="onboarding")
    return client


def _files(item):
    return Attachment.objects.filter(content_type=content_type_for(ChecklistItem), object_id=item.pk, archived_at__isnull=True)


def file_attached(user, item, attachment):
    """A document landed on a checklist item. It becomes the newest version; every earlier version is superseded.

    A pending, verified or expired item goes (back) to Uploaded, because the newest document has not been checked. A client that was
    active only because of the old document therefore returns to onboarding until Operation verifies the new one."""
    with transaction.atomic():
        item = ChecklistItem.objects.select_for_update(of=("self",)).select_related("client").get(pk=item.pk)
        number = (item.versions.order_by("-number").values_list("number", flat=True).first() or 0) + 1
        item.versions.exclude(state=ChecklistItemVersion.State.SUPERSEDED).update(state=ChecklistItemVersion.State.SUPERSEDED)
        ChecklistItemVersion.objects.create(item=item, number=number, attachment=attachment, filename=attachment.original_name[:255], uploaded_by=user)
        if item.status in (Item.PENDING, Item.VERIFIED, Item.EXPIRED):
            was = item.status
            item.status, item.verified_by, item.verified_at, item.expires_on = Item.UPLOADED, None, None, None
            item.save(update_fields=["status", "verified_by", "verified_at", "expires_on", "updated_at"])
            record(user, item.client, "checklist_uploaded" if was == Item.PENDING else "checklist_new_version", to_value=f"{item.name_en} v{number}")
            if was != Item.PENDING:
                recompute_status(user, item.client)
        else:
            record(user, item.client, "checklist_new_version", to_value=f"{item.name_en} v{number}")


def _locked_item(item):
    return ChecklistItem.objects.select_for_update(of=("self",)).select_related("client").get(pk=item.pk)


def _expiry(raw, required):
    if raw in (None, ""):
        if required:
            raise ValidationError({"expires_on": [MSG_EXPIRY]})
        return None
    try:
        day = date.fromisoformat(str(raw))
    except ValueError:
        raise ValidationError({"expires_on": [MSG_EXPIRY]})
    if day <= timezone.localdate():
        raise ValidationError({"expires_on": [MSG_EXPIRY_PAST]})
    return day


def verify_item(actor, item, expires_on=None):
    """Verifies the newest version. Items flagged `expires_required` must come with the date the document runs out."""
    with transaction.atomic():
        item = _locked_item(item)
        if item.archived_at or item.status != Item.UPLOADED:
            raise ValidationError({"detail": MSG_STATE})
        if not _files(item).exists():
            raise ValidationError({"detail": MSG_NO_FILE})
        day = _expiry(expires_on, item.expires_required)
        now = timezone.now()
        item.status, item.verified_by, item.verified_at, item.expires_on = Item.VERIFIED, actor, now, day
        item.save(update_fields=["status", "verified_by", "verified_at", "expires_on", "updated_at"])
        latest = item.versions.order_by("-number").first()
        if latest is not None:
            latest.state, latest.verified_by, latest.verified_at, latest.expires_on = ChecklistItemVersion.State.VERIFIED, actor, now, day
            latest.save(update_fields=["state", "verified_by", "verified_at", "expires_on"])
        record(actor, item.client, "checklist_verified", to_value=item.name_en, comment=f"expires {day.isoformat()}" if day else "")
        recompute_status(actor, item.client)
    return item


def reset_item(actor, item, note=""):
    """Send an item back to Pending (a document was wrong, or a verification was a mistake)."""
    with transaction.atomic():
        item = _locked_item(item)
        if item.archived_at or item.status == Item.PENDING:
            raise ValidationError({"detail": MSG_STATE})
        item.status, item.verified_by, item.verified_at, item.na_reason, item.expires_on = Item.PENDING, None, None, "", None
        item.save(update_fields=["status", "verified_by", "verified_at", "na_reason", "expires_on", "updated_at"])
        item.versions.filter(state=ChecklistItemVersion.State.VERIFIED).update(state=ChecklistItemVersion.State.UPLOADED, verified_by=None, verified_at=None, expires_on=None)
        record(actor, item.client, "checklist_reset", to_value=item.name_en, comment=(note or "")[:300])
        recompute_status(actor, item.client)
    return item


def mark_not_applicable(actor, item, reason):
    reason = (reason or "").strip()
    if not reason:
        raise ValidationError({"reason": [MSG_REASON]})
    with transaction.atomic():
        item = _locked_item(item)
        if item.archived_at or item.status == Item.NOT_APPLICABLE:
            raise ValidationError({"detail": MSG_STATE})
        item.status, item.na_reason, item.verified_by, item.verified_at = Item.NOT_APPLICABLE, reason[:500], actor, timezone.now()
        item.save(update_fields=["status", "na_reason", "verified_by", "verified_at", "updated_at"])
        record(actor, item.client, "checklist_not_applicable", to_value=item.name_en, comment=reason[:300])
        recompute_status(actor, item.client)
    return item


def set_required(actor, item, required):
    with transaction.atomic():
        item = _locked_item(item)
        if item.archived_at:
            raise ValidationError({"detail": MSG_STATE})
        item.required = bool(required)
        item.save(update_fields=["required", "updated_at"])
        record(actor, item.client, "checklist_required" if item.required else "checklist_optional", to_value=item.name_en)
        recompute_status(actor, item.client)
    return item


def archive_item(actor, item):
    with transaction.atomic():
        item = _locked_item(item)
        if item.archived_at:
            raise ValidationError({"detail": MSG_STATE})
        item.archived_at = timezone.now()
        item.save(update_fields=["archived_at", "updated_at"])
        record(actor, item.client, "checklist_removed", to_value=item.name_en)
        recompute_status(actor, item.client)
    return item


def add_item(actor, client, name_en, name_ar, required=True):
    name_en, name_ar = (name_en or "").strip()[:120], (name_ar or "").strip()[:120]
    if not name_en or not name_ar:
        raise ValidationError({"name_en": [MSG_NAME]})
    with transaction.atomic():
        pos = (client.checklist.order_by("-position").values_list("position", flat=True).first() or 0) + 1
        item = ChecklistItem.objects.create(client=client, name_en=name_en, name_ar=name_ar, required=bool(required), position=pos)
        record(actor, client, "checklist_added", to_value=name_en)
        recompute_status(actor, client)
    return item


# ---------- recurring tasks ----------
def due_date(task, k, days=frozenset()):
    """The k-th nominal date of the rule (before weekends and holidays move it), always counted from the start date.
    `days` (the holidays) only matters for the first and last working day rules."""
    return recurrence.nominal(task.frequency, task.start_date, task.interval_days, k, task.day_rule, task.nth, task.weekday, days)


def holidays():
    return frozenset(Holiday.objects.values_list("date", flat=True))


def due_on(task, k, days=None):
    """The date the k-th task is actually due: the nominal date, moved by the rule's weekend policy (Friday and Saturday are the weekend)."""
    days = holidays() if days is None else days
    return recurrence.due(task.frequency, task.start_date, task.interval_days, k, days, task.day_rule, task.nth, task.weekday, task.weekend_policy)


def _skipped(task, k, days):
    """No task for an occurrence on a closed day when the rule skips (every working day, a daily rule, or the policy "skip")."""
    return recurrence.skipped(task.frequency, task.weekend_policy, due_date(task, k, days), days)


def _clean_task(data, creating):
    out = {}
    title = (data.get("title") or "").strip()
    if not title:
        raise ValidationError({"title": [MSG_TITLE]})
    out["title"] = title[:150]
    out["description"] = (data.get("description") or "").strip()[:1000]
    freq = data.get("frequency")
    if freq not in FREQUENCIES:
        raise ValidationError({"frequency": [MSG_FREQUENCY]})
    out["frequency"] = freq
    interval = None
    if freq == "custom":
        try:
            interval = int(data.get("interval_days"))
        except (TypeError, ValueError):
            raise ValidationError({"interval_days": [MSG_INTERVAL]})
        if not 1 <= interval <= 365:
            raise ValidationError({"interval_days": [MSG_INTERVAL]})
    out["interval_days"] = interval
    day_rule = data.get("day_rule") or "date"
    if day_rule not in recurrence.DAY_RULES:
        raise ValidationError({"day_rule": [MSG_DAY_RULE]})
    if day_rule != "date" and freq not in recurrence.MONTHS:
        raise ValidationError({"day_rule": [MSG_DAY_RULE_FREQUENCY]})
    nth = weekday = None
    if day_rule == "nth_weekday":
        try:
            nth = int(data.get("nth"))
        except (TypeError, ValueError):
            raise ValidationError({"nth": [MSG_NTH]})
        if nth not in recurrence.NTH:
            raise ValidationError({"nth": [MSG_NTH]})
        try:
            weekday = int(data.get("weekday"))
        except (TypeError, ValueError):
            raise ValidationError({"weekday": [MSG_WEEKDAY]})
        if not 0 <= weekday <= 6:
            raise ValidationError({"weekday": [MSG_WEEKDAY]})
    out["day_rule"], out["nth"], out["weekday"] = day_rule, nth, weekday
    policy = data.get("weekend_policy") or "next"
    if policy not in recurrence.POLICIES:
        raise ValidationError({"weekend_policy": [MSG_POLICY]})
    out["weekend_policy"] = policy
    start = data.get("start_date")
    try:
        start = date.fromisoformat(str(start))
    except ValueError:
        raise ValidationError({"start_date": [MSG_START]})
    if creating and start < timezone.localdate():
        raise ValidationError({"start_date": [MSG_START_OLD]})
    out["start_date"] = start
    return out


def _assignee(raw):
    if raw in (None, "", 0):
        return None
    user = operation_users().filter(pk=raw if str(raw).isdigit() else 0).first()
    if user is None:
        raise ValidationError({"assignee": [MSG_ASSIGNEE]})
    return user


def create_recurring(actor, client, data):
    fields = _clean_task(data, creating=True)
    assignee = _assignee(data.get("assignee"))
    with transaction.atomic():
        task = RecurringTask.objects.create(client=client, assignee=assignee, created_by=actor, next_due=fields["start_date"], **fields)
        record(actor, client, "recurring_created", to_value=task.title)
    generate_due()  # a task that starts today shows up straight away
    return RecurringTask.objects.get(pk=task.pk)


def update_recurring(actor, task, data):
    with transaction.atomic():
        task = RecurringTask.objects.select_for_update(of=("self",)).select_related("client").get(pk=task.pk)
        merged = {k: data.get(k, getattr(task, k)) for k in ("title", "description", "frequency", "interval_days", "start_date", "day_rule", "nth", "weekday", "weekend_policy")}
        merged["start_date"] = str(merged["start_date"])
        schedule_changed = any(str(merged[k]) != str(getattr(task, k)) for k in ("frequency", "interval_days", "start_date", "day_rule", "nth", "weekday", "weekend_policy"))
        fields = _clean_task(merged, creating=False)
        for k, v in fields.items():
            setattr(task, k, v)
        if "assignee" in data:
            task.assignee = _assignee(data.get("assignee"))
        if "active" in data:
            task.active = bool(data["active"])
        if schedule_changed:
            # A new schedule is a new version and counts from today: tasks already made keep their version and dates.
            task.version += 1
            k, days = 0, holidays()
            while due_date(task, k, days) < timezone.localdate():
                k += 1
            task.occurrences = k
        task.next_due = due_on(task, task.occurrences)
        task.save()
        record(actor, task.client, "recurring_updated", to_value=task.title)
    return task


def days_ahead():
    """How many days before its due date a recurring task is created (the RECURRING_DAYS_AHEAD setting, 0 to 30; 0 = on the due date)."""
    try:
        return max(0, min(30, int(getattr(settings, "RECURRING_DAYS_AHEAD", 0))))
    except (TypeError, ValueError):
        return 0


def generate_due(today=None, limit=12):
    """Create the tasks that are due, or due within the "days ahead" setting. Safe to run any number of times and from several workers:
    one task per (rule, version, period), enforced by the database. Holidays are read now, so a calendar edit moves only tasks that have
    not been created yet. A task created early keeps its real due date; only its appearance on the list moves forward."""
    today = (today or timezone.localdate()) + timedelta(days=days_ahead())
    days = holidays()
    made = 0
    for task in RecurringTask.objects.filter(active=True, next_due__lte=today).select_related("client", "assignee"):
        with transaction.atomic():
            task = RecurringTask.objects.select_for_update(of=("self",)).select_related("client", "assignee").get(pk=task.pk)
            k, created_here = task.occurrences, 0
            while due_on(task, k, days) <= today:
                if created_here < limit and not _skipped(task, k, days):
                    assignee = task.assignee if task.assignee_id and task.assignee.is_active else None
                    nominal_date = due_date(task, k, days)
                    inst, created = TaskInstance.objects.get_or_create(
                        recurring=task, rule_version=task.version, period=recurrence.period(task.frequency, nominal_date),
                        defaults={"client": task.client, "title": task.title, "assignee": assignee, "due_date": due_on(task, k, days)},
                    )
                    if created:
                        made += 1
                        created_here += 1
                        for who in ([assignee] if assignee else [operation_head()]):
                            if who:
                                notify(who, "task_due", link="/operation?tab=tasks", dedupe_key=f"task:{inst.pk}", ref=inst.title, name=task.client.company_name)
                k += 1  # beyond the limit, long-missed dates are skipped over rather than flooding the list
            task.occurrences, task.next_due = k, due_on(task, k, days)
            task.save(update_fields=["occurrences", "next_due", "updated_at"])
    return made


def _locked_task(task):
    return TaskInstance.objects.select_for_update(of=("self",)).select_related("client").get(pk=task.pk)


def complete_task(actor, task, note=""):
    note = (note or "").strip()
    if len(note) > 1000:
        raise ValidationError({"note": [MSG_NOTE_LONG]})
    with transaction.atomic():
        task = _locked_task(task)
        if task.status not in TaskInstance.ACTIVE:
            raise ValidationError({"detail": MSG_TASK_CLOSED})
        task.status, task.completion_note, task.closed_by, task.closed_at = Task.DONE, note, actor, timezone.now()
        task.save(update_fields=["status", "completion_note", "closed_by", "closed_at", "updated_at"])
        record(actor, task.client, "task_completed", to_value=task.title, comment=note[:300])
    return task


def skip_task(actor, task, reason):
    reason = (reason or "").strip()
    if not reason:
        raise ValidationError({"reason": [MSG_SKIP]})
    with transaction.atomic():
        task = _locked_task(task)
        if task.status not in TaskInstance.ACTIVE:
            raise ValidationError({"detail": MSG_TASK_CLOSED})
        task.status, task.skip_reason, task.closed_by, task.closed_at = Task.SKIPPED, reason[:1000], actor, timezone.now()
        task.save(update_fields=["status", "skip_reason", "closed_by", "closed_at", "updated_at"])
        record(actor, task.client, "task_skipped", to_value=task.title, comment=reason[:300])
    return task


# ---------- QA meetings ----------
def log_meeting(actor, client, held_on, notes, next_date=None):
    notes = (notes or "").strip()
    if not isinstance(held_on, date):
        raise ValidationError({"held_on": [MSG_HELD]})
    if held_on > timezone.localdate():
        raise ValidationError({"held_on": [MSG_HELD_FUTURE]})
    if not notes:
        raise ValidationError({"notes": [MSG_MEETING_NOTES]})
    if next_date is None:
        next_date = held_on + timedelta(days=client.qa_cadence_days)  # the suggestion, used when nobody chooses a date
    elif next_date <= held_on:
        raise ValidationError({"next_date": [MSG_NEXT]})
    with transaction.atomic():
        m = QAMeeting.objects.create(client=client, held_on=held_on, notes=notes[:3000], next_date=next_date, logged_by=actor)
        record(actor, client, "qa_meeting_logged", to_value=held_on.isoformat(), comment=notes[:300])
    return m


def set_cadence(actor, client, days):
    try:
        days = int(days)
    except (TypeError, ValueError):
        raise ValidationError({"qa_cadence_days": [MSG_CADENCE]})
    if not 7 <= days <= 365:
        raise ValidationError({"qa_cadence_days": [MSG_CADENCE]})
    client.qa_cadence_days = days
    client.save(update_fields=["qa_cadence_days", "updated_at"])
    record(actor, client, "qa_cadence_changed", to_value=str(days))
    return client


# ---------- document expiry ----------
EXPIRY_WARNING_DAYS = 30


def expire_documents(today=None):
    """Daily. A verified document past its expiry date becomes Expired and its client goes back to onboarding; the Operation head is told.
    Also warns once, 30 days ahead. Safe to run any number of times: a notification is keyed by item and expiry date."""
    today = today or timezone.localdate()
    sent = 0
    head = operation_head()
    soon = today + timedelta(days=EXPIRY_WARNING_DAYS)
    due = ChecklistItem.objects.filter(status=Item.VERIFIED, expires_on__lt=today, archived_at__isnull=True).select_related("client")
    clients = {}
    for item in due:
        with transaction.atomic():
            item = _locked_item(item)
            if item.status != Item.VERIFIED or item.expires_on is None or item.expires_on >= today:
                continue
            item.status = Item.EXPIRED
            item.save(update_fields=["status", "updated_at"])
            record(None, item.client, "checklist_expired", to_value=item.name_en, comment=item.expires_on.isoformat())
            clients[item.client_id] = item.client
        if head:
            sent += bool(notify(head, "kyc_expired", link=f"/operation/{item.client_id}", dedupe_key=f"kycexpired:{item.pk}:{item.expires_on}", ref=item.name_en, name=item.client.company_name))
    for client in clients.values():
        recompute_status(None, Client.objects.get(pk=client.pk))
    if head:
        warn = ChecklistItem.objects.filter(status=Item.VERIFIED, expires_on__gte=today, expires_on__lte=soon, archived_at__isnull=True).select_related("client")
        for item in warn:
            sent += bool(notify(head, "kyc_expiring", link=f"/operation/{item.client_id}", dedupe_key=f"kycsoon:{item.pk}:{item.expires_on}", ref=item.name_en, name=item.client.company_name))
    return sent + len(clients)
