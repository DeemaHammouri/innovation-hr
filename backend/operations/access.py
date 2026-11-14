"""Operation works on clients. The CEO and the Commercial side can read; nobody else sees any of it."""
from django.db.models import Q

from core.roles import CEO, COMMERCIAL_HEAD, COMMERCIAL_MEMBER, OPERATION_HEAD, OPERATION_MEMBER, role_key

OP = (OPERATION_HEAD, OPERATION_MEMBER)


def is_op(user):
    return role_key(user) in OP


def is_op_head(user):
    return role_key(user) == OPERATION_HEAD


def has_access(user):
    return role_key(user) in (CEO, COMMERCIAL_HEAD, COMMERCIAL_MEMBER, *OP)


def visible_clients_q(user):
    role = role_key(user)
    if role in (CEO, COMMERCIAL_HEAD, *OP):
        return Q()
    if role == COMMERCIAL_MEMBER:
        return Q(contracts__lead__assigned_to=user)
    return Q(pk__in=[])


def can_view_client(user, client):
    role = role_key(user)
    if role in (CEO, COMMERCIAL_HEAD, *OP):
        return True
    if role == COMMERCIAL_MEMBER:
        return client.contracts.filter(lead__assigned_to=user).exists()
    return False


def can_work_task(user, task):
    """Any Operation person may handle a task assigned to them; the head may handle any."""
    return is_op(user) and (is_op_head(user) or task.assignee_id == user.pk)


def client_flags(user, client):
    return {"can_work": is_op(user), "can_manage": is_op_head(user)}
