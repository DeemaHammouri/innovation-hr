from django.contrib import admin
from django.urls import include, path

from core.views import HealthView, MyWorkView

# Every API route, written once. They are served under /api/v1/ (the contract) and under /api/ (kept as an alias for one release).
api_patterns = [
    path("", include("accounts.urls")),
    path("", include("clients.urls")),
    path("", include("audit.urls")),
    path("", include("notifications.urls")),
    path("", include("files.urls")),
    path("", include("comments.urls")),
    path("", include("lookups.urls")),
    path("", include("leads.urls")),
    path("", include("quotations.urls")),
    path("", include("contracts.urls")),
    path("", include("operations.urls")),
    path("", include("payments.urls")),
    path("", include("hr.urls")),
    path("", include("reports.urls")),
    path("my-work/", MyWorkView.as_view()),
    path("health/", HealthView.as_view()),
]

urlpatterns = [
    path("admin/", admin.site.urls),
    path("api/v1/", include(api_patterns)),
    path("api/", include(api_patterns)),
]

handler404 = "core.errors.json_404"
handler500 = "core.errors.json_500"
