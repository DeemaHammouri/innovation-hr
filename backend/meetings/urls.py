from rest_framework.routers import DefaultRouter

from .views import MeetingReportViewSet

router = DefaultRouter()
router.register("meeting-reports", MeetingReportViewSet, basename="meeting-report")

urlpatterns = router.urls
