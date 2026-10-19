import os
import platform
import re
import subprocess
import time

import django
from django.utils import timezone


# =====================================================
# DJANGO SETUP
# =====================================================

os.environ.setdefault(
    "DJANGO_SETTINGS_MODULE",
    "config.settings"
)

django.setup()


from .models import NetworkHealth, BandwidthTest
from .network_info import get_network_info
from .speed_test import run_speed_test


# =====================================================
# SETTINGS
# =====================================================

HEALTH_CHECK_INTERVAL = 5

BANDWIDTH_TEST_INTERVAL = 15 * 60

PING_HOST = "8.8.8.8"

PING_COUNT = 5

PING_TIMEOUT_MS = 2000


# =====================================================
# ALERT THRESHOLDS
# =====================================================

MAX_PING = 200

MAX_PACKET_LOSS = 5

MIN_WIFI_SIGNAL = 30


# =====================================================
# TIMEZONE
# =====================================================

def get_ist_time():

    return timezone.localtime(
        timezone.now(),
        timezone.get_fixed_timezone(330)
    )


# =====================================================
# FORMAT IST TIME
# =====================================================

def get_ist_time_from(timestamp):

    return timezone.localtime(
        timestamp,
        timezone.get_fixed_timezone(330)
    ).strftime(
        "%d %b %Y, %I:%M:%S %p"
    )


# =====================================================
# GET PING + PACKET LOSS
# =====================================================
#
# Sends 5 ping packets to the same host.
#
# Returns:
#
# {
#     "ping": average latency,
#     "packet_loss": packet loss percentage
# }
#
# Example:
#
# 32 ms
# 41 ms
# 38 ms
# 35 ms
# 40 ms
#
# Average = 37.2 ms
#
# Packet loss = 0%
#
# =====================================================

