from django.http import JsonResponse

from .models import NetworkHealth, BandwidthTest


# =====================================================
# CONNECTION QUALITY
# =====================================================

def get_connection_quality(
    live_latency,
    packet_loss,
    download,
    upload,
):
    """
    Derive connection quality from live network health
    and the latest valid bandwidth test.

    Important:
    A failed/invalid bandwidth test should not by itself
    make a healthy Internet connection look FAIR or POOR.
    """

    # -------------------------------------------------
    # INTERNET OFFLINE
    # -------------------------------------------------

    if live_latency is None:
        return "OFFLINE"

    # -------------------------------------------------
    # CONVERT VALUES SAFELY
    # -------------------------------------------------

    try:
        latency = float(live_latency)
    except (TypeError, ValueError):
        latency = None

    try:
        loss = float(packet_loss)
    except (TypeError, ValueError):
        loss = 0

    try:
        download_speed = float(download)
    except (TypeError, ValueError):
        download_speed = None

    try:
        upload_speed = float(upload)
    except (TypeError, ValueError):
        upload_speed = None

    # -------------------------------------------------
    # POOR CONNECTION
    # -------------------------------------------------

    if latency is not None and latency > 200:
        return "POOR"

    if loss > 5:
        return "POOR"

    # -------------------------------------------------
    # FAIR CONNECTION
    # -------------------------------------------------

    if latency is not None and latency > 100:
        return "FAIR"

    if loss > 2:
        return "FAIR"

    # -------------------------------------------------
    # BANDWIDTH
    # -------------------------------------------------
    #
    # Only use bandwidth when the result is valid.
    #
    # A download speed of 0 Mbps can happen because
    # the speed test failed or returned an invalid result.
    #
    # Therefore, 0 Mbps should NOT automatically make
    # the connection FAIR.
    # -------------------------------------------------

    valid_download = (
        download_speed is not None
        and download_speed > 0
    )

    valid_upload = (
        upload_speed is not None
        and upload_speed > 0
    )

    if valid_download and download_speed < 10:
        return "FAIR"

    if valid_upload and upload_speed < 5:
        return "FAIR"

    # -------------------------------------------------
    # GOOD
    # -------------------------------------------------

    return "GOOD"


# =====================================================
# LIVE STATUS API
# =====================================================

def live_status(request):

    # =================================================
    # LATEST NETWORK HEALTH
    # =================================================

    health = (
        NetworkHealth.objects
        .order_by("-timestamp")
        .first()
    )

    # =================================================
    # LATEST BANDWIDTH TEST
    # =================================================

    latest_test = (
        BandwidthTest.objects
        .order_by("-timestamp")
        .first()
    )

    # =================================================
    # RECENT BANDWIDTH TESTS
    # =================================================

    recent_tests = (
        BandwidthTest.objects
        .order_by("-timestamp")[:20]
    )

    # =================================================
    # NO HEALTH DATA
    # =================================================

    if health is None:

        return JsonResponse({

            "available": False,

            "message":
                "No live network data yet.",

        })

    # =================================================
    # LATEST VALUES
    # =================================================

    live_latency = health.ping

    packet_loss = health.packet_loss

    latest_download = (
        latest_test.download_speed
        if latest_test
        else None
    )

    latest_upload = (
        latest_test.upload_speed
        if latest_test
        else None
    )

    speed_test_ping = (
        latest_test.ping
        if latest_test
        else None
    )

    # =================================================
    # CONNECTION QUALITY
    # =================================================

    connection_quality = get_connection_quality(

        live_latency,

        packet_loss,

        latest_download,

        latest_upload,

    )

    # =================================================
    # MONITOR STATUS
    # =================================================

    monitor_running = True

    # The health record is updated every health-check
    # cycle by the background monitor.

    last_health_check = health.timestamp

    # =================================================
    # NEXT BANDWIDTH TEST
    # =================================================
    #
    # The full bandwidth test runs every 15 minutes.
    #
    # IMPORTANT:
    # This value must match the actual interval used
    # by your background monitor.
    # =================================================

    next_bandwidth_test_seconds = None

    if latest_test:

        bandwidth_interval = 15 * 60

        elapsed_seconds = (
            health.timestamp - latest_test.timestamp
        ).total_seconds()

        remaining_seconds = (
            bandwidth_interval -
            elapsed_seconds
        )

        next_bandwidth_test_seconds = max(
            0,
            int(remaining_seconds)
        )

    # =================================================
    # OFFLINE / CONNECTION RESTORED INFORMATION
    # =================================================

    internet_connected = (
        health.internet_connected
    )

    connection_message = None

    if not internet_connected:

        connection_message = (
            "Internet connection is unavailable."
        )

    # =================================================
    # RECENT TEST DATA
    # =================================================

    recent_tests_data = []

    for test in recent_tests:

        recent_tests_data.append({

            "timestamp":
                test.timestamp.isoformat(),

            "download":
                test.download_speed,

            "upload":
                test.upload_speed,

            "speed_test_ping":
                test.ping,

            "packet_loss":
                test.packet_loss,

            "server":
                test.server_name,

        })

    # =================================================
    # RESPONSE
    # =================================================

    return JsonResponse({

        "available": True,

        # =================================================
        # MONITOR
        # =================================================

        "monitor": {

            "running":
                monitor_running,

            "last_health_check":
                last_health_check.isoformat(),

            "next_bandwidth_test_seconds":
                next_bandwidth_test_seconds,

        },

        # =================================================
        # CONNECTION QUALITY
        # =================================================

        "connection_quality": {

            "quality":
                connection_quality,

            "latency":
                live_latency,

            "packet_loss":
                packet_loss,

            "download":
                latest_download,

            "upload":
                latest_upload,

        },

        # =================================================
        # LIVE NETWORK HEALTH
        # =================================================
        #
        # live_latency is measured by pinging 8.8.8.8.
        #
        # =================================================

        "health": {

            "timestamp":
                health.timestamp.isoformat(),

            "internet_connected":
                health.internet_connected,

            "live_latency":
                health.ping,

            "packet_loss":
                health.packet_loss,

            "ssid":
                health.ssid,

            "wifi_signal":
                health.wifi_signal,

            "wifi_link_speed":
                health.wifi_link_speed,

            "local_ip":
                health.local_ip,

            "gateway":
                health.gateway,

            "status":
                health.status,

            "alert_message":
                health.alert_message,

        },

        # =================================================
        # CONNECTION MESSAGE
        # =================================================

        "connection": {

            "connected":
                internet_connected,

            "message":
                connection_message,

        },

        # =================================================
        # LATEST BANDWIDTH TEST
        # =================================================
        #
        # These values are measured only when the
        # full speed test runs.
        #
        # =================================================

        "bandwidth": {

            "timestamp":
                latest_test.timestamp.isoformat()
                if latest_test
                else None,

            "download":
                latest_test.download_speed
                if latest_test
                else None,

            "upload":
                latest_test.upload_speed
                if latest_test
                else None,

            "speed_test_ping":
                latest_test.ping
                if latest_test
                else None,

            "server":
                latest_test.server_name
                if latest_test
                else None,

        },

        # =================================================
        # RECENT 20 BANDWIDTH TESTS
        # =================================================

        "recent_tests":
            recent_tests_data,

    })
