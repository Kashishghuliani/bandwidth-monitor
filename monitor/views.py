
import ipaddress
import socket

from django.contrib import messages
from django.shortcuts import redirect, render
from django.views.decorators.http import require_http_methods

from .models import TargetIP, IPCheckResult


MAX_TARGETS = 20


def validate_target(value):
    """Accept public IP addresses or hostnames, rejecting private IPs."""
    value = value.strip()

    try:
        ip = ipaddress.ip_address(value)
        if not ip.is_global:
            return False, "Please enter a public IP address."
        return True, value
    except ValueError:
        pass

    # Basic hostname validation
    hostname = value.rstrip(".")
    if not hostname or len(hostname) > 253:
        return False, "Enter a valid hostname or public IP."

    try:
        labels = hostname.split(".")
        if any(
            not label
            or len(label) > 63
            or label.startswith("-")
            or label.endswith("-")
            or not all(c.isalnum() or c == "-" for c in label)
            for label in labels
        ):
            return False, "Enter a valid hostname or public IP."

        addresses = socket.getaddrinfo(
            hostname, None, type=socket.SOCK_STREAM
        )
        if not addresses:
            return False, "Hostname could not be resolved."

        for address in addresses:
            resolved_ip = ipaddress.ip_address(address[4][0])
            if not resolved_ip.is_global:
                return False, "Hostname must resolve only to public IPs."

    except (socket.gaierror, ValueError, OSError):
        return False, "Hostname could not be resolved to a public IP."

    return True, hostname


@require_http_methods(["GET", "POST"])
def dashboard(request):
    """Display connectivity results and add monitoring targets."""

    if request.method == "POST":
        name = request.POST.get("name", "").strip()
        address = request.POST.get("ip_address", "").strip()
        check_type = request.POST.get("check_type", "").strip()

        if not name or len(name) > 100:
            messages.error(request, "Enter a name up to 100 characters.")
        elif check_type not in ("ping", "https"):
            messages.error(request, "Choose a valid check type.")
        elif TargetIP.objects.count() >= MAX_TARGETS:
            messages.error(request, "The dashboard has reached its target limit.")
        else:
            valid, result = validate_target(address)

            if not valid:
                messages.error(request, result)
            elif TargetIP.objects.filter(ip_address=result).exists():
                messages.error(request, "This target already exists.")
            else:
                TargetIP.objects.create(
                    name=name,
                    ip_address=result,
                    check_type=check_type,
                )
                messages.success(request, f"Added {name} successfully.")

        return redirect("monitor:dashboard")

    targets = TargetIP.objects.all().order_by("name")
    latest_results = []

    for target in targets:
        latest = (
            IPCheckResult.objects
            .filter(target=target)
            .order_by("-checked_at")
            .first()
        )
        latest_results.append({
            "target": target,
            "latest": latest,
        })

    recent_results = (
        IPCheckResult.objects
        .select_related("target")
        .order_by("-checked_at")[:50]
    )

    context = {
        "targets": targets,
        "latest_results": latest_results,
        "recent_results": recent_results,
    }

    return render(request, "monitor/dashboard.html", context)
