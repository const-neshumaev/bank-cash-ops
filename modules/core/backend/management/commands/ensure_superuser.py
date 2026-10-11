import os

from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand


class Command(BaseCommand):
    """Create the initial administrator from environment variables.

    The command is idempotent: it does nothing when the account already exists,
    which makes it safe to call from the container entrypoint on every start.
    """

    help = "Create the initial administrator account if it is missing."

    def handle(self, *args, **options):
        user_model = get_user_model()

        email = os.environ.get("DJANGO_SUPERUSER_EMAIL")
        password = os.environ.get("DJANGO_SUPERUSER_PASSWORD")

        if not email or not password:
            self.stdout.write(
                "DJANGO_SUPERUSER_EMAIL/DJANGO_SUPERUSER_PASSWORD are not set; "
                "skipping the initial administrator."
            )
            return

        if user_model.objects.filter(email=email).exists():
            self.stdout.write(f"The account {email} already exists; nothing to do.")
            return

        user_model.objects.create_superuser(
            email=email,
            password=password,
            first_name=os.environ.get("DJANGO_SUPERUSER_FIRST_NAME", "System"),
            last_name=os.environ.get("DJANGO_SUPERUSER_LAST_NAME", "Administrator"),
        )
        self.stdout.write(self.style.SUCCESS(f"The administrator {email} has been created."))
