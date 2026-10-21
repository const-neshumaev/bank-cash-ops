"""Apply the principle-dependent defaults to the existing rate types.

The official (national bank) rate is stored per calendar day and is required for
every operation date. The other principles keep the historical "since set"
semantics and are not required daily. New rate types get the same defaults from
the API and the administration form.
"""

from django.db import migrations


def set_defaults(apps, schema_editor):
    CurrencyRateType = apps.get_model("references", "CurrencyRateType")
    for rate_type in CurrencyRateType.objects.all():
        if rate_type.principle == "official":
            rate_type.validity = "calendar_day"
            rate_type.daily_required = True
        else:
            rate_type.validity = "since_set"
            rate_type.daily_required = False
        rate_type.save(update_fields=["validity", "daily_required"])


def restore(apps, schema_editor):
    CurrencyRateType = apps.get_model("references", "CurrencyRateType")
    CurrencyRateType.objects.update(validity="since_set", daily_required=False)


class Migration(migrations.Migration):

    dependencies = [
        ("references", "0003_currencyratetype_daily_required_and_more"),
    ]

    operations = [
        migrations.RunPython(set_defaults, restore),
    ]
