from django.apps import AppConfig


class OperationsConfig(AppConfig):
    name = "operations"

    def ready(self):
        from core import access as registry

        from . import access, mywork, reminders, services  # noqa: F401  (importing registers the My Work provider and the daily job)
        from .models import ChecklistItem

        # Files on a checklist item: anyone who can see the client can read them; Operation can add them.
        registry.register(
            "checklist_item", ChecklistItem,
            can_view=lambda user, item: access.can_view_client(user, item.client),
            can_write=lambda user, item: access.is_op(user),
            can_attach=lambda user, item, category="": access.is_op(user) and item.archived_at is None,
            label=lambda item: item.name_en, link=lambda item: f"/operation/{item.client_id}",
            after_attach=services.file_attached,
        )
