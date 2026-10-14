"""Project views: CRUD, plan generation (no execution), scripts, scenes, timelines,
renders, assets, and HMAC-signed upload URLs."""
import hashlib
import hmac
import time
import uuid
from urllib.parse import quote

from channels.models import Channel
from core.utils import OwnsChannel, record_audit
from django.conf import settings
from django.db.models import Max
from django.shortcuts import get_object_or_404
from rest_framework import generics, permissions, status, viewsets
from rest_framework.exceptions import ValidationError
from rest_framework.response import Response
from rest_framework.views import APIView

from . import media_engine
from .models import Asset, Project, RenderJob, Scene, ScriptVersion, TimelineVersion
from .serializers import (
    AssetSerializer,
    ProjectSerializer,
    RenderJobSerializer,
    SceneSerializer,
    ScriptVersionSerializer,
    TimelineVersionSerializer,
)

MAX_UPLOAD_BYTES = 512 * 1024 * 1024
ALLOWED_UPLOAD_MIMES = {
    "image/png", "image/jpeg", "image/webp",
    "video/mp4", "video/quicktime", "video/webm",
    "audio/mpeg", "audio/wav", "audio/mp4",
    "text/vtt", "text/plain", "application/pdf",
}


def _owned_project(user, pk):
    return get_object_or_404(
        Project.objects.select_related("channel"), pk=pk, channel__owner=user
    )


# ---------------------------------------------------------------------------
# Projects
# ---------------------------------------------------------------------------
class ProjectViewSet(viewsets.ModelViewSet):
    serializer_class = ProjectSerializer
    permission_classes = [permissions.IsAuthenticated, OwnsChannel]

    def get_queryset(self):
        qs = Project.objects.filter(channel__owner=self.request.user).select_related("channel")
        channel_id = self.request.query_params.get("channel_id")
        if channel_id:
            qs = qs.filter(channel_id=channel_id)
        return qs

    def perform_create(self, serializer):
        channel = get_object_or_404(
            Channel, pk=self.request.data.get("channel"), owner=self.request.user
        )
        project = serializer.save(channel=channel)
        record_audit(
            self.request.user, "project.create", "project", str(project.id),
            request=self.request,
        )

    def perform_update(self, serializer):
        project = serializer.save()
        record_audit(
            self.request.user, "project.update", "project", str(project.id),
            request=self.request,
        )

    def perform_destroy(self, instance):
        record_audit(
            self.request.user, "project.delete", "project", str(instance.id),
            request=self.request,
        )
        instance.delete()


class GeneratePlanView(APIView):
    """Validate inputs and return a structured production plan WITHOUT executing it."""

    STAGES = [
        "research", "script", "storyboard", "generate_assets", "generate_narration",
        "assemble", "render", "validate", "final_review",
    ]

    def post(self, request, pk):
        project = _owned_project(request.user, pk)
        target = int(request.data.get("target_duration_seconds") or project.target_duration_seconds)
        fmt = request.data.get("format") or project.format
        if fmt not in ("LONG_FORM", "SHORT", "DOCUMENTARY", "EXPLAINER", "CINEMATIC"):
            raise ValidationError({"format": "Unsupported format."})
        if target <= 0 or target > 12 * 3600:
            raise ValidationError({"target_duration_seconds": "Must be between 1 and 43200."})

        scene_count = max(1, round(target / 8))
        estimated_minutes = round(target / 60 * 2.5, 1)
        plan = {
            "stages": [
                {"name": stage, "order": i, "requires_approval": stage in ("script", "final_review")}
                for i, stage in enumerate(self.STAGES)
            ],
            "scene_count_estimate": scene_count,
            "estimated_duration": {
                "estimate": True,
                "total_minutes": estimated_minutes,
                "method": "duration_heuristic_v1",
            },
            "estimated_cost": {
                "estimate": True,
                "amount_usd": round(scene_count * 0.12, 2),
                "method": "cost_heuristic_v1",
                "disclaimer": "Heuristic estimate only; actual cost depends on provider routing and budgets.",
            },
            "models": (project.channel.automation_config or {}).get("preferred_models", []),
            "approvals": ["script", "final_review"],
        }
        record_audit(
            request.user, "project.generate_plan", "project", str(project.id),
            request=request, metadata={"format": fmt, "target_duration_seconds": target},
        )
        return Response(plan)


