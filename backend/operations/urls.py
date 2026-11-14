from rest_framework.routers import DefaultRouter

from .views import AssigneeViewSet, ChecklistViewSet, MeetingViewSet, OpClientViewSet, RecurringViewSet, TaskViewSet

router = DefaultRouter()
router.register("operations/clients", OpClientViewSet, basename="op-client")
router.register("operations/checklist", ChecklistViewSet, basename="op-checklist")
router.register("operations/recurring", RecurringViewSet, basename="op-recurring")
router.register("operations/tasks", TaskViewSet, basename="op-task")
router.register("operations/assignees", AssigneeViewSet, basename="op-assignee")
router.register("operations/meetings", MeetingViewSet, basename="op-meeting")

urlpatterns = router.urls
