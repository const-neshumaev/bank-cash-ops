"""In-process registry of the print forms declared by modules (the SPI).

Modules declare document types and templates in ``AppConfig.ready``; the
``printing`` module persists them with ``sync_print_templates`` and resolves a
template's variable provider when rendering.
"""

from __future__ import annotations

from modules.printing.contracts.dto import PrintDocumentTypeSpec, PrintTemplateSpec
from modules.printing.contracts.services import PrintVariableProvider


class PrintTemplateRegistryService:
    """Stores the document types, templates and variable providers."""

    def __init__(self) -> None:
        self._document_types: dict[str, PrintDocumentTypeSpec] = {}
        self._templates: dict[str, PrintTemplateSpec] = {}
        self._providers: dict[str, PrintVariableProvider] = {}

    def register_document_type(self, spec: PrintDocumentTypeSpec) -> None:
        if spec.code in self._document_types:
            raise RuntimeError(f"Print document type '{spec.code}' is already registered")
        self._document_types[spec.code] = spec

    def register_template(
        self,
        spec: PrintTemplateSpec,
        provider: PrintVariableProvider | None = None,
    ) -> None:
        if spec.code in self._templates:
            raise RuntimeError(f"Print template '{spec.code}' is already registered")
        if spec.document_type not in self._document_types:
            raise RuntimeError(
                f"Print document type '{spec.document_type}' must be registered "
                f"before template '{spec.code}'"
            )
        self._templates[spec.code] = spec
        if provider is not None:
            self._providers[spec.provider] = provider

    def has_document_type(self, code: str) -> bool:
        return code in self._document_types

    def has_template(self, code: str) -> bool:
        return code in self._templates

    def document_type_specs(self) -> tuple[PrintDocumentTypeSpec, ...]:
        return tuple(self._document_types.values())

    def template_specs(self) -> tuple[PrintTemplateSpec, ...]:
        return tuple(self._templates.values())

    def get_template_spec(self, code: str) -> PrintTemplateSpec | None:
        return self._templates.get(code)

    def get_provider(self, code: str) -> PrintVariableProvider | None:
        return self._providers.get(code)

    def unregister_template(self, code: str) -> None:
        """Forget a template (used by tests and extension teardown)."""
        spec = self._templates.pop(code, None)
        if spec is None:
            return
        if not any(item.provider == spec.provider for item in self._templates.values()):
            self._providers.pop(spec.provider, None)

    def unregister_document_type(self, code: str) -> None:
        """Forget a document type (used by tests and extension teardown)."""
        self._document_types.pop(code, None)


#: The single registry instance shared inside the process.
print_template_registry = PrintTemplateRegistryService()
