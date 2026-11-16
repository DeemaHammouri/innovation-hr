"""Sign-in lockout: 5 wrong passwords for one account within 5 minutes lock that account, and too many from one address lock the address.

Counters live in Django's cache (a file cache shared by the workers in production; use Redis for several machines, see
docs/DEPLOYMENT.md). The check runs BEFORE the password is looked at, so the 6th attempt is refused even with the right password.
A successful sign-in clears the account's counter.
"""
from django.conf import settings
from django.core.cache import cache


def _limit(name, default):
    return getattr(settings, name, default)


def _window():
    return _limit("LOGIN_WINDOW_SECONDS", 300)


def _keys(identifier, ip):
    return f"login-fail:id:{identifier[:254]}", f"login-fail:ip:{ip}"


def blocked(identifier, ip):
    k_id, k_ip = _keys(identifier, ip)
    return cache.get(k_id, 0) >= _limit("LOGIN_MAX_FAILS_PER_EMAIL", 5) or cache.get(k_ip, 0) >= _limit("LOGIN_MAX_FAILS_PER_IP", 20)


def record_failure(identifier, ip):
    for key in _keys(identifier, ip):
        cache.add(key, 0, _window())  # the window starts at the first failure and does not slide
        try:
            cache.incr(key)
        except ValueError:
            cache.set(key, 1, _window())


def clear(identifier):
    cache.delete(_keys(identifier, "")[0])
