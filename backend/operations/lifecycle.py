"""The life of one Operation task, after it has been created.

    open -> in_progress -> submitted -> done              (the usual road)
                |   ^          |
                v   |          +-> in_progress          (sent back, with a note)
             waiting / blocked  (each needs a reason; resume goes back to in_progress)

The assignee (or the Operation head) starts, reports progress, waits, blocks and submits. A reviewer (the Operation head or the CEO,
never the person who did the work) approves or sends back. Every step is written to the client's history in the same transaction.
Escalation is separate: one row per task and level, kept unique by the database."""
from django.db import IntegrityError, transaction
from django.utils import timezone
from rest_framework.exceptions import PermissionDenied, ValidationError

from audit.models import record
from files.models import Attachment
from notifications.service import notify

from . import access
from .models import Deliverable, Escalation, TaskInstance
from .services import operation_head

S = TaskInstance.Status
MSG_STATE = "That can't be done in the current state."
MSG_NOT_YOURS = "This task is not assigned to you."
MSG_REVIEWER = "Only the Operation head or the CEO can review tasks."
MSG_SELF_REVIEW = "Someone else must review a task you worked on."
MSG_PROGRESS = "Progress must be a number from 0 to 100."
MSG_REASON_WAIT = "Write what you are waiting for."
MSG_REASON_BLOCK = "Write what is blocking the work."
MSG_RETURN = "Write what needs to change."
MSG_ESCALATE = "Write why this needs more attention."
MSG_ESCALATED = "This task has already been escalated as far as it can go."
MSG_ESCALATE_WHO = "Only the person doing the task or the Operation head can escalate it."
MSG_PUBLISH_STATE = "Submit the task before publishing its files to the client."
MSG_PUBLISH_FILE = "Choose a file attached to this task."
MSG_PUBLISH_TITLE = "Give the file a title the client will recognise."
MSG_PUBLISHED = "That file was already published."
MSG_NO_ACCOUNT = "This client has no portal account yet."


def _lock(task):
    return TaskInstance.objects.select_for_update().select_related("client", "assignee").get(pk=task.pk)


def _worker(actor, task):
    if not access.can_work_task(actor, task):
        raise PermissionDenied(MSG_NOT_YOURS)


def _reviewer(actor, task):
    if not actor.has_capability("operation.review"):
        raise PermissionDenied(MSG_REVIEWER)
    if task.assignee_id == actor.pk:
        raise PermissionDenied(MSG_SELF_REVIEW)


def _must_be(task, *states):
    if task.status not in states:
        raise ValidationError({"detail": MSG_STATE})


def start(actor, task):
    with transaction.atomic():
        task = _lock(task)
        _worker(actor, task)
        _must_be(task, S.OPEN)
        task.status, task.started_at = S.IN_PROGRESS, timezone.now()
        if task.assignee_id is None:
            task.assignee = actor  # whoever starts an unassigned task takes it
        task.save(update_fields=["status", "started_at", "assignee", "updated_at"])
        record(actor, task.client, "task_started", to_value=task.title)
    return task


def set_progress(actor, task, value, note=""):
    try:
        value = int(value)
    except (TypeError, ValueError):
        raise ValidationError({"progress": [MSG_PROGRESS]})
    if not 0 <= value <= 100:
        raise ValidationError({"progress": [MSG_PROGRESS]})
    with transaction.atomic():
        task = _lock(task)
        _worker(actor, task)
        _must_be(task, S.IN_PROGRESS)
        before = task.progress
        task.progress = value
        task.save(update_fields=["progress", "updated_at"])
        record(actor, task.client, "task_progress", from_value=str(before), to_value=str(value), comment=(note or "").strip()[:300])
    return task


def _hold(actor, task, state, reason, message, action):
    reason = (reason or "").strip()
    if not reason:
        raise ValidationError({"reason": [message]})
    with transaction.atomic():
        task = _lock(task)
        _worker(actor, task)
        _must_be(task, S.IN_PROGRESS)
        task.status, task.status_reason = state, reason[:1000]
        task.save(update_fields=["status", "status_reason", "updated_at"])
        record(actor, task.client, action, to_value=task.title, comment=reason[:300])
    return task


def wait(actor, task, reason):
    return _hold(actor, task, S.WAITING, reason, MSG_REASON_WAIT, "task_waiting")


def block(actor, task, reason):
    return _hold(actor, task, S.BLOCKED, reason, MSG_REASON_BLOCK, "task_blocked")


def resume(actor, task):
    with transaction.atomic():
        task = _lock(task)
        _worker(actor, task)
        _must_be(task, S.WAITING, S.BLOCKED)
        task.status, task.status_reason = S.IN_PROGRESS, ""
        task.save(update_fields=["status", "status_reason", "updated_at"])
        record(actor, task.client, "task_resumed", to_value=task.title)
    return task


def submit(actor, task, note=""):
    note = (note or "").strip()
    if len(note) > 1000:
        raise ValidationError({"note": ["Keep this under 1000 characters."]})
    with transaction.atomic():
        task = _lock(task)
        _worker(actor, task)
        _must_be(task, S.IN_PROGRESS)
        task.status, task.progress, task.submitted_at, task.completion_note = S.SUBMITTED, 100, timezone.now(), note
        task.review_note = ""
        task.save(update_fields=["status", "progress", "submitted_at", "completion_note", "review_note", "updated_at"])
        record(actor, task.client, "task_submitted", to_value=task.title, comment=note[:300])
    for who in {operation_head()} - {None, actor}:
        notify(who, "task_submitted", link="/operation?tab=tasks", dedupe_key=f"tasksub:{task.pk}:{int(task.submitted_at.timestamp())}", ref=task.title, name=task.client.company_name)
    return task


