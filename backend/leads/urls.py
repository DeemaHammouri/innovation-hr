from django.urls import include, path
from rest_framework.routers import DefaultRouter

from .views import DashboardView, ImportBatchViewSet, LeadViewSet, TargetView

router = DefaultRouter()
router.register("leads", LeadViewSet, basename="lead")
router.register("import-batches", ImportBatchViewSet, basename="import-batch")

urlpatterns = [
    path("leads/dashboard/", DashboardView.as_view()),
    path("leads/target/", TargetView.as_view()),
    path("", include(router.urls)),
]
