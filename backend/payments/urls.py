from django.urls import path
from rest_framework.routers import DefaultRouter

from .views import ClientPaymentsViewSet, InstalmentViewSet, OverviewView, PaymentViewSet

router = DefaultRouter()
router.register("payments/clients", ClientPaymentsViewSet, basename="pay-client")
router.register("payments/instalments", InstalmentViewSet, basename="pay-instalment")
router.register("payments/records", PaymentViewSet, basename="pay-record")

urlpatterns = [path("payments/overview/", OverviewView.as_view())] + router.urls
