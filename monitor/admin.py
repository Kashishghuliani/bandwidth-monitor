from django.contrib import admin
from .models import TargetIP, IPCheckResult


@admin.register(TargetIP)
class TargetIPAdmin(admin.ModelAdmin):
    list_display = (
        "name",
        "ip_address",
        "check_type",
        "is_active",
        "created_at",
    )
    list_filter = ("check_type", "is_active")
    search_fields = ("name", "ip_address")

@admin.register(IPCheckResult)
class IPCheckResultAdmin(admin.ModelAdmin):
    list_display = (
        "target",
        "checked_at",
        "is_reachable",
        "latency_ms",
        "packet_loss_percent",
        "status",
    )
    list_filter = ("status", "is_reachable")
    search_fields = ("target__name", "target__ip_address")
