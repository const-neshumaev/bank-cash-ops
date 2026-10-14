from django.db import migrations

# Currencies are inlined on purpose: a migration must keep behaving the same way
# even if the application code evolves later.
CURRENCIES = [
    {"code": "BYN", "name": "Белорусский рубль", "symbol": "Br", "minor_units": 2},
    {"code": "USD", "name": "Доллар США", "symbol": "$", "minor_units": 2},
    {"code": "EUR", "name": "Евро", "symbol": "€", "minor_units": 2},
    {"code": "RUB", "name": "Российский рубль", "symbol": "₽", "minor_units": 2},
]


def seed_currencies(apps, schema_editor):
    Currency = apps.get_model("core", "Currency")
    for definition in CURRENCIES:
        Currency.objects.get_or_create(
            code=definition["code"],
            defaults={
                "name": definition["name"],
                "symbol": definition["symbol"],
                "minor_units": definition["minor_units"],
                "is_active": True,
            },
        )


def unseed_currencies(apps, schema_editor):
    Currency = apps.get_model("core", "Currency")
    Currency.objects.filter(code__in=[definition["code"] for definition in CURRENCIES]).delete()


class Migration(migrations.Migration):

    dependencies = [
        ("core", "0008_currency_cashdeskcurrency"),
    ]

    operations = [
        migrations.RunPython(seed_currencies, unseed_currencies),
    ]
