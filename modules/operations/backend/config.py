"""Per-cash-desk operation configuration.

The operations allowed at a cash desk are resolved dynamically (see
``docs/adr/0014-cash-desk-configuration-templates.md``):

1. the cash desk's own operations, when it has any (an override);
2. otherwise the nearest defined template on the branch path — the cash desk's
   branch, its ancestors and finally the bank-wide template;
3. with neither, no operation is allowed (deny by default).

A template that exists but lists no operations is a defined, empty template and
therefore also denies every operation.
"""

from __future__ import annotations

from dataclasses import dataclass

from django.db import transaction
from django.utils.translation import gettext_lazy as _
from rest_framework.exceptions import ValidationError

from modules.common.contracts import registry
from modules.core.contracts import ORG_DIRECTORY
from modules.operations.backend.models import (
    CashDeskOperation,
    OperationTemplate,
    OperationType,
)

#: Sources of an effective configuration.
OWN = "own"
BRANCH = "branch"
BANK = "bank"
NONE = "none"


@dataclass(frozen=True)
class EffectiveOperationConfig:
    """The operations in force at a cash desk and where they come from."""

    codes: tuple[str, ...]
    source: str
    template_branch_id: int | None = None


def _org_directory():
    return registry.get(ORG_DIRECTORY)


def configured_operation_codes(cash_desk_id: int) -> list[str] | None:
    """Return the operations set on a cash desk, or ``None`` when not overridden."""
    codes = list(
        CashDeskOperation.objects.filter(cash_desk_id=cash_desk_id).values_list(
            "operation_type__code", flat=True
        )
    )
    return codes or None


def template_operation_codes(branch_id: int | None) -> set[str] | None:
    """Return the operations of a template, or ``None`` when it is not defined."""
    template = OperationTemplate.objects.filter(branch_id=branch_id).first()
    if template is None:
        return None
    return set(template.operation_types.values_list("code", flat=True))


def _branch_path(cash_desk_id: int) -> tuple[int, ...]:
    """Return the cash desk's branch and its ancestors, nearest first."""
    cash_desk = _org_directory().get_cash_desk(cash_desk_id)
    if cash_desk is None or cash_desk.branch_id is None:
        return ()
    return _org_directory().branch_ancestor_ids(cash_desk.branch_id)


def effective_operation_config(cash_desk_id: int) -> EffectiveOperationConfig:
    """Resolve the effective operations of a cash desk and their source."""
    own = configured_operation_codes(cash_desk_id)
    if own is not None:
        return EffectiveOperationConfig(codes=tuple(sorted(own)), source=OWN)

    for branch_id in _branch_path(cash_desk_id):
        codes = template_operation_codes(branch_id)
        if codes is not None:
            return EffectiveOperationConfig(
                codes=tuple(sorted(codes)),
                source=BRANCH,
                template_branch_id=branch_id,
            )

    bank = template_operation_codes(None)
    if bank is not None:
        return EffectiveOperationConfig(codes=tuple(sorted(bank)), source=BANK)

    return EffectiveOperationConfig(codes=(), source=NONE)


def effective_operation_codes(cash_desk_id: int) -> set[str]:
    """Return the effective operations of a cash desk (empty means none)."""
    return set(effective_operation_config(cash_desk_id).codes)


def allowed_operation_types(cash_desk_id: int):
    """Operation types available at a cash desk (none when unconfigured)."""
    codes = effective_operation_codes(cash_desk_id)
    if not codes:
        return OperationType.objects.none()
    return OperationType.objects.filter(is_active=True, code__in=codes).order_by("name")


def is_operation_allowed(cash_desk_id: int, operation_type: OperationType) -> bool:
    """Return whether ``operation_type`` may be posted at the cash desk."""
    return operation_type.code in effective_operation_codes(cash_desk_id)


def _resolve_types(codes) -> list[OperationType]:
    """Validate operation codes and return the matching types, de-duplicated."""
    unique_codes = list(dict.fromkeys(codes))
    types = {t.code: t for t in OperationType.objects.filter(code__in=unique_codes)}
    unknown = sorted(set(unique_codes) - set(types))
    if unknown:
        raise ValidationError(
            _("Unknown operation types: %(codes)s.") % {"codes": ", ".join(unknown)}
        )
    return [types[code] for code in unique_codes]


def set_operation_types(cash_desk_id: int, codes) -> None:
    """Replace the operations of a cash desk; an empty list removes the override."""
    operation_types = _resolve_types(codes)
    with transaction.atomic():
        CashDeskOperation.objects.filter(cash_desk_id=cash_desk_id).delete()
        for operation_type in operation_types:
            CashDeskOperation.objects.create(
                cash_desk_id=cash_desk_id, operation_type=operation_type
            )


def set_template_operation_types(branch_id: int | None, codes) -> OperationTemplate:
    """Create or replace an operation template for the bank or a single branch."""
    operation_types = _resolve_types(codes)
    with transaction.atomic():
        template, _ = OperationTemplate.objects.get_or_create(branch_id=branch_id)
        template.operation_types.set(operation_types)
    return template


def delete_template(branch_id: int | None) -> None:
    """Remove the operation template for the bank or a branch, if it exists."""
    OperationTemplate.objects.filter(branch_id=branch_id).delete()