# ---------------------------------------------------------------------------
# Scripts
# ---------------------------------------------------------------------------
class ScriptViewSet(viewsets.ModelViewSet):
    serializer_class = ScriptVersionSerializer
    permission_classes = [permissions.IsAuthenticated]

    def _project(self):
        return _owned_project(self.request.user, self.kwargs["project_pk"])

    def get_queryset(self):
        return ScriptVersion.objects.filter(project=self._project())

    def perform_create(self, serializer):
        project = self._project()
        last = project.script_versions.aggregate(m=Max("version_number"))["m"] or 0
        script = serializer.save(project=project, version_number=last + 1)
        record_audit(
            self.request.user, "script.create", "script", str(script.id),
            request=self.request, metadata={"version": script.version_number},
        )

    def approve(self, request, project_pk=None, pk=None):
        """Approve a script version and record the Approval row in workflows."""
        from workflows.models import Approval

        script = self.get_object()
        script.approval_status = "APPROVED"
        script.save(update_fields=["approval_status"])
        approval = Approval.objects.create(
            project=script.project,
            approval_type="SCRIPT",
            status="APPROVED",
            requested_by=request.user,
            decided_by=request.user,
            decision_reason=request.data.get("reason", ""),
        )
        record_audit(
            request.user, "script.approve", "script", str(script.id),
            request=request, metadata={"approval_id": str(approval.id)},
        )
        return Response(ScriptVersionSerializer(script).data)


# ---------------------------------------------------------------------------
# Scenes
# ---------------------------------------------------------------------------
class SceneViewSet(viewsets.ModelViewSet):
    serializer_class = SceneSerializer
    permission_classes = [permissions.IsAuthenticated]
    http_method_names = ["get", "post", "patch", "delete"]

    def _project(self):
        return _owned_project(self.request.user, self.kwargs["project_pk"])

    def get_queryset(self):
        return Scene.objects.filter(project=self._project())

    def perform_create(self, serializer):
        project = self._project()
        last = project.scenes.aggregate(m=Max("position"))["m"]
        position = serializer.validated_data.get("position", (last or 0) + 1)
        scene = serializer.save(project=project, position=position)
        record_audit(
            self.request.user, "scene.create", "scene", str(scene.id), request=self.request,
        )

    def generate(self, request, project_pk=None, pk=None):
        """Create a GenerationJob for this scene via the provider gateway."""
        from providers.gateway import route_generation
        from providers.serializers import GenerationJobSerializer

        scene = self.get_object()
        project = scene.project
        task_type = "video" if scene.scene_type in ("CINEMATIC", "FACELESS") else "image"
        job = route_generation(
            task_type=task_type,
            requirements=scene.generation_settings or {"duration_seconds": scene.duration_seconds},
            channel=project.channel,
            project=project,
            scene=scene,
            idempotency_key=request.data.get("idempotency_key") or uuid.uuid4().hex,
            allow_paid_fallback=bool(request.data.get("allow_paid_fallback", False)),
            requested_model_id=request.data.get("model_id"),
            request_metadata={"scene_id": str(scene.id)},
        )
        scene.status = "GENERATING"
        scene.save(update_fields=["status", "updated_at"])
        record_audit(
            request.user, "scene.generate", "scene", str(scene.id),
            request=request, metadata={"job_id": str(job.id)},
        )
        return Response(GenerationJobSerializer(job).data, status=status.HTTP_201_CREATED)

    def regenerate(self, request, project_pk=None, pk=None):
        """Reset a scene to PENDING, invalidating its dependent generated outputs."""
        scene = self.get_object()
        scene.status = "PENDING"
        scene.save(update_fields=["status", "updated_at"])
        # Dependent generated assets for this scene are quarantined so the next
        # generate pass rebuilds only what this scene needs (incremental invalidation).
        quarantined = scene.assets.filter(source_type="GENERATED", status="READY").update(
            status="QUARANTINED"
        )
        record_audit(
            request.user, "scene.regenerate", "scene", str(scene.id),
            request=request, metadata={"quarantined_assets": quarantined},
        )
        return Response({"status": scene.status, "quarantined_assets": quarantined})


# ---------------------------------------------------------------------------
# Timelines (versioned)
# ---------------------------------------------------------------------------
class TimelineView(APIView):
    def get(self, request, project_pk):
        project = _owned_project(request.user, project_pk)
        latest = project.timeline_versions.first()
        if latest is None:
            return Response({"detail": "No timeline versions yet."}, status=status.HTTP_404_NOT_FOUND)
        return Response(TimelineVersionSerializer(latest).data)

    def post(self, request, project_pk):
        project = _owned_project(request.user, project_pk)
        timeline_json = request.data.get("timeline_json")
        try:
            media_engine.validate_timeline(timeline_json)
        except media_engine.TimelineValidationError as exc:
            raise ValidationError({"timeline_json": exc.details})
        last = project.timeline_versions.aggregate(m=Max("version_number"))["m"] or 0
        version = TimelineVersion.objects.create(
            project=project,
            version_number=last + 1,
            timeline_json=timeline_json,
            render_settings=request.data.get("render_settings", {}),
        )
        record_audit(
            request.user, "timeline.create", "timeline", str(version.id),
            request=request, metadata={"version": version.version_number},
        )
        return Response(TimelineVersionSerializer(version).data, status=status.HTTP_201_CREATED)


