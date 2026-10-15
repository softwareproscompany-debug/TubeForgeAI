# Generated for the billing app (SubscriptionTier, UserSubscription).

import uuid

import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models

from billing.tier_data import TIER_SEEDS


def seed_tiers(apps, schema_editor):
    """Idempotent seed of the three subscription tiers."""
    SubscriptionTier = apps.get_model("billing", "SubscriptionTier")
    for seed in TIER_SEEDS:
        SubscriptionTier.objects.update_or_create(
            name=seed["name"],
            defaults={
                "display_name": seed["display_name"],
                "price_monthly_cents": seed["price_monthly_cents"],
                "stripe_price_id": seed["stripe_price_id"],
                "max_projects": seed["max_projects"],
                "max_storage_gb": seed["max_storage_gb"],
                "max_api_calls_month": seed["max_api_calls_month"],
                "features": seed["features"],
            },
        )


class Migration(migrations.Migration):
    initial = True

    dependencies = (
        ("core", "0003_alter_auditevent_options_alter_notification_options_and_more"),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    )

    operations = (
        migrations.CreateModel(
            name="SubscriptionTier",
            fields=[
                (
                    "id",
                    models.UUIDField(
                        default=uuid.uuid4,
                        editable=False,
                        primary_key=True,
                        serialize=False,
                    ),
                ),
                ("name", models.CharField(max_length=50, unique=True)),
                ("display_name", models.CharField(max_length=100)),
                ("price_monthly_cents", models.IntegerField(default=0)),
                (
                    "stripe_price_id",
                    models.CharField(blank=True, default="", max_length=255),
                ),
                ("max_projects", models.IntegerField(default=0)),
                ("max_storage_gb", models.IntegerField(default=0)),
                ("max_api_calls_month", models.IntegerField(default=0)),
                ("features", models.JSONField(default=list)),
            ],
            options={"ordering": ("price_monthly_cents",)},
        ),
        migrations.CreateModel(
            name="UserSubscription",
            fields=[
                (
                    "id",
                    models.UUIDField(
                        default=uuid.uuid4,
                        editable=False,
                        primary_key=True,
                        serialize=False,
                    ),
                ),
                (
                    "stripe_customer_id",
                    models.CharField(blank=True, default="", max_length=255),
                ),
                (
                    "stripe_subscription_id",
                    models.CharField(blank=True, default="", max_length=255),
                ),
                (
                    "status",
                    models.CharField(
                        choices=[
                            ("active", "Active"),
                            ("past_due", "Past due"),
                            ("canceled", "Canceled"),
                            ("trialing", "Trialing"),
                            ("incomplete", "Incomplete"),
                        ],
                        default="active",
                        max_length=20,
                    ),
                ),
                ("current_period_start", models.DateTimeField(blank=True, null=True)),
                ("current_period_end", models.DateTimeField(blank=True, null=True)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                (
                    "tier",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.PROTECT,
                        related_name="subscriptions",
                        to="billing.subscriptiontier",
                    ),
                ),
                (
                    "user",
                    models.OneToOneField(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="subscription",
                        to=settings.AUTH_USER_MODEL,
                    ),
                ),
            ],
        ),
        migrations.RunPython(seed_tiers, migrations.RunPython.noop),
    )
