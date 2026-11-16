from django.urls import path
from rest_framework.routers import DefaultRouter

from .handover_api import HandoverViewSet, ProjectViewSet
from .monitoring import MonitoringView
from .views import AssigneeViewSet, ChecklistViewSet, MeetingViewSet, OpClientViewSet, RecurringViewSet, TaskViewSet

router = DefaultRouter()
router.register("operations/clients", OpClientViewSet, basename="op-client")
router.register("operations/checklist", ChecklistViewSet, basename="op-checklist")
router.register("operations/recurring", RecurringViewSet, basename="op-recurring")
router.register("operations/tasks", TaskViewSet, basename="op-task")
router.register("operations/assignees", AssigneeViewSet, basename="op-assignee")
router.register("operations/meetings", MeetingViewSet, basename="op-meeting")
router.register("handovers", HandoverViewSet, basename="handover")
router.register("projects", ProjectViewSet, basename="project")

urlpatterns = [path("operations/monitoring/", MonitoringView.as_view()), *router.urls]
