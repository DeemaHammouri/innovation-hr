from rest_framework.response import Response
from rest_framework.views import APIView

from notifications.models import Notification

from . import mywork
from .roles import role_key


class MyWorkView(APIView):
    """Everything waiting on the signed-in person, plus the numbers for the sidebar badges."""

    def get(self, request):
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
