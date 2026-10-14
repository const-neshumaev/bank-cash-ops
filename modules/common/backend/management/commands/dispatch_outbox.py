import time

from django.core.management.base import BaseCommand

from modules.common.backend import outbox


class Command(BaseCommand):
    """Deliver the pending outbox events to their subscribers."""

    help = "Deliver the pending outbox events to their subscribers."

    def add_arguments(self, parser):
        parser.add_argument("--loop", action="store_true", help="Poll continuously.")
        parser.add_argument(
            "--interval",
            type=float,
            default=2.0,
            help="Seconds between polls in loop mode (default: 2).",
        )
        parser.add_argument("--limit", type=int, default=100, help="Max events per poll.")

    def handle(self, *args, **options):
        if options["loop"]:
            self.stdout.write("Dispatching outbox events in a loop. Press Ctrl+C to stop.")
            while True:
                outbox.dispatch_pending(limit=options["limit"])
                time.sleep(options["interval"])
        delivered = outbox.dispatch_pending(limit=options["limit"])
        self.stdout.write(self.style.SUCCESS(f"Delivered {delivered} events."))
