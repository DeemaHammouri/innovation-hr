from django.urls import include, path
from rest_framework.routers import DefaultRouter
from rest_framework_simplejwt.views import TokenRefreshView

from . import views

router = DefaultRouter()
router.register("users", views.UserViewSet, basename="user")

urlpatterns = [
    path("auth/login/", views.LoginView.as_view()),
    path("auth/logout/", views.LogoutView.as_view()),
    path("auth/refresh/", TokenRefreshView.as_view()),
    path("auth/me/", views.MeView.as_view()),
    path("auth/change-password/", views.ChangePasswordView.as_view()),
    path("dashboard/summary/", views.DashboardSummaryView.as_view()),
    path("departments/", views.DepartmentListView.as_view()),
    path("", include(router.urls)),
]
