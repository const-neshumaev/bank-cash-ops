"""Load the ISO 4217 currency catalogue into the reference data.

The command is idempotent: it creates missing currencies, fills the ISO numeric
code on rows that do not have one yet, and adds the English translation. Existing
rows (including any bank edits to the name or symbol) are left untouched. The
catalogue itself lives in :mod:`modules.references.backend.catalogue.iso4217`.
"""

from __future__ import annotations

from django.core.management.base import BaseCommand
from django.db import transaction

from modules.references.backend.catalogue.iso4217 import ISO_CURRENCIES
from modules.references.backend.models import Currency, CurrencyTranslation


class Command(BaseCommand):
    help = "Load the ISO 4217 currency catalogue (idempotent)."

    @transaction.atomic
    def handle(self, *args, **options):
        created = updated = translations = 0
        for code, numeric_code, minor_units, name, english_name in ISO_CURRENCIES:
            currency, was_created = Currency.objects.get_or_create(
                code=code,
                defaults={
                    "numeric_code": numeric_code,
                    "name": name,
                    "minor_units": minor_units,
                    "is_active": True,
                },
            )
            if was_created:
                created += 1
            elif not currency.numeric_code:
                currency.numeric_code = numeric_code
                currency.save(update_fields=["numeric_code"])
                updated += 1
            _, translation_created = CurrencyTranslation.objects.get_or_create(
                currency=currency,
                language="en",
                defaults={"name": english_name},
            )
            translations += int(translation_created)

        self.stdout.write(
            self.style.SUCCESS(
                f"ISO 4217 catalogue loaded: {created} created, {updated} updated, "
                f"{translations} translations added."
            )
        )
