"""Payments belong to the Commercial head. The CEO can read. Nobody else sees any of it."""


def is_head(user):
    return user.has_capability("payment.manage")


def has_access(user):
    return user.has_capability("payment.view")


def can_view(user, obj=None):
    return has_access(user)


def can_write(user, obj=None):
    return is_head(user)
