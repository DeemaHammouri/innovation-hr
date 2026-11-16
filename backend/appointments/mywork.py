"""My Work: my appointments that start today (company time) and the ones I let pass without closing."""
from django.utils import timezone

from core.mywork import provider

from .models import Appointment


@provider
def appointment_items(user):
    if not user.has_capability("appointment.access"):
        return []
    now = timezone.now()
    end_of_today = timezone.localtime(now).replace(hour=23, minute=59, second=59, microsecond=999999)
    out = []
    for a in Appointment.objects.filter(owner=user, status="scheduled", starts_at__lte=end_of_today).order_by("starts_at")[:30]:
        late = a.starts_at < now
        out.append(
            {"kind": "appointment_overdue" if late else "appointment_today", "section": "appointments", "ref": a.get_type_display(), "title": a.title,
             "link": f"/appointments?open={a.pk}", "due": timezone.localtime(a.starts_at).date().isoformat(), "overdue": late}
        )
    return out
