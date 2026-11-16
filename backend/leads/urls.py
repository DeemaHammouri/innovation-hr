from django.urls import include, path
from rest_framework.routers import DefaultRouter

from .views import DashboardView, ImportBatchViewSet, LeadViewSet, TargetAssigneesView, TargetDetailView, TargetListView

router = DefaultRouter()
router.register("leads", LeadViewSet, basename="lead")
router.register("import-batches", ImportBatchViewSet, basename="import-batch")

urlpatterns = [
    path("leads/dashboard/", DashboardView.as_view()),
    path("leads/targets/", TargetListView.as_view()),
    path("leads/targets/assignees/", TargetAssigneesView.as_view()),
    path("leads/targets/<int:pk>/", TargetDetailView.as_view()),
    path("", include(router.urls)),
]
