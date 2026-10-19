import json
import os
import platform
import subprocess


# =====================================================
# SETTINGS
# =====================================================

# Official Ookla Speedtest CLI
SPEEDTEST_EXE = os.path.abspath(
    os.path.join(
        os.path.dirname(__file__),
        "..",
        "tools",
        "speedtest.exe",
    )
)

MIN_VALID_SPEED = 0.01
MAX_VALID_SPEED = 10000.0

MIN_VALID_PING = 0.0
MAX_VALID_PING = 5000.0


# =====================================================
# VALIDATE SPEED
# =====================================================

def validate_speed(speed, speed_type):

    try:
        speed = float(speed)

    except (TypeError, ValueError):

        print(
            f"Invalid {speed_type} speed: "
            f"{speed}"
        )

        return None

    if speed < MIN_VALID_SPEED:

        print(
            f"Invalid {speed_type} speed: "
            f"{speed} Mbps"
        )

        return None

    if speed > MAX_VALID_SPEED:

        print(
            f"Unrealistic {speed_type} speed: "
            f"{speed} Mbps"
        )

        return None

    return round(speed, 2)


# =====================================================
# VALIDATE PING
# =====================================================

def validate_ping(ping):

    try:

        ping = float(ping)

    except (TypeError, ValueError):

        print(
            f"Invalid ping: {ping}"
        )

        return None

    if (
        ping < MIN_VALID_PING
        or ping > MAX_VALID_PING
    ):

        print(
            f"Unrealistic ping: "
            f"{ping} ms"
        )

        return None

    return round(ping, 2)


# =====================================================
# CHECK OOKLA EXECUTABLE
# =====================================================

def check_speedtest_executable():

    if not os.path.exists(SPEEDTEST_EXE):

        raise FileNotFoundError(
            "Ookla Speedtest executable not found.\n"
            f"Expected location:\n"
            f"{SPEEDTEST_EXE}"
        )


# =====================================================
# RUN OOKLA SPEEDTEST
# =====================================================

def run_speed_test():

    print()
    print("========================================")
    print("Running Ookla Speedtest...")
    print("========================================")

    # =================================================
    # CHECK EXECUTABLE
    # =================================================

    check_speedtest_executable()

    print(
        f"Executable: {SPEEDTEST_EXE}"
    )

    # =================================================
    # COMMAND
    # =================================================

    command = [

        SPEEDTEST_EXE,

        "--accept-license",

        "--accept-gdpr",

        "--format=json",
    ]

    try:

        # =================================================
        # RUN OFFICIAL OOKLA CLI
        # =================================================

        result = subprocess.run(

            command,

            capture_output=True,

            text=True,

            timeout=180,
        )

        # =================================================
        # CHECK PROCESS ERROR
        # =================================================

        if result.returncode != 0:

            print(
                "Ookla Speedtest failed."
            )

            if result.stderr:

                print(
                    "Error:"
                )

                print(
                    result.stderr.strip()
                )

            raise RuntimeError(
                "Ookla Speedtest returned "
                f"exit code {result.returncode}"
            )

        # =================================================
        # GET JSON OUTPUT
        # =================================================

        output = result.stdout.strip()

        if not output:

            raise RuntimeError(
                "Ookla Speedtest returned "
                "empty output."
            )

        # =================================================
        # PARSE JSON
        # =================================================

        try:

            data = json.loads(
                output
            )

        except json.JSONDecodeError as e:

            print(
                "Could not parse Ookla "
                "Speedtest JSON."
            )

            print(
                "Raw output:"
            )

            print(output)

            raise RuntimeError(
                f"Invalid JSON returned "
                f"by Ookla: {e}"
            )

        # =================================================
        # DOWNLOAD
        # =================================================
        #
        # Ookla returns bandwidth in BYTES/SECOND.
        #
        # Mbps =
        # bytes/sec * 8 / 1,000,000
        # =================================================

        download_bandwidth = (
            data
            .get("download", {})
            .get("bandwidth")
        )

        if download_bandwidth is None:

            download = None

        else:

            download = (
                float(download_bandwidth)
                * 8
                / 1_000_000
            )

            download = validate_speed(
                download,
                "download"
            )

        # =================================================
        # UPLOAD
        # =================================================

        upload_bandwidth = (
            data
            .get("upload", {})
            .get("bandwidth")
        )

        if upload_bandwidth is None:

            upload = None

        else:

            upload = (
                float(upload_bandwidth)
                * 8
                / 1_000_000
            )

            upload = validate_speed(
                upload,
                "upload"
            )

        # =================================================
        # PING
        # =================================================

        ping_value = (
            data
            .get("ping", {})
            .get("latency")
        )

        ping = validate_ping(
            ping_value
        )

        # =================================================
        # SERVER
        # =================================================

        server_data = data.get(
            "server",
            {}
        )

        server_name = server_data.get(
            "name",
            "Unknown"
        )

        server_location = server_data.get(
            "location",
            "Unknown"
        )

        server_country = server_data.get(
            "country",
            "Unknown"
        )

        server_id = server_data.get(
            "id",
            "Unknown"
        )

        server_host = server_data.get(
            "host",
            "Unknown"
        )

        # =================================================
        # ISP
        # =================================================

        isp = data.get(
            "isp",
            "Unknown"
        )

        # =================================================
        # RESULT
        # =================================================

        result_data = {

            "download":
                download,

            "upload":
                upload,

            "ping":
                ping,

            "server":
                server_name,

            "server_location":
                server_location,

            "server_country":
                server_country,

            "server_id":
                server_id,

            "server_host":
                server_host,

            "isp":
                isp,
        }

        # =================================================
        # TERMINAL OUTPUT
        # =================================================

        print()
        print("----------------------------------------")
        print("Ookla Speed Test Result")
        print("----------------------------------------")

        if download is not None:

            print(
                f"Download: "
                f"{download:.2f} Mbps"
            )

        else:

            print(
                "Download: unavailable"
            )

        if upload is not None:

            print(
                f"Upload: "
                f"{upload:.2f} Mbps"
            )

        else:

            print(
                "Upload: unavailable"
            )

        if ping is not None:

            print(
                f"Ping: "
                f"{ping:.2f} ms"
            )

        else:

            print(
                "Ping: unavailable"
            )

        print(
            f"ISP: {isp}"
        )

        print(
            f"Server: "
            f"{server_name}"
        )

        print(
            f"Location: "
            f"{server_location}, "
            f"{server_country}"
        )

        print(
            f"Server ID: "
            f"{server_id}"
        )

        print(
            f"Server Host: "
            f"{server_host}"
        )

        print("----------------------------------------")

        return result_data

    except subprocess.TimeoutExpired:

        print()
        print(
            "Ookla Speedtest timed out "
            "after 180 seconds."
        )

        raise

    except Exception as e:

        print()
        print(
            f"Speedtest failed: {e}"
        )

        raise


# =====================================================
# TEST DIRECTLY
# =====================================================

if __name__ == "__main__":

    result = run_speed_test()

    print()
    print("========================================")
    print("FINAL RESULT")
    print("========================================")

    print(
        f"Download: "
        f"{result['download']} Mbps"
    )

    print(
        f"Upload: "
        f"{result['upload']} Mbps"
    )

    print(
        f"Ping: "
        f"{result['ping']} ms"
    )

    print(
        f"ISP: "
        f"{result['isp']}"
    )

    print(
        f"Server: "
        f"{result['server']}"
    )

    print(
        f"Location: "
        f"{result['server_location']}"
    )

    print(
        f"Server ID: "
        f"{result['server_id']}"
    )