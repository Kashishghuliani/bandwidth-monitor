
import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        (
            "monitor",
            "0008_device_bandwidthtest_device_networkhealth_device_and_more",
        ),
    ]

    operations = [
        migrations.DeleteModel(
            name="BandwidthTest",
        ),
        migrations.DeleteModel(
            name="NetworkHealth",
        ),
        migrations.DeleteModel(
            name="Device",
        ),
        migrations.CreateModel(
            name="TargetIP",
            fields=[
                (
                    "id",
                    models.BigAutoField(
                        auto_created=True,
                        primary_key=True,
                        serialize=False,
                        verbose_name="ID",
                    ),
                ),
                ("name", models.CharField(max_length=100)),
                ("ip_address", models.GenericIPAddressField(unique=True)),
                ("is_active", models.BooleanField(default=True)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
            ],
            options={
                "verbose_name": "Target IP",
                "verbose_name_plural": "Target IPs",
                "ordering": ["name"],
            },
        ),
        migrations.CreateModel(
            name="IPCheckResult",
            fields=[
                (
                    "id",
                    models.BigAutoField(
                        auto_created=True,
                        primary_key=True,
                        serialize=False,
                        verbose_name="ID",
                    ),
                ),
                ("checked_at", models.DateTimeField(auto_now_add=True)),
                ("is_reachable", models.BooleanField(default=False)),
                ("latency_ms", models.FloatField(blank=True, null=True)),
                ("packet_loss_percent", models.FloatField(blank=True, null=True)),
                (
                    "status",
                    models.CharField(
                        choices=[
                            ("healthy", "Healthy"),
                            ("warning", "Warning"),
                            ("offline", "Offline"),
                        ],
                        default="offline",
                        max_length=20,
                    ),
                ),
                ("error_message", models.TextField(blank=True)),
                (
                    "target",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="check_results",
                        to="monitor.targetip",
                    ),
                ),
            ],
            options={
                "ordering": ["-checked_at"],
            },
        ),
        migrations.AddIndex(
            model_name="ipcheckresult",
            index=models.Index(
                fields=["target", "-checked_at"],
                name="ipcheck_target_time_idx",
            ),
        ),
    ]
