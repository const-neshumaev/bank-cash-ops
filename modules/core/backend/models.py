from datetime import datetime, time

from django.conf import settings
from django.contrib.auth.models import AbstractUser
from django.core.exceptions import ValidationError
from django.core.validators import RegexValidator
from django.db import models
from django.utils import timezone
from django.utils.functional import cached_property
from django.utils.translation import gettext_lazy as _

from modules.common.backend.models import TimeStampedModel
from modules.common.backend.schemas import qualified_table
from modules.common.contracts import registry
from modules.core.backend.managers import UserManager
from modules.core.backend.permission_codes import PermissionCode
from modules.references.contracts import (
    REFERENCE_DIRECTORY,
    CurrencyRatePrinciple,
    RateTypeValidity,
)

mac_address_validator = RegexValidator(
    regex=r"^([0-9A-Fa-f]{2}:){5}[0-9A-Fa-f]{2}$",
    message=_("Enter a MAC address in the form AA:BB:CC:DD:EE:FF."),
)


class Role(TimeStampedModel):
    """A named set of permissions that can be assigned to users.

    Roles are data: administrators create and edit them, so the set of roles is
    not fixed by the code. The permission codes a role grants are stored as a
    validated list drawn from the catalog in
    :mod:`modules.core.backend.permission_codes`.
    """

    code = models.SlugField(_("code"), max_length=64, unique=True)
    name = models.CharField(_("name"), max_length=150)
    description = models.TextField(_("description"), blank=True)
    permissions = models.JSONField(_("permissions"), default=list, blank=True)
    is_system = models.BooleanField(
        _("system role"),
        default=False,
        help_text=_("System roles are shipped with the product and cannot be deleted."),
    )

    class Meta:
        verbose_name = _("role")
        verbose_name_plural = _("roles")
        db_table = qualified_table("core", "core_role")
        ordering = ("name",)

    def __str__(self):
        return self.name


class User(AbstractUser):
    """Application user that authenticates with an email address.

    The legacy ``username`` field is removed; users are identified by their
    unique email. A user may hold several roles, and the union of their
    permissions decides what the person is allowed to do.
    """

    username = None
    email = models.EmailField(_("email address"), unique=True)
    first_name = models.CharField(_("first name"), max_length=150)
    last_name = models.CharField(_("last name"), max_length=150)
    middle_name = models.CharField(_("middle name"), max_length=150, blank=True)
    phone = models.CharField(_("phone number"), max_length=32, blank=True)
    language = models.CharField(
        _("language"),
        max_length=8,
        blank=True,
        help_text=_("Empty means the bank-wide default language."),
    )
    roles = models.ManyToManyField(
        "core.Role",
        related_name="users",
        blank=True,
        verbose_name=_("roles"),
    )

    USERNAME_FIELD = "email"
    REQUIRED_FIELDS = ["first_name", "last_name"]

    objects = UserManager()

    class Meta:
        verbose_name = _("user")
        verbose_name_plural = _("users")
        db_table = qualified_table("core", "core_user")
        ordering = ("last_name", "first_name", "email")

    def __str__(self):
        return self.full_name or self.email

    @property
    def full_name(self):
        """Return the display name built from the available name parts."""
        parts = [self.last_name, self.first_name, self.middle_name]
        return " ".join(part for part in parts if part).strip()

    @cached_property
    def permission_codes(self) -> frozenset[str]:
        """Return the union of the permission codes granted by the user's roles."""
        codes: set[str] = set()
        for role in self.roles.all():
            codes.update(role.permissions or [])
        return frozenset(codes)

    def has_permission(self, code: str) -> bool:
        """Return whether the user is allowed to perform the action ``code``."""
        return bool(self.is_superuser or code in self.permission_codes)

    @property
    def is_admin(self):
        """Whether the user is allowed to administer the system."""
        return bool(self.is_superuser or self.has_permission(PermissionCode.USERS_MANAGE))


