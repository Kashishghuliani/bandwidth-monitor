import re
import subprocess


# =====================================================
# RUN WINDOWS COMMAND
# =====================================================

def run_command(command):

    result = subprocess.run(
        command,
        capture_output=True,
        text=True,
        shell=True,
        encoding="utf-8",
        errors="ignore",
    )

    return result.stdout


# =====================================================
# GET WI-FI INFORMATION
# =====================================================

def get_wifi_info():

    output = run_command(
        "netsh wlan show interfaces"
    )

    info = {
        "ssid": None,
        "signal": None,
        "link_speed": None,
        "interface": None,
    }

    for line in output.splitlines():

        line = line.strip()

        # -------------------------------------------------
        # WI-FI INTERFACE NAME
        # -------------------------------------------------

        if re.match(
            r"^Name\s*:",
            line,
            re.IGNORECASE,
        ):

            info["interface"] = line.split(
                ":",
                1
            )[1].strip()

        # -------------------------------------------------
        # SSID
        # -------------------------------------------------

        elif re.match(
            r"^SSID\s*:",
            line,
            re.IGNORECASE,
        ):

            info["ssid"] = line.split(
                ":",
                1
            )[1].strip()

        # -------------------------------------------------
        # SIGNAL
        # -------------------------------------------------

        elif re.match(
            r"^Signal\s*:",
            line,
            re.IGNORECASE,
        ):

            info["signal"] = line.split(
                ":",
                1
            )[1].strip()

        # -------------------------------------------------
        # RECEIVE RATE
        # -------------------------------------------------

        elif re.match(
            r"^Receive rate.*:",
            line,
            re.IGNORECASE,
        ):

            value = line.split(
                ":",
                1
            )[1].strip()

            info["link_speed"] = f"{value} Mbps"

    return info


# =====================================================
# GET WI-FI ADAPTER IPv4 INFORMATION
# =====================================================

def get_wifi_adapter_info():

    """
    Get IPv4 address and IPv4 default gateway
    specifically from the Wi-Fi adapter.
    """

    output = run_command(
        "ipconfig /all"
    )

    # Split Windows adapter sections
    sections = re.split(
        r"\r?\n(?=(?:Wireless LAN|Ethernet) adapter )",
        output,
        flags=re.IGNORECASE,
    )

    for section in sections:

        # We only want the Wi-Fi adapter
        if not re.search(
            r"adapter Wi-Fi:",
            section,
            re.IGNORECASE,
        ):

            continue

        local_ip = None
        gateway = None

        lines = section.splitlines()

        # -------------------------------------------------
        # SEARCH ADAPTER INFORMATION
        # -------------------------------------------------

        for i, line in enumerate(lines):

            stripped = line.strip()

            # -------------------------------------------------
            # IPv4 ADDRESS
            # -------------------------------------------------

            if re.search(
                r"IPv4 Address",
                stripped,
                re.IGNORECASE,
            ):

                if ":" in stripped:

                    value = stripped.split(
                        ":",
                        1
                    )[1].strip()

                    # Remove possible "(Preferred)"
                    value = value.split(
                        "(",
                        1
                    )[0].strip()

                    if re.match(
                        r"^\d{1,3}(?:\.\d{1,3}){3}$",
                        value,
                    ):

                        local_ip = value

            # -------------------------------------------------
            # DEFAULT GATEWAY
            # -------------------------------------------------

            elif re.search(
                r"Default Gateway",
                stripped,
                re.IGNORECASE,
            ):

                # Same-line gateway
                if ":" in stripped:

                    value = stripped.split(
                        ":",
                        1
                    )[1].strip()

                    if re.match(
                        r"^\d{1,3}(?:\.\d{1,3}){3}$",
                        value,
                    ):

                        gateway = value

                # Gateway may appear on next line
                j = i + 1

                while j < len(lines):

                    next_value = lines[j].strip()

                    if not next_value:

                        j += 1
                        continue

                    if re.match(
                        r"^\d{1,3}(?:\.\d{1,3}){3}$",
                        next_value,
                    ):

                        gateway = next_value
                        break

                    # Stop when another property begins
                    if ":" in next_value:

                        break

                    j += 1

        return {
            "local_ip": local_ip,
            "gateway": gateway,
        }

    return {
        "local_ip": None,
        "gateway": None,
    }


# =====================================================
# GET PACKET LOSS
# =====================================================

def get_packet_loss(host="8.8.8.8"):

    output = run_command(
        f"ping -n 5 {host}"
    )

    # Windows output:
    # Packets: Sent = 5, Received = 5, Lost = 0 (0% loss),

    match = re.search(
        r"Lost\s*=\s*\d+\s*\((\d+)%\s*loss\)",
        output,
        re.IGNORECASE,
    )

    if match:
        return float(match.group(1))

    return None


# =====================================================
# GET COMPLETE NETWORK INFORMATION
# =====================================================

def get_network_info():

    wifi = get_wifi_info()

    network = get_wifi_adapter_info()

    packet_loss = get_packet_loss()

    return {
        **wifi,
        **network,
        "packet_loss": packet_loss,
    }


# =====================================================
# TEST DIRECTLY
# =====================================================

if __name__ == "__main__":

    info = get_network_info()

    print()
    print("Network Information")
    print("-------------------")

    for key, value in info.items():

        print(
            f"{key}: {value}"
        )