"""Domain models of the ``operations`` module.

The module owns the operation engine data: the catalogue of operation types and
their amount slots, the immutable operation journal (operation + lines),
register movements and the materialised cash balances.

Cross-module references (cash desk, shift, cashier) are stored as stable
identifiers, never as ORM relations — see ``docs/modules.md`` and
``docs/adr/0004-operational-accounting-registers.md``.
"""

from __future__ import annotations

import os
from decimal import Decimal

from django.db import models
from django.utils import timezone
from django.utils.translation import gettext_lazy as _

from modules.common.backend.i18n import pick_translation
from modules.common.backend.models import TimeStampedModel
from modules.common.backend.schemas import qualified_table
from modules.operations.backend.registers import RegisterCode
from modules.operations.contracts.dto import OperationKind


def _env_flag(name: str, default: bool = False) -> bool:
    return os.environ.get(name, str(default)).strip().lower() in {"1", "true", "yes", "on"}


class OperationType(TimeStampedModel):
    """Metadata of an operation kind: how it is posted and what it requires.

    Operation types are data: the base set lives in ``operations-standard`` and
    bank specific operations come from extension modules. A type without a
    registered handler is posted from its declarative ``template``.
    """

    class Kind(models.TextChoices):
        INCOME = OperationKind.INCOME, _("Income")
        EXPENSE = OperationKind.EXPENSE, _("Expense")
        EXCHANGE = OperationKind.EXCHANGE, _("Exchange")
        INTERNAL = OperationKind.INTERNAL, _("Internal")

    code = models.SlugField(_("code"), max_length=64, unique=True)
    name = models.CharField(_("name"), max_length=150)
    kind = models.CharField(_("kind"), max_length=16, choices=Kind.choices)
    is_external = models.BooleanField(
        _("external operation"),
        default=False,
        help_text=_("The operation calls a bank subsystem over REST."),
    )
    requires_client = models.BooleanField(_("requires client data"), default=False)
    client_id_threshold = models.DecimalField(
        _("client document threshold"),
        max_digits=18,
        decimal_places=2,
        null=True,
        blank=True,
        help_text=_("Amount in the base currency above which a client document is required."),
    )
    permission_code = models.CharField(
        _("required permission"),
        max_length=64,
        blank=True,
        help_text=_("Permission code a user needs to perform the operation."),
    )
    template = models.JSONField(
        _("posting template"),
        default=dict,
        blank=True,
        help_text=_("Declarative postings for operations without a handler."),
    )
    is_active = models.BooleanField(_("active"), default=True)

    class Meta:
        verbose_name = _("operation type")
        verbose_name_plural = _("operation types")
        db_table = qualified_table("operations", "operations_operationtype")
        ordering = ("name",)

    def __str__(self):
        return self.name

    def localized_name(self, language: str | None = None) -> str:
        """Return the name in ``language`` (the active one when omitted).

        Falls back to the base ``name`` when the language has no translation
        (see ``docs/adr/0016-translatable-reference-data.md``).
        """
        return pick_translation(
            self.name,
            ((row.language, row.name) for row in self.translations.all()),
            language,
        )


class OperationTypeTranslation(TimeStampedModel):
    """The name of an operation type in one language.

    The base value stays on :attr:`OperationType.name`; this table holds the
    translations owned by the module (see
    ``docs/adr/0016-translatable-reference-data.md``).
    """

    operation_type = models.ForeignKey(
        OperationType,
        on_delete=models.CASCADE,
        related_name="translations",
        verbose_name=_("operation type"),
    )
    language = models.CharField(_("language"), max_length=8)
    name = models.CharField(_("name"), max_length=150)

    class Meta:
        verbose_name = _("operation type translation")
        verbose_name_plural = _("operation type translations")
        db_table = qualified_table("operations", "operations_operationtypetranslation")
        ordering = ("language",)
        constraints = (
            models.UniqueConstraint(
                fields=["operation_type", "language"],
                name="operations_unique_operation_type_translation",
            ),
        )

    def __str__(self):
        return f"{self.operation_type.code} [{self.language}]"


