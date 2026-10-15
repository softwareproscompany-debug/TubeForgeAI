"""Onboarding serializers."""

from rest_framework import serializers

from .models import ONBOARDING_STEPS, OnboardingProgress


class OnboardingProgressSerializer(serializers.ModelSerializer):
    is_complete = serializers.ReadOnlyField()

    class Meta:
        model = OnboardingProgress
        fields = (
            "id",
            "current_step",
            "completed_steps",
            "skipped",
            "is_complete",
            "started_at",
            "completed_at",
            "updated_at",
        )
        read_only_fields = fields


class CompleteStepSerializer(serializers.Serializer):
    step = serializers.ChoiceField(choices=[(s, s) for s in ONBOARDING_STEPS])
