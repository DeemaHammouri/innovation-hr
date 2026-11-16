from django.apps import AppConfig


class OperationsConfig(AppConfig):
    name = "operations"

    def ready(self):
        from core import access as registry

        from . import access, mywork, reminders, services  # noqa: F401  (importing registers the My Work provider and the daily job)
        from .models import ChecklistItem, Handover, Project

        # Files on a checklist item: anyone who can see the client can read them; Operation can add them.
        registry.register(
            "checklist_item", ChecklistItem,
            can_view=lambda user, item: access.can_view_client(user, item.client),
            can_write=lambda user, item: access.is_op(user),
            can_attach=lambda user, item, category="": access.is_op(user) and item.archived_at is None,
            label=lambda item: item.name_en, link=lambda item: f"/operation/{item.client_id}",
            after_attach=services.file_attached,
        )

        from .handover_api import visible_q

        # A handover carries an activity trail and comments, never files: nothing about the contract can ride along with it.
        registry.register(
            "handover", Handover, can_view=lambda user, h: Handover.objects.filter(visible_q(user), pk=h.pk).exists(),
            can_write=lambda user, h: False, can_attach=lambda user, h, category="": False,
            label=lambda h: f"{h.ref} {h.client.company_name}", link=lambda h: f"/handovers/{h.pk}",
        )
        registry.register(
            "project", Project, can_view=lambda user, p: user.has_capability("project.view"), can_write=lambda user, p: False,
            can_attach=lambda user, p, category="": False, label=lambda p: f"{p.ref} {p.name}", link=lambda p: f"/projects/{p.pk}",
        )
