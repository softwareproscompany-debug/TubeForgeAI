"""Publishing views: idempotent publication jobs, integrity checks, approvals,
scheduling, and source-labeled analytics."""

import zoneinfo
from datetime import datetime

from django.db import IntegrityError
from django.shortcuts import get_object_or_404
from django.utils import timezone
from rest_framework import generics, permissions, status, viewsets
from rest_framework.decorators import action
from rest_framework.exceptions import ValidationError
from rest_framework.response import Response

from channels.models import Channel
from core.utils import InvalidTransitionAPI, record_audit
from projects.models import Asset, Project

from . import youtube as yt
from .models import AnalyticsSnapshot, PublicationJob
from .serializers import (
    AnalyticsSnapshotSerializer,
    PublicationJobCreateSerializer,
    PublicationJobSerializer,
)


def _owned_publication(user, pk):
    return get_object_or_404(
        PublicationJob.objects.select_related("project__channel", "channel"),
        pk=pk,
        channel__owner=user,
    )


def _blocking_issues(publication):
    issues = yt.ContentIntegrityChecker.run(publication.project, publication)
    return [i for i in issues if i["severity"] == "blocking"], issues


class PublicationJobViewSet(viewsets.ModelViewSet):
    serializer_class = PublicationJobSerializer
    permission_classes = (permissions.IsAuthenticated,)
    http_method_names = ("get", "post", "patch", "delete")

    def get_queryset(self):
        return PublicationJob.objects.filter(
            channel__owner=self.request.user
        ).select_related("project", "channel", "asset")

    def get_serializer_class(self):
        if self.action == "create":
            return PublicationJobCreateSerializer
        return PublicationJobSerializer

    def create(self, request, *args, **kwargs):
        serializer = PublicationJobCreateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        key = serializer.validated_data["idempotency_key"]
        # Idempotent publication: a duplicate key returns the existing job (200),
        # never a second publication record.
        existing = PublicationJob.objects.filter(idempotency_key=key).first()
        if existing is not None:
            if existing.channel.owner != request.user:
                raise ValidationError({"idempotency_key": "Key already used."})
            return Response(PublicationJobSerializer(existing).data)
        project = get_object_or_404(
            Project.objects.select_related("channel"),
            pk=serializer.validated_data["project"].id,
            channel__owner=request.user,
        )
        asset = serializer.validated_data.get("asset")
        if asset is not None:
            asset = get_object_or_404(
                Asset, pk=asset.id, project__channel__owner=request.user
            )
        try:
            publication = PublicationJob.objects.create(
                project=project,
                channel=project.channel,
                asset=asset,
                title=serializer.validated_data["title"],
                description=serializer.validated_data.get("description", ""),
                tags=serializer.validated_data.get("tags", []),
                visibility=serializer.validated_data.get("visibility", "private"),
                scheduled_at=serializer.validated_data.get("scheduled_at"),
                status="DRAFT",
                idempotency_key=key,
            )
        except IntegrityError:
            # Lost the race with a concurrent create using the same key: the
            # pre-check above already verified any existing row belongs to us.
            existing = PublicationJob.objects.filter(idempotency_key=key).first()
            if existing is not None and existing.channel.owner == request.user:
                return Response(PublicationJobSerializer(existing).data)
            raise
        record_audit(
            request.user,
            "publication.create",
            "publication_job",
            str(publication.id),
            request=request,
        )
        return Response(
            PublicationJobSerializer(publication).data, status=status.HTTP_201_CREATED
        )

    def perform_update(self, serializer):
        publication = serializer.save()
        record_audit(
            self.request.user,
            "publication.update",
            "publication_job",
            str(publication.id),
            request=self.request,
        )

    @action(detail=True, methods=["post"])
    def validate(self, request, pk=None):
        publication = _owned_publication(request.user, pk)
        blocking, issues = _blocking_issues(publication)
        try:
            yt.UploadStateMachine.transition(publication, "VALIDATING")
        except yt.InvalidUploadTransition as exc:
            raise InvalidTransitionAPI(str(exc)) from exc
        return Response(
            {"issues": issues, "blocking": blocking, "status": publication.status}
        )

    @action(detail=True, methods=["post"])
    def approve(self, request, pk=None):
        """Approve for upload. Blocking integrity issues prevent approval. When the
        channel policy demands human approval, a PUBLISH Approval gates it."""
        from workflows.models import Approval

        publication = _owned_publication(request.user, pk)
        blocking, issues = _blocking_issues(publication)
        if blocking:
            raise ValidationError(
                {
                    "blocking": blocking,
                    "detail": "Resolve blocking issues before approval.",
                }
            )
        policy = publication.channel.publishing_policy or {}
        if policy.get("require_approval", True):
            approved = Approval.objects.filter(
                project=publication.project, approval_type="PUBLISH", status="APPROVED"
            ).exists()
            if not approved:
                approval, _created = Approval.objects.get_or_create(
                    project=publication.project,
                    approval_type="PUBLISH",
                    status="PENDING",
                    defaults={"requested_by": request.user},
                )
                return Response(
                    {
                        "approval_required": True,
                        "approval_id": str(approval.id),
                        "issues": issues,
                    },
                    status=status.HTTP_202_ACCEPTED,
                )
        try:
            if publication.status == "DRAFT":
                yt.UploadStateMachine.transition(publication, "VALIDATING")
            yt.UploadStateMachine.transition(publication, "APPROVED")
        except yt.InvalidUploadTransition as exc:
            raise InvalidTransitionAPI(str(exc)) from exc
        record_audit(
            request.user,
            "publication.approve",
            "publication_job",
            str(publication.id),
            request=request,
        )
        return Response(PublicationJobSerializer(publication).data)

    @action(detail=True, methods=["post"])
    def schedule(self, request, pk=None):
        """Schedule publication. Times are timezone-aware, honoring channel.timezone."""
        publication = _owned_publication(request.user, pk)
        raw = request.data.get("scheduled_at")
        if not raw:
            raise ValidationError({"scheduled_at": "scheduled_at is required."})
        try:
            scheduled_at = datetime.fromisoformat(str(raw))
        except ValueError as exc:
            raise ValidationError({"scheduled_at": "Must be ISO-8601."}) from exc
        if timezone.is_naive(scheduled_at):
            try:
                tz = zoneinfo.ZoneInfo(publication.channel.timezone or "UTC")
            except zoneinfo.ZoneInfoNotFoundError:
                tz = zoneinfo.ZoneInfo("UTC")
            scheduled_at = scheduled_at.replace(tzinfo=tz)
        if scheduled_at <= timezone.now():
            raise ValidationError({"scheduled_at": "Must be in the future."})
        publication.scheduled_at = scheduled_at
        publication.save(update_fields=["scheduled_at", "updated_at"])
        try:
            if publication.status == "DRAFT":
                yt.UploadStateMachine.transition(publication, "VALIDATING")
            if publication.status == "VALIDATING":
                yt.UploadStateMachine.transition(publication, "APPROVED")
            yt.UploadStateMachine.transition(publication, "SCHEDULED")
        except yt.InvalidUploadTransition as exc:
            raise InvalidTransitionAPI(str(exc)) from exc
        record_audit(
            request.user,
            "publication.schedule",
            "publication_job",
            str(publication.id),
            request=request,
            metadata={"scheduled_at": scheduled_at.isoformat()},
        )
        return Response(PublicationJobSerializer(publication).data)

    @action(detail=True, methods=["post"])
    def cancel(self, request, pk=None):
        publication = _owned_publication(request.user, pk)
        try:
            yt.UploadStateMachine.transition(publication, "CANCELED")
        except yt.InvalidUploadTransition as exc:
            raise InvalidTransitionAPI(str(exc)) from exc
        record_audit(
            request.user,
            "publication.cancel",
            "publication_job",
            str(publication.id),
            request=request,
        )
        return Response(PublicationJobSerializer(publication).data)


class ChannelAnalyticsView(generics.ListAPIView):
    serializer_class = AnalyticsSnapshotSerializer

    def get_queryset(self):
        channel = get_object_or_404(
            Channel, pk=self.kwargs["pk"], owner=self.request.user
        )
        return AnalyticsSnapshot.objects.filter(channel=channel)


class VideoAnalyticsView(generics.ListAPIView):
    """Source-labeled metrics for one video (YOUTUBE_API / CALCULATED /
    AI_INTERPRETATION / FORECAST)."""

    serializer_class = AnalyticsSnapshotSerializer

    def get_queryset(self):
        return AnalyticsSnapshot.objects.filter(
            channel__owner=self.request.user,
            youtube_video_id=self.kwargs["video_id"],
        )
