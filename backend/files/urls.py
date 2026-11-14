from django.urls import path

from . import views

urlpatterns = [
    path("files/", views.AttachmentListCreateView.as_view()),
    path("files/<int:pk>/download/", views.AttachmentDownloadView.as_view()),
    path("files/<int:pk>/archive/", views.AttachmentArchiveView.as_view()),
]
