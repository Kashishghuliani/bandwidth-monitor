
from django.core.management.base import BaseCommand, CommandError

from monitor.models import Device


class Command(BaseCommand):
    help = (
        "List registered monitoring devices. "
        "Bandwidth tests should run through each device's Windows agent."
    )

    def add_arguments(self, parser):
        parser.add_argument(
            "--device-id",
            type=str,
            help="Optional UUID of a registered device.",
        )

    def handle(self, *args, **options):
        devices = Device.objects.all().order_by("name")

        device_id = options.get("device_id")
        if device_id:
            devices = devices.filter(device_id=device_id)

        if not devices.exists():
            raise CommandError("No matching registered devices were found.")

        self.stdout.write(
            self.style.SUCCESS("Registered monitoring devices:")
        )

        for device in devices:
            self.stdout.write(
                f"- {device.name} | "
                f"ID: {device.device_id} | "
                f"Owner: {device.user.username} | "
                f"Active: {device.is_active}"
            )

        self.stdout.write(
            "\nThis command does not run a speed test. "
            "The Windows agent runs tests locally and uploads results "
            "to the Django API."
        )
