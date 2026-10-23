
from datetime import timedelta

from django.contrib.auth.decorators import login_required
from django.http import Http404
from django.shortcuts import render
from django.utils import timezone

from .models import BandwidthTest, Device, NetworkHealth


HEARTBEAT_TIMEOUT_SECONDS = 30


def get_connection_quality(
    internet_connected,
    ping,
    packet_loss,
    wifi_signal,
):
    """Determine connection quality using current network health."""

    if not internet_connected:
        return "OFFLINE"

    try:
        ping = float(ping) if ping is not None else None
    except (TypeError, ValueError):
        ping = None

    try:
        packet_loss = (
            float(packet_loss) if packet_loss is not None else None
        )
    except (TypeError, ValueError):
        packet_loss = None

    try:
        wifi_signal = (
            float(str(wifi_signal).replace("%", "").strip())
            if wifi_signal is not None
            else None
        )
    except (TypeError, ValueError):
        wifi_signal = None

    if ping is not None and ping > 200:
        return "POOR"

    if packet_loss is not None and packet_loss > 5:
        return "POOR"

    if wifi_signal is not None and wifi_signal < 30:
        return "POOR"

    if ping is not None and ping > 100:
        return "FAIR"

    if packet_loss is not None and packet_loss > 2:
        return "FAIR"

    if wifi_signal is not None and wifi_signal < 50:
        return "FAIR"

    return "GOOD"


def get_monitor_status(health):
    """Return whether the device has sent a recent heartbeat."""

    if health is None or health.monitor_heartbeat is None:
        return "unavailable"

    heartbeat_age = (
        timezone.now() - health.monitor_heartbeat
    ).total_seconds()

    if 0 <= heartbeat_age <= HEARTBEAT_TIMEOUT_SECONDS:
        return "running"

    return "unavailable"


def get_today_statistics(tests):
    """Calculate today's statistics for the selected device."""

    now = timezone.localtime(timezone.now())

    today_start = now.replace(
        hour=0,
        minute=0,
        second=0,
        microsecond=0,
    )

    tomorrow_start = today_start + timedelta(days=1)

    today_tests = list(
        tests.filter(
            timestamp__gte=today_start,
            timestamp__lt=tomorrow_start,
        )
    )

    downloads = [
        test.download_speed
        for test in today_tests
        if test.download_speed is not None
    ]

    uploads = [
        test.upload_speed
        for test in today_tests
        if test.upload_speed is not None
    ]

    pings = [
        test.ping
        for test in today_tests
        if test.ping is not None
    ]

    return {
        "avg_download": (
            sum(downloads) / len(downloads) if downloads else None
        ),
        "max_download": max(downloads) if downloads else None,
        "min_download": min(downloads) if downloads else None,
        "avg_upload": (
            sum(uploads) / len(uploads) if uploads else None
        ),
        "avg_ping": (
            sum(pings) / len(pings) if pings else None
        ),
    }


def get_chart_data(tests):
    """Return chart data for the selected device's last 100 tests."""

    chart_tests = list(
        tests.order_by("-timestamp")[:100]
    )
    chart_tests.reverse()

    return {
        "labels": [
            timezone.localtime(test.timestamp).strftime("%H:%M:%S")
            for test in chart_tests
        ],
        "download": [
            test.download_speed for test in chart_tests
        ],
        "upload": [
            test.upload_speed for test in chart_tests
        ],
        "ping": [
            test.ping for test in chart_tests
        ],
    }


def get_recent_tests_data(tests):
    """Return recent test data for the selected device."""

    recent_tests = tests.order_by("-timestamp")[:20]

    return [
        {
            "timestamp": test.timestamp.isoformat(),
            "download": test.download_speed,
            "upload": test.upload_speed,
            "speed_test_ping": test.ping,
            "packet_loss": test.packet_loss,
            "server": test.server_name,
        }
        for test in recent_tests
    ]


@login_required
def dashboard(request):
    """
    Display monitoring data for a device owned by the signed-in user.

    An optional ?device_id=<UUID> selects one of that user's devices.
    """

    devices = Device.objects.filter(
        user=request.user,
        is_active=True,
    ).order_by("name")

    selected_device_id = request.GET.get("device_id")

    if selected_device_id:
        device = devices.filter(
            device_id=selected_device_id,
        ).first()

        if device is None:
            raise Http404(
                "Device not found or you do not have access to it."
            )
    else:
        # Default to the user's most recently seen device.
        device = devices.order_by("-last_seen", "name").first()

    latest = None
    health = None
    recent_tests = []
    statistics = {
        "avg_download": None,
        "max_download": None,
        "min_download": None,
        "avg_upload": None,
        "avg_ping": None,
    }

    chart_data = {
        "labels": [],
        "download": [],
        "upload": [],
        "ping": [],
    }

    monitor_status = "unavailable"
    quality = "OFFLINE"

    if device is not None:
        tests = BandwidthTest.objects.filter(device=device)

        latest = tests.order_by("-timestamp").first()

        health = NetworkHealth.objects.filter(
            device=device,
        ).first()

        recent_tests = tests.order_by("-timestamp")[:20]

        statistics = get_today_statistics(tests)
        chart_data = get_chart_data(tests)

        if health is not None:
            quality = get_connection_quality(
                health.internet_connected,
                health.ping,
                health.packet_loss,
                health.wifi_signal,
            )

        monitor_status = get_monitor_status(health)

    context = {
        # Preserve the existing dashboard template's context names.
        "latest": latest,
        "recent_tests": recent_tests,
        "statistics": statistics,
        "labels": chart_data["labels"],
        "download_data": chart_data["download"],
        "upload_data": chart_data["upload"],
        "ping_data": chart_data["ping"],
        "health": health,
        "connection_quality": quality,
        "monitor_status": monitor_status,
        "last_health_check": (
            health.timestamp if health else None
        ),
        "last_successful_check": (
            health.last_successful_check if health else None
        ),
        "next_bandwidth_test": (
            health.next_bandwidth_test.isoformat()
            if health and health.next_bandwidth_test
            else None
        ),
        "monitor_heartbeat": (
            health.monitor_heartbeat.isoformat()
            if health and health.monitor_heartbeat
            else None
        ),

        # New context for device selection.
        "devices": devices,
        "selected_device": device,
    }

    return render(
        request,
        "monitor/dashboard.html",
        context,
    )
