"""Shared utilities: pagination, error envelope, correlation IDs, permissions, audit."""

import re
import uuid

from rest_framework import pagination, permissions
from rest_framework.exceptions import APIException, ValidationError
from rest_framework.response import Response
from rest_framework.throttling import ScopedRateThrottle
from rest_framework.views import exception_handler


# ---------------------------------------------------------------------------
# Pagination
# ---------------------------------------------------------------------------
class TubeForgePagination(pagination.PageNumberPagination):
    page_size = 25
    page_size_query_param = "page_size"
    max_page_size = 200


# ---------------------------------------------------------------------------
# Structured API errors
# ---------------------------------------------------------------------------
class TubeForgeAPIException(APIException):
    """Base for domain exceptions that must keep their spec error code."""


class UpstreamError(TubeForgeAPIException):
    status_code = 502
    default_code = "UPSTREAM_ERROR"
    default_detail = "An upstream provider request failed."


class BudgetExceededAPI(TubeForgeAPIException):
    status_code = 402
    default_code = "BUDGET_EXCEEDED"
    default_detail = "A budget limit was exceeded."


class PaidFallbackApprovalRequiredAPI(TubeForgeAPIException):
    status_code = 409
    default_code = "PAID_FALLBACK_APPROVAL_REQUIRED"
    default_detail = "Routing to a paid provider requires explicit approval."


class InvalidTransitionAPI(TubeForgeAPIException):
    status_code = 400
    default_code = "INVALID_TRANSITION"
    default_detail = "The requested state transition is not allowed."


def _error_code(exc, status_code):
    # Domain exceptions keep their explicit spec codes; everything else maps by status.
    if isinstance(exc, TubeForgeAPIException):
        return exc.default_code
    return {
        400: "validation_error",
        401: "unauthorized",
        403: "permission_denied",
        404: "not_found",
        405: "method_not_allowed",
        409: "conflict",
        429: "throttled",
    }.get(status_code, "error")


def _error_message(data):
    if isinstance(data, dict):
        detail = data.get("detail", data)
        return str(detail)
    if isinstance(data, list):
        return "; ".join(str(x) for x in data)
    return str(data)


def tubeforge_exception_handler(exc, context):
    """Render every DRF error as {"error": {code, message, retryable, correlation_id}}."""
    response = exception_handler(exc, context)
    request = context.get("request") if context else None
    correlation_id = getattr(request, "correlation_id", None) or uuid.uuid4().hex
    if response is not None:
        response.data = {
            "error": {
                "code": _error_code(exc, response.status_code),
                "message": _error_message(response.data),
                "retryable": response.status_code
                in (408, 409, 429, 500, 502, 503, 504),
                "correlation_id": correlation_id,
            }
        }
        response["X-Correlation-ID"] = correlation_id
        return response
    return Response(
        {
            "error": {
                "code": "internal_error",
                "message": "An unexpected error occurred.",
                "retryable": True,
                "correlation_id": correlation_id,
            }
        },
        status=500,
        headers={"X-Correlation-ID": correlation_id},
    )


# ---------------------------------------------------------------------------
# Correlation IDs
# ---------------------------------------------------------------------------
class CorrelationIdMiddleware:
    """Reads X-Correlation-ID or generates one; attaches to request and response."""

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        correlation_id = request.META.get("HTTP_X_CORRELATION_ID") or uuid.uuid4().hex
        request.correlation_id = correlation_id
        response = self.get_response(request)
        response["X-Correlation-ID"] = correlation_id
        return response


# ---------------------------------------------------------------------------
# Throttling
# ---------------------------------------------------------------------------
class LoginRateThrottle(ScopedRateThrottle):
    """Strict scoped throttle for the login endpoint (scope 'login', 10/minute)."""

    scope = "login"


# ---------------------------------------------------------------------------
# Permissions
# ---------------------------------------------------------------------------
class IsOwner(permissions.BasePermission):
    """Object-level permission: ``obj.owner`` must be the requesting user."""

    def has_object_permission(self, request, view, obj):
        return getattr(obj, "owner", None) == request.user


class OwnsChannel(permissions.BasePermission):
    """Object-level permission: ``obj.channel.owner`` must be the requesting user."""

    def has_object_permission(self, request, view, obj):
        channel = getattr(obj, "channel", None)
        return channel is not None and channel.owner_id == request.user.id


# ---------------------------------------------------------------------------
# Audit
# ---------------------------------------------------------------------------
_SECRET_KEY_RE = re.compile(
    r"password|passwd|pwd|token|secret|api[_-]?key|private[_-]?key|credential",
    re.IGNORECASE,
)
REDACTED = "***REDACTED***"


def scrub_secrets(value):
    """Recursively replace values of secret-looking keys with ***REDACTED***."""
    if isinstance(value, dict):
        return {
            k: (REDACTED if _SECRET_KEY_RE.search(str(k)) else scrub_secrets(v))
            for k, v in value.items()
        }
    if isinstance(value, (list, tuple)):
        return [scrub_secrets(v) for v in value]
    return value


def record_audit(
    actor,
    action,
    resource_type,
    resource_id,
    outcome="success",
    request=None,
    metadata=None,
):
    """Write an AuditEvent. ``metadata`` is scrubbed — secrets are never logged."""
    from .models import AuditEvent

    correlation_id = getattr(request, "correlation_id", None) or uuid.uuid4().hex
    AuditEvent.objects.create(
        actor=actor if getattr(actor, "is_authenticated", False) else None,
        action=action,
        resource_type=resource_type,
        resource_id=str(resource_id),
        outcome=outcome,
        correlation_id=correlation_id,
        metadata=scrub_secrets(metadata or {}),
    )


# ---------------------------------------------------------------------------
# Serializer helpers
# ---------------------------------------------------------------------------
def parse_uuid(value, field="id"):
    """Parse a UUID from request input.

    ``get_object_or_404(Model, pk=bad_value)`` raises ``ValueError`` (HTTP 500)
    on malformed UUIDs; this raises DRF ``ValidationError`` (HTTP 400) instead.
    """
    try:
        return uuid.UUID(str(value))
    except (ValueError, AttributeError, TypeError):
        raise ValidationError({field: "Must be a valid UUID."})


class SecretRedactionMixin:
    """Mask fields listed in ``Meta.secret_fields`` on output.

    Those fields remain write-capable on input; responses never carry values.
    """

    def to_representation(self, instance):
        data = super().to_representation(instance)
        for field in getattr(self.Meta, "secret_fields", ()):
            if field in data:
                data[field] = REDACTED
        return data
