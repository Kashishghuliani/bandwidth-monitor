
import json
import logging
import os
import shutil
import subprocess
from pathlib import Path


logger = logging.getLogger(__name__)

SPEEDTEST_PATH = os.environ.get("SPEEDTEST_PATH", "").strip()
SPEEDTEST_TIMEOUT = int(
    os.environ.get("SPEEDTEST_TIMEOUT", "180")
)


def find_speedtest_executable():
    """
    Find the Ookla Speedtest CLI executable.

    Set SPEEDTEST_PATH to its full path when it is not on PATH.
    """
    if SPEEDTEST_PATH:
        executable = Path(SPEEDTEST_PATH)

        if executable.is_file():
            return str(executable)

        raise FileNotFoundError(
            f"Speedtest executable not found: {executable}"
        )

    executable = shutil.which("speedtest")

    if executable:
        return executable

    # Optional local tools directory, relative to this file.
    project_root = Path(__file__).resolve().parent.parent

    candidates = [
        project_root / "tools" / "speedtest.exe",
        project_root / "tools" / "speedtest",
    ]

    for candidate in candidates:
        if candidate.is_file():
            return str(candidate)

    raise FileNotFoundError(
        "Ookla Speedtest CLI was not found. Install it or set "
        "SPEEDTEST_PATH to its executable."
    )


def run_speed_test():
    """
    Run an Ookla speed test and return normalized results.

    Returns:
        {
            "download_speed": float,  # Mbps
            "upload_speed": float,    # Mbps
            "ping": float,             # milliseconds
            "server_name": str | None
        }
    """
    executable = find_speedtest_executable()

    try:
        result = subprocess.run(
            [executable, "--accept-license", "--accept-gdpr", "--format=json"],
            capture_output=True,
            text=True,
            timeout=SPEEDTEST_TIMEOUT,
            check=False,
            shell=False,
            encoding="utf-8",
            errors="replace",
        )
    except subprocess.TimeoutExpired as exc:
        raise RuntimeError(
            f"Speed test exceeded {SPEEDTEST_TIMEOUT} seconds."
        ) from exc
    except OSError as exc:
        raise RuntimeError(
            f"Could not start Speedtest CLI: {exc}"
        ) from exc

    if result.returncode != 0:
        error_message = result.stderr.strip() or result.stdout.strip()
        raise RuntimeError(
            f"Speedtest CLI failed: {error_message or 'unknown error'}"
        )

    try:
        data = json.loads(result.stdout)
        download_bps = float(data["download"]["bandwidth"]) * 8
        upload_bps = float(data["upload"]["bandwidth"]) * 8
        ping_ms = float(data["ping"]["latency"])
    except (json.JSONDecodeError, KeyError, TypeError, ValueError) as exc:
        logger.exception("Could not parse Speedtest CLI output")
        raise RuntimeError("Speedtest CLI returned unexpected JSON.") from exc

    # Ookla JSON bandwidth is bytes per second.
    download_mbps = download_bps / 1_000_000
    upload_mbps = upload_bps / 1_000_000

    server_name = data.get("server", {}).get("name")

    return {
        "download_speed": round(download_mbps, 2),
        "upload_speed": round(upload_mbps, 2),
        "ping": round(ping_ms, 2),
        "server_name": server_name,
    }


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)

    try:
        print(json.dumps(run_speed_test(), indent=2))
    except (RuntimeError, FileNotFoundError) as exc:
        logger.error("%s", exc)
        raise SystemExit(1)
