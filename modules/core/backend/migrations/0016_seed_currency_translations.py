from django.db import migrations

# English names are inlined on purpose: a migration must keep behaving the same
# way even if the application code evolves later.
TRANSLATIONS = [
    ("BYN", "Belarusian ruble"),
    ("USD", "US dollar"),
    ("EUR", "Euro"),
    ("RUB", "Russian ruble"),
]


def seed_currency_translations(apps, schema_editor):
    Currency = apps.get_model("core", "Currency")
    CurrencyTranslation = apps.get_model("core", "CurrencyTranslation")
    for code, name in TRANSLATIONS:
        currency = Currency.objects.filter(code=code).first()
        if currency is None:
            continue
        CurrencyTranslation.objects.get_or_create(
            currency=currency,
            language="en",
            defaults={"name": name},
        )


def unseed_currency_translations(apps, schema_editor):
    CurrencyTranslation = apps.get_model("core", "CurrencyTranslation")
    codes = [code for code, _ in TRANSLATIONS]
    CurrencyTranslation.objects.filter(currency__code__in=codes, language="en").delete()


class Migration(migrations.Migration):

    dependencies = [
        ("core", "0015_currencytranslation"),
    ]

    operations = [
        migrations.RunPython(seed_currency_translations, unseed_currency_translations),
    ]
