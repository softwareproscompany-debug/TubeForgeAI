"""Onboarding progress views.

Progress is per-user (OneToOne). The first GET lazily creates the row so
the frontend can always read state without a separate "start" call.
"""

from django.utils import timezone
from rest_framework import permissions, status
from rest_framework.response import Response
from rest_framework.views import APIView

from core.utils import record_audit

from .models import ONBOARDING_STEPS, OnboardingProgress
from .serializers import CompleteStepSerializer, OnboardingProgressSerializer


def _get_or_create_progress(user):
    progress, _ = OnboardingProgress.objects.get_or_create(user=user)
    return progress


def _advance(progress, completed_step):
    """Mark a step done and move current_step to the next incomplete step."""
    completed = list(progress.completed_steps or [])
    if completed_step not in completed:
        completed.append(completed_step)
    progress.completed_steps = completed
    remaining = [s for s in ONBOARDING_STEPS if s not in completed]
    if remaining:
        progress.current_step = remaining[0]
    else:
        progress.current_step = ONBOARDING_STEPS[-1]
        progress.completed_at = timezone.now()
    progress.save(
        update_fields=["completed_steps", "current_step", "completed_at", "updated_at"]
    )
    return progress


class OnboardingProgressView(APIView):
    """GET the current user's onboarding state (created lazily)."""

    permission_classes = (permissions.IsAuthenticated,)

    def get(self, request):
        progress = _get_or_create_progress(request.user)
        return Response(OnboardingProgressSerializer(progress).data)


class OnboardingCompleteStepView(APIView):
    """POST {step} to mark a wizard step complete and advance."""

    permission_classes = (permissions.IsAuthenticated,)

    def post(self, request):
        serializer = CompleteStepSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        progress = _get_or_create_progress(request.user)
        progress = _advance(progress, serializer.validated_data["step"])
        record_audit(
            request.user,
            "onboarding.step_complete",
            "onboarding",
            str(progress.id),
            request=request,
            metadata={"step": serializer.validated_data["step"]},
        )
        return Response(OnboardingProgressSerializer(progress).data)


class OnboardingSkipView(APIView):
    """POST to skip the whole wizard (user can revisit from settings)."""

    permission_classes = (permissions.IsAuthenticated,)

    def post(self, request):
        progress = _get_or_create_progress(request.user)
        progress.skipped = True
        progress.completed_at = timezone.now()
        progress.save(update_fields=["skipped", "completed_at", "updated_at"])
        record_audit(
            request.user,
            "onboarding.skipped",
            "onboarding",
            str(progress.id),
            request=request,
        )
        return Response(
            OnboardingProgressSerializer(progress).data, status=status.HTTP_200_OK
        )


class OnboardingResetView(APIView):
    """POST to restart the wizard from step one (used from settings)."""

    permission_classes = (permissions.IsAuthenticated,)

    def post(self, request):
        progress = _get_or_create_progress(request.user)
        progress.current_step = ONBOARDING_STEPS[0]
        progress.completed_steps = []
        progress.skipped = False
        progress.completed_at = None
        progress.save(
            update_fields=[
                "current_step",
                "completed_steps",
                "skipped",
                "completed_at",
                "updated_at",
            ]
        )
        return Response(OnboardingProgressSerializer(progress).data)
