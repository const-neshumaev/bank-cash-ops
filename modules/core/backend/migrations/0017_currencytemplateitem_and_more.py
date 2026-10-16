"""Move the currency catalogue to ``references`` and switch ``core`` to codes.

The currency catalogue (``Currency`` / ``CurrencyTranslation``) moves to the
``references`` module, and the ``core`` tables that referenced a currency switch
from a foreign key to a plain ISO code (see ``docs/adr/0017-references-module.md``).
The migration therefore copies the catalogue first, backfills the new code
columns from the old foreign keys, and only then drops the old columns and
models. The ``rate_type`` values are renamed to the new principle codes
(``central`` -> ``official``).
"""

import django.db.models.deletion
from django.db import migrations, models


def copy_currencies_to_references(apps, schema_editor):
    """Copy the currency catalogue (and its translations) into ``references``."""
    Currency = apps.get_model("core", "Currency")
    RefCurrency = apps.get_model("references", "Currency")
    CurrencyTranslation = apps.get_model("core", "CurrencyTranslation")
    RefTranslation = apps.get_model("references", "CurrencyTranslation")

    code_to_ref = {}
    for currency in Currency.objects.order_by("id"):
        ref = RefCurrency.objects.create(
            code=currency.code,
            numeric_code="",
            name=currency.name,
            symbol=currency.symbol or "",
            minor_units=currency.minor_units,
            is_active=currency.is_active,
        )
        code_to_ref[currency.code] = ref.id

    code_by_id = dict(Currency.objects.values_list("id", "code"))
    for translation in CurrencyTranslation.objects.all():
        RefTranslation.objects.create(
            currency_id=code_to_ref[code_by_id[translation.currency_id]],
            language=translation.language,
            name=translation.name,
        )


def clear_references(apps, schema_editor):
    """Remove the rows copied into ``references`` (reverse of the copy)."""
    apps.get_model("references", "CurrencyTranslation").objects.all().delete()
    apps.get_model("references", "Currency").objects.all().delete()


def backfill_cash_desk_currency(apps, schema_editor):
    """Fill ``core_cashdeskcurrency.currency_code`` from the old foreign key."""
    with schema_editor.connection.cursor() as cursor:
        cursor.execute(
            'UPDATE "core"."core_cashdeskcurrency" AS cdc '
            "SET currency_code = cur.code "
            'FROM "core"."core_currency" AS cur '
            "WHERE cdc.currency_id = cur.id"
        )


def backfill_template_items(apps, schema_editor):
    """Turn the ``CurrencyTemplate.currencies`` many-to-many into template items."""
    with schema_editor.connection.cursor() as cursor:
        cursor.execute(
            'INSERT INTO "core"."core_currencytemplateitem" '
            "(created_at, updated_at, template_id, currency_code) "
            "SELECT now(), now(), tcc.currencytemplate_id, cur.code "
            'FROM "core"."core_currencytemplate_currencies" AS tcc '
            'JOIN "core"."core_currency" AS cur ON cur.id = tcc.currency_id'
        )


def backfill_currency_rate_codes(apps, schema_editor):
    """Fill the rate code columns from the old currency foreign keys."""
    with schema_editor.connection.cursor() as cursor:
        cursor.execute(
            'UPDATE "core"."core_currencyrate" AS r '
            "SET currency_code = c.code, base_currency_code = b.code "
            'FROM "core"."core_currency" AS c, "core"."core_currency" AS b '
            "WHERE r.currency_id = c.id AND r.base_currency_id = b.id"
        )


def map_rate_types(apps, schema_editor):
    """Rename the legacy ``central`` rate type to the ``official`` principle."""
    with schema_editor.connection.cursor() as cursor:
        cursor.execute(
            'UPDATE "core"."core_currencyrate" '
            "SET rate_type = 'official' WHERE rate_type = 'central'"
        )


def noop(apps, schema_editor):
    pass


