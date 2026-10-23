
import hashlib
import json
import secrets

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse

from .models import BandwidthTest, Device, NetworkHealth


User = get_user_model()


class DeviceIsolationTests(TestCase):
    def setUp(self):
        self.user1 = User.objects.create_user(
            username="user_one",
            password="TestPassword123!",
        )
        self.user2 = User.objects.create_user(
            username="user_two",
            password="TestPassword123!",
        )

        # Store only the SHA-256 hash of the device token.
        self.raw_token = secrets.token_hex(32)
        token_hash = hashlib.sha256(
            self.raw_token.encode("utf-8")
        ).hexdigest()

        self.device1 = Device.objects.create(
            user=self.user1,
            name="Laptop One",
            device_token_hash=token_hash,
        )

        self.device2 = Device.objects.create(
            user=self.user2,
            name="Laptop Two",
            device_token_hash=hashlib.sha256(
                secrets.token_hex(32).encode("utf-8")
            ).hexdigest(),
        )

        BandwidthTest.objects.create(
            device=self.device1,
            download_speed=100,
            upload_speed=20,
            ping=10,
        )

        BandwidthTest.objects.create(
            device=self.device2,
            download_speed=500,
            upload_speed=100,
            ping=5,
        )

    def test_dashboard_requires_login(self):
        response = self.client.get(reverse("dashboard"))

        self.assertEqual(response.status_code, 302)
        self.assertIn("/accounts/login/", response.url)

    def test_user_sees_only_their_devices(self):
        self.client.login(
            username="user_one",
            password="TestPassword123!",
        )

        response = self.client.get(reverse("dashboard"))

        self.assertEqual(response.status_code, 200)

        device_ids = [
            str(device.device_id)
            for device in response.context["devices"]
        ]

        self.assertIn(str(self.device1.device_id), device_ids)
        self.assertNotIn(str(self.device2.device_id), device_ids)

    def test_user_cannot_select_another_users_device(self):
        self.client.login(
            username="user_one",
            password="TestPassword123!",
        )

        response = self.client.get(
            reverse("live_status"),
            {"device_id": str(self.device2.device_id)},
        )

        self.assertEqual(response.status_code, 404)

    def test_live_status_requires_login(self):
        response = self.client.get(reverse("live_status"))

        self.assertEqual(response.status_code, 302)
        self.assertIn("/accounts/login/", response.url)


class AgentApiAuthenticationTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            username="agent_owner",
            password="TestPassword123!",
        )

        self.token = secrets.token_hex(32)

        Device.objects.create(
            user=self.user,
            name="Test Laptop",
            device_token_hash=hashlib.sha256(
                self.token.encode("utf-8")
            ).hexdigest(),
        )

    def test_health_endpoint_rejects_missing_token(self):
        response = self.client.post(
            reverse("ingest_health"),
            data=json.dumps({"internet_connected": True}),
            content_type="application/json",
        )

        self.assertEqual(response.status_code, 401)

    def test_bandwidth_endpoint_rejects_invalid_token(self):
        response = self.client.post(
            reverse("ingest_bandwidth"),
            data=json.dumps({
                "download_speed": 100,
                "upload_speed": 20,
                "ping": 10,
            }),
            content_type="application/json",
            HTTP_AUTHORIZATION="Bearer invalid-token",
        )

        self.assertEqual(response.status_code, 401)

    def test_health_endpoint_accepts_valid_token(self):
        response = self.client.post(
            reverse("ingest_health"),
            data=json.dumps({
                "internet_connected": True,
                "ping": 12.5,
                "packet_loss": 0,
            }),
            content_type="application/json",
            HTTP_AUTHORIZATION=f"Bearer {self.token}",
        )

        self.assertEqual(response.status_code, 200)
        self.assertTrue(
            NetworkHealth.objects.filter(
                device__user=self.user,
                internet_connected=True,
            ).exists()
        )

    def test_bandwidth_endpoint_saves_data_for_authenticated_device(self):
        response = self.client.post(
            reverse("ingest_bandwidth"),
            data=json.dumps({
                "download_speed": 100,
                "upload_speed": 20,
                "ping": 10,
                "packet_loss": 0,
            }),
            content_type="application/json",
            HTTP_AUTHORIZATION=f"Bearer {self.token}",
        )

        self.assertEqual(response.status_code, 201)

        test = BandwidthTest.objects.get(
            device__user=self.user,
        )

        self.assertEqual(test.download_speed, 100)
        self.assertEqual(test.upload_speed, 20)
