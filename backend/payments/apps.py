from django.apps import AppConfig


class PaymentsConfig(AppConfig):
    name = "payments"

    def ready(self):
        from core import access as registry

        from . import access, mywork, reminders  # noqa: F401  (importing registers the My Work provider and the daily job)
        from .models import Instalment, Payment

        # History, comments and receipts of an instalment or a payment follow the same rule as the screens: Commercial head
        # writes, the CEO reads, nobody else can even tell the record exists.
        registry.register(
            "instalment", Instalment, can_view=access.can_view, can_write=access.can_write, can_attach=lambda u, o, category="": access.can_write(u),
            label=lambda i: f"#{i.number}", link=lambda i: f"/payments/{i.client_id}",
        )
        registry.register(
            "payment", Payment, can_view=access.can_view, can_write=access.can_write, can_attach=lambda u, o, category="": access.can_write(u),
            label=lambda p: f"#{p.pk}", link=lambda p: f"/payments/{p.instalment.client_id}",
        )