def get_ping_stats(host=PING_HOST):

    if platform.system() == "Windows":

        command = [
            "ping",
            "-n",
            str(PING_COUNT),
            "-w",
            str(PING_TIMEOUT_MS),
            host,
        ]

    else:

        command = [
            "ping",
            "-c",
            str(PING_COUNT),
            "-W",
            str(PING_TIMEOUT_MS // 1000),
            host,
        ]

    try:

        result = subprocess.run(
            command,
            capture_output=True,
            text=True,
            timeout=15,
        )

        output = result.stdout

        # =================================================
        # PACKET LOSS
        # =================================================

        packet_loss = None

        if platform.system() == "Windows":

            loss_match = re.search(
                r"Lost\s*=\s*\d+\s*\((\d+)%\s*loss\)",
                output,
                re.IGNORECASE,
            )

            if loss_match:

                packet_loss = float(
                    loss_match.group(1)
                )

        else:

            loss_match = re.search(
                r"(\d+(?:\.\d+)?)%\s*packet loss",
                output,
                re.IGNORECASE,
            )

            if loss_match:

                packet_loss = float(
                    loss_match.group(1)
                )

        # =================================================
        # LATENCY
        # =================================================

        latencies = []

        if platform.system() == "Windows":

            for line in output.splitlines():

                match = re.search(
                    r"time[=<]\s*(\d+(?:\.\d+)?)\s*ms",
                    line,
                    re.IGNORECASE,
                )

                if match:

                    latencies.append(
                        float(match.group(1))
                    )

        else:

            for line in output.splitlines():

                match = re.search(
                    r"time[=<]\s*(\d+(?:\.\d+)?)\s*ms",
                    line,
                    re.IGNORECASE,
                )

                if match:

                    latencies.append(
                        float(match.group(1))
                    )

        # =================================================
        # NO SUCCESSFUL PINGS
        # =================================================

        if not latencies:

            return {
                "ping": None,
                "packet_loss": (
                    packet_loss
                    if packet_loss is not None
                    else 100.0
                ),
            }

        # =================================================
        # AVERAGE LATENCY
        # =================================================

        average_ping = (
            sum(latencies)
            / len(latencies)
        )

        # =================================================
        # PACKET LOSS FALLBACK
        # =================================================
        #
        # If Windows/Linux did not provide the summary,
        # calculate loss from successful responses.
        #
        # =================================================

        if packet_loss is None:

            packet_loss = (
                (
                    PING_COUNT
                    - len(latencies)
                )
                / PING_COUNT
            ) * 100

        return {

            "ping": round(
                average_ping,
                2
            ),

            "packet_loss": round(
                packet_loss,
                2
            ),

        }

    except Exception as e:

        print(
            f"Ping test failed: {e}"
        )

        return {

            "ping": None,

            "packet_loss": 100.0,

        }


# =====================================================
# CHECK ALERTS
# =====================================================

def check_alerts(
    ping,
    network
):

    alerts = []

    # =================================================
    # INTERNET
    # =================================================

    if ping is None:

        alerts.append(
            "Internet connection is unavailable."
        )

        return alerts

    # =================================================
    # LATENCY
    # =================================================

    if ping > MAX_PING:

        alerts.append(
            f"High latency detected: "
            f"{ping:.2f} ms"
        )

    # =================================================
    # PACKET LOSS
    # =================================================

    packet_loss = network.get(
        "packet_loss"
    )

    try:

        packet_loss = float(
            packet_loss
        )

        if packet_loss > MAX_PACKET_LOSS:

            alerts.append(
                f"High packet loss: "
                f"{packet_loss:.1f}%"
            )

    except (
        TypeError,
        ValueError
    ):

        pass

    # =================================================
    # WI-FI SIGNAL
    # =================================================

    signal = network.get(
        "signal"
    )

    try:

        signal = float(
            str(signal)
            .replace("%", "")
            .strip()
        )

        if signal < MIN_WIFI_SIGNAL:

            alerts.append(
                f"Weak Wi-Fi signal: "
                f"{signal:.0f}%"
            )

    except (
        TypeError,
        ValueError
    ):

        pass

    return alerts


# =====================================================
# GET HEALTH OBJECT
# =====================================================

def get_health():

    health, created = (
        NetworkHealth.objects
        .get_or_create(
            id=1,
            defaults={
                "internet_connected": False,
                "status": "offline",
                "monitor_heartbeat": timezone.now(),
            }
        )
    )

    return health


# =====================================================
# SAVE NEXT BANDWIDTH TEST
# =====================================================

def save_next_bandwidth_test(
    next_test_time
):

    health = get_health()

    health.next_bandwidth_test = (
        next_test_time
    )

    health.save(
        update_fields=[
            "next_bandwidth_test"
        ]
    )


# =====================================================
# SAVE HEALTH STATUS
# =====================================================

def save_health_status(
    ping,
    network,
    alerts
):

    connected = ping is not None

    if not connected:

        status = "offline"

    elif alerts:

        status = "warning"

    else:

        status = "healthy"

    alert_message = "\n".join(
        alerts
    )

    health = get_health()

    # =================================================
    # NETWORK HEALTH
    # =================================================

    health.internet_connected = connected

    health.ping = ping

    health.packet_loss = (
        network.get("packet_loss")
    )

    health.ssid = (
        network.get("ssid")
    )

    health.wifi_signal = (
        network.get("signal")
    )

    health.wifi_link_speed = (
        network.get("link_speed")
    )

    health.local_ip = (
        network.get("local_ip")
    )

    health.gateway = (
        network.get("gateway")
    )

    health.status = status

    health.alert_message = alert_message

    # =================================================
    # LAST SUCCESSFUL INTERNET CHECK
    # =================================================

    if connected:

        health.last_successful_check = (
            timezone.now()
        )

    # =================================================
    # HEALTH TIMESTAMP
    # =================================================

    health.timestamp = timezone.now()

    # =================================================
    # MONITOR HEARTBEAT
    # =================================================

    health.monitor_heartbeat = timezone.now()

    # =================================================
    # IMPORTANT
    #
    # next_bandwidth_test is NOT changed here.
    #
    # It is controlled only by run_bandwidth_test().
    # =================================================

    health.save()


# =====================================================
# RUN FULL BANDWIDTH TEST
# =====================================================

def run_bandwidth_test():

    print()
    print("----------------------------------------")
    print("Starting bandwidth test...")
    print("----------------------------------------")

    try:

        # =================================================
        # RUN OOKLA SPEED TEST
        # =================================================

        speed = run_speed_test()

        # =================================================
        # NETWORK INFORMATION
        # =================================================

        network = get_network_info()

        # =================================================
        # VALUES
        # =================================================

        download = speed.get(
            "download"
        )

        upload = speed.get(
            "upload"
        )

        ping = speed.get(
            "ping"
        )

        server = speed.get(
            "server",
            "Unknown"
        )

        # =================================================
        # VALIDATE SPEED-TEST PING
        # =================================================

        if ping is not None:

            try:

                ping = float(
                    ping
                )

                if (
                    ping < 0
                    or ping > 5000
                ):

                    print(
                        "Invalid speed-test "
                        f"ping: {ping} ms"
                    )

                    ping = None

            except (
                TypeError,
                ValueError
            ):

                ping = None

        # =================================================
        # SAVE BANDWIDTH TEST
        # =================================================

        test = BandwidthTest.objects.create(

            download_speed=download,

            upload_speed=upload,

            ping=ping,

            packet_loss=(
                network.get(
                    "packet_loss"
                )
            ),

            ssid=(
                network.get(
                    "ssid"
                )
            ),

            wifi_signal=(
                network.get(
                    "signal"
                )
            ),

            wifi_link_speed=(
                network.get(
                    "link_speed"
                )
            ),

            local_ip=(
                network.get(
                    "local_ip"
                )
            ),

            gateway=(
                network.get(
                    "gateway"
                )
            ),

            server_name=server,
        )

        # =================================================
        # TEST FINISHED
        # =================================================

        test_finished_at = timezone.now()

        # =================================================
        # NEXT BANDWIDTH TEST
        #
        # 15 MINUTES AFTER TEST FINISHES
        # =================================================

        next_test_time = (
            test_finished_at
            + timezone.timedelta(
                seconds=BANDWIDTH_TEST_INTERVAL
            )
        )

        # =================================================
        # SAVE NEXT TEST TIME
        # =================================================

        save_next_bandwidth_test(
            next_test_time
        )

        # =================================================
        # TERMINAL OUTPUT
        # =================================================

        print(
            "Bandwidth test completed."
        )

        print(
            f"Saved BandwidthTest ID: "
            f"{test.id}"
        )

        print(
            f"Download: "
            f"{download} Mbps"
        )

        print(
            f"Upload: "
            f"{upload} Mbps"
        )

        if ping is None:

            print(
                "Speed-test Ping: "
                "Not available"
            )

        else:

            print(
                f"Speed-test Ping: "
                f"{ping:.2f} ms"
            )

        print(
            f"Packet Loss: "
            f"{network.get('packet_loss')}%"
        )

        print(
            "Test finished at: "
            f"{get_ist_time_from(test_finished_at)}"
        )

        print(
            "Next bandwidth test: "
            f"{get_ist_time_from(next_test_time)}"
        )

        return next_test_time

    except Exception as e:

        print(
            f"Bandwidth test failed: {e}"
        )

        # =================================================
        # RETRY AFTER 15 MINUTES
        # =================================================

        failed_at = timezone.now()

        next_test_time = (
            failed_at
            + timezone.timedelta(
                seconds=BANDWIDTH_TEST_INTERVAL
            )
        )

        try:

            save_next_bandwidth_test(
                next_test_time
            )

        except Exception as save_error:

            print(
                "Could not save next "
                f"test time: {save_error}"
            )

        print(
            "Next bandwidth test after failure: "
            f"{get_ist_time_from(next_test_time)}"
        )

        return next_test_time


# =====================================================
# CONTINUOUS MONITOR
# =====================================================

def run_health_monitor():

    print()
    print("========================================")
    print("HOME BANDWIDTH MONITOR")
    print("========================================")

    print(
        f"Health check: every "
        f"{HEALTH_CHECK_INTERVAL} seconds"
    )

    print(
        f"Ping packets per health check: "
        f"{PING_COUNT}"
    )

    print(
        f"Bandwidth test: every "
        f"{BANDWIDTH_TEST_INTERVAL // 60} minutes"
    )

    print(
        "Timezone: IST (Asia/Kolkata)"
    )

    print(
        f"Ping host: {PING_HOST}"
    )

    print("========================================")

    # =================================================
    # GET HEALTH OBJECT
    # =================================================

    get_health()

    # =================================================
    # FIRST BANDWIDTH TEST
    # =================================================

    next_bandwidth_test = (
        run_bandwidth_test()
    )

    # =================================================
    # FIRST HEALTH CHECK SCHEDULE
    # =================================================

    next_health_check = (
        timezone.now()
        + timezone.timedelta(
            seconds=HEALTH_CHECK_INTERVAL
        )
    )

    # =================================================
    # CONTINUOUS LOOP
    # =================================================

    while True:

        # =================================================
        # CURRENT TIME
        # =================================================

        current_time = timezone.now()

        # =================================================
        # BANDWIDTH TEST
        # =================================================

        if current_time >= next_bandwidth_test:

            next_bandwidth_test = (
                run_bandwidth_test()
            )

        # =================================================
        # WAIT FOR HEALTH CHECK
        # =================================================

        current_time = timezone.now()

        remaining = (
            next_health_check
            - current_time
        ).total_seconds()

        if remaining > 0:

            time.sleep(
                remaining
            )

        # =================================================
        # PING + PACKET LOSS
        # =================================================

        try:

            ping_stats = get_ping_stats()

            ping = ping_stats.get(
                "ping"
            )

            ping_packet_loss = (
                ping_stats.get(
                    "packet_loss"
                )
            )

        except Exception as e:

            print(
                f"Ping error: {e}"
            )

            ping = None

            ping_packet_loss = 100.0

        # =================================================
        # NETWORK INFORMATION
        # =================================================

        try:

            network = get_network_info()

        except Exception as e:

            print(
                f"Network info error: {e}"
            )

            network = {}

        # =================================================
        # IMPORTANT
        #
        # Use packet loss from the SAME 5-packet ping
        # test used to calculate latency.
        #
        # This avoids a separate packet-loss ping test.
        # =================================================

        network["packet_loss"] = (
            ping_packet_loss
        )

        # =================================================
        # ALERTS
        # =================================================

        alerts = check_alerts(
            ping,
            network
        )

        # =================================================
        # SAVE HEALTH STATUS
        # =================================================

        try:

            save_health_status(
                ping,
                network,
                alerts
            )

        except Exception as e:

            print(
                f"Database error: {e}"
            )

        # =================================================
        # TERMINAL STATUS
        # =================================================

        ist_now = get_ist_time()

        print()

        print(
            f"[{ist_now.strftime('%d-%m-%Y %H:%M:%S')} IST]"
        )

        if ping is None:

            print(
                "Internet: DOWN"
            )

        else:

            print(
                "Internet: OK"
            )

            print(
                f"Average Ping: "
                f"{ping:.2f} ms"
            )

        print(
            f"Wi-Fi: "
            f"{network.get('ssid', 'Unknown')}"
        )

        print(
            f"Signal: "
            f"{network.get('signal', 'Unknown')}"
        )

        print(
            f"Packet Loss: "
            f"{network.get('packet_loss', 'Unknown')}%"
        )

        print(
            "Next bandwidth test: "
            f"{get_ist_time_from(next_bandwidth_test)}"
        )

        if alerts:

            print(
                "Status: WARNING"
            )

            for alert in alerts:

                print(
                    f"ALERT: {alert}"
                )

        else:

            print(
                "Status: HEALTHY"
            )

        # =================================================
        # SCHEDULE NEXT HEALTH CHECK
        # =================================================

        next_health_check = (
            next_health_check
            + timezone.timedelta(
                seconds=HEALTH_CHECK_INTERVAL
            )
        )

        # =================================================
        # CATCH UP IF NEEDED
        # =================================================

        current_time = timezone.now()

        if next_health_check < current_time:

            next_health_check = (
                current_time
                + timezone.timedelta(
                    seconds=HEALTH_CHECK_INTERVAL
                )
            )


# =====================================================
# START
# =====================================================

if __name__ == "__main__":

    run_health_monitor()
