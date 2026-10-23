
from django.contrib import admin

from .models import BandwidthTest, Device, NetworkHealth


@admin.register(Device)
class DeviceAdmin(admin.ModelAdmin):
    list_display = (
        "name",
        "user",
        "device_id",
        "is_active",
        "last_seen",
        "created_at",
    )
    list_filter = ("is_active", "created_at")
    search_fields = (
        "name",
        "user__username",
        "user__email",
        "device_id",
    )
    readonly_fields = (
        "device_id",
        "created_at",
        "last_seen",
    )
    ordering = ("name",)

    # Never expose stored credential hashes unnecessarily.
    exclude = ("device_token_hash",)


@admin.register(BandwidthTest)
class BandwidthTestAdmin(admin.ModelAdmin):
    list_display = (
        "timestamp",
        "device",
        "download_speed",
        "upload_speed",
        "ping",
        "packet_loss",
    )
    list_filter = ("timestamp",)
    search_fields = (
        "device__name",
        "device__user__username",
        "server_name",
    )
    readonly_fields = (
        "timestamp",
        "device",
        "download_speed",
        "upload_speed",
        "ping",
        "packet_loss",
        "ssid",
        "wifi_signal",
        "wifi_link_speed",
        "local_ip",
        "gateway",
        "server_name",
    )
    ordering = ("-timestamp",)

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return request.user.is_superuser


@admin.register(NetworkHealth)
class NetworkHealthAdmin(admin.ModelAdmin):
    list_display = (
        "device",
        "timestamp",
        "internet_connected",
        "ping",
        "packet_loss",
        "status",
        "monitor_heartbeat",
    )
    list_filter = (
        "internet_connected",
        "status",
    )
    search_fields = (
        "device__name",
        "device__user__username",
    )
    readonly_fields = (
        "device",
        "timestamp",
        "internet_connected",
        "ping",
        "packet_loss",
        "ssid",
        "wifi_signal",
        "wifi_link_speed",
        "local_ip",
        "gateway",
        "status",
        "alert_message",
        "last_successful_check",
        "next_bandwidth_test",
        "monitor_heartbeat",
    )

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return request.user.is_superuser
