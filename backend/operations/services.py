"""
Operation: onboarding a client, the KYC checklist, recurring tasks and follow-up QA meetings.

A client created by a contract handover starts "onboarding" and becomes "active" the moment every required checklist item is
verified (or marked not applicable with a reason). If a required item stops being satisfied later, it goes back to "onboarding".
"""
import calendar
from datetime import date, timedelta

from django.db import transaction
from django.utils import timezone
from rest_framework.exceptions import ValidationError

from accounts.models import User
from audit.models import record
from clients.models import Client
from core.access import content_type_for
from files.models import Attachment
from lookups.models import ChecklistTemplateItem
from notifications.service import notify, notify_many

from .models import ChecklistItem, QAMeeting, RecurringTask, TaskInstance

MSG_STATE = "That can't be done in the current state."
MSG_NO_FILE = "Upload the document first."
MSG_REASON = "Write why this item does not apply."
MSG_NAME = "Enter the document name in both languages."
MSG_NOTE_LONG = "Keep this under 1000 characters."
MSG_TITLE = "Enter a title for the task."
MSG_FREQUENCY = "Choose how often it repeats."
MSG_INTERVAL = "Enter a number of days from 1 to 365."
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

Item = ChecklistItem.Status
Task = TaskInstance.Status
FREQUENCIES = {c for c, _ in RecurringTask.Frequency.choices}


def operation_users():
    return User.objects.filter(is_active=True, department__name="Operation")


def operation_head():
    return operation_users().filter(role=User.Role.HEAD).first()


# ---------- onboarding ----------
def onboard(actor, contract):
    """On handover: create the client (or link the existing one with the same name) and copy the CEO's checklist template."""
    lead = contract.lead
    with transaction.atomic():
        client = Client.objects.filter(company_name__iexact=lead.company_name).first()
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
                ChecklistItem.objects.create(client=client, template_item=t, name_en=t.name_en, name_ar=t.name_ar, required=t.required, position=pos)
        record(actor, client, "contract_linked", to_value=contract.ref)
        if client.status == "onboarding":
            recompute_status(actor, client)
    return client


def _satisfied(item):
    return item.status in (Item.VERIFIED, Item.NOT_APPLICABLE)


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
    elif not ok and client.status == "active" and client.checklist.filter(archived_at__isnull=True, required=True).exclude(status__in=[Item.VERIFIED, Item.NOT_APPLICABLE]).exists():
        client.status = "onboarding"
        client.save(update_fields=["status", "updated_at"])
        record(actor, client, "back_to_onboarding", from_value="active", to_value="onboarding")
    return client


def _files(item):
    return Attachment.objects.filter(content_type=content_type_for(ChecklistItem), object_id=item.pk, archived_at__isnull=True)


def file_attached(user, item, attachment):
    """A document landed on a checklist item: Pending becomes Uploaded. Nothing else changes by uploading."""
    if item.status == Item.PENDING:
        item.status = Item.UPLOADED
        item.save(update_fields=["status", "updated_at"])
        record(user, item.client, "checklist_uploaded", to_value=item.name_en)


def _locked_item(item):
    return ChecklistItem.objects.select_for_update().select_related("client").get(pk=item.pk)


def verify_item(actor, item):
    with transaction.atomic():
        item = _locked_item(item)
        if item.archived_at or item.status != Item.UPLOADED:
            raise ValidationError({"detail": MSG_STATE})
        if not _files(item).exists():
            raise ValidationError({"detail": MSG_NO_FILE})
        item.status, item.verified_by, item.verified_at = Item.VERIFIED, actor, timezone.now()
        item.save(update_fields=["status", "verified_by", "verified_at", "updated_at"])
        record(actor, item.client, "checklist_verified", to_value=item.name_en)
        recompute_status(actor, item.client)
    return item


