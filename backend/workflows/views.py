"""Workflow views: run lifecycle, pause/resume/cancel/retry, events + SSE stream,
approvals, and project workflow creation with Temporal-or-synchronous start."""

import asyncio
import json

from django.conf import settings
from django.db import IntegrityError
from django.db.models import Q
from django.http import StreamingHttpResponse
from django.shortcuts import get_object_or_404
from django.utils import timezone
from rest_framework import permissions, status, viewsets
from rest_framework.decorators import action
from rest_framework.exceptions import ValidationError
from rest_framework.response import Response
from rest_framework.views import APIView

from core.utils import InvalidTransitionAPI, parse_uuid, record_audit
from projects.models import Project

from . import engine
from .models import Approval, WorkflowRun
from .serializers import (
    ApprovalDecideSerializer,
    ApprovalSerializer,
    WorkflowEventSerializer,
    WorkflowRunCreateSerializer,
    WorkflowRunSerializer,
)
from .temporal_workflows import TEMPORAL_AVAILABLE, build_workflow_id

SYNC_FALLBACK_STAGES = [
    "QUEUED",
    "RESEARCHING",
    "SCRIPTING",
    "STORYBOARDING",
    "GENERATING_ASSETS",
    "GENERATING_NARRATION",
    "ASSEMBLING",
    "RENDERING",
    "VALIDATING",
    "FINAL_REVIEW",
    "READY_TO_PUBLISH",
]


def _owned_run(user, pk):
    return get_object_or_404(
        WorkflowRun.objects.select_related("project__channel"),
        pk=pk,
        project__channel__owner=user,
    )


def _start_temporal_workflow(run):
    """Start the durable Temporal workflow. Raises on any connection failure."""
    if not TEMPORAL_AVAILABLE:
        raise RuntimeError("temporalio is not installed")

    from temporalio.client import Client

    from .temporal_workflows import VideoProductionWorkflow

    async def _start():
        client = await asyncio.wait_for(
            Client.connect(
                settings.TEMPORAL_HOST, namespace=settings.TEMPORAL_NAMESPACE
            ),
            timeout=5,
        )
        handle = await client.start_workflow(
            VideoProductionWorkflow.run,
            args=[str(run.id), str(run.project_id)],
            id=run.temporal_workflow_id,
            task_queue=settings.TEMPORAL_TASK_QUEUE,
        )
        return handle.id

    return asyncio.run(_start())


def _run_synchronous_stages(run, actor, request):
    """Fallback stage runner used when Temporal is unreachable.

    Transitions the run through the pipeline stages synchronously, writing a
    WorkflowEvent per stage. Recorded in output_summary as a synchronous run.
    """
    completed = []
    for stage in SYNC_FALLBACK_STAGES:
        run.refresh_from_db()
        if run.status in engine.TERMINAL_STATES:
            break
        try:
            engine.transition(
                run, stage, actor=actor, request=request, event_type="sync_stage"
            )
        except engine.InvalidTransition:
            # A concurrent pause/cancel raced the fallback runner; stop here
            # rather than 500ing the workflow creation.
            break
        completed.append(stage)
    run.refresh_from_db()
    summary = dict(run.output_summary or {})
    summary.update(
        {
            "execution_mode": "synchronous_fallback",
            "temporal_unreachable": True,
            "completed_stages": completed,
        }
    )
    run.output_summary = summary
    run.save(update_fields=["output_summary"])
    return completed


class ProjectWorkflowCreateView(APIView):
    """Create a workflow run for a project: DRAFT -> PLANNING, then start via
    Temporal, falling back to the synchronous stage runner when Temporal is
    unreachable (recorded in output_summary)."""

    def post(self, request, pk):
        project = get_object_or_404(
            Project.objects.select_related("channel"),
            pk=pk,
            channel__owner=request.user,
        )
        serializer = WorkflowRunCreateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        # Bounded retry: concurrent creates can compute the same version and
        # collide on the unique temporal_workflow_id; re-count and retry.
        for _ in range(3):
            version = project.workflow_runs.count() + 1
            try:
                run = WorkflowRun.objects.create(
                    project=project,
                    workflow_type=serializer.validated_data["workflow_type"],
                    temporal_workflow_id=build_workflow_id(project.id, version),
                    status="DRAFT",
                    current_stage="DRAFT",
                    input_snapshot=serializer.validated_data.get("input", {}),
                )
                break
            except IntegrityError:
                continue
        else:
            raise ValidationError(
                {"detail": "Could not allocate a workflow run; please retry."}
            )
        try:
            engine.transition(run, "PLANNING", actor=request.user, request=request)
        except engine.InvalidTransition as exc:
            raise InvalidTransitionAPI(str(exc)) from exc

        summary = dict(run.output_summary or {})
        try:
            handle_id = _start_temporal_workflow(run)
            summary.update(
                {"execution_mode": "temporal", "temporal_handle_id": handle_id}
            )
        except Exception as exc:  # noqa: BLE001 - temporal fallback; any failure uses synchronous mode
            completed = _run_synchronous_stages(run, request.user, request)
            summary.update(
                {
                    "execution_mode": "synchronous_fallback",
                    "temporal_unreachable": True,
                    "temporal_error": f"{type(exc).__name__}: {exc}"[:300],
                    "completed_stages": completed,
                }
            )
        run.output_summary = summary
        run.save(update_fields=["output_summary"])
        record_audit(
            request.user,
            "workflow.create",
            "workflow_run",
            str(run.id),
            request=request,
            metadata={
                "workflow_type": run.workflow_type,
                "execution_mode": summary.get("execution_mode"),
            },
        )
        return Response(WorkflowRunSerializer(run).data, status=status.HTTP_201_CREATED)


