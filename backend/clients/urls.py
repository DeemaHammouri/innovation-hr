from django.urls import include, path
from rest_framework.routers import DefaultRouter

from .portal import PortalMeView, PortalQuotationDetailView, PortalQuotationDocumentView, PortalQuotationListView, PortalQuotationSignView
from .views import ClientViewSet

router = DefaultRouter()
router.register("clients", ClientViewSet, basename="client")

urlpatterns = [
    path("portal/me/", PortalMeView.as_view()),
    path("portal/quotations/", PortalQuotationListView.as_view()),
    path("portal/quotations/<int:pk>/", PortalQuotationDetailView.as_view()),
    path("portal/quotations/<int:pk>/document/", PortalQuotationDocumentView.as_view()),
    path("portal/quotations/<int:pk>/sign/", PortalQuotationSignView.as_view()),
    path("", include(router.urls)),
]
