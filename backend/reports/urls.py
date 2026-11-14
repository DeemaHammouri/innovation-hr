from django.urls import path

from . import views

urlpatterns = [
    path("reports/", views.ReportIndex.as_view()),
    path("reports/<str:section>/", views.ReportView.as_view()),
    path("reports/<str:section>/export/", views.ReportExport.as_view()),
    path("search/", views.SearchView.as_view()),
]
