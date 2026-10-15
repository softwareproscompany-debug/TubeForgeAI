"""Swarm API: start runs, inspect the inter-agent conversation, cancel."""

from django.shortcuts import get_object_or_404
from django.utils import timezone
from rest_framework import permissions, status
from rest_framework.response import Response
from rest_framework.views import APIView

from core.utils import OwnsChannel, record_audit
from projects.models import Project

from .models import SwarmRun
from .orchestrator import SwarmOrchestrator
from .serializers import (
    AgentMessageSerializer,
    SwarmRunCreateSerializer,
    SwarmRunSerializer,
)


def _get_run(user, pk):
    run = get_object_or_404(
        SwarmRun.objects.select_related("project", "project__channel"),
        pk=pk,
        project__channel__owner=user,
    )
    return run


class SwarmRunListCreateView(APIView):
    """GET the user's swarm runs, newest first (powers the /swarm page).
    POST {project_id, topic} -> runs the full pipeline synchronously."""

    permission_classes = (permissions.IsAuthenticated,)

    def get(self, request):
        runs = SwarmRun.objects.filter(
            project__channel__owner=request.user
        ).select_related("project")
        return Response(SwarmRunSerializer(runs, many=True).data)

    def post(self, request):
        serializer = SwarmRunCreateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        project = get_object_or_404(
            Project,
            pk=serializer.validated_data["project_id"],
            channel__owner=request.user,
        )
        run = SwarmOrchestrator().start_run(
            project.id, serializer.validated_data["topic"]
        )
        record_audit(
            request.user,
            "swarm.run_start",
            "swarm_run",
            str(run.id),
            request=request,
            metadata={"project_id": str(project.id), "status": run.status},
        )
        return Response(SwarmRunSerializer(run).data, status=status.HTTP_201_CREATED)


class SwarmRunDetailView(APIView):
    """GET run status + current stage + per-agent states."""

    permission_classes = (permissions.IsAuthenticated, OwnsChannel)

    def get(self, request, pk):
        run = _get_run(request.user, pk)
        self.check_object_permissions(request, run)
        return Response(SwarmRunSerializer(run).data)


class SwarmRunMessagesView(APIView):
    """GET the chronological inter-agent conversation for a run."""

    permission_classes = (permissions.IsAuthenticated, OwnsChannel)

    def get(self, request, pk):
        run = _get_run(request.user, pk)
        self.check_object_permissions(request, run)
        messages = run.messages.select_related("from_agent", "to_agent")
        return Response(AgentMessageSerializer(messages, many=True).data)


class SwarmRunCancelView(APIView):
    """POST -> mark a still-running run cancelled."""

    permission_classes = (permissions.IsAuthenticated, OwnsChannel)

    def post(self, request, pk):
        run = _get_run(request.user, pk)
        self.check_object_permissions(request, run)
        if run.status == "running":
            run.status = "cancelled"
            run.completed_at = timezone.now()
            run.save(update_fields=["status", "completed_at"])
            record_audit(
                request.user,
                "swarm.run_cancel",
                "swarm_run",
                str(run.id),
                request=request,
            )
        return Response(SwarmRunSerializer(run).data)
