
import hashlib
import ipaddress
import json
import math

from datetime import timedelta

from django.contrib.auth.decorators import login_required
from django.http import JsonResponse
from django.utils import timezone
from django.utils.dateparse import parse_datetime
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_GET, require_POST

from .models import BandwidthTest, Device, NetworkHealth


# A device is considered online if its last heartbeat is recent.
HEARTBEAT_TIMEOUT_SECONDS = 30

# Used for the dashboard's next-test countdown.
BANDWIDTH_TEST_INTERVAL_SECONDS = 15 * 60


def _json_error(message, status=400):
    return JsonResponse(
        {"success": False, "error": message},
        status=status,
    )


def _read_json(request):
    """Parse a JSON request body safely."""
    try:
        payload = json.loads(request.body or b"{}")
    except (json.JSONDecodeError, UnicodeDecodeError):
        return None

    if not isinstance(payload, dict):
        return None

    return payload


def _safe_float(value, field_name, required=False):
    """Validate a numeric field and reject NaN/infinity."""
    if value is None or value == "":
        if required:
            raise ValueError(f"{field_name} is required.")
        return None

    if isinstance(value, bool):
        raise ValueError(f"{field_name} must be numeric.")

    try:
        number = float(value)
    except (TypeError, ValueError):
        raise ValueError(f"{field_name} must be numeric.")

    if not math.isfinite(number):
        raise ValueError(f"{field_name} must be finite.")

    return number


def _safe_ip(value, field_name):
    if value in (None, ""):
        return None

    if not isinstance(value, str):
        raise ValueError(f"{field_name} must be an IP address.")

    try:
        return str(ipaddress.ip_address(value.strip()))
    except ValueError:
        raise ValueError(f"{field_name} must be a valid IP address.")


def _parse_optional_datetime(value, field_name):
    if value in (None, ""):
        return None

    if not isinstance(value, str):
        raise ValueError(f"{field_name} must be an ISO datetime string.")

    parsed = parse_datetime(value)
    if parsed is None:
        raise ValueError(f"{field_name} is not a valid datetime.")

    # Make naive datetimes timezone-aware using Django's configured timezone.
    if timezone.is_naive(parsed):
        parsed = timezone.make_aware(
            parsed,
            timezone.get_current_timezone(),
        )

    return parsed


def _authenticate_device(request):
    """
    Authenticate a device using:
        Authorization: Bearer <device-token>

    Only the token hash is stored in the database.
    """
    authorization = request.headers.get("Authorization", "")
    parts = authorization.split()

    if len(parts) != 2 or parts[0].lower() != "bearer":
        return None

    raw_token = parts[1]

    # This implementation expects a 32-byte random token encoded as hex.
    if len(raw_token) != 64:
        return None

    try:
        bytes.fromhex(raw_token)
    except ValueError:
        return None

    token_hash = hashlib.sha256(
        raw_token.encode("utf-8")
    ).hexdigest()

    try:
        device = Device.objects.get(
            device_token_hash=token_hash,
            is_active=True,
        )
    except Device.DoesNotExist:
        return None

    return device


def get_connection_quality(
    internet_connected,
    ping,
    packet_loss,
    download=None,
    upload=None,
    wifi_signal=None,
):
    """Use one set of connection-quality rules across the API."""
    if not internet_connected:
        return "OFFLINE"

    if (
        (ping is not None and ping > 200)
        or (packet_loss is not None and packet_loss > 5)
    ):
        return "POOR"

    if (
        (ping is not None and ping > 100)
        or (packet_loss is not None and packet_loss > 2)
    ):
        return "FAIR"

    if download is not None and download < 10:
        return "FAIR"

    if upload is not None and upload < 5:
        return "FAIR"

    # Wi-Fi signal is optional because a device may use Ethernet.
    if wifi_signal is not None:
        try:
            signal_value = float(
                str(wifi_signal).replace("%", "").strip()
            )
            if signal_value < 30:
                return "FAIR"
        except (ValueError, TypeError):
            pass

    return "GOOD"


