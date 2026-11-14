"""Run a job at most once per local day, on whichever request or command comes first. Safe to call from many places."""
from django.db import IntegrityError, transaction
from django.utils import timezone

from .models import DailyRun


def run_once_per_day(name, fn):
    today = timezone.localdate()
    try:
        with transaction.atomic():
            DailyRun.objects.create(name=name, day=today)
    except IntegrityError:
        return False  # someone else already ran it today
    try:
        fn()
    except Exception:
        DailyRun.objects.filter(name=name, day=today).delete()  # a failed run may be retried
        raise
    return True
