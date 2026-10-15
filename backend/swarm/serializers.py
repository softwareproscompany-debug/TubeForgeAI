"""Swarm serializers."""

from rest_framework import serializers

from .models import Agent, AgentMessage, SwarmRun
from .orchestrator import SwarmOrchestrator


class AgentSerializer(serializers.ModelSerializer):
    class Meta:
        model = Agent
        fields = ("id", "name", "role", "model", "status")
        read_only_fields = fields


class AgentMessageSerializer(serializers.ModelSerializer):
    from_agent = AgentSerializer(read_only=True)
    to_agent = AgentSerializer(read_only=True)

    class Meta:
        model = AgentMessage
        fields = (
            "id",
            "from_agent",
            "to_agent",
            "message_type",
            "content",
            "created_at",
        )
        read_only_fields = fields


class SwarmRunSerializer(serializers.ModelSerializer):
    project_title = serializers.CharField(source="project.title", read_only=True)
    agents = serializers.SerializerMethodField()

    class Meta:
        model = SwarmRun
        fields = (
            "id",
            "project",
            "project_title",
            "topic",
            "status",
            "current_stage",
            "error",
            "started_at",
            "completed_at",
            "agents",
        )
        read_only_fields = fields

    def get_agents(self, run):
        """Per-run agent states derived from the message log.

        Agent.status is global and fleeting (synchronous runs); the message
        log is what tells us who has produced what in *this* run.
        """
        messages = run.messages.select_related("from_agent", "to_agent")
        produced = set()
        reviewed = False
        for message in messages:
            if message.message_type == "result" and message.from_agent:
                produced.add(message.from_agent.role)
            if message.message_type == "answer" and message.from_agent:
                reviewed = True
        rows = []
        for role in ("researcher", "writer", "editor", "publisher", "critic"):
            if role == "critic":
                state = (
                    "done"
                    if reviewed
                    else ("working" if run.status == "running" else "idle")
                )
            elif role in produced:
                state = "done"
            elif (
                run.status == "running"
                and SwarmOrchestrator.STAGE_AGENTS.get(run.current_stage) == role
            ):
                state = "working"
            else:
                state = "idle"
            rows.append({"role": role, "state": state})
        return rows


class SwarmRunCreateSerializer(serializers.Serializer):
    project_id = serializers.UUIDField()
    topic = serializers.CharField(min_length=3, max_length=2000)
