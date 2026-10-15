"""Onboarding URL routes."""

from django.urls import path

from .views import (
    OnboardingCompleteStepView,
    OnboardingProgressView,
    OnboardingResetView,
    OnboardingSkipView,
)

urlpatterns = [
    path(
        "onboarding/progress",
        OnboardingProgressView.as_view(),
        name="onboarding-progress",
    ),
    path(
        "onboarding/complete-step",
        OnboardingCompleteStepView.as_view(),
        name="onboarding-complete-step",
    ),
    path(
        "onboarding/skip",
        OnboardingSkipView.as_view(),
        name="onboarding-skip",
    ),
    path(
        "onboarding/reset",
        OnboardingResetView.as_view(),
        name="onboarding-reset",
    ),
]
