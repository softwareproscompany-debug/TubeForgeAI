"""Workflow state machine: exact state list, legal transitions, guarded transitions.

Terminal states: PUBLISHED, FAILED, CANCELED. FAILED additionally allows a
retry edge back to QUEUED. Late worker callbacks for terminal runs are ignored
(see apply_worker_event).
"""
from django.utils import timezone

WORKFLOW_STATES = [
    "DRAFT",
    "PLANNING",
    "AWAITING_APPROVAL",
    "QUEUED",
    "RESEARCHING",
    "SCRIPTING",
    "STORYBOARDING",
    "GENERATING_ASSETS",
    "GENERATING_NARRATION",
    "ASSEMBLING",
    "RENDERING",
    "VALIDATING",
    "FINAL_REVIEW",
    "READY_TO_PUBLISH",
    "UPLOADING",
    "SCHEDULED",
    "PUBLISHED",
    "FAILED",
    "CANCELED",
    "PAUSED",
    "BLOCKED_ON_RESOURCES",
    "BLOCKED_ON_APPROVAL",
]

TERMINAL_STATES = frozenset({"PUBLISHED", "FAILED", "CANCELED"})

_NON_TERMINAL = [s for s in WORKFLOW_STATES if s not in TERMINAL_STATES]
_PARKED = {"PAUSED", "CANCELED", "FAILED", "BLOCKED_ON_RESOURCES", "BLOCKED_ON_APPROVAL"}


def _build_transitions():
    legal = {state: set() for state in _NON_TERMINAL}
    chain = WORKFLOW_STATES[: WORKFLOW_STATES.index("PUBLISHED") + 1]
    for i, state in enumerate(chain):
        if i + 1 < len(chain):
            legal[state].add(chain[i + 1])
    # AWAITING_APPROVAL -> QUEUED is already the chain edge; kept explicit for clarity.
    legal["AWAITING_APPROVAL"].add("QUEUED")
    # Any non-terminal state can park / fail / cancel.
    for state in _NON_TERMINAL:
        legal[state] |= _PARKED
    # Recovery edges.
    legal["PAUSED"].add("QUEUED")
    legal["BLOCKED_ON_RESOURCES"].add("QUEUED")
    legal["BLOCKED_ON_APPROVAL"].add("AWAITING_APPROVAL")
    # Retry edge out of the (otherwise terminal) FAILED state.
    legal["FAILED"] = {"QUEUED"}
    # SCHEDULED may publish or cancel.
    legal["SCHEDULED"] |= {"PUBLISHED", "CANCELED"}
    for terminal in ("PUBLISHED", "CANCELED"):
        legal[terminal] = set()
    return {k: frozenset(v) for k, v in legal.items()}


LEGAL_TRANSITIONS = _build_transitions()


class InvalidTransition(Exception):
    def __init__(self, from_state, to_state):
        super().__init__(f"Invalid workflow transition: {from_state} -> {to_state}")
        self.from_state = from_state
        self.to_state = to_state


def validate_transition(from_state, to_state):
    if from_state not in WORKFLOW_STATES:
        raise InvalidTransition(from_state, to_state)
    if to_state not in LEGAL_TRANSITIONS.get(from_state, ()):
        raise InvalidTransition(from_state, to_state)
    return True


def transition(run, to_state, actor=None, request=None, event_type="state_changed"):
    """Validate, persist, and record a state transition on a WorkflowRun."""
    from core.utils import record_audit

    from .models import WorkflowEvent

    from_state = run.status
    validate_transition(from_state, to_state)
    run.status = to_state
    run.current_stage = to_state
    now = timezone.now()
    if run.started_at is None and to_state not in ("DRAFT", "PLANNING"):
        run.started_at = now
    if to_state in TERMINAL_STATES:
        run.completed_at = now
    run.save()
    WorkflowEvent.objects.create(
        run=run, event_type=event_type, stage=to_state,
        payload={"from": from_state, "to": to_state},
    )
    record_audit(
        actor, "workflow.transition", "workflow_run", str(run.id),
        request=request, metadata={"from": from_state, "to": to_state},
    )
    return run


def apply_worker_event(run, to_state, event_type="worker_callback", payload=None, actor=None):
    """Apply a late worker callback. Terminal runs ignore it (returns False)."""
    from .models import WorkflowEvent

    run.refresh_from_db()
    if run.status in TERMINAL_STATES:
        WorkflowEvent.objects.create(
            run=run, event_type="late_callback_ignored", stage=run.status,
            payload={"attempted_to": to_state, "payload": payload or {}},
        )
        return False
    transition(run, to_state, actor=actor, event_type=event_type)
    return True
