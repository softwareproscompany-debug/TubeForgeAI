"""Research views: runs execute a deterministic local analysis synchronously.

Honesty rules enforced here:
- Every AI-generated estimate is labeled {"estimate": true} inside evidence.
- We never claim private competitor analytics; demand signals are local
  heuristics and are worded as such.
"""

import hashlib
import re

from django.shortcuts import get_object_or_404
from django.utils import timezone
from rest_framework import generics, permissions, status, viewsets
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.views import APIView

from channels.models import Channel
from core.utils import OwnsChannel, record_audit

from .models import ContentIdea, ResearchRun, ResearchSource
from .serializers import (
    ContentIdeaSerializer,
    ResearchRunCreateSerializer,
    ResearchRunSerializer,
)

_ANALYSIS_VERSION = "local_heuristic_v1"
_IDEA_ANGLES = [
    ("tutorial", "Tutorial", 0.72),
    ("mistakes", "Mistakes to avoid", 0.66),
    ("case study", "Case study breakdown", 0.61),
    ("tools", "Tools comparison", 0.58),
    ("beginner guide", "Beginner guide", 0.55),
]


def _keywords(query, limit=6):
    words = [
        w.strip().lower()
        for w in re.split(r"[^\w']+", query or "")
        if len(w.strip()) > 2
    ]
    seen, out = set(), []
    for word in words:
        if word not in seen:
            seen.add(word)
            out.append(word)
        if len(out) == limit:
            break
    return out or ["video"]


def _execute_local_analysis(run):
    """Deterministic, dependency-free analysis producing sources + ideas."""
    keywords = _keywords(run.query)
    depth = int((run.parameters or {}).get("depth", 3))
    sources, ideas = [], []
    for index, keyword in enumerate(keywords[:3]):
        for slot, (angle, angle_title, confidence) in enumerate(_IDEA_ANGLES[:depth]):
            title = f"Demand signal: '{keyword}' — {angle}"
            content_hash = hashlib.sha256(
                f"{_ANALYSIS_VERSION}:{title}".encode()
            ).hexdigest()
            sources.append(
                ResearchSource(
                    run=run,
                    source_type="local_analysis",
                    source_url="",
                    title=title,
                    evidence={
                        "estimate": True,
                        "method": _ANALYSIS_VERSION,
                        "keyword": keyword,
                        "angle": angle,
                        "projected_monthly_searches": 500
                        * (index + 1)
                        * (slot + 1)
                        * max(len(keyword), 3),
                        "competition": "unknown — estimate only, not measured",
                        "disclaimer": (
                            "AI-generated estimate from a local heuristic. "
                            "Not private competitor analytics; treat as a starting hypothesis."
                        ),
                    },
                    content_hash=content_hash,
                    license_metadata={"origin": "tubeforge-local", "license": "n/a"},
                )
            )
    ResearchSource.objects.bulk_create(sources)

    for slot, (angle, angle_title, confidence) in enumerate(_IDEA_ANGLES[:depth]):
        title = f"{run.query.strip().title()}: {angle_title}"
        idea, _created = ContentIdea.objects.get_or_create(
            channel=run.channel,
            title=title[:500],
            defaults={
                "topic": run.query,
                "format": (run.parameters or {}).get("format", "LONG_FORM"),
                "priority": depth - slot,
                "confidence_score": confidence,
                "supporting_evidence": {
                    "estimate": True,
                    "method": _ANALYSIS_VERSION,
                    "angle": angle,
                    "disclaimer": "Confidence is a heuristic estimate, not measured performance.",
                },
                "status": "NEW",
            },
        )
        ideas.append(idea)
    return {"sources_created": len(sources), "ideas_created": len(ideas)}


def _owned_channel(user, pk):
    return get_object_or_404(Channel, pk=pk, owner=user)


class ResearchRunViewSet(viewsets.ModelViewSet):
    serializer_class = ResearchRunSerializer
    permission_classes = (permissions.IsAuthenticated, OwnsChannel)
    http_method_names = ("get", "post", "delete")

    def get_queryset(self):
        return (
            ResearchRun.objects.filter(channel__owner=self.request.user)
            .select_related("channel")
            .prefetch_related("sources")
        )

    def get_serializer_class(self):
        if self.action == "create":
            return ResearchRunCreateSerializer
        return ResearchRunSerializer

    def create(self, request, *args, **kwargs):
        serializer = ResearchRunCreateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        channel = get_object_or_404(
            Channel, pk=serializer.validated_data["channel"].id, owner=request.user
        )
        run = ResearchRun.objects.create(
            channel=channel,
            query=serializer.validated_data["query"],
            parameters=serializer.validated_data.get("parameters", {}),
            status="RUNNING",
            started_at=timezone.now(),
        )
        try:
            summary = _execute_local_analysis(run)
            run.status = "COMPLETED"
        except Exception as exc:  # noqa: BLE001 - local analysis must never 500 the request
            run.status = "FAILED"
            run.error_summary = str(exc)[:500]
            summary = {}
        run.completed_at = timezone.now()
        run.save()
        record_audit(
            request.user,
            "research_run.create",
            "research_run",
            str(run.id),
            request=request,
            metadata={"query": run.query, **summary},
        )
        return Response(ResearchRunSerializer(run).data, status=status.HTTP_201_CREATED)

    @action(detail=True, methods=["post"])
    def cancel(self, request, pk=None):
        run = self.get_object()
        if run.status in ("PENDING", "RUNNING"):
            run.status = "CANCELED"
            run.completed_at = timezone.now()
            run.save(update_fields=["status", "completed_at"])
            record_audit(
                request.user,
                "research_run.cancel",
                "research_run",
                str(run.id),
                request=request,
            )
        return Response(ResearchRunSerializer(run).data)


class ChannelIdeasView(generics.ListAPIView):
    serializer_class = ContentIdeaSerializer

    def get_queryset(self):
        channel = _owned_channel(self.request.user, self.kwargs["pk"])
        return ContentIdea.objects.filter(channel=channel)


class IdeaCreateProjectView(APIView):
    """Promote an idea into a project and mark the idea IN_PROJECT."""

    def post(self, request, pk):
        from projects.models import Project
        from projects.serializers import ProjectSerializer

        idea = get_object_or_404(ContentIdea, pk=pk, channel__owner=request.user)
        project = Project.objects.create(
            channel=idea.channel,
            content_idea=idea,
            title=idea.title,
            brief=idea.topic,
            format=idea.format
            if idea.format
            in ("LONG_FORM", "SHORT", "DOCUMENTARY", "EXPLAINER", "CINEMATIC")
            else "LONG_FORM",
            target_duration_seconds=600,
            aspect_ratio="16:9",
            language=idea.channel.default_language,
            status="DRAFT",
        )
        idea.status = "IN_PROJECT"
        idea.save(update_fields=["status"])
        record_audit(
            request.user,
            "idea.create_project",
            "project",
            str(project.id),
            request=request,
            metadata={"idea_id": str(idea.id)},
        )
        return Response(ProjectSerializer(project).data, status=status.HTTP_201_CREATED)
