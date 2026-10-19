from django.urls import path

from .views import dashboard
from .api import live_status


urlpatterns = [

    path(
        "",
        dashboard,
        name="dashboard"
    ),

    path(
        "api/live-status/",
        live_status,
        name="live_status"
    ),

]