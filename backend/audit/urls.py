from django.urls import path

from .tracking import FeedFiltersView, FeedView, TrackingView
from .views import ActivityListView

urlpatterns = [
    path("activity/", ActivityListView.as_view()),
    path("admin/tracking/", TrackingView.as_view()),
    path("admin/activity/", FeedView.as_view()),
    path("admin/activity/filters/", FeedFiltersView.as_view()),
]
