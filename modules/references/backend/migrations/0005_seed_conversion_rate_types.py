"""Seed the buy and sell rate types used for direct conversion pairs.

Direct conversion is quoted as a pair (for example EUR/USD) and has two sides:
the bank buys and sells the base currency of the pair. These two system types
keep conversion quotes separate from the ordinary buy and sell rates against the
national currency.
"""

from django.db import migrations

RATE_TYPES = [
    # (code, name (ru), english name, order)
    ("conversion_buy", "Покупка (конверсия)", "Conversion buy", 4),
    ("conversion_sell", "Продажа (конверсия)", "Conversion sell", 5),
]


def seed(apps, schema_editor):
    CurrencyRateType = apps.get_model("references", "CurrencyRateType")
    Translation = apps.get_model("references", "CurrencyRateTypeTranslation")
    for code, name, english_name, order in RATE_TYPES:
        rate_type, _created = CurrencyRateType.objects.get_or_create(
            code=code,
            defaults={
                "name": name,
                "principle": "conversion",
                "validity": "since_set",
                "daily_required": False,
                "is_system": True,
                "is_active": True,
                "order": order,
            },
        )
        Translation.objects.get_or_create(
            rate_type=rate_type,
            language="en",
            defaults={"name": english_name},
        )


def unseed(apps, schema_editor):
    CurrencyRateType = apps.get_model("references", "CurrencyRateType")
    CurrencyRateType.objects.filter(code__in=[row[0] for row in RATE_TYPES]).delete()


class Migration(migrations.Migration):

    dependencies = [
        ("references", "0004_set_rate_type_defaults"),
    ]

    operations = [
        migrations.RunPython(seed, unseed),
    ]
