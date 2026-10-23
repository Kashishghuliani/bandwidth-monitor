
import logging
import os
import time
from datetime import datetime, timezone

import requests

from monitor.network_info import get_network_info
from monitor.speed_test import run_speed_test


logging.basicConfig(
    level=os.environ.get("LOG_LEVEL", "INFO").upper(),
    format="%(asctime)s | %(levelname)s | %(message)s",
)

logger = logging.getLogger(__name__)

API_BASE_URL = os.environ.get(
    "BANDWIDTH_MONITOR_API_URL", ""
).rstrip("/")

DEVICE_TOKEN = os.environ.get(
    "BANDWIDTH_MONITOR_DEVICE_TOKEN", ""
)

CHECK_INTERVAL = int(
    os.environ.get("NETWORK_CHECK_INTERVAL", "30")
)

SPEEDTEST_INTERVAL = int(
    os.environ.get("SPEEDTEST_INTERVAL", "900")
)

REQUEST_TIMEOUT = 10


def check_configuration():
    """Validate the agent's required configuration."""
    if not API_BASE_URL:
        raise RuntimeError(
            "Set BANDWIDTH_MONITOR_API_URL to your hosted Django URL."
        )

    if not API_BASE_URL.startswith("https://"):
        raise RuntimeError(
            "The agent must use HTTPS to protect device tokens."
        )

    if not DEVICE_TOKEN:
        raise RuntimeError(
            "Set BANDWIDTH_MONITOR_DEVICE_TOKEN to the device token."
        )

    if CHECK_INTERVAL < 5:
        raise RuntimeError(
            "NETWORK_CHECK_INTERVAL must be at least 5 seconds."
        )

    if SPEEDTEST_INTERVAL < 60:
        raise RuntimeError(
            "SPEEDTEST_INTERVAL must be at least 60 seconds."
        )


def auth_headers():
    return {
        "Authorization": f"Bearer {DEVICE_TOKEN}",
        "Accept": "application/json",
    }


def upload_health(payload):
    """Send the latest network-health measurement to Django."""
    response = requests.post(
        f"{API_BASE_URL}/api/agent/health/",
        json=payload,
        headers=auth_headers(),
        timeout=REQUEST_TIMEOUT,
    )

    response.raise_for_status()


def upload_bandwidth(payload):
    """Send a completed speed test to Django."""
    response = requests.post(
        f"{API_BASE_URL}/api/agent/bandwidth/",
        json=payload,
        headers=auth_headers(),
        timeout=REQUEST_TIMEOUT,
    )

    response.raise_for_status()


def collect_health():
    """Collect local network information."""
    info = get_network_info()

    if not isinstance(info, dict):
        raise ValueError("get_network_info() must return a dictionary.")

    return {
        "internet_connected": bool(
            info.get("internet_connected", False)
        ),
        "ping": info.get("ping"),
        "packet_loss": info.get("packet_loss"),
        "ssid": info.get("ssid"),
        "wifi_signal": info.get("wifi_signal"),
        "wifi_link_speed": info.get("wifi_link_speed"),
        "local_ip": info.get("local_ip"),
        "gateway": info.get("gateway"),
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }


def collect_bandwidth():
    """Run the local Ookla speed test and prepare an upload payload."""
    result = run_speed_test()
    network = get_network_info()

    return {
        "download_speed": result["download_speed"],
        "upload_speed": result["upload_speed"],
        "ping": result["ping"],
        "packet_loss": network.get("packet_loss"),
        "ssid": network.get("ssid"),
        "wifi_signal": network.get("wifi_signal"),
        "wifi_link_speed": network.get("wifi_link_speed"),
        "local_ip": network.get("local_ip"),
        "gateway": network.get("gateway"),
        "server_name": result.get("server_name"),
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }


def run_monitor():
    """Run continuous health checks and periodic bandwidth tests."""
    check_configuration()

    logger.info("Starting bandwidth-monitor agent")
    logger.info("Health interval: %s seconds", CHECK_INTERVAL)
    logger.info("Speed-test interval: %s seconds", SPEEDTEST_INTERVAL)

    next_speedtest = time.monotonic()

    while True:
        loop_started = time.monotonic()

        try:
            health = collect_health()

            try:
                upload_health(health)
                logger.info("Network health uploaded successfully")
            except requests.RequestException:
                logger.exception("Failed to upload network health")

            if time.monotonic() >= next_speedtest:
                if health["internet_connected"]:
                    try:
                        logger.info("Starting bandwidth test")
                        bandwidth = collect_bandwidth()
                        upload_bandwidth(bandwidth)
                        logger.info(
                            "Bandwidth test uploaded: "
                            "download=%s Mbps, upload=%s Mbps",
                            bandwidth["download_speed"],
                            bandwidth["upload_speed"],
                        )
                    except (
                        requests.RequestException,
                        RuntimeError,
                        FileNotFoundError,
                        KeyError,
                        ValueError,
                    ):
                        logger.exception("Bandwidth test failed")

                else:
                    logger.warning(
                        "Skipping speed test because internet is unavailable"
                    )

                # Schedule the next test from now, avoiding a rapid retry loop.
                next_speedtest = time.monotonic() + SPEEDTEST_INTERVAL

        except Exception:
            logger.exception("Network-health collection failed")

        elapsed = time.monotonic() - loop_started
        time.sleep(max(1, CHECK_INTERVAL - elapsed))


if __name__ == "__main__":
    try:
        run_monitor()
    except KeyboardInterrupt:
        logger.info("Agent stopped by user")
    except RuntimeError as exc:
        logger.error("%s", exc)
        raise SystemExit(1)