class WorkflowRunViewSet(viewsets.ReadOnlyModelViewSet):
    serializer_class = WorkflowRunSerializer
    permission_classes = (permissions.IsAuthenticated,)

    def get_queryset(self):
        qs = WorkflowRun.objects.filter(
            project__channel__owner=self.request.user
        ).select_related("project__channel")
        project_id = self.request.query_params.get("project_id")
        if project_id:
            qs = qs.filter(project_id=parse_uuid(project_id, "project_id"))
        return qs

    def _transition_action(self, request, pk, to_state, action_name):
        run = _owned_run(request.user, pk)
        try:
            engine.transition(run, to_state, actor=request.user, request=request)
        except engine.InvalidTransition as exc:
            raise InvalidTransitionAPI(str(exc)) from exc
        record_audit(
            request.user,
            f"workflow.{action_name}",
            "workflow_run",
            str(run.id),
            request=request,
        )
        return Response(WorkflowRunSerializer(run).data)

    @action(detail=True, methods=["post"])
    def pause(self, request, pk=None):
        return self._transition_action(request, pk, "PAUSED", "pause")

    @action(detail=True, methods=["post"])
    def resume(self, request, pk=None):
        return self._transition_action(request, pk, "QUEUED", "resume")

    @action(detail=True, methods=["post"])
    def cancel(self, request, pk=None):
        return self._transition_action(request, pk, "CANCELED", "cancel")

    @action(detail=True, methods=["post"])
    def retry(self, request, pk=None):
        return self._transition_action(request, pk, "QUEUED", "retry")

    @action(detail=True, methods=["get"])
    def events(self, request, pk=None):
        run = _owned_run(request.user, pk)
        events = run.events.all()
        page = self.paginate_queryset(events)
        serializer = WorkflowEventSerializer(page or events, many=True)
        if page is not None:
            return self.get_paginated_response(serializer.data)
        return Response(serializer.data)

    @action(detail=True, methods=["get"])
    def stream(self, request, pk=None):
        """Server-Sent Events stream of the run's workflow events."""
        run = _owned_run(request.user, pk)

        def _generate():
            for event in run.events.order_by("occurred_at"):
                payload = {
                    "id": str(event.id),
                    "event_type": event.event_type,
                    "stage": event.stage,
                    "payload": event.payload,
                    "occurred_at": event.occurred_at.isoformat(),
                }
                yield f"data: {json.dumps(payload)}\n\n"
            yield "event: done\ndata: {}\n\n"

        response = StreamingHttpResponse(_generate(), content_type="text/event-stream")
        response["Cache-Control"] = "no-cache"
        return response


class ApprovalViewSet(viewsets.ModelViewSet):
    serializer_class = ApprovalSerializer
    http_method_names = ("get", "post")

    def get_queryset(self):
        return Approval.objects.filter(
            Q(project__channel__owner=self.request.user)
            | Q(requested_by=self.request.user)
        ).select_related("project", "workflow_run")

    def perform_create(self, serializer):
        project = get_object_or_404(
            Project,
            pk=parse_uuid(self.request.data.get("project"), "project"),
            channel__owner=self.request.user,
        )
        approval = serializer.save(project=project, requested_by=self.request.user)
        record_audit(
            self.request.user,
            "approval.request",
            "approval",
            str(approval.id),
            request=self.request,
            metadata={"approval_type": approval.approval_type},
        )

    @action(detail=True, methods=["post"])
    def decide(self, request, pk=None):
        approval = get_object_or_404(
            Approval.objects.select_related("project__channel"),
            pk=pk,
            project__channel__owner=request.user,
        )
        if approval.status != "PENDING":
            raise ValidationError({"detail": "This approval has already been decided."})
        serializer = ApprovalDecideSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        new_status = (
            "APPROVED"
            if serializer.validated_data["decision"] == "approved"
            else "REJECTED"
        )
        # Atomic decide: the conditional UPDATE is the single linearization
        # point, so two concurrent decides cannot both succeed.
        decided = Approval.objects.filter(pk=approval.pk, status="PENDING").update(
            status=new_status,
            decided_by=request.user,
            decision_reason=serializer.validated_data.get("reason", ""),
            decided_at=timezone.now(),
        )
        if not decided:
            raise ValidationError({"detail": "This approval has already been decided."})
        approval.refresh_from_db()
        record_audit(
            request.user,
            "approval.decide",
            "approval",
            str(approval.id),
            request=request,
            metadata={"status": approval.status},
        )
        return Response(ApprovalSerializer(approval).data)
