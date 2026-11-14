from django.apps import AppConfig


class HrConfig(AppConfig):
    name = "hr"

    def ready(self):
        from core import access as registry

        from . import access, mywork  # noqa: F401  (importing registers the My Work provider)
        from .models import LeaveRequest, PayrollRun

        # A leave request's history and comments: its owner, HR and the CEO. A payroll run's history (it never contains amounts): HR head and CEO.
        registry.register(
            "leave_request", LeaveRequest, can_view=lambda u, r: r.user_id == u.pk or access.sees_everyone(u),
            can_write=lambda u, r: False, label=lambda r: r.user.full_name, link=lambda r: "/leave",
        )
        registry.register(
            "payroll_run", PayrollRun, can_view=lambda u, r: access.sees_payroll(u), can_write=lambda u, r: access.manages_payroll(u),
            label=lambda r: r.month.strftime("%Y-%m"), link=lambda r: f"/payroll/{r.pk}",
        )
