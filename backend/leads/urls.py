from django.urls import include, path
from rest_framework.routers import DefaultRouter

from .views import ImportBatchViewSet, LeadViewSet

router = DefaultRouter()
router.register("leads", LeadViewSet, basename="lead")
router.register("import-batches", ImportBatchViewSet, basename="import-batch")

urlpatterns = [path("", include(router.urls))]
