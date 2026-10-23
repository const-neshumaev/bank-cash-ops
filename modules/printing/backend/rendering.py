"""Rendering of Word print forms and storage of the resulting documents.

``docxtpl`` renders a ``.docx`` file as a Jinja2 template. The template file,
the rendered output and the substitution context are stored in the database;
the module therefore never depends on the container filesystem for user data.
"""

from __future__ import annotations

import json
import logging
from collections.abc import Iterable
from io import BytesIO

from django.db import IntegrityError, transaction
from django.utils import timezone

from modules.printing.backend.models import (
    PrintDocument,
    PrintDocumentType,
    PrintNumberSequence,
    PrintTemplate,
)
from modules.printing.backend.registry import print_template_registry
from modules.printing.contracts import DOCX_CONTENT_TYPE
from modules.printing.contracts.dto import (
    PrintBinding,
    PrintDocumentHeader,
    PrintDocumentInfo,
    PrintDocumentTypeInfo,
    PrintFile,
    PrintOperation,
    PrintTemplateInfo,
    PrintVariable,
)

logger = logging.getLogger(__name__)


class PrintRenderingService:
    """Implementation of the ``PrintDocumentService`` contract."""

    def document_types(self) -> tuple[PrintDocumentTypeInfo, ...]:
        templates = self.templates()
        by_type: dict[str, list[PrintTemplateInfo]] = {}
        for template in templates:
            by_type.setdefault(template.document_type, []).append(template)
        return tuple(
            PrintDocumentTypeInfo(
                code=document_type.code,
                name=document_type.localized_name(),
                description=document_type.description,
                numbering_scope=document_type.numbering_scope,
                is_active=document_type.is_active,
                templates=tuple(by_type.get(document_type.code, ())),
            )
            for document_type in PrintDocumentType.objects.prefetch_related("translations")
        )

    def templates(self) -> tuple[PrintTemplateInfo, ...]:
        document_type_names = {
            row.code: row.localized_name()
            for row in PrintDocumentType.objects.prefetch_related("translations")
        }
        return tuple(
            self._template_info(template, document_type_names)
            for template in PrintTemplate.objects.prefetch_related("translations")
        )

    def template_file(self, code: str) -> PrintFile | None:
        template = PrintTemplate.objects.filter(code=code).first()
        if template is None or not template.file:
            return None
        return PrintFile(
            file_name=template.file_name or f"{template.code}.docx",
            content=bytes(template.file),
            content_type=DOCX_CONTENT_TYPE,
        )

    def render_operation(
        self,
        operation: PrintOperation,
        bindings: Iterable[PrintBinding],
        *,
        user_id: int | None = None,
    ) -> tuple[PrintDocumentInfo, ...]:
        """Render every configured template that has not been printed yet."""
        rendered: list[PrintDocumentInfo] = []
        for binding in bindings:
            template = (
                PrintTemplate.objects.prefetch_related("translations")
                .filter(code=binding.template, is_active=True)
                .first()
            )
            if template is None or not template.is_active:
                continue
            if template.document_type != binding.document_type:
                continue
            if not template.file:
                continue
            if PrintDocument.objects.filter(
                operation_id=operation.id, document_type=template.document_type
            ).exists():
                continue

            document_type = (
                PrintDocumentType.objects.prefetch_related("translations")
                .filter(code=template.document_type, is_active=True)
                .first()
            )
            if document_type is None:
                self._record_error(
                    template,
                    f"Print document type '{template.document_type}' is not available.",
                )
                continue

            provider = print_template_registry.get_provider(template.provider)
            if provider is None:
                self._record_error(
                    template, f"Print variable provider '{template.provider}' is not registered."
                )
                continue

            try:
                with transaction.atomic():
                    number = self._next_number(document_type.code)
                    header = PrintDocumentHeader(
                        number=number,
                        document_type=document_type.code,
                        document_type_name=document_type.localized_name(),
                        template_code=template.code,
                        template_name=template.localized_name(),
                    )
                    context = provider.build(operation, header)
                    content = _render_docx(bytes(template.file), context)
                    document = PrintDocument.objects.create(
                        document_type=document_type.code,
                        document_type_name=header.document_type_name,
                        template_code=template.code,
                        template_name=header.template_name,
                        operation_id=operation.id,
                        operation_type_code=operation.operation_type_code,
                        cash_desk_id=operation.cash_desk_id,
                        number=number,
                        file_name=f"{document_type.code}_{number}.docx",
                        content=content,
                        context=_json_safe(context),
                        created_by_id=user_id,
                    )
            except IntegrityError:
                # A concurrent request rendered the same operation first; the
                # unique (operation, document type) constraint keeps one copy.
                logger.warning(
                    "Print template %s was already rendered for operation %s",
                    template.code,
                    operation.id,
                )
                continue
            except Exception as exc:  # rendering errors must not break the operation
                logger.exception(
                    "Print template %s failed to render operation %s", template.code, operation.id
                )
                self._record_error(template, str(exc))
                continue

            self._clear_error(template)
            rendered.append(_to_info(document))
        return tuple(rendered)

    def operation_ids_with_documents(self, operation_ids: Iterable[int]) -> set[int]:
        ids = list(operation_ids)
        if not ids:
            return set()
        return set(
            PrintDocument.objects.filter(operation_id__in=ids).values_list(
                "operation_id", flat=True
            )
        )

    def operation_documents(self, operation_id: int) -> tuple[PrintDocumentInfo, ...]:
        return tuple(
            _to_info(document)
            for document in PrintDocument.objects.filter(operation_id=operation_id).order_by(
                "created_at", "id"
            )
        )

    def document_file(self, document_id: int) -> PrintFile | None:
        document = PrintDocument.objects.filter(pk=document_id).first()
        if document is None:
            return None
        return PrintFile(
            file_name=document.file_name,
            content=bytes(document.content),
            content_type=DOCX_CONTENT_TYPE,
        )

    def document(self, document_id: int) -> PrintDocumentInfo | None:
        document = PrintDocument.objects.filter(pk=document_id).first()
        return _to_info(document) if document is not None else None

    # -- helpers ---------------------------------------------------------- #
    @staticmethod
    def _template_info(
        template: PrintTemplate, document_type_names: dict[str, str]
    ) -> PrintTemplateInfo:
        provider = print_template_registry.get_provider(template.provider)
        variables: tuple[PrintVariable, ...] = provider.variables if provider else ()
        return PrintTemplateInfo(
            code=template.code,
            name=template.localized_name(),
            document_type=template.document_type,
            document_type_name=document_type_names.get(template.document_type, ""),
            description=template.description,
            provider=template.provider,
            file_name=template.file_name,
            has_file=template.has_file,
            updated_at=template.file_updated_at,
            last_error=template.last_error,
            is_active=template.is_active,
            variables=variables,
        )

    @staticmethod
    def _next_number(document_type: str) -> int:
        PrintNumberSequence.objects.get_or_create(document_type=document_type)
        sequence = PrintNumberSequence.objects.select_for_update().get(document_type=document_type)
        sequence.last_number += 1
        sequence.save(update_fields=["last_number", "updated_at"])
        return sequence.last_number

    @staticmethod
    def _record_error(template: PrintTemplate, message: str) -> None:
        template.last_error = (message or "")[:4000]
        template.last_error_at = timezone.now()
        template.save(update_fields=["last_error", "last_error_at", "updated_at"])

    @staticmethod
    def _clear_error(template: PrintTemplate) -> None:
        if not template.last_error and template.last_error_at is None:
            return
        template.last_error = ""
        template.last_error_at = None
        template.save(update_fields=["last_error", "last_error_at", "updated_at"])


#: The service instance published in the shared contract registry.
print_document_service = PrintRenderingService()


def _render_docx(template_content: bytes, context: dict) -> bytes:
    """Render a ``.docx`` Jinja template and return the resulting document."""
    from docxtpl import DocxTemplate

    template = DocxTemplate(BytesIO(template_content))
    template.render(context)
    output = BytesIO()
    template.save(output)
    return output.getvalue()


def _json_safe(context: dict) -> dict:
    """Convert Jinja values into something a JSONField can store."""
    return json.loads(json.dumps(context, default=str))


def _to_info(document: PrintDocument) -> PrintDocumentInfo:
    return PrintDocumentInfo(
        id=document.id,
        document_type=document.document_type,
        document_type_name=document.document_type_name,
        template_code=document.template_code,
        template_name=document.template_name,
        operation_id=document.operation_id,
        operation_type_code=document.operation_type_code,
        cash_desk_id=document.cash_desk_id,
        number=document.number,
        file_name=document.file_name,
        created_at=document.created_at,
    )