@csrf_exempt
@require_POST
def ingest_health(request):
    """Receive a health report from an authenticated monitoring agent."""
    device = _authenticate_device(request)
    if device is None:
        return _json_error("Invalid or revoked device token.", 401)

    payload = _read_json(request)
    if payload is None:
        return _json_error("Request body must be a valid JSON object.")

    try:
        ping = _safe_float(payload.get("ping"), "ping")
        packet_loss = _safe_float(
            payload.get("packet_loss"), "packet_loss"
        )

        if ping is not None and not 0 <= ping <= 60000:
            raise ValueError("ping is outside the accepted range.")

        if packet_loss is not None and not 0 <= packet_loss <= 100:
            raise ValueError("packet_loss must be between 0 and 100.")

        local_ip = _safe_ip(payload.get("local_ip"), "local_ip")
        gateway = _safe_ip(payload.get("gateway"), "gateway")

        last_successful_check = _parse_optional_datetime(
            payload.get("last_successful_check"),
            "last_successful_check",
        )
        next_bandwidth_test = _parse_optional_datetime(
            payload.get("next_bandwidth_test"),
            "next_bandwidth_test",
        )

    except ValueError as exc:
        return _json_error(str(exc))

    internet_connected = payload.get("internet_connected", False)
    if not isinstance(internet_connected, bool):
        return _json_error("internet_connected must be true or false.")

    status = payload.get("status", "healthy")
    if not isinstance(status, str) or len(status) > 50:
        return _json_error("status must be a string of at most 50 characters.")

    alert_message = payload.get("alert_message", "")
    if not isinstance(alert_message, str) or len(alert_message) > 10000:
        return _json_error("alert_message is invalid or too long.")

    def optional_text(name, max_length):
        value = payload.get(name)
        if value is None:
            return None
        if not isinstance(value, (str, int, float)):
            raise ValueError(f"{name} must be text.")
        value = str(value)
        if len(value) > max_length:
            raise ValueError(f"{name} is too long.")
        return value

    try:
        ssid = optional_text("ssid", 255)
        wifi_signal = optional_text("wifi_signal", 50)
        wifi_link_speed = optional_text("wifi_link_speed", 50)
    except ValueError as exc:
        return _json_error(str(exc))

    now = timezone.now()

    # The device is determined from the token, never from client JSON.
    NetworkHealth.objects.update_or_create(
        device=device,
        defaults={
            "internet_connected": internet_connected,
            "ping": ping,
            "packet_loss": packet_loss,
            "ssid": ssid,
            "wifi_signal": wifi_signal,
            "wifi_link_speed": wifi_link_speed,
            "local_ip": local_ip,
            "gateway": gateway,
            "status": status,
            "alert_message": alert_message,
            "last_successful_check": last_successful_check,
            "next_bandwidth_test": next_bandwidth_test,
            "monitor_heartbeat": now,
        },
    )

    Device.objects.filter(pk=device.pk).update(last_seen=now)

    return JsonResponse({
        "success": True,
        "message": "Health report received.",
        "received_at": now.isoformat(),
    })


@csrf_exempt
@require_POST
def ingest_bandwidth(request):
    """Receive a completed bandwidth test from an authenticated agent."""
    device = _authenticate_device(request)
    if device is None:
        return _json_error("Invalid or revoked device token.", 401)

    payload = _read_json(request)
    if payload is None:
        return _json_error("Request body must be a valid JSON object.")

    try:
        download_speed = _safe_float(
            payload.get("download_speed"),
            "download_speed",
            required=True,
        )
        upload_speed = _safe_float(
            payload.get("upload_speed"),
            "upload_speed",
            required=True,
        )
        ping = _safe_float(payload.get("ping"), "ping")
        packet_loss = _safe_float(
            payload.get("packet_loss"), "packet_loss"
        )

        if not 0 <= download_speed <= 10000:
            raise ValueError("download_speed must be between 0 and 10000.")

        if not 0 <= upload_speed <= 10000:
            raise ValueError("upload_speed must be between 0 and 10000.")

        if ping is not None and not 0 <= ping <= 60000:
            raise ValueError("ping is outside the accepted range.")

        if packet_loss is not None and not 0 <= packet_loss <= 100:
            raise ValueError("packet_loss must be between 0 and 100.")

        local_ip = _safe_ip(payload.get("local_ip"), "local_ip")
        gateway = _safe_ip(payload.get("gateway"), "gateway")

    except ValueError as exc:
        return _json_error(str(exc))

    def optional_text(name, max_length):
        value = payload.get(name)
        if value is None:
            return None
        if not isinstance(value, (str, int, float)):
            raise ValueError(f"{name} must be text.")
        value = str(value)
        if len(value) > max_length:
            raise ValueError(f"{name} is too long.")
        return value

    try:
        ssid = optional_text("ssid", 255)
        wifi_signal = optional_text("wifi_signal", 50)
        wifi_link_speed = optional_text("wifi_link_speed", 50)
        server_name = optional_text("server_name", 255)
    except ValueError as exc:
        return _json_error(str(exc))

    test = BandwidthTest.objects.create(
        device=device,
        download_speed=download_speed,
        upload_speed=upload_speed,
        ping=ping,
        packet_loss=packet_loss,
        ssid=ssid,
        wifi_signal=wifi_signal,
        wifi_link_speed=wifi_link_speed,
        local_ip=local_ip,
        gateway=gateway,
        server_name=server_name,
    )

    now = timezone.now()
    Device.objects.filter(pk=device.pk).update(last_seen=now)

    # Update the current health record's next-test estimate if it exists.
    NetworkHealth.objects.filter(device=device).update(
        next_bandwidth_test=(
            test.timestamp
            + timedelta(seconds=BANDWIDTH_TEST_INTERVAL_SECONDS)
        ),
    )

    return JsonResponse({
        "success": True,
        "message": "Bandwidth test received.",
        "test_id": test.pk,
        "timestamp": test.timestamp.isoformat(),
    }, status=201)