class SlotDef(TimeStampedModel):
    """An amount slot an operation type expects (its input shape)."""

    operation_type = models.ForeignKey(
        OperationType,
        on_delete=models.CASCADE,
        related_name="slots",
        verbose_name=_("operation type"),
    )
    code = models.SlugField(_("code"), max_length=64)
    name = models.CharField(_("name"), max_length=150)
    required = models.BooleanField(_("required"), default=True)
    fixed_currency = models.CharField(
        _("currency"),
        max_length=8,
        blank=True,
        help_text=_("When set, the slot only accepts this currency."),
    )
    order = models.PositiveSmallIntegerField(_("order"), default=0)

    class Meta:
        verbose_name = _("slot")
        verbose_name_plural = _("slots")
        db_table = qualified_table("operations", "operations_slotdef")
        ordering = ("order", "id")
        constraints = (
            models.UniqueConstraint(
                fields=["operation_type", "code"],
                name="operations_unique_slot_code",
            ),
        )

    def __str__(self):
        return f"{self.operation_type.code}.{self.code}"

    def localized_name(self, language: str | None = None) -> str:
        """Return the name in ``language`` (the active one when omitted).

        Falls back to the base ``name`` when the language has no translation
        (see ``docs/adr/0016-translatable-reference-data.md``).
        """
        return pick_translation(
            self.name,
            ((row.language, row.name) for row in self.translations.all()),
            language,
        )


class SlotDefTranslation(TimeStampedModel):
    """The name of an operation type's amount slot in one language.

    The base value stays on :attr:`SlotDef.name`; this table holds the
    translations owned by the module (see
    ``docs/adr/0016-translatable-reference-data.md``).
    """

    slot = models.ForeignKey(
        SlotDef,
        on_delete=models.CASCADE,
        related_name="translations",
        verbose_name=_("slot"),
    )
    language = models.CharField(_("language"), max_length=8)
    name = models.CharField(_("name"), max_length=150)

    class Meta:
        verbose_name = _("slot translation")
        verbose_name_plural = _("slot translations")
        db_table = qualified_table("operations", "operations_slotdeftranslation")
        ordering = ("language",)
        constraints = (
            models.UniqueConstraint(
                fields=["slot", "language"],
                name="operations_unique_slot_translation",
            ),
        )

    def __str__(self):
        return f"{self.slot} [{self.language}]"


class Operation(TimeStampedModel):
    """An immutable operation document.

    A posted operation is never edited; a mistake is corrected by posting a
    reversal (``reversal_of``) and marking the original as ``reversed``.
    """

    class Status(models.TextChoices):
        POSTED = "posted", _("Posted")
        REVERSED = "reversed", _("Reversed")

    operation_type = models.ForeignKey(
        OperationType,
        on_delete=models.PROTECT,
        related_name="operations",
        verbose_name=_("operation type"),
    )
    number = models.PositiveBigIntegerField(
        _("number"),
        help_text=_("Running number within the cash desk."),
    )
    cash_desk_id = models.PositiveBigIntegerField(_("cash desk"))
    shift_id = models.PositiveBigIntegerField(_("shift"))
    cashier_id = models.PositiveBigIntegerField(_("cashier"))
    status = models.CharField(
        _("status"),
        max_length=16,
        choices=Status.choices,
        default=Status.POSTED,
    )
    idempotency_key = models.CharField(_("idempotency key"), max_length=128, blank=True)
    client_name = models.CharField(_("client name"), max_length=255, blank=True)
    client_document = models.CharField(_("client document"), max_length=64, blank=True)
    comment = models.CharField(_("comment"), max_length=255, blank=True)
    posted_at = models.DateTimeField(_("posted at"), default=timezone.now)
    reversal_of = models.ForeignKey(
        "self",
        null=True,
        blank=True,
        on_delete=models.PROTECT,
        related_name="reversals",
        verbose_name=_("reversal of"),
    )

    class Meta:
        verbose_name = _("operation")
        verbose_name_plural = _("operations")
        db_table = qualified_table("operations", "operations_operation")
        ordering = ("-posted_at", "-id")
        indexes = (
            models.Index(fields=["cash_desk_id", "posted_at"]),
            models.Index(fields=["shift_id"]),
            models.Index(fields=["operation_type", "posted_at"]),
        )
        constraints = (
            models.UniqueConstraint(
                fields=["cash_desk_id", "number"],
                name="operations_unique_number_per_cash_desk",
            ),
            models.UniqueConstraint(
                fields=["cash_desk_id", "idempotency_key"],
                condition=~models.Q(idempotency_key=""),
                name="operations_unique_idempotency_key",
            ),
        )

    def __str__(self):
        return f"{self.operation_type.code} #{self.number} @ {self.cash_desk_id}"


