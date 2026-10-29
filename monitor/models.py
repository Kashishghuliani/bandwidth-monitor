
from django.db import models


class TargetIP(models.Model):
    """An IP address that the scheduled monitor checks."""

    name = models.CharField(max_length=100)
    ip_address = models.CharField(max_length=253, unique=True)

    CHECK_TYPE_CHOICES = [
        ("ping", "Ping"),
        ("https", "HTTPS"),
    ]

    check_type = models.CharField(
        max_length=10,
        choices=CHECK_TYPE_CHOICES,
        default="ping",
    )

    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["name"]
        verbose_name = "Target IP"
        verbose_name_plural = "Target IPs"

    def __str__(self):
        return f"{self.name} ({self.ip_address})"


class IPCheckResult(models.Model):
    """Results from a scheduled connectivity check."""

    STATUS_CHOICES = [
        ("healthy", "Healthy"),
        ("warning", "Warning"),
        ("offline", "Offline"),
    ]

    target = models.ForeignKey(
        TargetIP,
        on_delete=models.CASCADE,
        related_name="check_results",
    )
    checked_at = models.DateTimeField(auto_now_add=True)
    is_reachable = models.BooleanField(default=False)
    latency_ms = models.FloatField(null=True, blank=True)
    packet_loss_percent = models.FloatField(
        null=True,
        blank=True,
    )
    status = models.CharField(
        max_length=20,
        choices=STATUS_CHOICES,
        default="offline",
    )
    error_message = models.TextField(blank=True)

    class Meta:
        ordering = ["-checked_at"]
        indexes = [
            models.Index(
                fields=["target", "-checked_at"],
                name="ipcheck_target_time_idx",
            ),
        ]

    def __str__(self):
        return (
            f"{self.target.ip_address} - "
            f"{self.status} - {self.checked_at}"
        )
