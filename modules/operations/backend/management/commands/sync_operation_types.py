from django.core.management.base import BaseCommand

from modules.operations.backend.sync import sync_operation_types


class Command(BaseCommand):
    """Create or update the operation types declared by the installed modules."""

    help = "Create or update the operation types declared by the installed modules."

    def handle(self, *args, **options):
        synced = sync_operation_types()
        self.stdout.write(self.style.SUCCESS(f"Synced {synced} operation types."))
