"""Regression tests for the backend audit fixes (Oct 14).

Covers: admin-only system settings, input validation (400 not 500), FK
reassignment guards, idempotency scoping, atomic approval decide, and
budget scope authorization.
"""

import pytest

from core.models import SystemSetting
from projects.models import Project


@pytest.mark.django_db
def test_system_settings_list_requires_admin(auth_client, user):
    SystemSetting.objects.create(key="k", value={"v": 1})
    response = auth_client.get("/api/v1/system-settings")
    assert response.status_code == 403


@pytest.mark.django_db
def test_system_settings_list_allows_admin(auth_client, user):
    user.is_staff = True
    user.save()
    SystemSetting.objects.create(key="k", value={"v": 1})
    response = auth_client.get("/api/v1/system-settings")
    assert response.status_code == 200


@pytest.mark.django_db
def test_generation_create_rejects_non_dict_requirements(auth_client, project):
    response = auth_client.post(
        "/api/v1/generation-jobs",
        {"task_type": "image", "project_id": str(project.id), "requirements": "fast"},
        format="json",
    )
    assert response.status_code == 400


@pytest.mark.django_db
def test_generation_create_rejects_malformed_project_uuid(auth_client):
    response = auth_client.post(
        "/api/v1/generation-jobs",
        {"task_type": "image", "project_id": "not-a-uuid"},
        format="json",
    )
    assert response.status_code == 400


@pytest.mark.django_db
def test_generation_create_idempotency_key_scoped_to_owner(
    auth_client, auth_client2, project
):
    # user2's key must not leak user1's job, and vice versa.
    response = auth_client2.post(
        "/api/v1/generation-jobs",
        {
            "task_type": "image",
            "project_id": str(project.id),  # owned by user1 -> 404 for user2
            "idempotency_key": "scoped-key-1",
        },
        format="json",
    )
    assert response.status_code == 404


@pytest.mark.django_db
def test_scene_generate_maps_no_provider_to_400(auth_client, project):
    from projects.models import Scene

    scene = Scene.objects.create(project=project, position=1, scene_type="FACELESS")
    response = auth_client.post(
        f"/api/v1/projects/{project.id}/scenes/{scene.id}/generate", {}, format="json"
    )
    assert response.status_code == 400  # no capable provider -> ValidationError
    scene.refresh_from_db()
    assert scene.status == "PENDING"  # not left in a lying GENERATING state


@pytest.mark.django_db
def test_project_channel_not_reassignable(auth_client, auth_client2, project, user2):
    from channels.models import Channel

    other = Channel.objects.create(owner=user2, title="Other")
    response = auth_client.patch(
        f"/api/v1/projects/{project.id}", {"channel": str(other.id)}, format="json"
    )
    assert response.status_code == 200
    project.refresh_from_db()
    assert project.channel.owner_id != user2.id


@pytest.mark.django_db
def test_publication_project_not_reassignable(auth_client, project):
    from publishing.models import PublicationJob

    other_project = Project.objects.create(
        channel=project.channel, title="Other project"
    )
    pub = PublicationJob.objects.create(
        project=project,
        channel=project.channel,
        title="t",
        idempotency_key="pub-key-1",
    )
    response = auth_client.patch(
        f"/api/v1/publications/{pub.id}",
        {"project": str(other_project.id), "title": "changed"},
        format="json",
    )
    assert response.status_code == 200
    pub.refresh_from_db()
    assert pub.project_id == project.id
    assert pub.title == "changed"


@pytest.mark.django_db
def test_notification_patch_only_marks_read(auth_client, user):
    from core.models import Notification

    note = Notification.objects.create(
        user=user, type="info", title="Original", body="Body"
    )
    response = auth_client.patch(
        f"/api/v1/notifications/{note.id}",
        {"title": "Hacked", "body": "Hacked"},
        format="json",
    )
    assert response.status_code == 200
    note.refresh_from_db()
    assert note.title == "Original"
    assert note.body == "Body"
    assert note.read_at is not None


@pytest.mark.django_db
def test_budget_cannot_target_another_users_channel(
    auth_client, auth_client2, user2, channel
):
    from channels.models import Channel as ChannelModel
    from providers.models import Budget

    other = ChannelModel.objects.create(owner=user2, title="Victim channel")
    response = auth_client.post(
        "/api/v1/budgets",
        {
            "scope_type": "channel",
            "scope_id": str(other.id),
            "limits": {"max_api_spend_daily": "0"},
        },
        format="json",
    )
    assert response.status_code == 404
    assert not Budget.objects.filter(scope_id=other.id).exists()


@pytest.mark.django_db
def test_budget_global_requires_staff(auth_client):
    response = auth_client.post(
        "/api/v1/budgets",
        {"scope_type": "global", "scope_id": None, "limits": {}},
        format="json",
    )
    assert response.status_code == 400


@pytest.mark.django_db
def test_approval_decide_is_idempotent(auth_client, project, user):
    from workflows.models import Approval

    approval = Approval.objects.create(
        project=project, approval_type="SCRIPT", status="PENDING", requested_by=user
    )
    url = f"/api/v1/approvals/{approval.id}/decide"
    first = auth_client.post(url, {"decision": "approved"}, format="json")
    assert first.status_code == 200
    assert first.json()["status"] == "APPROVED"
    second = auth_client.post(url, {"decision": "rejected"}, format="json")
    assert second.status_code == 400
    approval.refresh_from_db()
    assert approval.status == "APPROVED"  # first decision wins


@pytest.mark.django_db
def test_upload_url_rejects_bad_size(auth_client):
    response = auth_client.post(
        "/api/v1/assets/upload-url",
        {"filename": "x.mp4", "mime_type": "video/mp4", "size_bytes": "huge"},
        format="json",
    )
    assert response.status_code == 400


@pytest.mark.django_db
def test_upload_url_rejects_bad_project_uuid(auth_client):
    response = auth_client.post(
        "/api/v1/assets/upload-url",
        {
            "filename": "x.mp4",
            "mime_type": "video/mp4",
            "size_bytes": 100,
            "project_id": "nope",
        },
        format="json",
    )
    assert response.status_code == 400


@pytest.mark.django_db
def test_generate_plan_rejects_bad_target(auth_client, project):
    response = auth_client.post(
        f"/api/v1/projects/{project.id}/generate-plan",
        {"target_duration_seconds": "forever"},
        format="json",
    )
    assert response.status_code == 400


@pytest.mark.django_db
def test_channel_connect_validates_title_length(auth_client):
    response = auth_client.post(
        "/api/v1/channels/connect", {"title": "x" * 500}, format="json"
    )
    assert response.status_code == 400
