"""Publishing URL routes."""

from django.urls import path

from .views import ChannelAnalyticsView, PublicationJobViewSet, VideoAnalyticsView

pub_list = PublicationJobViewSet.as_view({"get": "list", "post": "create"})
pub_detail = PublicationJobViewSet.as_view(
    {"get": "retrieve", "patch": "partial_update", "delete": "destroy"}
)
pub_validate = PublicationJobViewSet.as_view({"post": "validate"})
pub_approve = PublicationJobViewSet.as_view({"post": "approve"})
pub_schedule = PublicationJobViewSet.as_view({"post": "schedule"})
pub_cancel = PublicationJobViewSet.as_view({"post": "cancel"})

urlpatterns = [
    path("publications", pub_list, name="publication-list"),
    path("publications/<uuid:pk>", pub_detail, name="publication-detail"),
    path("publications/<uuid:pk>/validate", pub_validate, name="publication-validate"),
    path("publications/<uuid:pk>/approve", pub_approve, name="publication-approve"),
    path("publications/<uuid:pk>/schedule", pub_schedule, name="publication-schedule"),
    path("publications/<uuid:pk>/cancel", pub_cancel, name="publication-cancel"),
    path(
        "channels/<uuid:pk>/analytics",
        ChannelAnalyticsView.as_view(),
        name="channel-analytics",
    ),
    path(
        "videos/<str:video_id>/analytics",
        VideoAnalyticsView.as_view(),
        name="video-analytics",
    ),
]