def approve(actor, task):
    with transaction.atomic():
        task = _lock(task)
        _reviewer(actor, task)
        _must_be(task, S.SUBMITTED)
        now = timezone.now()
        task.status, task.reviewed_by, task.reviewed_at, task.closed_by, task.closed_at = S.DONE, actor, now, actor, now
        task.save(update_fields=["status", "reviewed_by", "reviewed_at", "closed_by", "closed_at", "updated_at"])
        record(actor, task.client, "task_approved", to_value=task.title)
    if task.assignee_id and task.assignee_id != actor.pk:
        notify(task.assignee, "task_approved", link="/operation?tab=tasks", ref=task.title, name=task.client.company_name)
    return task


def send_back(actor, task, note):
    note = (note or "").strip()
    if not note:
        raise ValidationError({"comment": [MSG_RETURN]})
    with transaction.atomic():
        task = _lock(task)
        _reviewer(actor, task)
        _must_be(task, S.SUBMITTED)
        task.status, task.reviewed_by, task.reviewed_at, task.review_note, task.progress = S.IN_PROGRESS, actor, timezone.now(), note[:1000], 90
        task.save(update_fields=["status", "reviewed_by", "reviewed_at", "review_note", "progress", "updated_at"])
        record(actor, task.client, "task_returned", to_value=task.title, comment=note[:300])
    if task.assignee_id and task.assignee_id != actor.pk:
        notify(task.assignee, "task_returned", link="/operation?tab=tasks", ref=task.title, name=task.client.company_name)
    return task


def escalate(actor, task, reason, auto=False):
    """Level 1 tells the Operation head, level 2 tells the CEO. The next free level is used; a level is never used twice."""
    reason = (reason or "").strip()
    if not auto and not reason:
        raise ValidationError({"reason": [MSG_ESCALATE]})
    with transaction.atomic():
        task = _lock(task)
        if not auto:
            _worker(actor, task)
        _must_be(task, *TaskInstance.ACTIVE, S.SUBMITTED)
        have = set(task.escalations.values_list("level", flat=True))
        level = next((lv for lv in (1, 2) if lv not in have), None)
        if level is None:
            raise ValidationError({"detail": MSG_ESCALATED})
        if level == 2 and not auto and not actor.has_capability("operation.manage"):
            raise PermissionDenied(MSG_ESCALATE_WHO)
        try:
            with transaction.atomic():
                esc = Escalation.objects.create(task=task, level=level, reason=reason[:1000], by=None if auto else actor)
        except IntegrityError:
            raise ValidationError({"detail": MSG_ESCALATED})
        record(None if auto else actor, task.client, "task_escalated", to_value=f"{task.title} (level {level})", comment=reason[:300])
    targets = {operation_head()} if level == 1 else _ceos()
    for who in targets - {None, actor}:
        notify(who, "task_escalated", link="/operation?tab=tasks", dedupe_key=f"taskesc:{task.pk}:{level}", ref=task.title, name=task.client.company_name)
    return esc


def _ceos():
    from accounts.models import User

    return {u for u in User.objects.filter(is_active=True) if u.has_capability("settings.manage")}


def publish(actor, task, attachment_id, title):
    """Operation shows a file attached to the task to the client. Only after the task has been submitted, and only once per file."""
    title = (title or "").strip()
    if not title:
        raise ValidationError({"title": [MSG_PUBLISH_TITLE]})
    with transaction.atomic():
        task = _lock(task)
        if not actor.has_capability("operation.review") and not access.can_work_task(actor, task):
            raise PermissionDenied(MSG_NOT_YOURS)
        if task.status not in (S.SUBMITTED, S.DONE):
            raise ValidationError({"detail": MSG_PUBLISH_STATE})
        if task.client.portal_user_id is None:
            raise ValidationError({"detail": MSG_NO_ACCOUNT})
        from core.access import content_type_for

        att = Attachment.objects.filter(pk=attachment_id if str(attachment_id or "").isdigit() else 0, content_type=content_type_for(TaskInstance), object_id=task.pk, archived_at__isnull=True).first()
        if att is None:
            raise ValidationError({"attachment": [MSG_PUBLISH_FILE]})
        if Deliverable.objects.filter(attachment=att).exists():
            raise ValidationError({"attachment": [MSG_PUBLISHED]})
        d = Deliverable.objects.create(task=task, client=task.client, attachment=att, title=title[:150], published_by=actor)
        record(actor, task.client, "deliverable_published", to_value=title[:150], comment=task.title)
    notify(task.client.portal_user, "deliverable_published", link="/portal", ref=title, name=task.client.company_name)
    return d


def acknowledge(user, deliverable):
    """The client confirms they received it. Once; the time and the person are kept."""
    with transaction.atomic():
        d = Deliverable.objects.select_for_update().select_related("client", "task").get(pk=deliverable.pk)
        if d.acknowledged_at:
            raise ValidationError({"detail": "You already confirmed receiving this."})
        d.acknowledged_by, d.acknowledged_at = user, timezone.now()
        d.save(update_fields=["acknowledged_by", "acknowledged_at"])
        record(user, d.client, "deliverable_acknowledged", to_value=d.title)
    head = operation_head()
    if head:
        notify(head, "deliverable_acknowledged", link=f"/operation/{d.client_id}", ref=d.title, name=d.client.company_name)
    return d