class Branch(TimeStampedModel):
    """A bank branch; branches form a tree up to a single head office."""

    parent = models.ForeignKey(
        "self",
        null=True,
        blank=True,
        on_delete=models.PROTECT,
        related_name="children",
        verbose_name=_("parent branch"),
    )
    code = models.CharField(_("code"), max_length=32, unique=True, null=True, blank=True)
    name = models.CharField(_("name"), max_length=255)
    address = models.CharField(_("address"), max_length=255, blank=True)
    phone = models.CharField(_("phone number"), max_length=32, blank=True)
    is_head_office = models.BooleanField(_("head office"), default=False)
    is_active = models.BooleanField(_("active"), default=True)
    uses_individual_rates = models.BooleanField(
        _("uses individual rates"),
        default=False,
        help_text=_(
            "The branch uses only its own and lower-level rates; bank and parent rates "
            "do not apply."
        ),
    )

    class Meta:
        verbose_name = _("branch")
        verbose_name_plural = _("branches")
        db_table = qualified_table("core", "core_branch")
        ordering = ("name",)
        constraints = (
            models.UniqueConstraint(
                fields=["is_head_office"],
                condition=models.Q(is_head_office=True),
                name="core_unique_head_office",
            ),
        )

    def __str__(self):
        return self.name

    def ancestors(self):
        """Yield the parent chain from the immediate parent up to the root."""
        node = self.parent
        seen: set[int] = set()
        while node is not None:
            if node.pk in seen:
                break
            seen.add(node.pk)
            yield node
            node = node.parent

    def clean(self):
        """Validate the branch position in the hierarchy."""
        super().clean()
        # An empty code means "no internal bank identifier", stored as NULL so
        # several branches can omit it under the unique constraint.
        self.code = (self.code or "").strip() or None
        if self.is_head_office and self.parent_id is not None:
            raise ValidationError({"parent": _("The head office cannot have a parent.")})
        if not self.is_head_office and self.parent_id is None:
            raise ValidationError({"parent": _("Only the head office can have no parent.")})
        if self.pk is not None and self.parent_id is not None:
            if any(ancestor.pk == self.pk for ancestor in self.ancestors()):
                raise ValidationError({"parent": _("A branch cannot be its own ancestor.")})

    def save(self, *args, **kwargs):
        self.clean()
        return super().save(*args, **kwargs)


class BranchAccess(TimeStampedModel):
    """Grants a user visibility of a branch, optionally with its descendants.

    Access is data-driven and configured by the bank administrator. A user
    without any record sees no branches (deny-by-default); a superuser always
    sees every branch. The ``include_descendants`` flag expands the access to
    the whole subtree of the selected branch.
    """

    user = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name="branch_access",
        verbose_name=_("user"),
    )
    branch = models.ForeignKey(
        Branch,
        on_delete=models.CASCADE,
        related_name="user_access",
        verbose_name=_("branch"),
    )
    include_descendants = models.BooleanField(
        _("include child branches"),
        default=False,
        help_text=_("Also grant access to every child branch of this branch."),
    )

    class Meta:
        verbose_name = _("branch access")
        verbose_name_plural = _("branch access")
        db_table = qualified_table("core", "core_branchaccess")
        ordering = ("branch__name",)
        constraints = (
            models.UniqueConstraint(
                fields=["user", "branch"],
                name="core_unique_user_branch_access",
            ),
        )

    def __str__(self):
        return f"{self.user} → {self.branch}"


class CashDesk(TimeStampedModel):
    """A cashier workstation; one cash desk corresponds to one computer."""

    branch = models.ForeignKey(
        Branch,
        on_delete=models.PROTECT,
        related_name="cash_desks",
        verbose_name=_("branch"),
    )
    code = models.CharField(_("code"), max_length=32, unique=True, null=True, blank=True)
    name = models.CharField(_("name"), max_length=255)
    mac_address = models.CharField(
        _("MAC address"),
        max_length=17,
        unique=True,
        null=True,
        blank=True,
        validators=[mac_address_validator],
        help_text=_("Network address of the workstation, e.g. AA:BB:CC:DD:EE:FF."),
    )
    hostname = models.CharField(_("hostname"), max_length=255, blank=True)
    is_active = models.BooleanField(_("active"), default=True)
    uses_individual_rates = models.BooleanField(
        _("uses individual rates"),
        default=False,
        help_text=_("The cash desk uses only its own rates; branch and bank rates do not apply."),
    )

    class Meta:
        verbose_name = _("cash desk")
        verbose_name_plural = _("cash desks")
        db_table = qualified_table("core", "core_cashdesk")
        ordering = ("branch__name", "name")

    def __str__(self):
        return self.name

    def clean(self):
        """Normalise the code and MAC address so uniqueness is consistent."""
        super().clean()
        # An empty code means "no internal bank identifier", stored as NULL so
        # several cash desks can omit it under the unique constraint.
        self.code = (self.code or "").strip() or None
        if self.mac_address:
            self.mac_address = self.mac_address.upper()

    def save(self, *args, **kwargs):
        self.clean()
        return super().save(*args, **kwargs)


