from django.apps import AppConfig


class ClientsConfig(AppConfig):
    name = "clients"

    def ready(self):
        from core import access

        from .models import Client

        def can_view(user, obj):
            from operations import access as ops

            return bool(user.has_capability("client.manage")) or ops.can_view_client(user, obj)

        def can_attach(user, obj, category=""):
            from operations import access as ops

            return bool(user.has_capability("client.manage")) or ops.is_op(user)

        def can_comment(user, obj):
            from operations import access as ops

            return bool(user.has_capability("client.manage")) or ops.is_op(user)

        # Writing stays with the CEO and the Operation head (as before); Operation and read-only Commercial can also see, comment and attach.
        access.register(
            "client", Client, can_view=can_view, can_write=lambda user, obj: bool(user.has_capability("client.manage")), can_attach=can_attach, can_comment=can_comment,
            label=lambda c: c.company_name, link=lambda c: f"/clients/{c.pk}",
        )
