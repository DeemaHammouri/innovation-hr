from django.contrib import admin
from django.urls import include, path

from core.views import MyWorkView

urlpatterns = [
    path("admin/", admin.site.urls),
    path("api/", include("accounts.urls")),
    path("api/", include("clients.urls")),
    path("api/", include("audit.urls")),
    path("api/", include("notifications.urls")),
    path("api/", include("files.urls")),
    path("api/", include("comments.urls")),
    path("api/", include("lookups.urls")),
    path("api/", include("leads.urls")),
    path("api/", include("quotations.urls")),
    path("api/", include("contracts.urls")),
    path("api/", include("operations.urls")),
    path("api/", include("payments.urls")),
    path("api/", include("hr.urls")),
    path("api/", include("reports.urls")),
    path("api/my-work/", MyWorkView.as_view()),
]
