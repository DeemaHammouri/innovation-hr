from datetime import timedelta

from django.db import models
from django.utils import timezone


class UpdatedAtField(models.DateTimeField):
    """`auto_now`, except the value never repeats or goes back for the same row.

    The edit forms send back the `updated_at` they loaded and the server compares it (core.concurrency). On a machine whose clock ticks
    coarsely (Windows: about 15 ms) two saves of one record could get the identical timestamp, so a stale edit looked fresh. Here a save
    that would not move the timestamp forward moves it by one microsecond, so every saved version has its own token.

    It is stored exactly like a normal DateTimeField(auto_now=True), and `deconstruct` says so, so no migration is involved."""

    def __init__(self, *args, **kwargs):
        kwargs["auto_now"] = True
        super().__init__(*args, **kwargs)

    def pre_save(self, instance, add):
        now = timezone.now()
        previous = getattr(instance, self.attname, None)
        if previous is not None and not add and now <= previous:
            now = previous + timedelta(microseconds=1)
        setattr(instance, self.attname, now)
        return now

    def deconstruct(self):
        name, _path, args, kwargs = super().deconstruct()
        return name, "django.db.models.DateTimeField", args, kwargs