# ---------------------------------------------------------------------------
# Renders
# ---------------------------------------------------------------------------
class RenderJobViewSet(viewsets.ModelViewSet):
    serializer_class = RenderJobSerializer
    permission_classes = [permissions.IsAuthenticated]
    http_method_names = ["get", "post"]

    def _project(self):
        return _owned_project(self.request.user, self.kwargs["project_pk"])

    def get_queryset(self):
        return RenderJob.objects.filter(project=self._project()).select_related("timeline_version")

    def create(self, request, *args, **kwargs):
        project = self._project()
        timeline_version = get_object_or_404(
            TimelineVersion, pk=request.data.get("timeline_version_id"), project=project
        )
        try:
            media_engine.validate_timeline(timeline_version.timeline_json)
        except media_engine.TimelineValidationError as exc:
            raise ValidationError({"timeline_version_id": exc.details})
        asset_hashes = {
            str(a.id): (a.sha256 or a.object_key)
            for a in project.assets.filter(status="READY")
        }
        manifest = media_engine.build_render_manifest(
            asset_hashes, timeline_version.id,
            request.data.get("encoding_settings", {}), {"timeline_valid": True},
        )
        job = RenderJob.objects.create(
            project=project, timeline_version=timeline_version,
            status="QUEUED", manifest=manifest,
        )
        record_audit(
            request.user, "render.create", "render_job", str(job.id),
            request=request, metadata={"timeline_version": timeline_version.version_number},
        )
        return Response(RenderJobSerializer(job).data, status=status.HTTP_201_CREATED)

    def cancel(self, request, project_pk=None, pk=None):
        job = self.get_object()
        if job.status in ("QUEUED", "RUNNING"):
            job.status = "CANCELED"
            job.save(update_fields=["status"])
            record_audit(
                request.user, "render.cancel", "render_job", str(job.id), request=request,
            )
        return Response(RenderJobSerializer(job).data)


# ---------------------------------------------------------------------------
# Assets + signed upload URLs
# ---------------------------------------------------------------------------
class AssetViewSet(viewsets.ReadOnlyModelViewSet):
    serializer_class = AssetSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        return Asset.objects.filter(project__channel__owner=self.request.user).select_related(
            "project", "scene"
        )


def sign_upload_url(object_key, expires_in=900):
    """Build a short-lived HMAC-signed upload URL.

    Scheme: ``/api/v1/assets/direct-upload?key=<object_key>&exp=<unix_ts>&sig=<hex>``
    where ``sig = HMAC_SHA256(SECRET_KEY, "<object_key>:<exp>")``. The receiving
    endpoint recomputes the HMAC with :func:`verify_upload_signature` and rejects
    expired or tampered URLs. The signature covers only the key + expiry; the
    uploader must still be authenticated and own the target project.
    """
    exp = int(time.time()) + int(expires_in)
    payload = f"{object_key}:{exp}"
    sig = hmac.new(settings.SECRET_KEY.encode(), payload.encode(), hashlib.sha256).hexdigest()
    base = (settings.PUBLIC_APP_URL or "").rstrip("/")
    return {
        "upload_url": f"{base}/api/v1/assets/direct-upload?key={quote(object_key)}&exp={exp}&sig={sig}",
        "object_key": object_key,
        "expires_in": int(expires_in),
    }


def verify_upload_signature(object_key, exp, sig):
    """Return True iff the signature is valid and not expired."""
    try:
        if int(exp) < int(time.time()):
            return False
    except (TypeError, ValueError):
        return False
    expected = hmac.new(
        settings.SECRET_KEY.encode(), f"{object_key}:{exp}".encode(), hashlib.sha256
    ).hexdigest()
    return hmac.compare_digest(expected, sig or "")


class UploadUrlView(APIView):
    """Issue a short-lived signed upload URL after validating mime/size/owner."""

    def post(self, request):
        filename = (request.data.get("filename") or "").strip().lstrip("/")
        mime_type = request.data.get("mime_type", "")
        size_bytes = int(request.data.get("size_bytes") or 0)
        if not filename:
            raise ValidationError({"filename": "Filename is required."})
        if mime_type not in ALLOWED_UPLOAD_MIMES:
            raise ValidationError({"mime_type": f"Unsupported mime type: {mime_type}"})
        if size_bytes <= 0 or size_bytes > MAX_UPLOAD_BYTES:
            raise ValidationError({"size_bytes": f"Must be between 1 and {MAX_UPLOAD_BYTES}."})
        project_id = request.data.get("project_id")
        project = _owned_project(request.user, project_id) if project_id else None
        safe_name = "".join(c for c in filename if c.isalnum() or c in ("-", "_", ".", "/"))[:200]
        object_key = f"uploads/{request.user.id}/{uuid.uuid4().hex}/{safe_name}"
        signed = sign_upload_url(object_key)
        record_audit(
            request.user, "asset.upload_url", "project", str(project.id) if project else "",
            request=request, metadata={"mime_type": mime_type, "size_bytes": size_bytes},
        )
        return Response({**signed, "mime_type": mime_type, "size_bytes": size_bytes})