class OperationLine(TimeStampedModel):
    """A filled amount slot of an operation (one currency and amount)."""

    operation = models.ForeignKey(
        Operation,
        on_delete=models.CASCADE,
        related_name="lines",
        verbose_name=_("operation"),
    )
    slot = models.CharField(_("slot"), max_length=64)
    currency = models.CharField(_("currency"), max_length=8)
    amount = models.DecimalField(_("amount"), max_digits=18, decimal_places=2)
    rate = models.DecimalField(_("rate"), max_digits=18, decimal_places=8, null=True, blank=True)

    class Meta:
        verbose_name = _("operation line")
        verbose_name_plural = _("operation lines")
        db_table = qualified_table("operations", "operations_operationline")
        ordering = ("id",)

    def __str__(self):
        return f"{self.slot}: {self.amount} {self.currency}"


class Movement(TimeStampedModel):
    """A signed register movement produced by an operation."""

    operation = models.ForeignKey(
        Operation,
        on_delete=models.CASCADE,
        related_name="movements",
        verbose_name=_("operation"),
    )
    register = models.CharField(_("register"), max_length=32)
    cash_desk_id = models.PositiveBigIntegerField(_("cash desk"))
    currency = models.CharField(_("currency"), max_length=8)
    operation_type_code = models.CharField(_("operation type"), max_length=64, blank=True)
    amount = models.DecimalField(_("amount"), max_digits=18, decimal_places=2)

    class Meta:
        verbose_name = _("movement")
        verbose_name_plural = _("movements")
        db_table = qualified_table("operations", "operations_movement")
        ordering = ("id",)
        indexes = (models.Index(fields=["register", "cash_desk_id", "currency"]),)

    def __str__(self):
        return f"{self.register} {self.amount} {self.currency}"


class CashBalance(TimeStampedModel):
    """Materialised cash on hand at a cash desk, per currency.

    The movements are the source of truth; this table is a derived, quickly
    readable balance that the engine keeps consistent and that can always be
    rebuilt. Negative balances are rejected both by the engine and by a check
    constraint — see ``docs/adr/0005-multicurrency-cash-balances.md``.
    """

    cash_desk_id = models.PositiveBigIntegerField(_("cash desk"))
    currency = models.CharField(_("currency"), max_length=8)
    amount = models.DecimalField(_("amount"), max_digits=18, decimal_places=2, default=Decimal("0"))

    class Meta:
        verbose_name = _("cash balance")
        verbose_name_plural = _("cash balances")
        db_table = qualified_table("operations", "operations_cashbalance")
        ordering = ("cash_desk_id", "currency")
        constraints = (
            models.UniqueConstraint(
                fields=["cash_desk_id", "currency"],
                name="operations_unique_cash_balance",
            ),
            models.CheckConstraint(
                condition=models.Q(amount__gte=0),
                name="operations_non_negative_cash_balance",
            ),
        )

    def __str__(self):
        return f"{self.cash_desk_id}/{self.currency}: {self.amount}"


class OperationNumberSequence(models.Model):
    """Running operation number per cash desk (the numbering source)."""

    cash_desk_id = models.PositiveBigIntegerField(_("cash desk"), unique=True)
    last_number = models.PositiveBigIntegerField(_("last number"), default=0)

    class Meta:
        verbose_name = _("operation number sequence")
        verbose_name_plural = _("operation number sequences")
        db_table = qualified_table("operations", "operations_operationnumbersequence")

    def __str__(self):
        return f"{self.cash_desk_id}: {self.last_number}"


