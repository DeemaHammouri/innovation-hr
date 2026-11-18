"""Create, change and finish general tasks. Every step is written to the task's history in the same transaction."""
from datetime import date

from django.db import transaction
from django.utils import timezone
from rest_framework.exceptions import PermissionDenied, ValidationError

from accounts.models import User
from audit.models import record
from notifications.service import notify

from . import scope
from .models import GeneralTask

S = GeneralTask.Status
MSG_CANT_ASSIGN = "You can't give a task to this person."
MSG_TITLE = "Enter a title for the task."
MSG_DEADLINE = "Choose a deadline."
MSG_PAST = "The deadline can't be in the past."
MSG_ONLY_ASSIGNEE = "Only the person the task was given to can mark it as done."
MSG_DONE = "This task is already done."
MSG_NOT_YOURS = "You can't change this task."
MSG_WHO_GIVES = "Only the CEO and department heads can give tasks."


def _parse_deadline(raw):
    try:
        return date.fromisoformat(str(raw)[:10])
    except (TypeError, ValueError):
        raise ValidationError({"deadline": [MSG_DEADLINE]})


def _assignee(actor, raw):
    user = User.objects.filter(pk=int(raw) if str(raw or "").isdigit() else 0).first()
    if user is None or not scope.can_assign_to(actor, user):
        raise ValidationError({"assignee": [MSG_CANT_ASSIGN]})
    return user


def _collect(errors, fn):
    try:
        return fn()
    except ValidationError as e:
        errors.update(e.detail)
        return None


def _link(task):
    return f"/tasks?open={task.pk}"


def create(actor, data):
    if not (actor.has_capability("gtask.assign_any") or actor.has_capability("gtask.assign_team")):
        raise PermissionDenied(MSG_WHO_GIVES)
    errors = {}
    title = str(data.get("title") or "").strip()
    if not title:
        errors["title"] = [MSG_TITLE]
    deadline = _collect(errors, lambda: _parse_deadline(data.get("deadline")))
    if deadline and deadline < timezone.localdate():
        errors["deadline"] = [MSG_PAST]
    assignee = _collect(errors, lambda: _assignee(actor, data.get("assignee")))
    if errors:
        raise ValidationError(errors)
    with transaction.atomic():
        task = GeneralTask.objects.create(title=title[:200], description=str(data.get("description") or "").strip(), assignee=assignee, assigned_by=actor, deadline=deadline)
        record(actor, task, "gtask_created", to_value=assignee.full_name, comment=title[:200])
    notify(assignee, "gtask_assigned", link=_link(task), dedupe_key=f"gtaskassigned:{task.pk}:{assignee.pk}", actor=actor.full_name, ref=task.title[:120], name=deadline.isoformat())
    return task


def update(actor, task, data):
    """Title, details, assignee and deadline of an open task. Changing the deadline starts a new overdue-alert round."""
    with transaction.atomic():
        task = GeneralTask.objects.select_for_update(of=("self",)).select_related("assignee", "assigned_by").get(pk=task.pk)
        if not scope.can_manage(actor, task):
            raise PermissionDenied(MSG_NOT_YOURS)
        if task.status == S.DONE:
            raise ValidationError({"detail": MSG_DONE})
        errors = {}
        old_title, old_deadline = task.title, task.deadline
        if "title" in data:
            title = str(data.get("title") or "").strip()
            if title:
                task.title = title[:200]
            else:
                errors["title"] = [MSG_TITLE]
        if "description" in data:
            task.description = str(data.get("description") or "").strip()
        new_assignee = None
        if "assignee" in data and str(data.get("assignee")) != str(task.assignee_id):
            new_assignee = _collect(errors, lambda: _assignee(actor, data.get("assignee")))
        if "deadline" in data:
            deadline = _collect(errors, lambda: _parse_deadline(data.get("deadline")))
            if deadline and deadline != task.deadline:
                if deadline < timezone.localdate():
                    errors["deadline"] = [MSG_PAST]
                else:
                    task.deadline = deadline
        if errors:
            raise ValidationError(errors)
        if task.title != old_title:
            record(actor, task, "gtask_edited", from_value=old_title, to_value=task.title)
        if task.deadline != old_deadline:
            task.alert_round += 1  # the old overdue alert is spent; the new deadline gets its own
            record(actor, task, "gtask_deadline_changed", from_value=old_deadline.isoformat(), to_value=task.deadline.isoformat())
        if new_assignee is not None:
            record(actor, task, "gtask_reassigned", from_value=task.assignee.full_name, to_value=new_assignee.full_name)
            task.assignee = new_assignee
        task.save()
    if new_assignee is not None:
        notify(new_assignee, "gtask_assigned", link=_link(task), dedupe_key=f"gtaskassigned:{task.pk}:{new_assignee.pk}", actor=actor.full_name, ref=task.title[:120], name=task.deadline.isoformat())
    elif task.deadline != old_deadline and actor.pk != task.assignee_id:
        notify(task.assignee, "gtask_deadline", link=_link(task), ref=task.title[:120], name=task.deadline.isoformat())
    return task


def mark_done(actor, task):
    """Only the person it was given to, never the CEO or the head. Late means finished after the deadline day, fixed here, once."""
    with transaction.atomic():
        task = GeneralTask.objects.select_for_update(of=("self",)).select_related("assignee", "assigned_by").get(pk=task.pk)
        if task.assignee_id != actor.pk:
            raise PermissionDenied(MSG_ONLY_ASSIGNEE)
        if task.status == S.DONE:
            raise ValidationError({"detail": MSG_DONE})
        now = timezone.now()
        task.status, task.done_at = S.DONE, now
        task.done_late = timezone.localtime(now).date() > task.deadline
        task.save()
        record(actor, task, "gtask_done_late" if task.done_late else "gtask_done", from_value=S.OPEN, to_value=S.DONE)
    if task.assigned_by_id != actor.pk:
        notify(task.assigned_by, "gtask_done_late" if task.done_late else "gtask_done", link=_link(task), actor=actor.full_name, ref=task.title[:120], name="")
    return task
