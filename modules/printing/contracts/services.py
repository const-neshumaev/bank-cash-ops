"""Service interfaces published by the ``printing`` module."""

from __future__ import annotations

from collections.abc import Iterable
from typing import Any, Protocol

from modules.printing.contracts.dto import (
    PrintBinding,
    PrintDocumentHeader,
    PrintDocumentInfo,
    PrintDocumentTypeInfo,
    PrintDocumentTypeSpec,
    PrintFile,
    PrintOperation,
    PrintTemplateInfo,
    PrintTemplateSpec,
    PrintVariable,
)


class PrintVariableProvider(Protocol):
    """Computes the substitution variables of one print form.

    A provider is code owned by the module that declares the template. It
    receives the operation snapshot and the identity of the document being
    rendered and returns the values substituted into the Word template.
    """

    variables: tuple[PrintVariable, ...]

    def build(self, operation: PrintOperation, document: PrintDocumentHeader) -> dict[str, Any]: ...


class PrintTemplateRegistry(Protocol):
    """Registry of the print document types and templates declared by modules."""

    def register_document_type(self, spec: PrintDocumentTypeSpec) -> None: ...

    def register_template(
        self,
        spec: PrintTemplateSpec,
        provider: PrintVariableProvider | None = None,
    ) -> None: ...

    def has_document_type(self, code: str) -> bool: ...

    def has_template(self, code: str) -> bool: ...

    def document_type_specs(self) -> tuple[PrintDocumentTypeSpec, ...]: ...

    def template_specs(self) -> tuple[PrintTemplateSpec, ...]: ...

    def get_template_spec(self, code: str) -> PrintTemplateSpec | None: ...

    def get_provider(self, code: str) -> PrintVariableProvider | None: ...


class PrintDocumentService(Protocol):
    """Rendering and document storage, offered to the modules that print."""

    def document_types(self) -> tuple[PrintDocumentTypeInfo, ...]: ...

    def templates(self) -> tuple[PrintTemplateInfo, ...]: ...

    def template_file(self, code: str) -> PrintFile | None: ...

    def render_operation(
        self,
        operation: PrintOperation,
        bindings: Iterable[PrintBinding],
        *,
        user_id: int | None = None,
    ) -> tuple[PrintDocumentInfo, ...]:
        """Render the configured templates and store the resulting documents."""
        ...

    def operation_ids_with_documents(self, operation_ids: Iterable[int]) -> set[int]: ...

    def operation_documents(self, operation_id: int) -> tuple[PrintDocumentInfo, ...]: ...

    def document_file(self, document_id: int) -> PrintFile | None: ...

    def document(self, document_id: int) -> PrintDocumentInfo | None: ...
