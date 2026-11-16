from django.apps import AppConfig


class AppointmentsConfig(AppConfig):
    name = "appointments"

    def ready(self):
        from . import mywork, reminders  # noqa: F401  (importing registers the My Work provider)