@login_required
@require_GET
def live_status(request):
    """
    Return live status for one device belonging to the signed-in user.

    Optional query parameter:
        ?device_id=<device UUID>
    """
    user_devices = Device.objects.filter(
        user=request.user,
        is_active=True,
    )

    selected_device_id = request.GET.get("device_id")

    if selected_device_id:
        device = user_devices.filter(
            device_id=selected_device_id,
        ).first()

        if device is None:
            return _json_error(
                "Device not found or you do not have access to it.",
                404,
            )
    else:
        device = user_devices.order_by("-last_seen").first()

    if device is None:
        return JsonResponse({
            "available": False,
            "message": "No registered monitoring device yet.",
            "monitor_running": False,
            "device": None,
        })

    health = NetworkHealth.objects.filter(
        device=device,
    ).first()

    latest_test = BandwidthTest.objects.filter(
        device=device,
    ).first()

    recent_tests = list(
        BandwidthTest.objects.filter(
            device=device,
        ).order_by("-timestamp")[:20]
    )

    now = timezone.now()

    heartbeat = health.monitor_heartbeat if health else None
    monitor_running = bool(
        heartbeat
        and now - heartbeat <= timedelta(
            seconds=HEARTBEAT_TIMEOUT_SECONDS
        )
    )

    if health is None:
        return JsonResponse({
            "available": False,
            "message": "No health data received for this device yet.",
            "monitor_running": monitor_running,
            "device": {
                "id": str(device.device_id),
                "name": device.name,
                "last_seen": (
                    device.last_seen.isoformat()
                    if device.last_seen else None
                ),
            },
        })

    internet_connected = health.internet_connected
    ping = health.ping
    packet_loss = health.packet_loss

    download = (
        latest_test.download_speed if latest_test else None
    )
    upload = (
        latest_test.upload_speed if latest_test else None
    )

    quality = get_connection_quality(
        internet_connected=internet_connected,
        ping=ping,
        packet_loss=packet_loss,
        download=download,
        upload=upload,
        wifi_signal=health.wifi_signal,
    )

    next_test_seconds = None
    if health.next_bandwidth_test:
        next_test_seconds = max(
            0,
            int(
                (
                    health.next_bandwidth_test - now
                ).total_seconds()
            ),
        )
    elif latest_test:
        next_test_seconds = max(
            0,
            int(
                BANDWIDTH_TEST_INTERVAL_SECONDS
                - (now - latest_test.timestamp).total_seconds()
            ),
        )

    return JsonResponse({
        "available": True,
        "monitor_running": monitor_running,
        "device": {
            "id": str(device.device_id),
            "name": device.name,
            "last_seen": (
                device.last_seen.isoformat()
                if device.last_seen else None
            ),
        },
        "health": {
            "timestamp": health.timestamp.isoformat(),
            "internet_connected": internet_connected,
            "ping": ping,
            "packet_loss": packet_loss,
            "ssid": health.ssid,
            "wifi_signal": health.wifi_signal,
            "wifi_link_speed": health.wifi_link_speed,
            "local_ip": health.local_ip,
            "gateway": health.gateway,
            "status": health.status,
            "alert_message": health.alert_message,
            "last_successful_check": (
                health.last_successful_check.isoformat()
                if health.last_successful_check else None
            ),
            "monitor_heartbeat": (
                heartbeat.isoformat() if heartbeat else None
            ),
        },
        "connection": {
            "quality": quality,
        },
        "bandwidth": {
            "download_speed": download,
            "upload_speed": upload,
            "ping": latest_test.ping if latest_test else ping,
            "packet_loss": (
                latest_test.packet_loss
                if latest_test else packet_loss
            ),
            "timestamp": (
                latest_test.timestamp.isoformat()
                if latest_test else None
            ),
            "next_test_seconds": next_test_seconds,
        },
        "recent_tests": [
            {
                "timestamp": test.timestamp.isoformat(),
                "download_speed": test.download_speed,
                "upload_speed": test.upload_speed,
                "ping": test.ping,
                "packet_loss": test.packet_loss,
            }
            for test in recent_tests
        ],
    })
