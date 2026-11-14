from django.urls import path

from .views import CommentListCreateView, MentionableView

urlpatterns = [
    path("comments/", CommentListCreateView.as_view()),
    path("mentionable/", MentionableView.as_view()),
]
