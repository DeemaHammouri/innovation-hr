from rest_framework.routers import DefaultRouter

from .views import GeneralTaskViewSet

router = DefaultRouter()
router.register("tasks", GeneralTaskViewSet, basename="gtask")

urlpatterns = router.urls
