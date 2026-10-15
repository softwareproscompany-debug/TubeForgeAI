"""Channel URL routes."""

from django.urls import path

from .views import (
    AutomationRuleViewSet,
    ChannelConnectView,
    ChannelDisconnectView,
    ChannelOAuthCallbackView,
    ChannelSettingsView,
    ChannelValidateView,
    ChannelViewSet,
)

channel_list = ChannelViewSet.as_view({"get": "list", "post": "create"})
channel_detail = ChannelViewSet.as_view(
    {"get": "retrieve", "patch": "partial_update", "put": "update", "delete": "destroy"}
)
rule_list = AutomationRuleViewSet.as_view({"get": "list", "post": "create"})
rule_detail = AutomationRuleViewSet.as_view(
    {"get": "retrieve", "patch": "partial_update", "put": "update", "delete": "destroy"}
)

urlpatterns = [
    path("channels", channel_list, name="channel-list"),
    path("channels/connect", ChannelConnectView.as_view(), name="channel-connect"),
    path("channels/<uuid:pk>", channel_detail, name="channel-detail"),
    path(
        "channels/<uuid:pk>/oauth/callback",
        ChannelOAuthCallbackView.as_view(),
        name="channel-oauth-callback",
    ),
    path(
        "channels/<uuid:pk>/disconnect",
        ChannelDisconnectView.as_view(),
        name="channel-disconnect",
    ),
    path(
        "channels/<uuid:pk>/validate",
        ChannelValidateView.as_view(),
        name="channel-validate",
    ),
    path(
        "channels/<uuid:pk>/settings",
        ChannelSettingsView.as_view(),
        name="channel-settings",
    ),
    path(
        "channels/<uuid:channel_pk>/automation-rules",
        rule_list,
        name="automation-rule-list",
    ),
    path(
        "channels/<uuid:channel_pk>/automation-rules/<uuid:pk>",
        rule_detail,
        name="automation-rule-detail",
    ),
]
