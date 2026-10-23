"""Domain models of the ``printing`` module.

The module owns printed document types, the Word templates uploaded by the bank,
the number sequences and the rendered documents. The templates and rendered
files are stored in the database: a bank can download, edit and upload them from
the administration UI.

Module boundaries: a rendered document references an operation by its stable
identifier and stores the data the template needed as a snapshot. No ORM
relation to another module's tables is declared.
"""

from __future__ import annotations

from django.db import models
from django.utils.translation import gettext_lazy as _

from modules.common.backend.i18n import pick_translation
from modules.common.backend.models import TimeStampedModel
from modules.common.backend.schemas import qualified_table


class PrintDocumentType(TimeStampedModel):
    """A kind of printed document (a cash receipt, an order, and so on).

    The type is declared by a module (see ``printing_standard``) and owns the
    bank-wide document number sequence. Only bank-wide numbering is implemented
    at the moment; ``numbering_scope`` reserves the place for other scopes.
    """

    class NumberingScope(models.TextChoices):
        BANK = "bank", _("Bank-wide")

    code = models.SlugField(_("code"), max_length=64, unique=True)
    name = models.CharField(_("name"), max_length=150)
    description = models.TextField(_("description"), blank=True)
    numbering_scope = models.CharField(
        _("numbering scope"),
        max_length=16,
        choices=NumberingScope.choices,
        default=NumberingScope.BANK,
    )
    is_active = models.BooleanField(_("active"), default=True)

    class Meta:
        verbose_name = _("print document type")
        verbose_name_plural = _("print document types")
        db_table = qualified_table("printing", "printing_printdocumenttype")
        ordering = ("name",)

    def __str__(self):
        return self.name

    def localized_name(self, language: str | None = None) -> str:
        """Return the name in ``language`` with a fallback to the base name."""
        return pick_translation(
            self.name,
            ((row.language, row.name) for row in self.translations.all()),
            language,
        )


class PrintDocumentTypeTranslation(TimeStampedModel):
    """The name of a printed document type in one language."""

    document_type = models.ForeignKey(
        PrintDocumentType,
        on_delete=models.CASCADE,
        related_name="translations",
        verbose_name=_("print document type"),
    )
    language = models.CharField(_("language"), max_length=8)
    name = models.CharField(_("name"), max_length=150)

    class Meta:
        verbose_name = _("print document type translation")
        verbose_name_plural = _("print document type translations")
        db_table = qualified_table("printing", "printing_printdocumenttypetranslation")
        ordering = ("language",)
        constraints = (
            models.UniqueConstraint(
                fields=["document_type", "language"],
                name="printing_unique_document_type_translation",
            ),
        )

    def __str__(self):
        return f"{self.document_type} [{self.language}]"


class PrintTemplate(TimeStampedModel):
    """A print form: a declared template plus the bank's uploaded Word file.

    ``code``, the document type and the provider function are declared by the
    owning module and refreshed by ``sync_print_templates``. The file and its
    metadata belong to the bank administrator and are never overwritten by the
    synchronisation.
    """

    code = models.SlugField(_("code"), max_length=64, unique=True)
    name = models.CharField(_("name"), max_length=150)
    description = models.TextField(_("description"), blank=True)
    document_type = models.CharField(_("document type"), max_length=64)
    provider = models.CharField(_("provider"), max_length=64)
    file = models.BinaryField(
        _("file"),
        null=True,
        blank=True,
        editable=False,
        help_text=_("The Word template (.docx) uploaded by the administrator."),
    )
    file_name = models.CharField(_("file name"), max_length=255, blank=True)
    file_size = models.PositiveIntegerField(_("file size"), null=True, blank=True)
    file_updated_at = models.DateTimeField(_("file updated at"), null=True, blank=True)
    file_updated_by_id = models.PositiveBigIntegerField(_("file updated by"), null=True, blank=True)
    last_error = models.TextField(_("last error"), blank=True)
    last_error_at = models.DateTimeField(_("last error at"), null=True, blank=True)
    is_active = models.BooleanField(_("active"), default=True)

    class Meta:
        verbose_name = _("print template")
        verbose_name_plural = _("print templates")
        db_table = qualified_table("printing", "printing_printtemplate")
        ordering = ("name",)
        indexes = (models.Index(fields=["document_type"]),)

    def __str__(self):
        return self.name

    @property
    def has_file(self) -> bool:
        return bool(self.file)

    def localized_name(self, language: str | None = None) -> str:
        """Return the name in ``language`` with a fallback to the base name."""
        return pick_translation(
            self.name,
            ((row.language, row.name) for row in self.translations.all()),
            language,
        )


class PrintTemplateTranslation(TimeStampedModel):
    """The name of a print template in one language."""

    template = models.ForeignKey(
        PrintTemplate,
        on_delete=models.CASCADE,
        related_name="translations",
        verbose_name=_("print template"),
    )
    language = models.CharField(_("language"), max_length=8)
    name = models.CharField(_("name"), max_length=150)

    class Meta:
        verbose_name = _("print template translation")
        verbose_name_plural = _("print template translations")
        db_table = qualified_table("printing", "printing_printtemplatetranslation")
        ordering = ("language",)
        constraints = (
            models.UniqueConstraint(
                fields=["template", "language"],
                name="printing_unique_template_translation",
            ),
        )

    def __str__(self):
        return f"{self.template} [{self.language}]"


class PrintNumberSequence(TimeStampedModel):
    """The running number of one printed document type (bank-wide)."""

    document_type = models.CharField(_("document type"), max_length=64, unique=True)
    last_number = models.PositiveBigIntegerField(_("last number"), default=0)

    class Meta:
        verbose_name = _("print number sequence")
        verbose_name_plural = _("print number sequences")
        db_table = qualified_table("printing", "printing_printnumbersequence")

    def __str__(self):
        return f"{self.document_type}: {self.last_number}"


class PrintDocument(TimeStampedModel):
    """A rendered document stored as an immutable snapshot.

    The rendered Word file is kept so a reprint reproduces exactly what the
    cashier printed when the operation was posted, even if the template has
    changed since then. Names and the cash desk are snapshotted for the same
    reason.
    """

    document_type = models.CharField(_("document type"), max_length=64)
    document_type_name = models.CharField(_("document type name"), max_length=150)
    template_code = models.CharField(_("template"), max_length=64)
    template_name = models.CharField(_("template name"), max_length=150)
    operation_id = models.PositiveBigIntegerField(_("operation"))
    operation_type_code = models.CharField(_("operation type"), max_length=64)
    cash_desk_id = models.PositiveBigIntegerField(_("cash desk"))
    number = models.PositiveBigIntegerField(_("number"))
    file_name = models.CharField(_("file name"), max_length=255)
    content = models.BinaryField(_("content"))
    context = models.JSONField(_("context"), default=dict, blank=True)
    created_by_id = models.PositiveBigIntegerField(_("created by"), null=True, blank=True)

    class Meta:
        verbose_name = _("printed document")
        verbose_name_plural = _("printed documents")
        db_table = qualified_table("printing", "printing_printdocument")
        ordering = ("-created_at", "-id")
        indexes = (
            models.Index(fields=["operation_id"]),
            models.Index(fields=["cash_desk_id", "created_at"]),
        )
        constraints = (
            models.UniqueConstraint(
                fields=["document_type", "number"],
                name="printing_unique_document_number",
            ),
            models.UniqueConstraint(
                fields=["operation_id", "document_type"],
                name="printing_unique_operation_document_type",
            ),
        )

    def __str__(self):
        return f"{self.document_type} #{self.number} ({self.operation_type_code})"
