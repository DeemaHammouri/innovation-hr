from django.apps import AppConfig


class LeadsConfig(AppConfig):
    name = "leads"

    def ready(self):
        from core import access as registry

        from . import access, mywork, reminders  # noqa: F401  (importing registers the My Work provider and the daily job)
        from .models import Lead

        registry.register(
            "lead", Lead, can_view=access.can_view, can_write=access.can_pipeline_write,
            can_comment=lambda user, lead: access.can_view(user, lead) and not lead.archived_at,
            label=lambda lead: f"{lead.ref} {lead.company_name}", link=lambda lead: f"/leads/{lead.pk}",
        )