def reset_item(actor, item, note=""):
    """Send an item back to Pending (a document was wrong, or a verification was a mistake)."""
    with transaction.atomic():
        item = _locked_item(item)
        if item.archived_at or item.status == Item.PENDING:
            raise ValidationError({"detail": MSG_STATE})
        item.status, item.verified_by, item.verified_at, item.na_reason = Item.PENDING, None, None, ""
        item.save(update_fields=["status", "verified_by", "verified_at", "na_reason", "updated_at"])
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
def add_months(d, n):
    y, m = d.year + (d.month - 1 + n) // 12, (d.month - 1 + n) % 12 + 1
    return date(y, m, min(d.day, calendar.monthrange(y, m)[1]))


def due_date(task, k):
    """The k-th due date, always counted from the start date so a 31st does not drift to the 28th for good."""
    f = task.frequency
    if f == "daily":
        return task.start_date + timedelta(days=k)
    if f == "weekly":
        return task.start_date + timedelta(weeks=k)
    if f == "biweekly":
        return task.start_date + timedelta(weeks=2 * k)
    if f == "monthly":
        return add_months(task.start_date, k)
    if f == "yearly":
        return add_months(task.start_date, 12 * k)
    return task.start_date + timedelta(days=(task.interval_days or 1) * k)


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
        task = RecurringTask.objects.select_for_update().select_related("client").get(pk=task.pk)
        merged = {k: data.get(k, getattr(task, k)) for k in ("title", "description", "frequency", "interval_days", "start_date")}
        merged["start_date"] = str(merged["start_date"])
        schedule_changed = any(str(merged[k]) != str(getattr(task, k)) for k in ("frequency", "interval_days", "start_date"))
        fields = _clean_task(merged, creating=False)
        for k, v in fields.items():
            setattr(task, k, v)
        if "assignee" in data:
            task.assignee = _assignee(data.get("assignee"))
        if "active" in data:
            task.active = bool(data["active"])
        if schedule_changed:
            # A new schedule counts from today: the next due date is the first one on or after today.
            k = 0
            while due_date(task, k) < timezone.localdate():
                k += 1
            task.occurrences = k
        task.next_due = due_date(task, task.occurrences)
        task.save()
        record(actor, task.client, "recurring_updated", to_value=task.title)
    return task


def generate_due(today=None, limit=12):
    """Create the task instances that are due. Safe to run any number of times: one instance per task per due date."""
    today = today or timezone.localdate()
    made = 0
    for task in RecurringTask.objects.filter(active=True, next_due__lte=today).select_related("client", "assignee"):
        with transaction.atomic():
            task = RecurringTask.objects.select_for_update().select_related("client", "assignee").get(pk=task.pk)
            k, created_here = task.occurrences, 0
            while due_date(task, k) <= today:
                if created_here < limit:
                    assignee = task.assignee if task.assignee_id and task.assignee.is_active else None
                    inst, created = TaskInstance.objects.get_or_create(
                        recurring=task, due_date=due_date(task, k), defaults={"client": task.client, "title": task.title, "assignee": assignee},
                    )
                    if created:
                        made += 1
                        created_here += 1
                        for who in ([assignee] if assignee else [operation_head()]):
                            if who:
                                notify(who, "task_due", link="/operation?tab=tasks", dedupe_key=f"task:{inst.pk}", ref=inst.title, name=task.client.company_name)
                k += 1  # beyond the limit, long-missed dates are skipped over rather than flooding the list
            task.occurrences, task.next_due = k, due_date(task, k)
            task.save(update_fields=["occurrences", "next_due", "updated_at"])
    return made


def _locked_task(task):
    return TaskInstance.objects.select_for_update().select_related("client").get(pk=task.pk)


def complete_task(actor, task, note=""):
    note = (note or "").strip()
    if len(note) > 1000:
        raise ValidationError({"note": [MSG_NOTE_LONG]})
    with transaction.atomic():
        task = _locked_task(task)
        if task.status != Task.OPEN:
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
        if task.status != Task.OPEN:
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
