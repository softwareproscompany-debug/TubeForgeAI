"""Tier-limit enforcement helpers.

Usage::

    from billing.limits import check_limit, require_tier

    # in a view / perform_create:
    check_limit(request.user, "projects")   # raises 402 when over limit

    @require_tier("pro")
    def my_view(request): ...

``check_limit`` is deliberately narrow today: it knows how to count the
"projects" resource. To enforce a new resource (e.g. "storage_gb"),
add a ``_count_<resource>(user)`` function and register it in ``_COUNTERS``.
"""

from functools import wraps

from rest_framework.exceptions import APIException

from core.utils import TubeForgeAPIException

from .models import SubscriptionTier


class TierLimitExceededAPI(TubeForgeAPIException):
    status_code = 402
    default_code = "TIER_LIMIT_EXCEEDED"
    default_detail = "Your plan's limit for this resource has been reached."


class TierRequiredAPI(APIException):
    status_code = 403
    default_code = "TIER_REQUIRED"
    default_detail = "This feature requires a higher subscription tier."


def _count_projects(user) -> int:
    from projects.models import Project

    return Project.objects.filter(channel__owner=user).count()


# resource name -> (tier attribute holding the limit, counter callable)
_COUNTERS = {
    "projects": ("max_projects", _count_projects),
}


def get_user_tier(user):
    """Return the user's SubscriptionTier, or None when absent.

    Queries fresh each call (rather than using the cached reverse
    relation) so a tier change — e.g. applied by the Stripe webhook —
    takes effect immediately within the same process.
    """
    if user is None or getattr(user, "is_anonymous", False):
        return None
    return SubscriptionTier.objects.filter(subscriptions__user=user).first()


def count_projects(user) -> int:
    """Number of projects owned by ``user`` (all channels)."""
    return _count_projects(user)


def check_limit(user, resource: str) -> int:
    """Raise TierLimitExceededAPI (402) when the user's tier limit for
    ``resource`` is reached. Returns the current usage count otherwise."""
    if resource not in _COUNTERS:
        raise ValueError(f"Unknown billable resource: {resource!r}")
    limit_attr, counter = _COUNTERS[resource]
    tier = get_user_tier(user)
    limit = getattr(tier, limit_attr, 0) if tier else 0
    used = counter(user)
    if used >= limit:
        tier_name = tier.name if tier else "free"
        raise TierLimitExceededAPI(
            f"Your '{tier_name}' plan allows {limit} {resource} "
            f"(currently using {used}). Upgrade your plan to add more."
        )
    return used


def require_tier(min_tier: str):
    """View decorator enforcing a minimum tier ("free" < "pro" < "enterprise")."""
    from .tier_data import TIER_ORDER

    def decorator(view_func):
        @wraps(view_func)
        def wrapper(request, *args, **kwargs):
            tier = get_user_tier(request.user)
            tier_name = tier.name if tier else "free"
            if TIER_ORDER.index(tier_name) < TIER_ORDER.index(min_tier):
                raise TierRequiredAPI(
                    f"This feature requires the '{min_tier}' plan or higher. "
                    f"You are on '{tier_name}'."
                )
            return view_func(request, *args, **kwargs)

        return wrapper

    return decorator
