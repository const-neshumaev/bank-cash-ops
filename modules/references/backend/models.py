"""Reference data models owned by the ``references`` module.

The module owns the system-wide dictionaries several modules depend on: the
currency catalogue (ISO 4217) and the bank's rate types. Their values cross the
module boundary through the ``ReferenceDirectory`` contract, and other modules
store a currency or rate type by its stable code (never as an ORM relation). See
``docs/adr/0017-references-module.md``.
"""

from __future__ import annotations

from django.core.exceptions import ValidationError
from django.db import models
from django.utils.translation import gettext_lazy as _

from modules.common.backend.i18n import pick_translation
from modules.common.backend.models import TimeStampedModel
from modules.common.backend.schemas import qualified_table
from modules.common.contracts import registry
from modules.references.contracts import (
    RATE_TYPE_USAGE_GUARD,
    CurrencyRatePrinciple,
    RateTypeValidity,
)


class Currency(TimeStampedModel):
    """A currency of the ISO 4217 catalogue the bank works with (reference data).

    The ``code`` is the stable identifier stored in other modules; the name,
    symbol, ISO numeric code and number of minor units are presentation data.
    """

    code = models.CharField(_("code"), max_length=8, unique=True)
    numeric_code = models.CharField(
        _("numeric code"),
        max_length=3,
        blank=True,
        help_text=_("ISO 4217 numeric code, when the currency has one."),
    )
    name = models.CharField(_("name"), max_length=100)
    symbol = models.CharField(_("symbol"), max_length=8, blank=True)
    minor_units = models.PositiveSmallIntegerField(_("minor units"), default=2)
    is_active = models.BooleanField(_("active"), default=True)

    class Meta:
        verbose_name = _("currency")
        verbose_name_plural = _("currencies")
        db_table = qualified_table("references", "references_currency")
        ordering = ("code",)

    def __str__(self):
        return self.code

    def save(self, *args, **kwargs):
        self.code = (self.code or "").strip().upper()
        return super().save(*args, **kwargs)

    def localized_name(self, language: str | None = None) -> str:
        """Return the currency name for ``language`` (the active one when omitted)."""
        return pick_translation(
            self.name,
            ((t.language, t.name) for t in self.translations.all()),
            language,
        )


class CurrencyTranslation(TimeStampedModel):
    """A localized name of a currency for a single language.

    The base value lives in :attr:`Currency.name`; a row here overrides it for the
    given language. See ``docs/adr/0016-translatable-reference-data.md``.
    """

    currency = models.ForeignKey(
        Currency,
        on_delete=models.CASCADE,
        related_name="translations",
        verbose_name=_("currency"),
    )
    language = models.CharField(_("language"), max_length=8)
    name = models.CharField(_("name"), max_length=100)

    class Meta:
        verbose_name = _("currency translation")
        verbose_name_plural = _("currency translations")
        db_table = qualified_table("references", "references_currencytranslation")
        constraints = (
            models.UniqueConstraint(
                fields=["currency", "language"],
                name="references_unique_currency_translation",
            ),
        )

    def __str__(self):
        return f"{self.currency} ({self.language})"


