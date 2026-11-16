"""Who works on a project: one primary employee and any number of support people.

Only the Operation head staffs a project, and only with active people from Operation. Replacing the primary needs a written reason;
the person who leaves keeps their row with an end date and that reason, so the history of who held the project is never lost. The
database itself refuses a second active primary (`project_one_active_primary`), so two heads clicking at once cannot create one."""
from django.db import IntegrityError, transaction
from django.utils import timezone
from rest_framework.exceptions import PermissionDenied, ValidationError

from audit.models import record
from notifications.service import notify

from .models import Project, ProjectStaff
from .services import operation_users

Role = ProjectStaff.Role
MSG_HEAD = "Only the Operation head can staff a project."
MSG_PERSON = "Choose someone from Operation."
MSG_REASON = "Write why the primary employee is being replaced."
MSG_CLOSED = "A closed project cannot be staffed."
MSG_SAME = "That person is already the primary employee."
MSG_TWICE = "That person already works on this project."
MSG_NOT_ON = "That person is not on this project."
MSG_PRIMARY_REMOVE = "Replace the primary employee instead of removing them."
MSG_REMOVE_DEFAULT = "Removed from the project."


def _need_head(actor):
    if not actor.has_capability("project.staff"):
        raise PermissionDenied(MSG_HEAD)


def _person(raw):
    user = operation_users().filter(pk=raw if str(raw or "").isdigit() else 0).first()
    if user is None:
        raise ValidationError({"user": [MSG_PERSON]})
    return user


def _locked(project):
    p = Project.objects.select_for_update().get(pk=project.pk)
    if p.status == Project.Status.CLOSED:
        raise ValidationError({"detail": MSG_CLOSED})
    return p


def active(project):
    return project.staff.filter(ended_at__isnull=True)


def _end(actor, row, reason):
    row.ended_at, row.ended_by, row.end_reason = timezone.now(), actor, reason[:300]
    row.save(update_fields=["ended_at", "ended_by", "end_reason"])


def assign_primary(actor, project, user_id, reason=""):
    """First primary: no reason needed. Replacing the primary: reason required, the old one is ended and the new one starts in one transaction."""
    _need_head(actor)
    user = _person(user_id)
    reason = (reason or "").strip()
    try:
        with transaction.atomic():
            project = _locked(project)
            current = active(project).filter(role=Role.PRIMARY).first()
            if current is not None and current.user_id == user.pk:
                raise ValidationError({"user": [MSG_SAME]})
            if current is not None and not reason:
                raise ValidationError({"reason": [MSG_REASON]})
            if current is not None:
                _end(actor, current, reason)
                record(actor, project, "primary_replaced", from_value=current.user.full_name, to_value=user.full_name, comment=reason[:300])
            existing_support = active(project).filter(user=user).first()
            if existing_support is not None:  # a support person promoted to primary: their support row ends
                _end(actor, existing_support, "Became the primary employee.")
            ProjectStaff.objects.create(project=project, user=user, role=Role.PRIMARY, assigned_by=actor)
            if current is None:
                record(actor, project, "primary_assigned", to_value=user.full_name)
    except IntegrityError:
        raise ValidationError({"detail": "The project was staffed by someone else a moment ago. Reload and try again."})
    notify(user, "project_assigned", link=f"/projects/{project.pk}", ref=project.ref, name=project.name)
    if current is not None and current.user.is_active:
        notify(current.user, "project_unassigned", link=f"/projects/{project.pk}", ref=project.ref, name=project.name)
    return project


def add_support(actor, project, user_id):
    _need_head(actor)
    user = _person(user_id)
    try:
        with transaction.atomic():
            project = _locked(project)
            if active(project).filter(user=user).exists():
                raise ValidationError({"user": [MSG_TWICE]})
            ProjectStaff.objects.create(project=project, user=user, role=Role.SUPPORT, assigned_by=actor)
            record(actor, project, "support_added", to_value=user.full_name)
    except IntegrityError:
        raise ValidationError({"user": [MSG_TWICE]})
    notify(user, "project_assigned", link=f"/projects/{project.pk}", ref=project.ref, name=project.name)
    return project


def remove_support(actor, project, user_id, reason=""):
    _need_head(actor)
    with transaction.atomic():
        project = _locked(project)
        row = active(project).filter(user_id=user_id if str(user_id or "").isdigit() else 0).select_related("user").first()
        if row is None:
            raise ValidationError({"user": [MSG_NOT_ON]})
        if row.role == Role.PRIMARY:
            raise ValidationError({"user": [MSG_PRIMARY_REMOVE]})
        _end(actor, row, (reason or "").strip() or MSG_REMOVE_DEFAULT)
        record(actor, project, "support_removed", from_value=row.user.full_name, comment=row.end_reason[:300])
    if row.user.is_active:
        notify(row.user, "project_unassigned", link=f"/projects/{project.pk}", ref=project.ref, name=project.name)
    return project
