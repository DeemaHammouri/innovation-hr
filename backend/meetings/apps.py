from django.apps import AppConfig


class MeetingsConfig(AppConfig):
    name = "meetings"

    def ready(self):
        from core import access as registry

        from . import access
        from .models import MeetingReport

        def can_view(user, r):
            return MeetingReport.objects.filter(access.visible_q(user), pk=r.pk).exists()

        registry.register(
            "meetingreport", MeetingReport, can_view=can_view, can_write=lambda u, r: any(access.flags(u, r).values()), can_attach=lambda u, r, c: False,
            label=lambda r: f"MR-{r.pk:05d} {r.lead.company_name}", link=lambda r: f"/meetings/{r.pk}",
        )
