from django.urls import include, path
from rest_framework.routers import DefaultRouter

from .portal import PortalMeView
from .views import ClientViewSet

router = DefaultRouter()
router.register("clients", ClientViewSet, basename="client")

urlpatterns = [path("portal/me/", PortalMeView.as_view()), path("", include(router.urls))]
