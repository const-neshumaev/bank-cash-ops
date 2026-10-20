"""Materialise declared operation types into the ``operations`` tables.

Operation types are declared by extension modules through the SPI; the
``operations`` module owns their persistence. ``sync_operation_types`` upserts
the declared types and their slots. It never deletes a type that is no longer
declared, because posted operations reference it (``PROTECT``).
"""

from __future__ import annotations

from modules.operations.backend.models import (
    OperationType,
    OperationTypeTranslation,
    SlotDef,
    SlotDefTranslation,
)
from modules.operations.backend.registry import operation_type_registry
from modules.operations.backend.thresholds import ClientDataPolicy
from modules.operations.contracts.dto import OperationTypeSpec

#: Fields owned by the declaring module: synchronisation always refreshes them.
DECLARATIVE_FIELDS = ("name", "kind", "is_external", "permission_code", "template")


def sync_operation_types() -> int:
    """Create or update the declared operation types; return how many were synced.

    Declarative metadata is refreshed on every run. The administrator-managed
    settings (client-data policy, threshold, activity) are seeded only when the
    type is created and are never overwritten afterwards.
    """
    synced = 0
    for spec in operation_type_registry.types():
        defaults = {
            "name": spec.name,
            "kind": spec.kind,
            "is_external": spec.is_external,
            "permission_code": spec.permission_code,
            "template": spec.template,
        }
        operation_type = OperationType.objects.filter(code=spec.code).first()
        if operation_type is None:
            operation_type = OperationType(
                code=spec.code,
                client_data_policy=spec.client_data_policy
                or (ClientDataPolicy.ALWAYS if spec.requires_client else ClientDataPolicy.NEVER),
                threshold_type=spec.threshold_type,
                threshold_value=spec.threshold_value,
                threshold_currency=spec.threshold_currency,
                **defaults,
            )
            operation_type.clean()
            operation_type.save()
        else:
            for field, value in defaults.items():
                setattr(operation_type, field, value)
            operation_type.save(update_fields=[*DECLARATIVE_FIELDS, "updated_at"])
        _sync_translations(
            OperationTypeTranslation, operation_type, "operation_type", spec.translations
        )
        _sync_slots(operation_type, spec)
        synced += 1
    return synced


def _sync_slots(operation_type: OperationType, spec: OperationTypeSpec) -> None:
    codes = [slot.code for slot in spec.slots]
    operation_type.slots.exclude(code__in=codes).delete()
    for slot in spec.slots:
        slot_def, _ = SlotDef.objects.update_or_create(
            operation_type=operation_type,
            code=slot.code,
            defaults={
                "name": slot.name,
                "required": slot.required,
                "fixed_currency": slot.fixed_currency,
                "order": slot.order,
            },
        )
        _sync_translations(SlotDefTranslation, slot_def, "slot", slot.translations)


def _sync_translations(
    translation_model, parent, parent_field: str, translations: dict[str, str]
) -> None:
    """Upsert the declared translations without removing undeclared ones."""
    for language, name in translations.items():
        translation_model.objects.update_or_create(
            **{parent_field: parent, "language": language},
            defaults={"name": name},
        )
