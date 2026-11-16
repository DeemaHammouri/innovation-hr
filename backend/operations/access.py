"""Operation works on clients. The CEO and the Commercial side can read; nobody else sees any of it."""
from django.db.models import Q



def is_op(user):
    return user.has_capability("operation.work")


def is_op_head(user):
    return user.has_capability("operation.manage")


def has_access(user):
    return user.has_capability("operation.access")


def own_deal_q(user):
    """A Commercial person's own deals: contracts on leads assigned to them, or that they requested."""
    return Q(contracts__lead__assigned_to=user) | Q(contracts__requested_by=user)


def visible_clients_q(user):
    if user.has_capability("operation.view_all_clients"):
        return Q()
    if user.has_capability("operation.view_own_deals"):
        return own_deal_q(user)
    return Q(pk__in=[])


def can_view_client(user, client):
    if user.has_capability("operation.view_all_clients"):
        return True
    if user.has_capability("operation.view_own_deals"):
        return client.contracts.filter(Q(lead__assigned_to=user) | Q(requested_by=user)).exists()
    return False


def can_work_task(user, task):
    """Any Operation person may handle a task assigned to them; the head may handle any."""
    return is_op(user) and (is_op_head(user) or task.assignee_id == user.pk)


def client_flags(user, client):
    return {"can_work": is_op(user), "can_manage": is_op_head(user)}