class OperationsSettings(TimeStampedModel):
    """Bank-wide operation settings (a singleton row).

    Holds the editable defaults the engine and the administration read: the base
    currency and the client data policy. The row is created on first access from
    the environment defaults declared in ``module.yaml``.
    """

    base_currency = models.CharField(_("base currency"), max_length=8, default="BYN")
    client_id_threshold = models.DecimalField(
        _("client document threshold"),
        max_digits=18,
        decimal_places=2,
        default=Decimal("0"),
    )
    require_client = models.BooleanField(_("require client data"), default=False)

    class Meta:
        verbose_name = _("operations settings")
        verbose_name_plural = _("operations settings")
        db_table = qualified_table("operations", "operations_operationssettings")

    def save(self, *args, **kwargs):
        self.pk = 1
        return super().save(*args, **kwargs)

    @classmethod
    def load(cls) -> OperationsSettings:
        """Return the singleton, creating it from environment defaults if needed."""
        settings, _ = cls.objects.get_or_create(
            pk=1,
            defaults={
                "base_currency": os.environ.get("BCO_OPERATIONS_BASE_CURRENCY", "BYN"),
                "client_id_threshold": Decimal(
                    os.environ.get("BCO_OPERATIONS_CLIENT_ID_THRESHOLD", "0")
                ),
                "require_client": _env_flag("BCO_OPERATIONS_REQUIRE_CLIENT"),
            },
        )
        return settings

    def __str__(self):
        return _("Operations settings")


class CashDeskOperation(TimeStampedModel):
    """An operation type enabled on a specific cash desk (an explicit override).

    When a cash desk has its own operations, they replace the effective template;
    a cash desk without its own operations inherits the nearest operation template
    (see :class:`OperationTemplate`). With neither, no operation is allowed.
    """

    cash_desk_id = models.PositiveBigIntegerField(_("cash desk"))
    operation_type = models.ForeignKey(
        OperationType,
        on_delete=models.CASCADE,
        related_name="cash_desks",
        verbose_name=_("operation type"),
    )

    class Meta:
        verbose_name = _("cash desk operation")
        verbose_name_plural = _("cash desk operations")
        db_table = qualified_table("operations", "operations_cashdeskoperation")
        ordering = ("operation_type__name",)
        constraints = (
            models.UniqueConstraint(
                fields=["cash_desk_id", "operation_type"],
                name="operations_unique_cash_desk_operation",
            ),
        )

    def __str__(self):
        return f"{self.cash_desk_id} — {self.operation_type}"


class OperationTemplate(TimeStampedModel):
    """A default set of cash desk operations, for the bank or a branch.

    ``branch_id`` is a stable identifier of a ``core`` branch (a plain integer,
    never an ORM relation — see ``docs/modules.md``). ``None`` is the bank-wide
    default; a template with a branch applies to that branch and its descendants,
    and a closer template overrides a farther one. A template that exists but
    lists no operation types means "no operation is allowed".
    """

    branch_id = models.PositiveBigIntegerField(_("branch"), null=True, blank=True)
    operation_types = models.ManyToManyField(
        OperationType,
        related_name="templates",
        blank=True,
        verbose_name=_("operation types"),
    )

    class Meta:
        verbose_name = _("operation template")
        verbose_name_plural = _("operation templates")
        db_table = qualified_table("operations", "operations_operationtemplate")
        constraints = (
            models.UniqueConstraint(
                fields=["branch_id"],
                name="operations_unique_operation_template_scope",
                nulls_distinct=False,
            ),
        )

    def __str__(self):
        return _("Bank template") if self.branch_id is None else f"Branch {self.branch_id}"


# Re-exported for convenience of callers that build movements.
__all__ = [
    "CashBalance",
    "CashDeskOperation",
    "Movement",
    "Operation",
    "OperationLine",
    "OperationNumberSequence",
    "OperationTemplate",
    "OperationsSettings",
    "OperationType",
    "OperationTypeTranslation",
    "RegisterCode",
    "SlotDef",
    "SlotDefTranslation",
]