class Shift(TimeStampedModel):
    """A cashier shift bound to a single cash desk for its whole lifetime.

    A shift is a server-side object independent of the browser session: it stays
    open across reconnects and logins until it is explicitly closed. At most one
    shift may be open per cashier and per cash desk.
    """

    class Status(models.TextChoices):
        OPEN = "open", _("Open")
        CLOSED = "closed", _("Closed")

    cash_desk = models.ForeignKey(
        CashDesk,
        on_delete=models.PROTECT,
        related_name="shifts",
        verbose_name=_("cash desk"),
    )
    cashier = models.ForeignKey(
        User,
        on_delete=models.PROTECT,
        related_name="shifts",
        verbose_name=_("cashier"),
    )
    status = models.CharField(
        _("status"),
        max_length=16,
        choices=Status.choices,
        default=Status.OPEN,
    )
    opened_at = models.DateTimeField(_("opened at"), auto_now_add=True)
    closed_at = models.DateTimeField(_("closed at"), null=True, blank=True)
    closed_by = models.ForeignKey(
        User,
        null=True,
        blank=True,
        on_delete=models.PROTECT,
        related_name="closed_shifts",
        verbose_name=_("closed by"),
    )

    class Meta:
        verbose_name = _("shift")
        verbose_name_plural = _("shifts")
        db_table = qualified_table("core", "core_shift")
        ordering = ("-opened_at",)
        constraints = (
            models.UniqueConstraint(
                fields=["cashier"],
                condition=models.Q(status="open"),
                name="core_unique_open_shift_per_cashier",
            ),
            models.UniqueConstraint(
                fields=["cash_desk"],
                condition=models.Q(status="open"),
                name="core_unique_open_shift_per_cash_desk",
            ),
        )

    def __str__(self):
        return f"{self.cash_desk} @ {self.opened_at:%Y-%m-%d %H:%M}"


class CashDeskCurrency(TimeStampedModel):
    """A currency enabled on a specific cash desk (an explicit override).

    When a cash desk has its own currencies, they replace the effective template;
    a cash desk without its own currencies inherits the nearest currency template
    (see :class:`CurrencyTemplate`). With neither, no currency is allowed.
    """

    cash_desk = models.ForeignKey(
        CashDesk,
        on_delete=models.CASCADE,
        related_name="allowed_currencies",
        verbose_name=_("cash desk"),
    )
    currency_code = models.CharField(_("currency"), max_length=8)

    class Meta:
        verbose_name = _("cash desk currency")
        verbose_name_plural = _("cash desk currencies")
        db_table = qualified_table("core", "core_cashdeskcurrency")
        ordering = ("currency_code",)
        constraints = (
            models.UniqueConstraint(
                fields=["cash_desk", "currency_code"],
                name="core_unique_cash_desk_currency",
            ),
        )

    def __str__(self):
        return f"{self.cash_desk} — {self.currency_code}"


class CurrencyTemplate(TimeStampedModel):
    """A default set of cash desk currencies, for the bank or a branch.

    A template without a branch is the bank-wide default; a template with a branch
    applies to that branch and its descendants, and a closer template overrides a
    farther one. A template that exists but lists no currencies means "no currency
    is allowed" — the absence of any template denies by default as well.
    """

    branch = models.ForeignKey(
        Branch,
        null=True,
        blank=True,
        on_delete=models.CASCADE,
        related_name="currency_templates",
        verbose_name=_("branch"),
        help_text=_("Empty for the bank-wide template."),
    )

    class Meta:
        verbose_name = _("currency template")
        verbose_name_plural = _("currency templates")
        db_table = qualified_table("core", "core_currencytemplate")
        constraints = (
            models.UniqueConstraint(
                fields=["branch"],
                name="core_unique_currency_template_scope",
                nulls_distinct=False,
            ),
        )

    def __str__(self):
        return _("Bank template") if self.branch_id is None else str(self.branch)


class CurrencyTemplateItem(TimeStampedModel):
    """A currency included in a currency template.

    The currency is referenced by its ISO code (owned by the ``references``
    module); the code-based link keeps the modules' data apart (see
    ``docs/adr/0017-references-module.md``).
    """

    template = models.ForeignKey(
        CurrencyTemplate,
        on_delete=models.CASCADE,
        related_name="items",
        verbose_name=_("template"),
    )
    currency_code = models.CharField(_("currency"), max_length=8)

    class Meta:
        verbose_name = _("currency template item")
        verbose_name_plural = _("currency template items")
        db_table = qualified_table("core", "core_currencytemplateitem")
        ordering = ("currency_code",)
        constraints = (
            models.UniqueConstraint(
                fields=["template", "currency_code"],
                name="core_unique_currency_template_item",
            ),
        )

    def __str__(self):
        return f"{self.template} — {self.currency_code}"


