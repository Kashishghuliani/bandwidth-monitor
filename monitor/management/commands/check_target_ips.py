import platform
import re
import subprocess
import time
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

from django.core.management.base import BaseCommand

from monitor.models import IPCheckResult, TargetIP

PING_COUNT = 5
PING_TIMEOUT_SECONDS = 15
LATENCY_WARNING_MS = 200


def check_ip(ip_address):
    """
    Send multiple pings and return:
    (reachable, average_latency_ms, packet_loss_percent, error_message).
    """

    is_windows = platform.system().lower() == "windows"

    if is_windows:
        command = [
            "ping", "-n", str(PING_COUNT),
            "-w", "2000", ip_address,
        ]
    else:
        command = [
            "ping", "-c", str(PING_COUNT),
            "-W", "2", ip_address,
        ]

    try:
        result = subprocess.run(
            command,
            capture_output=True,
            text=True,
            timeout=PING_TIMEOUT_SECONDS,
            check=False,
        )

    except (subprocess.TimeoutExpired, OSError) as exc:
        return False, None, 100.0, str(exc)

    output = f"{result.stdout}\n{result.stderr}"

    # Extract the number of packets sent and received.
    if is_windows:
        packet_match = re.search(
            r"Packets:\s*Sent\s*=\s*(\d+),\s*"
            r"Received\s*=\s*(\d+),\s*Lost\s*=\s*(\d+)",
            output,
            re.IGNORECASE,
        )
    else:
        packet_match = re.search(
            r"(\d+)\s+packets transmitted,\s*"
            r"(\d+)\s+(?:packets\s+)?received",
            output,
            re.IGNORECASE,
        )

    if not packet_match:
        error = output.strip()[-500:] or "Could not parse ping output."
        return False, None, None, error

    sent = int(packet_match.group(1))
    received = int(packet_match.group(2))

    if sent == 0:
        return False, None, None, "No ping packets were sent."

    packet_loss = round(((sent - received) / sent) * 100, 1)
    reachable = received > 0

    if is_windows:
        latency_match = re.search(
            r"Average\s*=\s*(\d+)\s*ms",
            output,
            re.IGNORECASE,
        )
    else:
        latency_match = re.search(
            r"(?:rtt|round-trip).*?=\s*"
            r"[\d.]+/([\d.]+)/",
            output,
            re.IGNORECASE,
        )

    latency_ms = (
        round(float(latency_match.group(1)), 2)
        if latency_match and reachable
        else None
    )

    if not reachable:
        error = f"No replies received; {sent} ping packets lost."
    elif packet_loss > 0:
        lost = sent - received
        error = f"{lost} of {sent} ping packets lost."
    else:
        error = ""

    return reachable, latency_ms, packet_loss, error

def check_https(host):
    """
    Check whether a website responds over HTTPS.
    Return:
    (reachable, response_time_ms, packet_loss_percent, error_message).
    """

    url = host.strip()

    if not url.startswith(("http://", "https://")):
        url = f"https://{url}"

    if url.startswith("http://"):
        url = "https://" + url[len("http://"):]

    request = Request(
        url,
        headers={"User-Agent": "BandwidthMonitor/1.0"},
        method="GET",
    )

    start_time = time.perf_counter()

    try:
        with urlopen(request, timeout=10) as response:
            response.read(1)

        latency_ms = round(
            (time.perf_counter() - start_time) * 1000, 2
        )
        return True, latency_ms, 0.0, ""

    except HTTPError as exc:
        # An HTTP error response still proves the server responded.
        latency_ms = round(
            (time.perf_counter() - start_time) * 1000, 2
        )
        return True, latency_ms, 0.0, (
            f"Server responded with HTTP status {exc.code}."
        )

    except (URLError, TimeoutError, OSError) as exc:
        return False, None, 100.0, str(exc)


class Command(BaseCommand):
    help = "Check connectivity to all active target IP addresses"

    def handle(self, *args, **options):
        targets = TargetIP.objects.filter(is_active=True)

        if not targets.exists():
            self.stdout.write(
                self.style.WARNING("No active target IPs configured.")
            )
            return

        for target in targets:
            if target.check_type == "https":
                reachable, latency_ms, packet_loss, error = check_https(
                    target.ip_address
                )
            else:
                reachable, latency_ms, packet_loss, error = check_ip(
                    target.ip_address
                )

            if not reachable:
                status = "offline"
            elif (
                packet_loss > 0
                or latency_ms is None
                or latency_ms >= LATENCY_WARNING_MS
            ):
                status = "warning"
            else:
                status = "healthy"

            IPCheckResult.objects.create(
                target=target,
                is_reachable=reachable,
                latency_ms=latency_ms,
                packet_loss_percent=packet_loss,
                status=status,
                error_message=error,
            )

            latency_display = (
                f"{latency_ms:.2f} ms"
                if latency_ms is not None
                else "N/A"
            )

            self.stdout.write(
                f"{target.name} ({target.ip_address}) "
                f"[{target.check_type.upper()}]: "
                f"{status} | Latency: {latency_display} | "
                f"Packet loss: "
                f"{packet_loss if packet_loss is not None else 'N/A'}%"
            )
