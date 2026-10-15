"""Agent swarm models: agents, runs, and the persisted inter-agent conversation.

The swarm complements ``workflows`` (the deterministic scene-production
pipeline): where workflows execute generation jobs against provider GPUs,
the swarm is the conversational layer — five specialist agents that plan a
video together by exchanging messages, all of which are persisted here so
the whole deliberation is auditable.
"""

from django.db import models

from core.models import UUIDModel
from projects.models import Project


class Agent(UUIDModel):
    ROLE_CHOICES = (
        ("researcher", "Researcher"),
        ("writer", "Writer"),
        ("editor", "Editor"),
        ("publisher", "Publisher"),
        ("critic", "Critic"),
    )
    STATUS_CHOICES = (
        ("idle", "Idle"),
        ("working", "Working"),
    )

    name = models.CharField(max_length=100)
    role = models.CharField(max_length=32, choices=ROLE_CHOICES, unique=True)
    system_prompt = models.TextField()
    # "auto" = route through the provider gateway's selected text provider.
    model = models.CharField(max_length=200, default="auto")
    status = models.CharField(max_length=16, choices=STATUS_CHOICES, default="idle")
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ("name",)

    def __str__(self):
        return f"{self.name} ({self.role})"


class SwarmRun(UUIDModel):
    STATUS_CHOICES = (
        ("running", "Running"),
        ("completed", "Completed"),
        ("failed", "Failed"),
        ("cancelled", "Cancelled"),
    )

    project = models.ForeignKey(
        Project, on_delete=models.CASCADE, related_name="swarm_runs"
    )
    topic = models.TextField()
    status = models.CharField(max_length=16, choices=STATUS_CHOICES, default="running")
    current_stage = models.CharField(max_length=32, default="research")
    error = models.TextField(blank=True, default="")
    started_at = models.DateTimeField(auto_now_add=True)
    completed_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ("-started_at",)

    def __str__(self):
        return f"SwarmRun {self.id} ({self.status})"

    @property
    def channel(self):
        """Lets ``OwnsChannel`` guard swarm runs via the project's channel."""
        return self.project.channel


class AgentMessage(UUIDModel):
    TYPE_CHOICES = (
        ("task", "Task"),
        ("result", "Result"),
        ("question", "Question"),
        ("answer", "Answer"),
        ("revision_request", "Revision request"),
    )

    swarm_run = models.ForeignKey(
        SwarmRun, on_delete=models.CASCADE, related_name="messages"
    )
    # null from_agent = system; null to_agent = broadcast to all agents.
    from_agent = models.ForeignKey(
        Agent, null=True, blank=True, on_delete=models.SET_NULL, related_name="+"
    )
    to_agent = models.ForeignKey(
        Agent, null=True, blank=True, on_delete=models.SET_NULL, related_name="+"
    )
    message_type = models.CharField(max_length=32, choices=TYPE_CHOICES)
    content = models.JSONField(default=dict)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ("created_at",)

    def __str__(self):
        src = self.from_agent.name if self.from_agent else "system"
        dst = self.to_agent.name if self.to_agent else "all"
        return f"{src} -> {dst} [{self.message_type}]"
