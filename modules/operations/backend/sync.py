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
from modules.operations.contracts.dto import OperationTypeSpec


def sync_operation_types() -> int:
    """Create or update the declared operation types; return how many were synced."""
    synced = 0
    for spec in operation_type_registry.types():
        operation_type, _ = OperationType.objects.update_or_create(
            code=spec.code,
            defaults={
                "name": spec.name,
                "kind": spec.kind,
                "is_external": spec.is_external,
                "requires_client": spec.requires_client,
                "client_id_threshold": spec.client_id_threshold,
                "permission_code": spec.permission_code,
                "template": spec.template,
            },
        )
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
