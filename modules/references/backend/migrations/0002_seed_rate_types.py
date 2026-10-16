"""Seed the system rate types (one per principle).

Each seeded rate type is a system row (``is_system=True``) so it cannot be
deleted from the API; a bank may add its own rate types alongside them. See
``docs/adr/0017-references-module.md``.
"""

from django.db import migrations

RATE_TYPES = [
    # (code, name (ru), principle, order, english name)
    ("official", "Курс Национального банка", "official", 0, "National bank rate"),
    ("buy", "Курс покупки", "buy", 1, "Buy rate"),
    ("sell", "Курс продажи", "sell", 2, "Sell rate"),
    ("conversion", "Курс конверсии", "conversion", 3, "Conversion rate"),
]


def seed_rate_types(apps, schema_editor):
    CurrencyRateType = apps.get_model("references", "CurrencyRateType")
    CurrencyRateTypeTranslation = apps.get_model("references", "CurrencyRateTypeTranslation")
    for code, name, principle, order, english_name in RATE_TYPES:
        rate_type, _created = CurrencyRateType.objects.get_or_create(
            code=code,
            defaults={
                "name": name,
                "principle": principle,
                "is_system": True,
                "is_active": True,
                "order": order,
            },
        )
        CurrencyRateTypeTranslation.objects.get_or_create(
            rate_type=rate_type,
            language="en",
            defaults={"name": english_name},
        )


def unseed_rate_types(apps, schema_editor):
    CurrencyRateType = apps.get_model("references", "CurrencyRateType")
    CurrencyRateType.objects.filter(code__in=[row[0] for row in RATE_TYPES]).delete()


class Migration(migrations.Migration):

    dependencies = [
        ("references", "0001_initial"),
    ]

    operations = [
        migrations.RunPython(seed_rate_types, unseed_rate_types),
    ]
