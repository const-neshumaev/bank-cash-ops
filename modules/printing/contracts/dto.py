"""Data transfer objects published by the ``printing`` module."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal


@dataclass(frozen=True)
class PrintVariable:
    """A substitution variable a template may use.

    ``code`` is the Jinja name (``{{ code }}``), ``description`` explains the
    value to the administrator who edits the template.
    """

    code: str
    description: str
    example: str = ""


@dataclass(frozen=True)
class PrintDocumentTypeSpec:
    """A kind of printed document declared by a module (e.g. a cash receipt)."""

    code: str
    name: str
    description: str = ""
    translations: dict[str, str] | None = None
    numbering_scope: str = "bank"


@dataclass(frozen=True)
class PrintTemplateSpec:
    """A print form declared by a module.

    The module owns the declaration (code, document type, provider); the bank
    administrator owns the uploaded Word file. ``default_file_path`` points to a
    sample shipped with the declaring module and is copied into the database
    when no file has been uploaded yet.
    """

    code: str
    name: str
    document_type: str
    provider: str
    description: str = ""
    translations: dict[str, str] | None = None
    default_file_path: str | None = None


@dataclass(frozen=True)
class PrintDocumentHeader:
    """The identity of the document being rendered.

    ``number`` is ``None`` for document types that are not numbered.
    """

    number: int | None
    document_type: str
    document_type_name: str
    template_code: str
    template_name: str


@dataclass(frozen=True)
class PrintOperationLine:
    """An operation amount line as a print template sees it."""

    slot: str
    slot_name: str
    currency: str
    currency_name: str
    amount: Decimal
    rate: Decimal | None = None
    rate_type: str = ""
    rate_is_individual: bool = False


@dataclass(frozen=True)
class PrintOperation:
    """The immutable operation data a print provider works with.

    The ``operations`` module builds this DTO, so the ``printing`` module never
    reads another module's tables.
    """

    id: int
    number: int
    operation_type_code: str
    operation_type_name: str
    operation_kind: str
    cash_desk_id: int
    cash_desk_name: str
    cash_desk_code: str
    branch_name: str
    bank_name: str
    cashier_id: int
    posted_at: datetime
    client_name: str = ""
    client_document: str = ""
    comment: str = ""
    base_currency: str = ""
    lines: tuple[PrintOperationLine, ...] = ()


@dataclass(frozen=True)
class PrintBinding:
    """A configured link: this operation prints this template for this type."""

    document_type: str
    template: str


@dataclass(frozen=True)
class PrintTemplateInfo:
    """A template as the administration API exposes it."""

    code: str
    name: str
    document_type: str
    document_type_name: str
    description: str
    provider: str
    file_name: str
    has_file: bool
    updated_at: datetime | None
    last_error: str
    is_active: bool
    variables: tuple[PrintVariable, ...]


@dataclass(frozen=True)
class PrintDocumentTypeInfo:
    """A document type together with its templates."""

    code: str
    name: str
    description: str
    numbering_scope: str
    is_active: bool
    templates: tuple[PrintTemplateInfo, ...] = ()


@dataclass(frozen=True)
class PrintDocumentInfo:
    """A rendered document (metadata only; the file is served separately)."""

    id: int
    document_type: str
    document_type_name: str
    template_code: str
    template_name: str
    operation_id: int
    operation_type_code: str
    cash_desk_id: int
    number: int | None
    file_name: str
    created_at: datetime


@dataclass(frozen=True)
class PrintFile:
    """A downloadable document or template file."""

    file_name: str
    content: bytes
    content_type: str
