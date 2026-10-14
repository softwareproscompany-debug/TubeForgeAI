"""Workflow URL routes."""
from django.urls import path

from .views import ApprovalViewSet, WorkflowRunViewSet

run_detail = WorkflowRunViewSet.as_view({"get": "retrieve"})
run_list = WorkflowRunViewSet.as_view({"get": "list"})
run_pause = WorkflowRunViewSet.as_view({"post": "pause"})
run_resume = WorkflowRunViewSet.as_view({"post": "resume"})
run_cancel = WorkflowRunViewSet.as_view({"post": "cancel"})
run_retry = WorkflowRunViewSet.as_view({"post": "retry"})
run_events = WorkflowRunViewSet.as_view({"get": "events"})
run_stream = WorkflowRunViewSet.as_view({"get": "stream"})
approval_list = ApprovalViewSet.as_view({"get": "list", "post": "create"})
approval_detail = ApprovalViewSet.as_view({"get": "retrieve"})
approval_decide = ApprovalViewSet.as_view({"post": "decide"})

urlpatterns = [
    path("workflows", run_list, name="workflow-list"),
    path("workflows/<uuid:pk>", run_detail, name="workflow-detail"),
    path("workflows/<uuid:pk>/pause", run_pause, name="workflow-pause"),
    path("workflows/<uuid:pk>/resume", run_resume, name="workflow-resume"),
    path("workflows/<uuid:pk>/cancel", run_cancel, name="workflow-cancel"),
    path("workflows/<uuid:pk>/retry", run_retry, name="workflow-retry"),
    path("workflows/<uuid:pk>/events", run_events, name="workflow-events"),
    path("workflows/<uuid:pk>/events/stream", run_stream, name="workflow-events-stream"),
    path("approvals", approval_list, name="approval-list"),
    path("approvals/<uuid:pk>", approval_detail, name="approval-detail"),
    path("approvals/<uuid:pk>/decide", approval_decide, name="approval-decide"),
]
