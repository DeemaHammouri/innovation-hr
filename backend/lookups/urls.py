from django.urls import include, path
from rest_framework.routers import DefaultRouter

from . import views

router = DefaultRouter()
router.register("rejection-reasons", views.RejectionReasonViewSet, basename="rejection-reason")
router.register("holidays", views.HolidayViewSet, basename="holiday")
router.register("services", views.ServiceViewSet, basename="service")
router.register("checklist-template", views.ChecklistTemplateItemViewSet, basename="checklist-template")

urlpatterns = [
    path("lookups/work-hours/", views.WorkHoursView.as_view()),
    path("lookups/sla/", views.SlaView.as_view()),
    path("lookups/", include(router.urls)),
]
