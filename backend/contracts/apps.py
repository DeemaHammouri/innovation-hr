from django.apps import AppConfig


class ContractsConfig(AppConfig):
    name = "contracts"

    def ready(self):
        from core import access as registry

        from . import access, mywork  # noqa: F401  (importing registers the My Work provider)
        from .models import Contract

        registry.register(
            "contract", Contract, can_view=access.can_view, can_write=access.can_write, can_attach=access.can_attach,
            label=lambda c: f"{c.ref} {c.lead.company_name}", link=lambda c: f"/contracts/{c.pk}",
        )
