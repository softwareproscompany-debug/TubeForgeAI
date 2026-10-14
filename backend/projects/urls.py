"""Project URL routes."""
from django.urls import path
from workflows.views import ProjectWorkflowCreateView

from .views import (
    AssetViewSet,
    GeneratePlanView,
    ProjectViewSet,
    RenderJobViewSet,
    SceneViewSet,
    ScriptViewSet,
    TimelineView,
    UploadUrlView,
)

project_list = ProjectViewSet.as_view({"get": "list", "post": "create"})
project_detail = ProjectViewSet.as_view(
    {"get": "retrieve", "patch": "partial_update", "put": "update", "delete": "destroy"}
)
script_list = ScriptViewSet.as_view({"get": "list", "post": "create"})
script_detail = ScriptViewSet.as_view({"get": "retrieve", "patch": "partial_update", "delete": "destroy"})
script_approve = ScriptViewSet.as_view({"post": "approve"})
scene_list = SceneViewSet.as_view({"get": "list", "post": "create"})
scene_detail = SceneViewSet.as_view({"get": "retrieve", "patch": "partial_update", "delete": "destroy"})
scene_generate = SceneViewSet.as_view({"post": "generate"})
scene_regenerate = SceneViewSet.as_view({"post": "regenerate"})
render_list = RenderJobViewSet.as_view({"get": "list", "post": "create"})
render_detail = RenderJobViewSet.as_view({"get": "retrieve"})
render_cancel = RenderJobViewSet.as_view({"post": "cancel"})
asset_list = AssetViewSet.as_view({"get": "list"})
asset_detail = AssetViewSet.as_view({"get": "retrieve"})

urlpatterns = [
    path("projects", project_list, name="project-list"),
    path("projects/<uuid:pk>", project_detail, name="project-detail"),
    path("projects/<uuid:pk>/generate-plan", GeneratePlanView.as_view(), name="project-generate-plan"),
    path("projects/<uuid:pk>/workflows", ProjectWorkflowCreateView.as_view(), name="project-workflows"),
    path("projects/<uuid:project_pk>/scripts", script_list, name="script-list"),
    path("projects/<uuid:project_pk>/scripts/<uuid:pk>", script_detail, name="script-detail"),
    path("projects/<uuid:project_pk>/scripts/<uuid:pk>/approve", script_approve, name="script-approve"),
    path("projects/<uuid:project_pk>/scenes", scene_list, name="scene-list"),
    path("projects/<uuid:project_pk>/scenes/<uuid:pk>", scene_detail, name="scene-detail"),
    path("projects/<uuid:project_pk>/scenes/<uuid:pk>/generate", scene_generate, name="scene-generate"),
    path("projects/<uuid:project_pk>/scenes/<uuid:pk>/regenerate", scene_regenerate, name="scene-regenerate"),
    path("projects/<uuid:project_pk>/timeline", TimelineView.as_view(), name="project-timeline"),
    path("projects/<uuid:project_pk>/renders", render_list, name="render-list"),
    path("projects/<uuid:project_pk>/renders/<uuid:pk>", render_detail, name="render-detail"),
    path("projects/<uuid:project_pk>/renders/<uuid:pk>/cancel", render_cancel, name="render-cancel"),
    path("projects/<uuid:project_pk>/assets", asset_list, name="project-assets"),
    path("assets", asset_list, name="asset-list"),
    path("assets/<uuid:pk>", asset_detail, name="asset-detail"),
    path("assets/upload-url", UploadUrlView.as_view(), name="asset-upload-url"),
]
