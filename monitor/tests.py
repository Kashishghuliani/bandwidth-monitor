from unittest.mock import patch

from django.core.management import call_command
from django.test import TestCase
from django.urls import reverse

from .models import IPCheckResult, TargetIP


class TargetIPModelTests(TestCase):
    def test_target_ip_creation(self):
        target = TargetIP.objects.create(
            name="Google DNS",
            ip_address="8.8.8.8",
        )

        self.assertEqual(target.name, "Google DNS")
        self.assertTrue(target.is_active)
        self.assertEqual(str(target.ip_address), "8.8.8.8")

    def test_target_ip_must_be_unique(self):
        TargetIP.objects.create(
            name="Target One",
            ip_address="8.8.8.8",
        )

        with self.assertRaises(Exception):
            TargetIP.objects.create(
                name="Duplicate Target",
                ip_address="8.8.8.8",
            )


class DashboardTests(TestCase):
    def setUp(self):
        self.target = TargetIP.objects.create(
            name="Google DNS",
            ip_address="8.8.8.8",
        )

    def test_dashboard_is_public(self):
        response = self.client.get(reverse("monitor:dashboard"))

        self.assertEqual(response.status_code, 200)

    def test_dashboard_shows_configured_targets(self):
        response = self.client.get(reverse("monitor:dashboard"))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Google DNS")
        self.assertContains(response, "8.8.8.8")

    def test_dashboard_shows_latest_check(self):
        IPCheckResult.objects.create(
            target=self.target,
            is_reachable=True,
            latency_ms=25.5,
            packet_loss_percent=0,
            status="healthy",
        )

        response = self.client.get(reverse("monitor:dashboard"))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Healthy")
        self.assertContains(response, "25.50")


class ScheduledIPCheckTests(TestCase):
    def setUp(self):
        self.target = TargetIP.objects.create(
            name="Google DNS",
            ip_address="8.8.8.8",
        )

    @patch("monitor.management.commands.check_target_ips.check_ip")
    def test_command_saves_successful_check(self, mock_check_ip):
        mock_check_ip.return_value = (True, 25.5, 0.0, "")

        call_command("check_target_ips")

        result = IPCheckResult.objects.get(target=self.target)

        self.assertTrue(result.is_reachable)
        self.assertEqual(result.latency_ms, 25.5)
        self.assertEqual(result.packet_loss_percent, 0)
        self.assertEqual(result.status, "healthy")

    @patch("monitor.management.commands.check_target_ips.check_ip")
    def test_command_saves_failed_check(self, mock_check_ip):
        mock_check_ip.return_value = (
            False,
            None,
            100.0,
            "Ping failed or timed out",
        )

        call_command("check_target_ips")

        result = IPCheckResult.objects.get(target=self.target)

        self.assertFalse(result.is_reachable)
        self.assertIsNone(result.latency_ms)
        self.assertEqual(result.packet_loss_percent, 100)
        self.assertEqual(result.status, "offline")
        self.assertEqual(result.error_message, "Ping failed or timed out")

    @patch("monitor.management.commands.check_target_ips.check_ip")
    def test_command_skips_inactive_targets(self, mock_check_ip):
        self.target.is_active = False
        self.target.save(update_fields=["is_active"])

        call_command("check_target_ips")

        mock_check_ip.assert_not_called()
        self.assertEqual(IPCheckResult.objects.count(), 0)
