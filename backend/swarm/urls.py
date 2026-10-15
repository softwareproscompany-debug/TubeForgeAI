"""Swarm URL routes (mounted under /api/v1/)."""

from django.urls import path

from .views import (
    SwarmRunCancelView,
    SwarmRunDetailView,
    SwarmRunListCreateView,
    SwarmRunMessagesView,
)

urlpatterns = [
    path("swarm/runs", SwarmRunListCreateView.as_view(), name="swarm-runs"),
    path("swarm/runs/<uuid:pk>", SwarmRunDetailView.as_view(), name="swarm-run-detail"),
    path(
        "swarm/runs/<uuid:pk>/messages",
        SwarmRunMessagesView.as_view(),
        name="swarm-run-messages",
    ),
    path(
        "swarm/runs/<uuid:pk>/cancel",
        SwarmRunCancelView.as_view(),
        name="swarm-run-cancel",
    ),
]
