from django.http import JsonResponse
from django.shortcuts import render
from django.utils import timezone

from .models import NetworkHealth, BandwidthTest


# =====================================================
# CONNECTION QUALITY
# =====================================================

def get_connection_quality(
    internet_connected,
    ping,
    packet_loss,
    wifi_signal,
):
    """
    Determine connection quality using LIVE network data.

    Bandwidth test results are intentionally NOT used here
    because they only update every 15 minutes.
    """

    if not internet_connected:
        return "OFFLINE"

    try:
        ping = (
            float(ping)
            if ping is not None
            else None
        )
    except (TypeError, ValueError):
        ping = None

    try:
        packet_loss = (
            float(packet_loss)
            if packet_loss is not None
            else None
        )
    except (TypeError, ValueError):
        packet_loss = None

    try:
        wifi_signal = (
            float(
                str(wifi_signal)
                .replace("%", "")
                .strip()
            )
            if wifi_signal is not None
            else None
        )
    except (TypeError, ValueError):
        wifi_signal = None

    # -------------------------------------------------
    # POOR
    # -------------------------------------------------

    if ping is not None and ping > 200:
        return "POOR"

    if packet_loss is not None and packet_loss > 5:
        return "POOR"

    if wifi_signal is not None and wifi_signal < 30:
        return "POOR"

    # -------------------------------------------------
    # FAIR
    # -------------------------------------------------

    if ping is not None and ping > 100:
        return "FAIR"

    if packet_loss is not None and packet_loss > 2:
        return "FAIR"

    if wifi_signal is not None and wifi_signal < 50:
        return "FAIR"

    return "GOOD"


# =====================================================
# MONITOR STATUS
# =====================================================

def get_monitor_status(health):

    if health is None:
        return "unavailable"

    heartbeat = health.monitor_heartbeat

    if heartbeat is None:
        return "unavailable"

    try:

        heartbeat_age = (
            timezone.now() - heartbeat
        ).total_seconds()

    except (TypeError, ValueError):

        return "unavailable"

    # Monitor checks every 5 seconds.
    # Allow a 20-second grace period.

    if heartbeat_age <= 20:
        return "running"

    return "unavailable"


# =====================================================
# TODAY'S STATISTICS
# =====================================================

def get_today_statistics():

    now = timezone.localtime(
        timezone.now()
    )

    today_start = now.replace(
        hour=0,
        minute=0,
        second=0,
        microsecond=0,
    )

    today_tests = (
        BandwidthTest.objects
        .filter(
            timestamp__gte=today_start
        )
    )

    download_values = [
        test.download_speed
        for test in today_tests
        if test.download_speed is not None
    ]

    upload_values = [
        test.upload_speed
        for test in today_tests
        if test.upload_speed is not None
    ]

    ping_values = [
        test.ping
        for test in today_tests
        if test.ping is not None
    ]

    return {

        "avg_download": (
            sum(download_values)
            / len(download_values)
            if download_values
            else None
        ),

        "max_download": (
            max(download_values)
            if download_values
            else None
        ),

        "min_download": (
            min(download_values)
            if download_values
            else None
        ),

        "avg_upload": (
            sum(upload_values)
            / len(upload_values)
            if upload_values
            else None
        ),

        "avg_ping": (
            sum(ping_values)
            / len(ping_values)
            if ping_values
            else None
        ),
    }


# =====================================================
# CHART DATA
# =====================================================

def get_chart_data():

    chart_tests = list(
        BandwidthTest.objects
        .order_by("-timestamp")[:100]
    )

    chart_tests.reverse()

    return {

        "labels": [
            timezone.localtime(
                test.timestamp
            ).strftime("%H:%M:%S")
            for test in chart_tests
        ],

        "download": [
            test.download_speed
            for test in chart_tests
        ],

        "upload": [
            test.upload_speed
            for test in chart_tests
        ],

        "ping": [
            test.ping
            for test in chart_tests
        ],
    }


# =====================================================
# RECENT TEST DATA
# =====================================================

