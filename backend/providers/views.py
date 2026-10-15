"""Provider views: CRUD, health checks, test generations, job routing, usage, budgets."""

import asyncio
from decimal import Decimal, InvalidOperation

from django.db import transaction
from django.db.models import Q
from django.shortcuts import get_object_or_404
from rest_framework import generics, status, viewsets
from rest_framework.decorators import action
from rest_framework.exceptions import ValidationError
from rest_framework.response import Response

from core.utils import (
    BudgetExceededAPI,
    PaidFallbackApprovalRequiredAPI,
    parse_uuid,
    record_audit,
)
from projects.models import Project, Scene

from . import gateway
from .models import AIModel, Budget, GenerationJob, Provider, ResourceUsageEvent
from .serializers import (
    AIModelSerializer,
    BudgetSerializer,
    GenerationJobSerializer,
    ProviderSerializer,
    ResourceUsageEventSerializer,
)


def _api_error(exc, api_cls):
    raise api_cls(f"{exc.code}: {exc}") from exc


class ProviderViewSet(viewsets.ModelViewSet):
    serializer_class = ProviderSerializer
    queryset = Provider.objects.all().select_related("secret_reference")

    def perform_create(self, serializer):
        provider = serializer.save()
        record_audit(
            self.request.user,
            "provider.create",
            "provider",
            str(provider.id),
            request=self.request,
        )

    def perform_update(self, serializer):
        provider = serializer.save()
        record_audit(
            self.request.user,
            "provider.update",
            "provider",
            str(provider.id),
            request=self.request,
        )

    @action(detail=True, methods=["post"])
    def health_check(self, request, pk=None):
        provider = self.get_object()
        adapter = gateway.get_adapter(provider)
        result = asyncio.run(adapter.health_check())
        provider.health_status = result.get("status", "UNKNOWN")
        provider.save(update_fields=["health_status", "updated_at"])
        record_audit(
            request.user,
            "provider.health_check",
            "provider",
            str(provider.id),
            request=request,
            metadata={"status": provider.health_status},
        )
        return Response({"provider_id": str(provider.id), **result})

    @action(detail=True, methods=["post"])
    def test_generation(self, request, pk=None):
        """Run a real, small adapter call (capabilities + health) against the provider."""
        provider = self.get_object()
        adapter = gateway.get_adapter(provider)
        capabilities = asyncio.run(adapter.capabilities())
        health = asyncio.run(adapter.health_check())
        return Response(
            {
                "provider_id": str(provider.id),
                "capabilities": capabilities,
                "health": health,
            }
        )


class AIModelViewSet(viewsets.ModelViewSet):
    serializer_class = AIModelSerializer

    def get_queryset(self):
        queryset = AIModel.objects.select_related("provider")
        provider_id = self.request.query_params.get("provider")
        if provider_id:
            queryset = queryset.filter(provider_id=provider_id)
        return queryset


