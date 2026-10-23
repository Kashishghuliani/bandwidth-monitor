
import uuid

from django.conf import settings
from django.db import models


class Device(models.Model):
    """A computer registered to a user for network monitoring."""

    device_id = models.UUIDField(
        default=uuid.uuid4,
        unique=True,
        editable=False,
    )
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="monitor_devices",
    )
    name = models.CharField(max_length=100)
    device_token_hash = models.CharField(
        max_length=64,
        unique=True,
    )
    created_at = models.DateTimeField(auto_now_add=True)
    last_seen = models.DateTimeField(null=True, blank=True)
    is_active = models.BooleanField(default=True)

    class Meta:
        ordering = ["name"]

    def __str__(self):
        return f"{self.name} ({self.user})"


class BandwidthTest(models.Model):
    """A bandwidth test collected from a monitored device."""

    # Nullable temporarily to support migration of existing records.
    device = models.ForeignKey(
        Device,
        on_delete=models.CASCADE,
        related_name="bandwidth_tests",
        null=True,
        blank=True,
    )

    timestamp = models.DateTimeField(auto_now_add=True)
    download_speed = models.FloatField()
    upload_speed = models.FloatField()
    ping = models.FloatField(null=True, blank=True)
    packet_loss = models.FloatField(null=True, blank=True)

    ssid = models.CharField(
        max_length=255,
        blank=True,
        null=True,
    )
    wifi_signal = models.CharField(
        max_length=50,
        blank=True,
        null=True,
    )
    wifi_link_speed = models.CharField(
        max_length=50,
        blank=True,
        null=True,
    )

    local_ip = models.GenericIPAddressField(
        blank=True,
        null=True,
    )
    gateway = models.GenericIPAddressField(
        blank=True,
        null=True,
    )
    server_name = models.CharField(
        max_length=255,
        blank=True,
        null=True,
    )

    class Meta:
        ordering = ["-timestamp"]
        indexes = [
            models.Index(
                fields=["device", "-timestamp"],
                name="bw_device_time_idx",
            ),
        ]

    def __str__(self):
        return (
            f"{self.timestamp} - "
            f"{self.download_speed:.2f} Mbps"
        )


class NetworkHealth(models.Model):
    """The latest health status for a monitored device."""

    # Nullable temporarily to support existing health records.
    device = models.ForeignKey(
        Device,
        on_delete=models.CASCADE,
        related_name="health_records",
        null=True,
        blank=True,
    )

    timestamp = models.DateTimeField(auto_now=True)

    internet_connected = models.BooleanField(default=False)

    ping = models.FloatField(null=True, blank=True)
    packet_loss = models.FloatField(null=True, blank=True)

    ssid = models.CharField(
        max_length=255,
        blank=True,
        null=True,
    )
    wifi_signal = models.CharField(
        max_length=50,
        blank=True,
        null=True,
    )
    wifi_link_speed = models.CharField(
        max_length=50,
        blank=True,
        null=True,
    )

    local_ip = models.GenericIPAddressField(
        blank=True,
        null=True,
    )
    gateway = models.GenericIPAddressField(
        blank=True,
        null=True,
    )

    status = models.CharField(
        max_length=50,
        default="healthy",
    )
    alert_message = models.TextField(
        blank=True,
        null=True,
    )

    last_successful_check = models.DateTimeField(
        null=True,
        blank=True,
    )
    next_bandwidth_test = models.DateTimeField(
        null=True,
        blank=True,
    )
    monitor_heartbeat = models.DateTimeField(
        null=True,
        blank=True,
    )

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["device"],
                name="unique_health_per_device",
            ),
        ]
        indexes = [
            models.Index(
                fields=["device", "-timestamp"],
                name="health_device_time_idx",
            ),
        ]

    def __str__(self):
        return f"{self.timestamp} - {self.status}"