class CurrencyRate(TimeStampedModel):
    """An exchange rate of a currency against a base currency.

    A rate is scoped to exactly one level: the bank (``branch`` and ``cash_desk``
    are null), a branch (``branch`` is set) or a cash desk (``cash_desk`` is set).
    A lower-level rate overrides a higher-level one; the ``uses_individual_rates``
    flags of a branch or cash desk cut off the levels above it.

    The bank rate type decides how the rate is stored. With ``calendar_day`` the
    rate is effective for the whole local date and there is at most one active
    rate per date and scope; with ``since_set`` the rate takes effect at
    ``effective_from`` and the latest rate not in the future wins.

    Rates are versioned: a correction of an already active ``calendar_day`` rate
    keeps the old row and marks it ``superseded_at``, so the journal remains
    complete. Only rows with ``superseded_at`` null participate in resolution.

    The currencies and the rate type are referenced by their codes (see
    ``docs/adr/0017-references-module.md``); ``rate_type`` is the code of a bank
    rate type owned by ``references``.
    """

    currency = models.CharField(_("currency"), max_length=8)
    base_currency = models.CharField(_("base currency"), max_length=8)
    branch = models.ForeignKey(
        Branch,
        null=True,
        blank=True,
        on_delete=models.CASCADE,
        related_name="currency_rates",
        verbose_name=_("branch"),
    )
    cash_desk = models.ForeignKey(
        CashDesk,
        null=True,
        blank=True,
        on_delete=models.CASCADE,
        related_name="currency_rates",
        verbose_name=_("cash desk"),
    )
    rate_type = models.CharField(
        _("rate type"),
        max_length=64,
        default=CurrencyRatePrinciple.OFFICIAL,
    )
    units = models.PositiveIntegerField(
        _("units"),
        default=1,
        help_text=_("The quoted value is set for this number of currency units."),
    )
    value = models.DecimalField(_("value"), max_digits=18, decimal_places=6)
    effective_from = models.DateTimeField(_("effective from"))
    effective_date = models.DateField(_("effective date"), null=True, blank=True)
    superseded_at = models.DateTimeField(
        _("superseded at"),
        null=True,
        blank=True,
        help_text=_("When the rate was replaced by a corrected version."),
    )
    created_by = models.ForeignKey(
        User,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="currency_rates_set",
        verbose_name=_("created by"),
    )

    class Meta:
        verbose_name = _("currency rate")
        verbose_name_plural = _("currency rates")
        db_table = qualified_table("core", "core_currencyrate")
        ordering = ("currency", "rate_type", "-effective_from", "-id")
        constraints = (
            models.CheckConstraint(
                condition=~(models.Q(branch__isnull=False) & models.Q(cash_desk__isnull=False)),
                name="core_currency_rate_single_scope",
            ),
            models.CheckConstraint(
                condition=models.Q(units__gte=1),
                name="core_currency_rate_units_positive",
            ),
            models.UniqueConstraint(
                fields=[
                    "currency",
                    "base_currency",
                    "branch",
                    "cash_desk",
                    "rate_type",
                    "effective_date",
                ],
                condition=models.Q(superseded_at__isnull=True, effective_date__isnull=False),
                name="core_unique_calendar_day_rate",
                nulls_distinct=False,
            ),
            models.UniqueConstraint(
                fields=[
                    "currency",
                    "base_currency",
                    "branch",
                    "cash_desk",
                    "rate_type",
                    "effective_from",
                ],
                condition=models.Q(superseded_at__isnull=True, effective_date__isnull=True),
                name="core_unique_since_set_rate",
                nulls_distinct=False,
            ),
        )

    def __str__(self):
        return f"{self.currency}/{self.base_currency} {self.rate_type} = {self.value}"

    @property
    def scope(self) -> str:
        """Return ``bank``, ``branch`` or ``cash_desk`` for the rate."""
        if self.cash_desk_id is not None:
            return "cash_desk"
        if self.branch_id is not None:
            return "branch"
        return "bank"

    @property
    def is_current(self) -> bool:
        """Return whether the row is the active version (not superseded)."""
        return self.superseded_at is None

    def clean(self):
        super().clean()
        self.currency = (self.currency or "").strip().upper()
        self.base_currency = (self.base_currency or "").strip().upper()
        if not self.base_currency:
            self.base_currency = BankSettings.load().base_currency
        if self.currency and self.currency == self.base_currency:
            raise ValidationError(
                {"base_currency": _("The base currency must differ from the currency.")}
            )
        if self.branch_id is not None and self.cash_desk_id is not None:
            raise ValidationError(_("A rate belongs to one scope: bank, branch or cash desk."))
        if self.units is None or self.units < 1:
            raise ValidationError({"units": _("The number of units must be at least one.")})
        if self.value is not None and self.value <= 0:
            raise ValidationError({"value": _("The rate value must be greater than zero.")})

        rate_type = registry.get(REFERENCE_DIRECTORY).get_rate_type(self.rate_type)
        if rate_type is None:
            raise ValidationError({"rate_type": _("Unknown rate type.")})
        if rate_type.principle == CurrencyRatePrinciple.OFFICIAL and (
            self.branch_id is not None or self.cash_desk_id is not None
        ):
            raise ValidationError(
                {"rate_type": _("The national bank rate is set for the whole bank.")}
            )

        bank_settings = BankSettings.load()
        if rate_type.principle == CurrencyRatePrinciple.CONVERSION:
            if (
                bank_settings.conversion_mode == BankSettings.ConversionMode.VIA_BASE
                and self.base_currency != bank_settings.base_currency
            ):
                raise ValidationError(
                    {
                        "base_currency": _(
                            "Conversion through the base currency requires the bank's "
                            "base currency as the quote currency."
                        )
                    }
                )
        elif self.base_currency != bank_settings.base_currency:
            raise ValidationError(
                {
                    "base_currency": _(
                        "Only the bank's base currency can be used as the quote currency "
                        "for this rate type."
                    )
                }
            )

        if rate_type.validity == RateTypeValidity.CALENDAR_DAY:
            if self.effective_date is None and self.effective_from is not None:
                # Historical callers set only the timestamp; a calendar-day rate
                # is stored by its local date.
                if timezone.is_naive(self.effective_from):
                    self.effective_from = timezone.make_aware(
                        self.effective_from, timezone.get_current_timezone()
                    )
                self.effective_date = timezone.localtime(self.effective_from).date()
            if self.effective_date is None:
                raise ValidationError({"effective_date": _("A calendar-day rate requires a date.")})
            self.effective_from = timezone.make_aware(
                datetime.combine(self.effective_date, time.min),
                timezone.get_current_timezone(),
            )
        else:
            if self.effective_date is not None:
                raise ValidationError({"effective_date": _("Only a calendar-day rate has a date.")})
            if self.effective_from is None:
                raise ValidationError(
                    {"effective_from": _("A since-set rate requires a date and time.")}
                )
            if timezone.is_naive(self.effective_from):
                self.effective_from = timezone.make_aware(
                    self.effective_from, timezone.get_current_timezone()
                )

    def save(self, *args, **kwargs):
        self.clean()
        return super().save(*args, **kwargs)


