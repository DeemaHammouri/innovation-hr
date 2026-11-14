"""Payments belong to the Commercial head. The CEO can read. Nobody else sees any of it."""
from core.roles import CEO, COMMERCIAL_HEAD, role_key


def is_head(user):
    return role_key(user) == COMMERCIAL_HEAD


def has_access(user):
    return role_key(user) in (CEO, COMMERCIAL_HEAD)


def can_view(user, obj=None):
    return has_access(user)


def can_write(user, obj=None):
    return is_head(user)
