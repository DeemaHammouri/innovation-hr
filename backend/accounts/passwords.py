"""Temporary passwords and the password policy."""
import secrets
import string

from django.contrib.auth.password_validation import validate_password
from django.core.exceptions import ValidationError as DjangoValidationError
from rest_framework import serializers

LOWER, UPPER, DIGITS = "abcdefghijkmnopqrstuvwxyz", "ABCDEFGHJKLMNPQRSTUVWXYZ", "23456789"  # no look-alikes (0/O, 1/l/I)
SYMBOLS = "!@#$%&*?"
LENGTH = 16


def generate_temporary_password():
    """16 random characters from the system's secure source, with at least one of each kind."""
    pools = [LOWER, UPPER, DIGITS, SYMBOLS]
    chars = [secrets.choice(p) for p in pools] + [secrets.choice(LOWER + UPPER + DIGITS + SYMBOLS) for _ in range(LENGTH - len(pools))]
    secrets.SystemRandom().shuffle(chars)
    return "".join(chars)


def check_policy(user, password):
    """Raise a DRF error listing every rule the password breaks: length, common, similar to the user's details, and the current one."""
    problems = []
    try:
        validate_password(password, user=user)
    except DjangoValidationError as exc:
        problems.extend(exc.messages)
    if user is not None and getattr(user, "pk", None) and user.check_password(password):
        problems.append("Choose a password that's different from your current one.")
    if problems:
        raise serializers.ValidationError(problems)
    return password
