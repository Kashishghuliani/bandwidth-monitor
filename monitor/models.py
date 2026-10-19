from django.db import models


class BandwidthTest(models.Model):

    timestamp = models.DateTimeField(
        auto_now_add=True
    )

    download_speed = models.FloatField()

    upload_speed = models.FloatField()

    ping = models.FloatField(
        null=True,
        blank=True
    )

    packet_loss = models.FloatField(
        null=True,
        blank=True
    )

    ssid = models.CharField(
        max_length=255,
        blank=True,
        null=True
    )

    wifi_signal = models.CharField(
        max_length=50,
        blank=True,
        null=True
    )

    wifi_link_speed = models.CharField(
        max_length=50,
        blank=True,
        null=True
    )

    local_ip = models.GenericIPAddressField(
        blank=True,
        null=True
    )

    gateway = models.GenericIPAddressField(
        blank=True,
        null=True
    )

    server_name = models.CharField(
        max_length=255,
        blank=True,
        null=True
    )

    class Meta:
        ordering = ["-timestamp"]

    def __str__(self):

        return (
            f"{self.timestamp} - "
            f"{self.download_speed:.2f} Mbps"
        )


# =====================================================
# LIVE NETWORK HEALTH
# =====================================================

class NetworkHealth(models.Model):

    # =================================================
    # LAST HEALTH CHECK
    # =================================================

    timestamp = models.DateTimeField(
        auto_now=True
    )

    # =================================================
    # INTERNET CONNECTION
    # =================================================

    internet_connected = models.BooleanField(
        default=False
    )

    # =================================================
    # LIVE NETWORK METRICS
    # =================================================

    ping = models.FloatField(
        null=True,
        blank=True
    )

    packet_loss = models.FloatField(
        null=True,
        blank=True
    )

    # =================================================
    # WI-FI INFORMATION
    # =================================================

    ssid = models.CharField(
        max_length=255,
        blank=True,
        null=True
    )

    wifi_signal = models.CharField(
        max_length=50,
        blank=True,
        null=True
    )

    wifi_link_speed = models.CharField(
        max_length=50,
        blank=True,
        null=True
    )

    # =================================================
    # NETWORK INFORMATION
    # =================================================

    local_ip = models.GenericIPAddressField(
        blank=True,
        null=True
    )

    gateway = models.GenericIPAddressField(
        blank=True,
        null=True
    )

    # =================================================
    # NETWORK STATUS
    # =================================================

    status = models.CharField(
        max_length=50,
        default="healthy"
    )

    alert_message = models.TextField(
        blank=True,
        null=True
    )

    # =================================================
    # LAST SUCCESSFUL INTERNET CHECK
    # =================================================

    last_successful_check = models.DateTimeField(
        null=True,
        blank=True
    )

    # =================================================
    # NEXT BANDWIDTH TEST
    # =================================================

    next_bandwidth_test = models.DateTimeField(
        null=True,
        blank=True
    )

    # =================================================
    # MONITOR HEARTBEAT
    # =================================================
    #
    # Updated by the Python monitor every health check.
    #
    # The dashboard uses this to determine whether the
    # monitor process is actually running.
    #
    # =================================================

    monitor_heartbeat = models.DateTimeField(
        null=True,
        blank=True
    )

    def __str__(self):

        return (
            f"{self.timestamp} - "
            f"{self.status}"
        )
