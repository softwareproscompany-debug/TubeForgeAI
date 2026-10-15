"""Onboarding progress tracking.

The wizard has four steps, completed in order but skippable:
  1. "welcome"       - intro to TubeForge
  2. "youtube"       - connect YouTube channel via OAuth
  3. "channel_setup" - niche, upload schedule, branding
  4. "first_project" - guided first project creation

``completed_steps`` is a JSON list of step names in completion order.
``current_step`` is the step the wizard should show next.
"""

from django.db import models

from core.models import User, UUIDModel

ONBOARDING_STEPS = ("welcome", "youtube", "channel_setup", "first_project")


class OnboardingProgress(UUIDModel):
    user = models.OneToOneField(
        User, on_delete=models.CASCADE, related_name="onboarding_progress"
    )
    current_step = models.CharField(max_length=32, default="welcome")
    completed_steps = models.JSONField(default=list)
    skipped = models.BooleanField(default=False)
    started_at = models.DateTimeField(auto_now_add=True)
    completed_at = models.DateTimeField(null=True, blank=True, default=None)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ("-started_at",)

    def __str__(self):
        return f"onboarding({self.user_id}, step={self.current_step})"

    @property
    def is_complete(self):
        return self.completed_at is not None
