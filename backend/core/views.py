import logging

from rest_framework.response import Response
from rest_framework.views import APIView

from notifications.models import Notification

from . import mywork
from .daily import run_once_per_day
from .roles import role_key


class MyWorkView(APIView):
    """Everything waiting on the signed-in person, plus the numbers for the sidebar badges."""

    def get(self, request):
        for name, job in mywork.daily_jobs():
            try:
                run_once_per_day(name, job)
            except Exception:  # reminders must never break the page
                logging.getLogger(__name__).exception("daily job %s failed", name)
        items = mywork.collect(request.user)
        return Response(
            {
                "role": role_key(request.user),
                "items": items,
                "total": len(items),
                "badges": mywork.badges(items),
                "unread_notifications": Notification.objects.filter(user=request.user, read_at__isnull=True).count(),
            }
        )