class BaseValue(TimeStampedModel):
    """A bank-wide base value effective from a date.

    Base values are effective-dated: the value in force on a date is the row with
    the greatest ``effective_from`` not after that date. Historical rows are
    append-only — once a row has taken effect it cannot be changed or removed, so
    operations that referred to it stay explainable. The amount is expressed in
    the national (base) currency; the currency code is stored as a snapshot so a
    later change of the bank's base currency does not reinterpret history.
    """

    effective_from = models.DateField(_("effective from"), unique=True)
    amount = models.DecimalField(_("amount"), max_digits=18, decimal_places=2)
    currency_code = models.CharField(_("currency"), max_length=8, blank=True)

    class Meta:
        verbose_name = _("base value")
        verbose_name_plural = _("base values")
        db_table = qualified_table("core", "core_basevalue")
        ordering = ("-effective_from",)

    def __str__(self):
        return f"{self.effective_from}: {self.amount} {self.currency_code}"

    def clean(self):
        super().clean()
        if self.amount is not None and self.amount <= 0:
            raise ValidationError({"amount": _("The amount must be greater than zero.")})

        code = (self.currency_code or "").strip().upper()
        if code:
            directory = registry.get(REFERENCE_DIRECTORY)
            if directory.get_currency(code) is None:
                raise ValidationError({"currency_code": _("Unknown currency.")})
            self.currency_code = code

        if self.pk:
            existing = type(self).objects.filter(pk=self.pk).first()
            if existing is not None and existing.effective_from <= timezone.localdate():
                changed = (
                    existing.effective_from != self.effective_from
                    or existing.amount != self.amount
                    or existing.currency_code != self.currency_code
                )
                if changed:
                    raise ValidationError(_("An effective base value cannot be changed."))

    def save(self, *args, **kwargs):
        if not self.currency_code:
            self.currency_code = BankSettings.load().base_currency
        self.currency_code = (self.currency_code or "").strip().upper()
        self.clean()
        return super().save(*args, **kwargs)

    def delete(self, *args, **kwargs):
        if self.effective_from <= timezone.localdate():
            raise ValidationError(_("An effective base value cannot be deleted."))
        return super().delete(*args, **kwargs)


