"""Who may give a task to whom, and who may see or change it.

The CEO (`gtask.assign_any`) gives tasks to anyone who works here. A department head (`gtask.assign_team`) gives tasks to people in their own
department, themselves included. Everyone with `gtask.access` can be given a task, sees their own, and marks it done: nobody else can.
"""
from django.db.models import Q

from accounts.models import User


def _is_staff(user):
    return user.is_active and user.has_capability("gtask.access")


def assignable_users(actor):
    """The people this person may give a task to, as a queryset."""
    if actor.has_capability("gtask.assign_any"):
        base = User.objects.filter(is_active=True)
    elif actor.has_capability("gtask.assign_team") and actor.department_id:
        base = User.objects.filter(is_active=True, department_id=actor.department_id)
    else:
        return User.objects.none()
    return base.filter(role_ref__capabilities__code="gtask.access").distinct().order_by("full_name")


def can_assign_to(actor, assignee):
    return _is_staff(assignee) and assignable_users(actor).filter(pk=assignee.pk).exists()


def _same_team(user, task):
    return user.has_capability("gtask.assign_team") and bool(user.department_id) and task.assignee.department_id == user.department_id


def can_manage(user, task):
    """Edit the title, deadline or assignee, and attach files for the assignee's team."""
    return user.has_capability("gtask.assign_any") or _same_team(user, task) or (task.assigned_by_id == user.pk and can_assign_to(user, task.assignee))


def can_view(user, task):
    return user.pk in (task.assignee_id, task.assigned_by_id) or user.has_capability("gtask.assign_any") or _same_team(user, task)


def visible_q(user):
    """Rows a person may see: their own, ones they gave, their department's (heads), everyone's (CEO)."""
    if user.has_capability("gtask.assign_any"):
        return Q()
    q = Q(assignee=user) | Q(assigned_by=user)
    if user.has_capability("gtask.assign_team") and user.department_id:
        q |= Q(assignee__department_id=user.department_id)
    return q