class GenerationJobViewSet(viewsets.ModelViewSet):
    serializer_class = GenerationJobSerializer
    http_method_names = ("get", "post")

    def get_queryset(self):
        # Jobs are always created with a project (create() requires one), so
        # every visible job is reachable through the requesting user's channel.
        # There is no "global job" branch: unscoped jobs must never leak across
        # owners on cancel/complete/get_object.
        return GenerationJob.objects.filter(
            Q(project__channel__owner=self.request.user)
            | Q(project__isnull=True, scene__project__channel__owner=self.request.user),
        ).select_related("provider", "model", "project")

    def create(self, request, *args, **kwargs):
        data = request.data
        task_type = data.get("task_type")
        if not task_type:
            raise ValidationError({"task_type": "task_type is required."})
        requirements = data.get("requirements", {})
        if not isinstance(requirements, dict):
            raise ValidationError({"requirements": "requirements must be an object."})
        request_metadata = data.get("request_metadata", {})
        if not isinstance(request_metadata, dict):
            raise ValidationError(
                {"request_metadata": "request_metadata must be an object."}
            )
        project = scene = None
        if data.get("project_id"):
            project = get_object_or_404(
                Project,
                pk=parse_uuid(data["project_id"], "project_id"),
                channel__owner=request.user,
            )
        if data.get("scene_id"):
            scene = get_object_or_404(
                Scene,
                pk=parse_uuid(data["scene_id"], "scene_id"),
                project__channel__owner=request.user,
            )
            project = project or scene.project
        if project is None:
            raise ValidationError({"project_id": "A project (or scene) is required."})
        channel = project.channel
        idempotency_key = data.get("idempotency_key")
        if idempotency_key:
            # Idempotent submit: a duplicate key returns the existing job (HTTP 200),
            # never a second job. Scoped to the requester's jobs so one user can
            # never observe or collide with another user's key.
            existing = (
                self.get_queryset().filter(idempotency_key=idempotency_key).first()
            )
            if existing is not None:
                return Response(GenerationJobSerializer(existing).data)
        try:
            job = gateway.route_generation(
                task_type=task_type,
                requirements=requirements,
                channel=channel,
                project=project,
                scene=scene,
                workflow_id=data.get("workflow_id"),
                policy=data.get("policy"),
                idempotency_key=idempotency_key,
                allow_paid_fallback=bool(data.get("allow_paid_fallback", False)),
                requested_model_id=data.get("model_id"),
                request_metadata=request_metadata,
            )
        except gateway.BudgetExceeded as exc:
            _api_error(exc, BudgetExceededAPI)
        except gateway.PaidFallbackApprovalRequired as exc:
            _api_error(exc, PaidFallbackApprovalRequiredAPI)
        except gateway.ProviderError as exc:
            raise ValidationError({"detail": f"{exc.code}: {exc}"}) from exc
        record_audit(
            request.user,
            "generation.create",
            "generation_job",
            str(job.id),
            request=request,
            metadata={"task_type": task_type},
        )
        return Response(
            GenerationJobSerializer(job).data, status=status.HTTP_201_CREATED
        )

    @action(detail=True, methods=["post"])
    def cancel(self, request, pk=None):
        job = self.get_object()
        if job.status in ("QUEUED", "RUNNING"):
            if job.external_job_id:
                try:
                    asyncio.run(
                        gateway.get_adapter(job.provider).cancel(job.external_job_id)
                    )
                except gateway.ProviderError:
                    pass  # cancel is best-effort against the provider
            job.status = "CANCELED"
            job.save(update_fields=["status"])
            record_audit(
                request.user,
                "generation.cancel",
                "generation_job",
                str(job.id),
                request=request,
            )
        return Response(GenerationJobSerializer(job).data)

    @action(detail=True, methods=["post"])
    def complete(self, request, pk=None):
        """Record finished outputs (used by polling loops / provider webhooks)."""
        job = self.get_object()
        if job.status not in ("QUEUED", "RUNNING"):
            raise ValidationError(
                {"detail": f"Job is already {job.status}; cannot complete it again."}
            )
        outputs = request.data.get("outputs", [])
        if not isinstance(outputs, list) or any(
            not isinstance(item, dict) for item in outputs
        ):
            raise ValidationError({"outputs": "outputs must be a list of objects."})
        actual_cost = request.data.get("actual_cost")
        if actual_cost is not None:
            try:
                Decimal(str(actual_cost))
            except InvalidOperation:
                raise ValidationError(
                    {"actual_cost": "actual_cost must be a number."}
                ) from None
        assets = gateway.complete_job(job, outputs, actual_cost=actual_cost)
        record_audit(
            request.user,
            "generation.complete",
            "generation_job",
            str(job.id),
            request=request,
            metadata={"assets": len(assets)},
        )
        return Response(GenerationJobSerializer(job).data)


class ResourceUsageListView(generics.ListAPIView):
    serializer_class = ResourceUsageEventSerializer

    def get_queryset(self):
        queryset = ResourceUsageEvent.objects.filter(
            job__project__channel__owner=self.request.user
        ).select_related("provider", "job")
        params = self.request.query_params
        if params.get("provider"):
            queryset = queryset.filter(provider_id=params["provider"])
        if params.get("resource_type"):
            queryset = queryset.filter(resource_type=params["resource_type"])
        if params.get("since"):
            queryset = queryset.filter(occurred_at__gte=params["since"])
        if params.get("until"):
            queryset = queryset.filter(occurred_at__lte=params["until"])
        return queryset


class BudgetViewSet(viewsets.ModelViewSet):
    serializer_class = BudgetSerializer
    http_method_names = ("get", "post", "patch", "put", "delete")

    def get_queryset(self):
        user = self.request.user
        channel_ids = list(user.channels.values_list("id", flat=True))
        project_ids = list(
            Project.objects.filter(channel__owner=user).values_list("id", flat=True)
        )
        return Budget.objects.filter(
            Q(scope_type="global")
            | Q(scope_type="channel", scope_id__in=channel_ids)
            | Q(scope_type="project", scope_id__in=project_ids)
        )

    def _check_scope_permission(self, budget):
        """Budgets are enforced globally by the gateway, so a budget must never
        be created or moved onto another user's scope (spend-limit DoS)."""
        from channels.models import Channel
        from workflows.models import WorkflowRun

        user = self.request.user
        scope_type, scope_id = budget.scope_type, budget.scope_id
        if scope_type == "global":
            if not user.is_staff:
                raise ValidationError(
                    {"scope_type": "Only staff can manage the global budget."}
                )
        elif scope_type == "channel":
            get_object_or_404(Channel, pk=scope_id, owner=user)
        elif scope_type == "project":
            get_object_or_404(Project, pk=scope_id, channel__owner=user)
        elif scope_type == "workflow":
            get_object_or_404(WorkflowRun, pk=scope_id, project__channel__owner=user)

    def perform_create(self, serializer):
        # Atomic: a scope violation must roll back the row, otherwise the
        # rejected budget would still be enforced by the gateway's global lookup.
        with transaction.atomic():
            budget = serializer.save()
            self._check_scope_permission(budget)
        record_audit(
            self.request.user,
            "budget.create",
            "budget",
            str(budget.id),
            request=self.request,
            metadata={"scope_type": budget.scope_type},
        )

    def perform_update(self, serializer):
        with transaction.atomic():
            budget = serializer.save()
            self._check_scope_permission(budget)
        record_audit(
            self.request.user,
            "budget.update",
            "budget",
            str(budget.id),
            request=self.request,
        )
