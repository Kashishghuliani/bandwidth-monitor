
from django.urls import path

from . import api
from . import views

urlpatterns = [
    # Web dashboard
    path("", views.dashboard, name="dashboard"),

    # Live status for the signed-in user's device
    path(
        "api/live-status/",
        api.live_status,
        name="live_status",
    ),

    # Data uploaded by installed Windows agents
    path(
        "api/agent/health/",
        api.ingest_health,
        name="ingest_health",
    ),
    path(
        "api/agent/bandwidth/",
        api.ingest_bandwidth,
        name="ingest_bandwidth",
    ),
]