class CurrencyRateType(TimeStampedModel):
    """A bank-managed kind of exchange rate.

    A rate type carries a bank-chosen ``name`` and points at one of the fixed
    :class:`~modules.references.contracts.CurrencyRatePrinciple` values. Several
    rate types may share a principle, which lets a cashier pick among, say, the
    cash and non-cash buying rates of the same currency. The seeded system rate
    types (one per principle) are shipped with the product; bank-added ones are
    ordinary content.
    """

    class Principle(models.TextChoices):
        OFFICIAL = CurrencyRatePrinciple.OFFICIAL, _("Official")
        BUY = CurrencyRatePrinciple.BUY, _("Buy")
        SELL = CurrencyRatePrinciple.SELL, _("Sell")
        CONVERSION = CurrencyRatePrinciple.CONVERSION, _("Conversion")

    class Validity(models.TextChoices):
        CALENDAR_DAY = RateTypeValidity.CALENDAR_DAY, _("Calendar day")
        SINCE_SET = RateTypeValidity.SINCE_SET, _("Since set")

    code = models.SlugField(_("code"), max_length=64, unique=True)
    name = models.CharField(_("name"), max_length=150)
    principle = models.CharField(
        _("principle"),
        max_length=16,
        choices=Principle.choices,
        default=Principle.OFFICIAL,
    )
    validity = models.CharField(
        _("rate validity"),
        max_length=16,
        choices=Validity.choices,
        default=Validity.SINCE_SET,
        help_text=_(
            "Calendar day keeps one active rate per date; since set applies a rate "
            "from an explicit date and time."
        ),
    )
    daily_required = models.BooleanField(
        _("daily required"),
        default=False,
        help_text=_("A rate of this type must exist for the date of the operation."),
    )
    is_system = models.BooleanField(
        _("system rate type"),
        default=False,
        help_text=_("System rate types are shipped with the product and cannot be deleted."),
    )
    is_active = models.BooleanField(_("active"), default=True)
    order = models.PositiveSmallIntegerField(_("order"), default=0)

    class Meta:
        verbose_name = _("rate type")
        verbose_name_plural = _("rate types")
        db_table = qualified_table("references", "references_currencyratetype")
        ordering = ("order", "code")

    def __str__(self):
        return self.name

    @classmethod
    def default_validity(cls, principle: str) -> str:
        """Return the default validity for a principle: official rates are daily."""
        if principle == CurrencyRatePrinciple.OFFICIAL:
            return RateTypeValidity.CALENDAR_DAY
        return RateTypeValidity.SINCE_SET

    @classmethod
    def default_daily_required(cls, principle: str) -> bool:
        """Return the default daily requirement: only the official rate is daily."""
        return principle == CurrencyRatePrinciple.OFFICIAL

    def localized_name(self, language: str | None = None) -> str:
        """Return the name in ``language`` (the active one when omitted)."""
        return pick_translation(
            self.name,
            ((t.language, t.name) for t in self.translations.all()),
            language,
        )

    def clean(self):
        """Keep the storage semantics stable once rates of this type exist."""
        super().clean()
        if self.pk is None:
            return
        previous = type(self).objects.filter(pk=self.pk).values_list("validity", flat=True).first()
        if previous is None or previous == self.validity:
            return
        try:
            guard = registry.get(RATE_TYPE_USAGE_GUARD)
        except LookupError:
            return
        if guard.is_rate_type_used(self.code):
            raise ValidationError(
                {
                    "validity": _(
                        "The rate validity cannot be changed while rates of this type exist."
                    )
                }
            )

    def save(self, *args, **kwargs):
        self.clean()
        return super().save(*args, **kwargs)


class CurrencyRateTypeTranslation(TimeStampedModel):
    """A localized name of a rate type for a single language.

    The base value lives in :attr:`CurrencyRateType.name`; this table holds the
    translations of the system rate types. Bank-added rate types are content and
    are not translated. See ``docs/adr/0016-translatable-reference-data.md``.
    """

    rate_type = models.ForeignKey(
        CurrencyRateType,
        on_delete=models.CASCADE,
        related_name="translations",
        verbose_name=_("rate type"),
    )
    language = models.CharField(_("language"), max_length=8)
    name = models.CharField(_("name"), max_length=150)

    class Meta:
        verbose_name = _("rate type translation")
        verbose_name_plural = _("rate type translations")
        db_table = qualified_table("references", "references_currencyratetypetranslation")
        constraints = (
            models.UniqueConstraint(
                fields=["rate_type", "language"],
                name="references_unique_rate_type_translation",
            ),
        )

    def __str__(self):
        return f"{self.rate_type} ({self.language})"
