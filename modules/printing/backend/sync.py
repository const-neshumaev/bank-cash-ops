"""Materialise the declared print forms into the ``printing`` tables.

Document types and templates are declared by modules through the SPI; the
``printing`` module owns their persistence. Synchronisation refreshes the
declarative fields and installs a sample Word file when the administrator has
not uploaded one yet. It never overwrites an uploaded file and never deletes a
template, because rendered documents keep referring to it.
"""

from __future__ import annotations

from pathlib import Path

from django.utils import timezone

from modules.printing.backend.models import (
    PrintDocumentType,
    PrintDocumentTypeTranslation,
    PrintTemplate,
    PrintTemplateTranslation,
)
from modules.printing.backend.registry import print_template_registry


def sync_print_templates() -> tuple[int, int]:
    """Create or update the declared forms; return ``(types, templates)`` counts."""
    document_types = _sync_document_types()
    templates = _sync_templates()
    return document_types, templates


def _sync_document_types() -> int:
    count = 0
    for spec in print_template_registry.document_type_specs():
        document_type, _ = PrintDocumentType.objects.update_or_create(
            code=spec.code,
            defaults={
                "name": spec.name,
                "description": spec.description,
                "numbering_scope": spec.numbering_scope,
            },
        )
        _sync_translations(
            PrintDocumentTypeTranslation,
            document_type,
            "document_type",
            spec.translations or {},
        )
        count += 1
    return count


def _sync_templates() -> int:
    count = 0
    for spec in print_template_registry.template_specs():
        template, created = PrintTemplate.objects.update_or_create(
            code=spec.code,
            defaults={
                "name": spec.name,
                "description": spec.description,
                "document_type": spec.document_type,
                "provider": spec.provider,
            },
        )
        if created or not template.file:
            _install_default_file(template, spec.default_file_path)
        _sync_translations(
            PrintTemplateTranslation,
            template,
            "template",
            spec.translations or {},
        )
        count += 1
    return count


def _install_default_file(template: PrintTemplate, path: str | None) -> None:
    """Store the sample template shipped with the declaring module."""
    if not path:
        return
    source = Path(path)
    if not source.is_file():
        return
    content = source.read_bytes()
    template.file = content
    template.file_name = source.name
    template.file_size = len(content)
    template.file_updated_at = timezone.now()
    template.save(update_fields=["file", "file_name", "file_size", "file_updated_at", "updated_at"])


def _sync_translations(translation_model, parent, parent_field: str, translations: dict) -> None:
    """Upsert the declared translations without removing the others."""
    for language, name in translations.items():
        translation_model.objects.update_or_create(
            **{parent_field: parent, "language": language},
            defaults={"name": name},
        )
