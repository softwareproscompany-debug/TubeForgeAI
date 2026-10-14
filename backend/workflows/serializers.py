"""Workflow serializers."""
from rest_framework import serializers

from .models import Approval, WorkflowEvent, WorkflowRun


class WorkflowRunSerializer(serializers.ModelSerializer):
    class Meta:
        model = WorkflowRun
        fields = [
            "id", "project", "workflow_type", "temporal_workflow_id", "status",
            "current_stage", "input_snapshot", "output_summary",
            "started_at", "completed_at", "created_at",
        ]
        read_only_fields = ["id", "temporal_workflow_id", "status", "current_stage",
                            "output_summary", "started_at", "completed_at", "created_at"]


class WorkflowRunCreateSerializer(serializers.Serializer):
    workflow_type = serializers.ChoiceField(
        choices=["VIDEO_PRODUCTION", "SHORTS_BATCH", "PUBLISH_ONLY"],
        default="VIDEO_PRODUCTION",
    )
    input = serializers.DictField(required=False, default=dict)


class WorkflowEventSerializer(serializers.ModelSerializer):
    class Meta:
        model = WorkflowEvent
        fields = ["id", "event_type", "stage", "payload", "occurred_at"]
        read_only_fields = fields


class ApprovalSerializer(serializers.ModelSerializer):
    requested_by = serializers.StringRelatedField(read_only=True)
    decided_by = serializers.StringRelatedField(read_only=True)

    class Meta:
        model = Approval
        fields = [
            "id", "project", "workflow_run", "approval_type", "status",
            "requested_by", "decided_by", "decision_reason",
            "requested_at", "decided_at",
        ]
        read_only_fields = ["id", "status", "requested_by", "decided_by",
                            "requested_at", "decided_at"]


class ApprovalDecideSerializer(serializers.Serializer):
    decision = serializers.ChoiceField(choices=["approved", "rejected"])
    reason = serializers.CharField(required=False, allow_blank=True, default="")
