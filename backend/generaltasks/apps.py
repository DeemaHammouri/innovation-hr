from django.apps import AppConfig


class GeneralTasksConfig(AppConfig):
    name = "generaltasks"

    def ready(self):
        from core import access as registry

        from . import mywork, reminders, scope  # noqa: F401  (importing registers the My Work provider and the daily job)
        from .models import GeneralTask

        # Notes, files and history on a task: whoever may see it reads them; the assignee and whoever gave it write them.
        registry.register(
            "gtask", GeneralTask,
            can_view=scope.can_view,
            can_write=lambda user, t: scope.can_view(user, t) and (t.assignee_id == user.pk or scope.can_manage(user, t)),
            can_attach=lambda user, t, category="": t.status == GeneralTask.Status.OPEN and (t.assignee_id == user.pk or scope.can_manage(user, t)),
            label=lambda t: t.title, link=lambda t: f"/tasks?open={t.pk}",
        )
