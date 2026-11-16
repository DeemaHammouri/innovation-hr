import logging

from rest_framework.response import Response
from rest_framework.views import APIView

from notifications.models import Notification

from . import mywork
from .daily import run_once_per_day
from .roles import role_key


class MyWorkView(APIView):
    """Everything waiting on the signed-in person, plus the numbers for the sidebar badges."""

    required_capabilities = []  # any signed-in person; each provider decides what that person sees

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


class HealthView(APIView):
    """For load balancers and uptime checks: is the app up and can it reach its database. Reveals nothing else."""

    authentication_classes = []
    permission_classes = []
    throttle_classes = []

    def get(self, request):
        from django.db import connection

        try:
            with connection.cursor() as cur:
                cur.execute("SELECT 1")
                cur.fetchone()
        except Exception:
            return Response({"status": "down"}, status=503)
        return Response({"status": "ok"})


def json_404(request, exception=None):
    from django.http import JsonResponse

    return JsonResponse({"detail": "Not found."}, status=404)


def json_500(request):
    from django.http import JsonResponse

    return JsonResponse({"detail": "Something went wrong on our side. Try again, and tell your administrator if it keeps happening."}, status=500)
