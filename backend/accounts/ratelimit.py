"""Sign-in lockout: 5 wrong passwords for one account within 5 minutes lock that account, and too many from one address lock the address.

Counters are rows of `LoginFailure` in the database, so they are exact however many workers or containers take sign-ins at once (the
increment is a single `UPDATE ... SET count = count + 1`). The check runs BEFORE the password is looked at, so the 6th attempt is
refused even with the right password. The window starts at the first failure and does not slide. A successful sign-in clears the
account's counter.
"""
from datetime import timedelta

from django.conf import settings
from django.db import IntegrityError, transaction
from django.db.models import F
from django.utils import timezone

from .models import LoginFailure


def _limit(name, default):
    return getattr(settings, name, default)


def _window():
    return _limit("LOGIN_WINDOW_SECONDS", 300)


def _keys(identifier, ip):
    return f"id:{identifier[:254]}", f"ip:{ip}"


def _count(key, now):
    return LoginFailure.objects.filter(key=key, expires_at__gt=now).values_list("count", flat=True).first() or 0


def blocked(identifier, ip):
    k_id, k_ip = _keys(identifier, ip)
    now = timezone.now()
    return _count(k_id, now) >= _limit("LOGIN_MAX_FAILS_PER_EMAIL", 5) or _count(k_ip, now) >= _limit("LOGIN_MAX_FAILS_PER_IP", 20)


def _increment(key, now):
    if LoginFailure.objects.filter(key=key).update(count=F("count") + 1):
        return
    try:
        with transaction.atomic():
            LoginFailure.objects.create(key=key, count=1, expires_at=now + timedelta(seconds=_window()))
    except IntegrityError:  # another worker created it first: count on top of theirs
        LoginFailure.objects.filter(key=key).update(count=F("count") + 1)


def record_failure(identifier, ip):
    now = timezone.now()
    LoginFailure.objects.filter(expires_at__lte=now).delete()  # a finished window starts over, and stale rows do not pile up
    for key in _keys(identifier, ip):
        _increment(key, now)


def clear(identifier):
    LoginFailure.objects.filter(key=_keys(identifier, "")[0]).delete()
