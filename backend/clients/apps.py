from django.apps import AppConfig


class ClientsConfig(AppConfig):
    name = "clients"

    def ready(self):
        from core import access

        from .models import Client

        # Same rule as the clients endpoint: the CEO and the Operation head.
        allowed = lambda user, obj: user.can_manage_clients
        access.register(
            "client", Client, can_view=allowed, can_write=allowed,
            label=lambda c: c.company_name, link=lambda c: f"/clients/{c.pk}",
        )
