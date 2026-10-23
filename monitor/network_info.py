
import platform
import re
import subprocess


def run_command(command, timeout=5):
    """Run a local system command safely and return its output."""
    try:
        result = subprocess.run(
            command,
            capture_output=True,
            text=True,
            timeout=timeout,
            check=False,
            shell=False,
            encoding="utf-8",
            errors="replace",
        )

        if result.returncode != 0:
            return ""

        return result.stdout.strip()

    except (subprocess.TimeoutExpired, OSError):
        return ""


def get_ping_info(host="1.1.1.1"):
    """
    Ping a public IP to check basic internet connectivity.

    Returns ping latency in milliseconds and packet loss percentage.
    """
    if platform.system().lower() == "windows":
        output = run_command(
            ["ping", "-n", "4", "-w", "1500", host],
            timeout=8,
        )

        loss_match = re.search(
            r"\((\d+)%\s*loss\)",
            output,
            re.IGNORECASE,
        )

        if not loss_match:
            loss_match = re.search(
                r"(\d+)%\s*loss",
                output,
                re.IGNORECASE,
            )

        ping_match = re.search(
            r"(?:Average|Average =).*?(\d+)\s*ms",
            output,
            re.IGNORECASE,
        )

        if not ping_match:
            ping_match = re.search(
                r"Average\s*=\s*(\d+)\s*ms",
                output,
                re.IGNORECASE,
            )

        packet_loss = float(loss_match.group(1)) if loss_match else None
        ping = float(ping_match.group(1)) if ping_match else None

        # Do not report a successful connection if every ping failed.
        connected = packet_loss is not None and packet_loss < 100

        return {
            "internet_connected": connected,
            "ping": ping,
            "packet_loss": packet_loss,
        }

    # Linux/macOS support is best-effort.
    output = run_command(
        ["ping", "-c", "4", "-W", "2", host],
        timeout=10,
    )

    loss_match = re.search(r"(\d+(?:\.\d+)?)%\s*packet loss", output)
    ping_match = re.search(
        r"=\s*[\d.]+/([\d.]+)/",
        output,
    )

    packet_loss = float(loss_match.group(1)) if loss_match else None
    ping = float(ping_match.group(1)) if ping_match else None

    return {
        "internet_connected": packet_loss is not None and packet_loss < 100,
        "ping": ping,
        "packet_loss": packet_loss,
    }


def get_windows_wifi_info():
    """Collect Wi-Fi details using Windows netsh."""
    output = run_command(["netsh", "wlan", "show", "interfaces"])

    if not output:
        return {
            "ssid": None,
            "wifi_signal": None,
            "wifi_link_speed": None,
        }

    ssid = None
    signal = None
    link_speed = None

    for line in output.splitlines():
        line = line.strip()

        # Match English Windows output. Other Windows display languages
        # may use different field labels.
        if re.match(r"^SSID\s*:", line, re.IGNORECASE):
            value = line.split(":", 1)[1].strip()
            if value:
                ssid = value

        elif re.match(r"^Signal\s*:", line, re.IGNORECASE):
            value = line.split(":", 1)[1].strip()
            if value:
                signal = value

        elif re.match(r"^Receive rate\s*\(Mbps\)\s*:", line, re.IGNORECASE):
            value = line.split(":", 1)[1].strip()
            if value:
                link_speed = f"{value} Mbps"

    return {
        "ssid": ssid,
        "wifi_signal": signal,
        "wifi_link_speed": link_speed,
    }


def get_windows_ip_info():
    """Read local IPv4 address and default gateway from ipconfig."""
    output = run_command(["ipconfig"])

    local_ip = None
    gateway = None
    current_adapter = []

    def inspect_adapter(lines):
        adapter_text = "\n".join(lines)

        # English Windows ipconfig output.
        ipv4_match = re.search(
            r"IPv4 Address[.\s]*:\s*"
            r"(?:\([^)]*\)\s*)?"
            r"(\d{1,3}(?:\.\d{1,3}){3})",
            adapter_text,
            re.IGNORECASE,
        )

        gateway_match = re.search(
            r"Default Gateway[.\s]*:\s*"
            r"(\d{1,3}(?:\.\d{1,3}){3})",
            adapter_text,
            re.IGNORECASE,
        )

        adapter_ip = ipv4_match.group(1) if ipv4_match else None
        adapter_gateway = gateway_match.group(1) if gateway_match else None

        # Ignore disconnected adapters and loopback addresses.
        if adapter_ip and adapter_ip.startswith("127."):
            adapter_ip = None

        return adapter_ip, adapter_gateway

    for line in output.splitlines():
        if line and not line[0].isspace() and ":" in line:
            if current_adapter:
                adapter_ip, adapter_gateway = inspect_adapter(current_adapter)

                if adapter_ip and local_ip is None:
                    local_ip = adapter_ip
                    gateway = adapter_gateway

            current_adapter = []

        current_adapter.append(line)

    if current_adapter:
        adapter_ip, adapter_gateway = inspect_adapter(current_adapter)

        if adapter_ip and local_ip is None:
            local_ip = adapter_ip
            gateway = adapter_gateway

    return {
        "local_ip": local_ip,
        "gateway": gateway,
    }


def get_network_info():
    """
    Return all network fields expected by health_monitor.py.
    """
    ping_info = get_ping_info()

    if platform.system().lower() == "windows":
        wifi_info = get_windows_wifi_info()
        ip_info = get_windows_ip_info()
    else:
        wifi_info = {
            "ssid": None,
            "wifi_signal": None,
            "wifi_link_speed": None,
        }
        ip_info = {
            "local_ip": None,
            "gateway": None,
        }

    return {
        **ping_info,
        **wifi_info,
        **ip_info,
    }


if __name__ == "__main__":
    import json

    print(json.dumps(get_network_info(), indent=2))
