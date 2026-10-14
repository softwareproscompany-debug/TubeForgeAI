"""Research URL routes."""
from django.urls import path

from .views import ChannelIdeasView, IdeaCreateProjectView, ResearchRunViewSet

run_list = ResearchRunViewSet.as_view({"get": "list", "post": "create"})
run_detail = ResearchRunViewSet.as_view({"get": "retrieve", "delete": "destroy"})
run_cancel = ResearchRunViewSet.as_view({"post": "cancel"})

urlpatterns = [
    path("research-runs", run_list, name="research-run-list"),
    path("research-runs/<uuid:pk>", run_detail, name="research-run-detail"),
    path("research-runs/<uuid:pk>/cancel", run_cancel, name="research-run-cancel"),
    path("channels/<uuid:pk>/ideas", ChannelIdeasView.as_view(), name="channel-ideas"),
    path("ideas/<uuid:pk>/create-project", IdeaCreateProjectView.as_view(), name="idea-create-project"),
]
