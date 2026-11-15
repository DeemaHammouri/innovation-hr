"""Sign-in rate limiting: too many wrong passwords for one email, or from one address, locks sign-in for a while.

Counters live in Django's cache. The default in-memory cache is per process; production settings use a file cache shared by all workers
on one machine (use Redis for several machines, see docs/DEPLOYMENT.md). A successful sign-in clears the email's counter.
"""
from django.conf import settings
from django.core.cache import cache

WINDOW = 15 * 60  # seconds a failure counts for


def _limit(name, default):
    return getattr(settings, name, default)


def _keys(email, ip):
    return f"login-fail:email:{email[:254]}", f"login-fail:ip:{ip}"


def blocked(email, ip):
    k_email, k_ip = _keys(email, ip)
    return cache.get(k_email, 0) >= _limit("LOGIN_MAX_FAILS_PER_EMAIL", 8) or cache.get(k_ip, 0) >= _limit("LOGIN_MAX_FAILS_PER_IP", 40)


def record_failure(email, ip):
    for key in _keys(email, ip):
        cache.add(key, 0, WINDOW)  # starts the window on the first failure only
        try:
            cache.incr(key)
        except ValueError:
            cache.set(key, 1, WINDOW)


def clear(email):
    cache.delete(_keys(email, "")[0])
