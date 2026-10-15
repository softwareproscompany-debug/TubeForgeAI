"""Canonical subscription-tier seed data.

Pure-Python constants (no Django imports) so both the seeding migration and
the post_save signal can use the exact same values without import cycles.
"""

TIER_SEEDS = (
    {
        "name": "free",
        "display_name": "Free",
        "price_monthly_cents": 0,
        "stripe_price_id": "",
        "max_projects": 3,
        "max_storage_gb": 5,
        "max_api_calls_month": 1000,
        "features": [
            "3 projects",
            "5 GB media storage",
            "1,000 AI API calls / month",
            "Community support",
        ],
    },
    {
        "name": "pro",
        "display_name": "Pro",
        "price_monthly_cents": 2900,
        "stripe_price_id": "",
        "max_projects": 50,
        "max_storage_gb": 500,
        "max_api_calls_month": 100000,
        "features": [
            "50 projects",
            "500 GB media storage",
            "100,000 AI API calls / month",
            "Priority render queue",
            "Email support",
        ],
    },
    {
        "name": "enterprise",
        "display_name": "Enterprise",
        "price_monthly_cents": 29900,
        "stripe_price_id": "",
        "max_projects": 1000000,
        "max_storage_gb": 10000,
        "max_api_calls_month": 10000000,
        "features": [
            "Unlimited projects",
            "10 TB media storage",
            "10M AI API calls / month",
            "Dedicated render workers",
            "SSO + audit logs",
            "Dedicated success manager",
        ],
    },
)

TIER_ORDER = ("free", "pro", "enterprise")