class BankSettings(TimeStampedModel):
    """Bank-wide settings (a singleton row).

    Holds the languages the application offers, the bank-wide language default,
    the national (base) currency and the conversion mode used when converting
    between currencies. The row is created on first access from the ``settings``
    defaults (``LANGUAGES`` and ``LANGUAGE_CODE``); see
    ``docs/adr/0015-application-language-layers.md`` and
    ``docs/adr/0020-currency-rate-units-and-conversion.md``.
    """

    class ConversionMode(models.TextChoices):
        VIA_BASE = "via_base", _("Through the base currency")
        DIRECT = "direct", _("Direct cross rates")

    default_language = models.CharField(_("default language"), max_length=8, default="ru")
    enabled_languages = models.JSONField(_("enabled languages"), default=list, blank=True)
    base_currency = models.CharField(_("base currency"), max_length=8, default="BYN")
    conversion_mode = models.CharField(
        _("conversion mode"),
        max_length=16,
        choices=ConversionMode.choices,
        default=ConversionMode.VIA_BASE,
        help_text=_(
            "Through the base currency uses cross rates via the national currency; "
            "direct uses explicit pairs such as EUR/USD."
        ),
    )

    class Meta:
        verbose_name = _("bank settings")
        verbose_name_plural = _("bank settings")
        db_table = qualified_table("core", "core_banksettings")

    def save(self, *args, **kwargs):
        self.pk = 1
        return super().save(*args, **kwargs)

    def clean(self):
        super().clean()
        supported = {code for code, _name in settings.LANGUAGES}
        enabled = list(self.enabled_languages or [])
        unknown = sorted(set(enabled) - supported)
        if unknown:
            raise ValidationError(
                {
                    "enabled_languages": _("Unsupported languages: %(codes)s.")
                    % {"codes": ", ".join(unknown)}
                }
            )
        if self.default_language and self.default_language not in enabled:
            raise ValidationError(
                {
                    "default_language": _(
                        "The default language must be one of the enabled languages."
                    )
                }
            )

        code = (self.base_currency or "").strip().upper()
        if not code:
            raise ValidationError({"base_currency": _("The base currency is required.")})
        directory = registry.get(REFERENCE_DIRECTORY)
        if directory.get_currency(code) is None:
            raise ValidationError({"base_currency": _("Unknown currency.")})
        self.base_currency = code

        if self.pk:
            previous = (
                type(self)
                .objects.filter(pk=self.pk)
                .values_list("base_currency", flat=True)
                .first()
            )
            if previous and previous != code:
                if CurrencyRate.objects.exclude(base_currency=code).exists():
                    raise ValidationError(
                        {
                            "base_currency": _(
                                "The base currency cannot be changed while currency "
                                "rates with another base currency exist."
                            )
                        }
                    )
                if BaseValue.objects.exclude(currency_code=code).exists():
                    raise ValidationError(
                        {
                            "base_currency": _(
                                "The base currency cannot be changed while base values "
                                "in another currency exist."
                            )
                        }
                    )

    @classmethod
    def load(cls) -> "BankSettings":
        """Return the singleton, creating it from the settings defaults if needed."""
        obj, _created = cls.objects.get_or_create(
            pk=1,
            defaults={
                "default_language": settings.LANGUAGE_CODE.split("-")[0],
                "enabled_languages": [code for code, _name in settings.LANGUAGES],
                "base_currency": "BYN",
                "conversion_mode": cls.ConversionMode.VIA_BASE,
            },
        )
        return obj

    def __str__(self):
        return _("Bank settings")
