"""Pytest configuration: in-memory sqlite, throwaway secrets, Django setup."""
import os

os.environ.setdefault("TESTING", "true")
os.environ.setdefault("SECRET_KEY", "test-secret-key-0123456789abcdef-not-for-production")
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings")

try:
    from cryptography.fernet import Fernet

    os.environ.setdefault("FERNET_KEY", Fernet.generate_key().decode())
except Exception:  # pragma: no cover
    os.environ.setdefault("FERNET_KEY", "AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA=")

import django  # noqa: E402

django.setup()

import pytest  # noqa: E402
from django.contrib.auth import get_user_model  # noqa: E402
from rest_framework.authtoken.models import Token  # noqa: E402
from rest_framework.test import APIClient  # noqa: E402


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
        channel=channel, title="Test Project", format="LONG_FORM",
        target_duration_seconds=600, aspect_ratio="16:9", language="en",
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
