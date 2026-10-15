"""Billing serializers."""

from rest_framework import serializers

from .models import SubscriptionTier, UserSubscription


class SubscriptionTierSerializer(serializers.ModelSerializer):
    price_monthly_usd = serializers.SerializerMethodField()

    class Meta:
        model = SubscriptionTier
        fields = (
            "id",
            "name",
            "display_name",
            "price_monthly_cents",
            "price_monthly_usd",
            "max_projects",
            "max_storage_gb",
            "max_api_calls_month",
            "features",
        )

    def get_price_monthly_usd(self, obj) -> float:
        return obj.price_monthly_cents / 100


class UserSubscriptionSerializer(serializers.ModelSerializer):
    tier = SubscriptionTierSerializer(read_only=True)

    class Meta:
        model = UserSubscription
        fields = (
            "id",
            "tier",
            "status",
            "current_period_start",
            "current_period_end",
            "created_at",
            "updated_at",
        )


class CheckoutRequestSerializer(serializers.Serializer):
    tier = serializers.ChoiceField(choices=("pro", "enterprise"))