class Migration(migrations.Migration):

    dependencies = [
        ("core", "0016_seed_currency_translations"),
        ("references", "0001_initial"),
    ]

    operations = [
        # 1. Copy the catalogue into the references schema.
        migrations.RunPython(copy_currencies_to_references, clear_references),
        # 2. Cash desk currencies: reference by code.
        migrations.AddField(
            model_name="cashdeskcurrency",
            name="currency_code",
            field=models.CharField(max_length=8, null=True, verbose_name="currency"),
        ),
        migrations.RunPython(backfill_cash_desk_currency, noop),
        migrations.RemoveConstraint(
            model_name="cashdeskcurrency",
            name="core_unique_cash_desk_currency",
        ),
        migrations.RemoveField(
            model_name="cashdeskcurrency",
            name="currency",
        ),
        migrations.AlterModelOptions(
            name="cashdeskcurrency",
            options={
                "ordering": ("currency_code",),
                "verbose_name": "cash desk currency",
                "verbose_name_plural": "cash desk currencies",
            },
        ),
        migrations.AlterField(
            model_name="cashdeskcurrency",
            name="currency_code",
            field=models.CharField(max_length=8, verbose_name="currency"),
        ),
        migrations.AddConstraint(
            model_name="cashdeskcurrency",
            constraint=models.UniqueConstraint(
                fields=("cash_desk", "currency_code"), name="core_unique_cash_desk_currency"
            ),
        ),
        # 3. Currency templates: the many-to-many becomes explicit items.
        migrations.CreateModel(
            name="CurrencyTemplateItem",
            fields=[
                (
                    "id",
                    models.BigAutoField(
                        auto_created=True, primary_key=True, serialize=False, verbose_name="ID"
                    ),
                ),
                ("created_at", models.DateTimeField(auto_now_add=True, verbose_name="created at")),
                ("updated_at", models.DateTimeField(auto_now=True, verbose_name="updated at")),
                ("currency_code", models.CharField(max_length=8, verbose_name="currency")),
            ],
            options={
                "verbose_name": "currency template item",
                "verbose_name_plural": "currency template items",
                "db_table": '"core"."core_currencytemplateitem"',
                "ordering": ("currency_code",),
            },
        ),
        migrations.AddField(
            model_name="currencytemplateitem",
            name="template",
            field=models.ForeignKey(
                on_delete=django.db.models.deletion.CASCADE,
                related_name="items",
                to="core.currencytemplate",
                verbose_name="template",
            ),
        ),
        migrations.RunPython(backfill_template_items, noop),
        migrations.RemoveField(
            model_name="currencytemplate",
            name="currencies",
        ),
        migrations.AddConstraint(
            model_name="currencytemplateitem",
            constraint=models.UniqueConstraint(
                fields=("template", "currency_code"), name="core_unique_currency_template_item"
            ),
        ),
        # 4. Currency rates: currencies and rate type become codes.
        migrations.AddField(
            model_name="currencyrate",
            name="currency_code",
            field=models.CharField(max_length=8, null=True, verbose_name="currency"),
        ),
        migrations.AddField(
            model_name="currencyrate",
            name="base_currency_code",
            field=models.CharField(max_length=8, null=True, verbose_name="base currency"),
        ),
        migrations.RunPython(backfill_currency_rate_codes, noop),
        migrations.RemoveField(
            model_name="currencyrate",
            name="currency",
        ),
        migrations.RemoveField(
            model_name="currencyrate",
            name="base_currency",
        ),
        migrations.RenameField(
            model_name="currencyrate",
            old_name="currency_code",
            new_name="currency",
        ),
        migrations.RenameField(
            model_name="currencyrate",
            old_name="base_currency_code",
            new_name="base_currency",
        ),
        migrations.RunPython(map_rate_types, noop),
        migrations.AlterField(
            model_name="currencyrate",
            name="rate_type",
            field=models.CharField(default="official", max_length=32, verbose_name="rate type"),
        ),
        migrations.AlterField(
            model_name="currencyrate",
            name="currency",
            field=models.CharField(max_length=8, verbose_name="currency"),
        ),
        migrations.AlterField(
            model_name="currencyrate",
            name="base_currency",
            field=models.CharField(max_length=8, verbose_name="base currency"),
        ),
        migrations.AlterModelOptions(
            name="currencyrate",
            options={
                "ordering": ("currency", "rate_type", "-effective_from"),
                "verbose_name": "currency rate",
                "verbose_name_plural": "currency rates",
            },
        ),
        # 5. Bank-wide base currency.
        migrations.AddField(
            model_name="banksettings",
            name="base_currency",
            field=models.CharField(default="BYN", max_length=8, verbose_name="base currency"),
        ),
        # 6. Drop the moved models from core.
        migrations.DeleteModel(
            name="CurrencyTranslation",
        ),
        migrations.DeleteModel(
            name="Currency",
        ),
    ]
