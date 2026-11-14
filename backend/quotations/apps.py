from django.apps import AppConfig


class QuotationsConfig(AppConfig):
    name = "quotations"

    def ready(self):
        from core import access as registry

        from . import access, mywork, reminders  # noqa: F401  (importing registers the My Work provider and the daily job)
        from .models import Quotation

        registry.register(
            "quotation", Quotation, can_view=access.can_view, can_write=access.can_write, can_attach=access.can_attach,
            label=lambda q: f"{q.ref} {q.lead.company_name}", link=lambda q: f"/quotations/{q.pk}",
        )
