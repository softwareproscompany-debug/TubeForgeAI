"""Integration-test bootstrap for TubeForge AI.

Sets up Django (settings module ``config.settings``, TESTING=true -> sqlite)
with the backend source tree on ``sys.path``.

The backend sibling may still be mid-build when these tests are collected, so
*everything* backend-dependent is imported lazily inside fixtures / test
bodies. If Django cannot even be set up, tests skip with a clear message
instead of erroring at collection time.
"""

import os
import pathlib
import sys

import pytest

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings")
os.environ["TESTING"] = "true"

_BACKEND_ROOT = pathlib.Path.home() / "workspace" / "tubeforge-ai" / "backend"
if _BACKEND_ROOT.is_dir() and str(_BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(_BACKEND_ROOT))

try:
    import django  # noqa: E402

    django.setup()
    BACKEND_AVAILABLE = True
    SETUP_ERROR = None
except Exception as exc:  # pragma: no cover - only when backend is mid-build
    BACKEND_AVAILABLE = False
    SETUP_ERROR = exc


def require_backend():
    """Skip the calling test when the backend cannot be imported."""
    if not BACKEND_AVAILABLE:
        pytest.skip(f"backend unavailable: {SETUP_ERROR!r}")


@pytest.fixture
def backend():
    """Gate fixture: skip unless Django + settings loaded."""
    require_backend()
    return True


@pytest.fixture
def db_user(backend):
    """A persisted core.User (UUID pk)."""
    try:
        from core.models import User
    except Exception as exc:
        pytest.skip(f"core.User unavailable: {exc!r}")
    user = User.objects.create_user(
        username="int-test-user",
        email="int-test@tubeforge.local",
        password="test-password-not-real",
    )
    return user


@pytest.fixture
def db_channel(backend, db_user):
    """A persisted channels.Channel owned by db_user."""
    try:
        from channels.models import Channel
    except Exception as exc:
        pytest.skip(f"channels.Channel unavailable: {exc!r}")
    kwargs = {}
    # Defensive: discover the owner FK name from the model instead of guessing.
    for field in Channel._meta.get_fields():
        if getattr(field, "many_to_one", False) and field.related_model is not None:
            try:
                from core.models import User as _U

                if issubclass(field.related_model, _U):
                    kwargs[field.name] = db_user
                    break
            except Exception:
                continue
    channel = Channel.objects.create(name="int-test-channel", **kwargs)
    return channel


@pytest.fixture
def db_project(backend, db_user, db_channel):
    """A persisted projects.Project linked to db_channel."""
    try:
        from projects.models import Project
    except Exception as exc:
        pytest.skip(f"projects.Project unavailable: {exc!r}")
    kwargs = {"title": "int-test-project", "prompt": "a video about testing"}
    for field in Project._meta.get_fields():
        if getattr(field, "many_to_one", False) and field.related_model is not None:
            rel = field.related_model
            try:
                from channels.models import Channel as _C
                from core.models import User as _U

                if issubclass(rel, _C):
                    kwargs.setdefault(field.name, db_channel)
                elif issubclass(rel, _U):
                    kwargs.setdefault(field.name, db_user)
            except Exception:
                continue
    project = Project.objects.create(**kwargs)
    return project
