"""Recording changes of the administrator-managed operation type settings.

The history is append-only. It is written from the REST API and from the Django
admin so that both paths leave the same audit trail. Only the settings an
administrator may change are tracked; declarative metadata (code, kind, slots,
posting template) is owned by the declaring module and is not part of history.
"""

from __future__ import annotations

from decimal import Decimal
from typing import Any

from modules.operations.backend.models import OperationType, OperationTypeSettingsChange

#: Operation type fields whose changes are recorded.
TRACKED_FIELDS: tuple[str, ...] = (
    "client_data_policy",
    "threshold_type",
    "threshold_value",
    "threshold_currency",
    "rate_type",
    "is_active",
)


def snapshot(operation_type: OperationType) -> dict[str, Any]:
    """Return a JSON-serialisable snapshot of the tracked settings."""
    return {
        "client_data_policy": operation_type.client_data_policy,
        "threshold_type": operation_type.threshold_type,
        "threshold_value": (
            None
            if operation_type.threshold_value is None
            else str(operation_type.threshold_value.quantize(Decimal("0.01")))
        ),
        "threshold_currency": operation_type.threshold_currency,
        "rate_type": operation_type.rate_type,
        "is_active": operation_type.is_active,
    }


def diff(before: dict[str, Any], after: dict[str, Any]) -> dict[str, dict[str, Any]]:
    """Return ``{field: {"before": ..., "after": ...}}`` for changed fields."""
    changes: dict[str, dict[str, Any]] = {}
    for field in TRACKED_FIELDS:
        if before.get(field) != after.get(field):
            changes[field] = {"before": before.get(field), "after": after.get(field)}
    return changes


def record_settings_change(
    operation_type: OperationType,
    *,
    before: dict[str, Any] | None,
    after: dict[str, Any] | None = None,
    user=None,
) -> OperationTypeSettingsChange | None:
    """Append a history entry when a tracked setting changed.

    ``before`` is ``None`` when the type is created; creation itself is not a
    settings change, so nothing is recorded. The user is stored by id and email
    snapshot, so the entry remains readable after the account is removed.
    """
    if before is None:
        return None
    current = after if after is not None else snapshot(operation_type)
    changes = diff(before, current)
    if not changes:
        return None
    return OperationTypeSettingsChange.objects.create(
        operation_type=operation_type,
        changed_by_id=getattr(user, "id", None),
        changed_by_email=getattr(user, "email", "") or "",
        changes=changes,
    )
