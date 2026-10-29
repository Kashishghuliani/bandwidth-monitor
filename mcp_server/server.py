import requests

from mcp.server.fastmcp import FastMCP


# =====================================================
# MCP SERVER
# =====================================================

mcp = FastMCP("Bandwidth Monitor")


# =====================================================
# DJANGO API
# =====================================================

API_URL = "http://127.0.0.1:8000/api/live-status/"


# =====================================================
# GET CURRENT NETWORK STATUS
# =====================================================

@mcp.tool()
def get_network_status():
    """
    Get the current network and Wi-Fi status.
    """

    try:

        response = requests.get(
            API_URL,
            timeout=10,
        )

        response.raise_for_status()

        data = response.json()

        return {
            "connection_quality":
                data.get(
                    "connection_quality"
                ),

            "health":
                data.get(
                    "health"
                ),

            "connection":
                data.get(
                    "connection"
                ),
        }

    except Exception as e:

        return {
            "error": str(e)
        }


# =====================================================
# GET LATEST BANDWIDTH
# =====================================================

@mcp.tool()
def get_latest_bandwidth():
    """
    Get the latest download and upload speed.
    """

    try:

        response = requests.get(
            API_URL,
            timeout=10,
        )

        response.raise_for_status()

        data = response.json()

        return data.get(
            "bandwidth"
        )

    except Exception as e:

        return {
            "error": str(e)
        }


# =====================================================
# GET BANDWIDTH HISTORY
# =====================================================

@mcp.tool()
def get_bandwidth_history():
    """
    Get recent bandwidth test results.
    """

    try:

        response = requests.get(
            API_URL,
            timeout=10,
        )

        response.raise_for_status()

        data = response.json()

        return data.get(
            "recent_tests",
            []
        )

    except Exception as e:

        return {
            "error": str(e)
        }


# =====================================================
# GET NETWORK ALERTS
# =====================================================

@mcp.tool()
def get_network_alerts():
    """
    Get the current network alert information.
    """

    try:

        response = requests.get(
            API_URL,
            timeout=10,
        )

        response.raise_for_status()

        data = response.json()

        health = data.get(
            "health",
            {}
        )

        alert_message = health.get(
            "alert_message"
        )

        return {
            "status":
                health.get(
                    "status"
                ),

            "has_alert":
                bool(alert_message),

            "alert_message":
                alert_message,

        }

    except Exception as e:

        return {
            "error": str(e)
        }


# =====================================================
# START MCP SERVER
# =====================================================

if __name__ == "__main__":

    mcp.run()