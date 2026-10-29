
from django.shortcuts import render

from .models import TargetIP, IPCheckResult


def dashboard(request):
    """Display connectivity results for configured target IPs."""

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

    return render(
        request,
        "monitor/dashboard.html",
        context,
    )