def get_recent_tests_data():

    recent_tests = (
        BandwidthTest.objects
        .order_by("-timestamp")[:20]
    )

    data = []

    for test in recent_tests:

        data.append({

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

    return data


# =====================================================
# DASHBOARD
# =====================================================

def dashboard(request):

    latest = (
        BandwidthTest.objects
        .order_by("-timestamp")
        .first()
    )

    health = (
        NetworkHealth.objects
        .order_by("-timestamp")
        .first()
    )

    recent_tests = (
        BandwidthTest.objects
        .order_by("-timestamp")[:20]
    )

    statistics = (
        get_today_statistics()
    )

    chart_data = (
        get_chart_data()
    )

    quality = (
        get_connection_quality(
            health.internet_connected,
            health.ping,
            health.packet_loss,
            health.wifi_signal,
        )
        if health
        else "OFFLINE"
    )

    monitor_status = (
        get_monitor_status(health)
    )

    context = {

        "latest":
            latest,

        "recent_tests":
            recent_tests,

        "statistics":
            statistics,

        "labels":
            chart_data["labels"],

        "download_data":
            chart_data["download"],

        "upload_data":
            chart_data["upload"],

        "ping_data":
            chart_data["ping"],

        "health":
            health,

        "connection_quality":
            quality,

        "monitor_status":
            monitor_status,

        "last_health_check": (
            health.timestamp
            if health
            else None
        ),

        "last_successful_check": (
            health.last_successful_check
            if (
                health
                and health.last_successful_check
            )
            else None
        ),

        "next_bandwidth_test": (
            health.next_bandwidth_test.isoformat()
            if (
                health
                and health.next_bandwidth_test
            )
            else None
        ),

        "monitor_heartbeat": (
            health.monitor_heartbeat.isoformat()
            if (
                health
                and health.monitor_heartbeat
            )
            else None
        ),
    }

    return render(
        request,
        "monitor/dashboard.html",
        context,
    )


# =====================================================
# LIVE STATUS API
# =====================================================

def live_status(request):

    health = (
        NetworkHealth.objects
        .order_by("-timestamp")
        .first()
    )

    latest_test = (
        BandwidthTest.objects
        .order_by("-timestamp")
        .first()
    )

    # =================================================
    # NO HEALTH DATA
    # =================================================

    if health is None:

        return JsonResponse({

            "available":
                False,

            "message":
                "No live network data yet.",

            "monitor": {

                "status":
                    "unavailable",

                "last_health_check":
                    None,

                "last_successful_check":
                    None,

                "monitor_heartbeat":
                    None,

                "next_bandwidth_test":
                    None,

            },

            "health": {

                "timestamp":
                    None,

                "internet_connected":
                    False,

                "live_latency":
                    None,

                "packet_loss":
                    None,

                "ssid":
                    None,

                "wifi_signal":
                    None,

                "wifi_link_speed":
                    None,

                "local_ip":
                    None,

                "gateway":
                    None,

                "status":
                    "offline",

                "alert_message":
                    None,

            },

            "connection": {

                "connected":
                    False,

                "message":
                    "Internet connection is unavailable.",

            },

            "connection_quality": {

                "quality":
                    "OFFLINE",

                "latency":
                    None,

                "packet_loss":
                    None,

                "download":
                    None,

                "upload":
                    None,

            },

            "bandwidth": {

                "timestamp":
                    None,

                "download":
                    None,

                "upload":
                    None,

                "speed_test_ping":
                    None,

                "server":
                    None,

            },

            "statistics":
                get_today_statistics(),

            "chart":
                get_chart_data(),

            "recent_tests":
                [],

        })


    # =================================================
    # MONITOR STATUS
    # =================================================

    monitor_status = (
        get_monitor_status(health)
    )


    # =================================================
    # CONNECTION QUALITY
    # =================================================

    quality = get_connection_quality(

        health.internet_connected,

        health.ping,

        health.packet_loss,

        health.wifi_signal,

    )


    # =================================================
    # RECENT TESTS
    # =================================================

    recent_tests_data = (
        get_recent_tests_data()
    )


    # =================================================
    # STATISTICS
    # =================================================

    statistics = (
        get_today_statistics()
    )


    # =================================================
    # CHART
    # =================================================

    chart_data = (
        get_chart_data()
    )


    # =================================================
    # RESPONSE
    # =================================================

    return JsonResponse({

        "available":
            True,

        # =================================================
        # MONITOR
        # =================================================

        "monitor": {

            "status":
                monitor_status,

            "last_health_check":
                health.timestamp.isoformat(),

            "last_successful_check": (

                health.last_successful_check.isoformat()

                if health.last_successful_check

                else None

            ),

            "monitor_heartbeat": (

                health.monitor_heartbeat.isoformat()

                if health.monitor_heartbeat

                else None

            ),

            # Absolute timestamp.
            # Frontend calculates countdown.

            "next_bandwidth_test": (

                health.next_bandwidth_test.isoformat()

                if health.next_bandwidth_test

                else None

            ),

        },


        # =================================================
        # CONNECTION QUALITY
        # =================================================

        "connection_quality": {

            "quality":
                quality,

            "latency":
                health.ping,

            "packet_loss":
                health.packet_loss,

            "download": (

                latest_test.download_speed

                if latest_test

                else None

            ),

            "upload": (

                latest_test.upload_speed

                if latest_test

                else None

            ),

        },


        # =================================================
        # LIVE NETWORK HEALTH
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
        # CONNECTION
        # =================================================

        "connection": {

            "connected":
                health.internet_connected,

            "message": (

                "Internet connection is unavailable."

                if not health.internet_connected

                else None

            ),

        },


        # =================================================
        # LATEST BANDWIDTH TEST
        # =================================================

        "bandwidth": {

            "timestamp": (

                latest_test.timestamp.isoformat()

                if latest_test

                else None

            ),

            "download": (

                latest_test.download_speed

                if latest_test

                else None

            ),

            "upload": (

                latest_test.upload_speed

                if latest_test

                else None

            ),

            "speed_test_ping": (

                latest_test.ping

                if latest_test

                else None

            ),

            "server": (

                latest_test.server_name

                if latest_test

                else None

            ),

        },


        # =================================================
        # STATISTICS
        # =================================================

        "statistics":
            statistics,


        # =================================================
        # CHART
        # =================================================

        "chart":
            chart_data,


        # =================================================
        # RECENT TESTS
        # =================================================

        "recent_tests":
            recent_tests_data,

    })