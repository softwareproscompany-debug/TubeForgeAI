"""Pytest configuration: in-memory sqlite, throwaway secrets, Django setup."""

import os


def _ensure_test_env(name, default):
    """Fill a test-safe default when the env var is missing *or empty*.

    settings' ``env()`` treats "" as missing and raises, while
    ``setdefault()`` would keep a stale empty value (the exact shape of the
    CI "Required environment variable ... is not set" failure). Explicitly
    set non-empty values are always respected.
    """
    if not os.environ.get(name):
        os.environ[name] = default


_ensure_test_env("TESTING", "true")
_ensure_test_env("SECRET_KEY", "test-secret-key-0123456789abcdef-not-for-production")
_ensure_test_env("DJANGO_SETTINGS_MODULE", "config.settings")

try:
    from cryptography.fernet import Fernet

    _ensure_test_env("FERNET_KEY", Fernet.generate_key().decode())
except Exception:  # noqa: BLE001 - test setup fallback; pragma: no cover
    _ensure_test_env("FERNET_KEY", "AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA=")

import django

django.setup()

import pytest
from django.contrib.auth import get_user_model
from rest_framework.authtoken.models import Token
from rest_framework.test import APIClient


@pytest.fixture
def user(db):
    return get_user_model().objects.create_user(
        username="owner", email="owner@example.com", password="pass12345"
    )


@pytest.fixture
def user2(db):
    return get_user_model().objects.create_user(
        username="intruder", email="intruder@example.com", password="pass12345"
    )


@pytest.fixture
def channel(db, user):
    from channels.models import Channel

    return Channel.objects.create(
        owner=user, youtube_channel_id="UCtestchannel1", title="Test Channel"
    )


@pytest.fixture
def project(db, channel):
    from projects.models import Project

    return Project.objects.create(
        channel=channel,
        title="Test Project",
        format="LONG_FORM",
        target_duration_seconds=600,
        aspect_ratio="16:9",
        language="en",
    )


@pytest.fixture
def auth_client(db, user):
    token = Token.objects.create(user=user)
    client = APIClient()
    client.credentials(HTTP_AUTHORIZATION="Token " + token.key)
    return client


@pytest.fixture
def auth_client2(db, user2):
    token = Token.objects.create(user=user2)
    client = APIClient()
    client.credentials(HTTP_AUTHORIZATION="Token " + token.key)
    return client
