from django.urls import include, path
from rest_framework.routers import DefaultRouter

from .portal import PortalDeliverableAcknowledgeView, PortalDeliverableDownloadView, PortalDeliverableListView, PortalMeView, PortalQuotationDetailView, PortalQuotationDocumentView, PortalQuotationListView, PortalQuotationSignView
from .portal import PortalContractDetailView, PortalContractDocumentView, PortalContractListView, PortalContractSignView
from .views import ClientViewSet

router = DefaultRouter()
router.register("clients", ClientViewSet, basename="client")

urlpatterns = [
    path("portal/me/", PortalMeView.as_view()),
    path("portal/deliverables/", PortalDeliverableListView.as_view()),
    path("portal/deliverables/<int:pk>/download/", PortalDeliverableDownloadView.as_view()),
    path("portal/deliverables/<int:pk>/acknowledge/", PortalDeliverableAcknowledgeView.as_view()),
    path("portal/quotations/", PortalQuotationListView.as_view()),
    path("portal/quotations/<int:pk>/", PortalQuotationDetailView.as_view()),
    path("portal/quotations/<int:pk>/document/", PortalQuotationDocumentView.as_view()),
    path("portal/quotations/<int:pk>/sign/", PortalQuotationSignView.as_view()),
    path("portal/contracts/", PortalContractListView.as_view()),
    path("portal/contracts/<int:pk>/", PortalContractDetailView.as_view()),
    path("portal/contracts/<int:pk>/document/", PortalContractDocumentView.as_view()),
    path("portal/contracts/<int:pk>/sign/", PortalContractSignView.as_view()),
    path("", include(router.urls)),
]
