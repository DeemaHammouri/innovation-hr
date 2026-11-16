from rest_framework.routers import DefaultRouter

from .views import ContractTemplateViewSet, ContractViewSet

router = DefaultRouter()
router.register("contract-templates", ContractTemplateViewSet, basename="contract-template")
router.register("contracts", ContractViewSet, basename="contract")

urlpatterns = router.urls
