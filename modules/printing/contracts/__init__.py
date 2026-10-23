"""Public contract of the ``printing`` module.

Other modules use the types re-exported here and resolve the services through
``modules.common.contracts.registry``.
"""

from modules.printing.contracts.dto import (
    PrintBinding,
    PrintDocumentHeader,
    PrintDocumentInfo,
    PrintDocumentTypeInfo,
    PrintDocumentTypeSpec,
    PrintFile,
    PrintOperation,
    PrintOperationLine,
    PrintTemplateInfo,
    PrintTemplateSpec,
    PrintVariable,
)
from modules.printing.contracts.services import (
    PrintDocumentService,
    PrintTemplateRegistry,
    PrintVariableProvider,
)

#: Name under which the print template registry is published. Modules declaring
#: their own forms resolve it in ``AppConfig.ready``::
#:
#:     registry.get(PRINT_TEMPLATE_REGISTRY).register_template(spec, Provider())
PRINT_TEMPLATE_REGISTRY = "printing.templates"

#: Name under which the rendering/document service is published.
PRINT_DOCUMENT_SERVICE = "printing.documents"

#: Content type of the generated (and uploaded) Word documents.
DOCX_CONTENT_TYPE = "application/vnd.openxmlformats-officedocument.wordprocessingml.document"

__all__ = [
    "DOCX_CONTENT_TYPE",
    "PRINT_DOCUMENT_SERVICE",
    "PRINT_TEMPLATE_REGISTRY",
    "PrintBinding",
    "PrintDocumentHeader",
    "PrintDocumentInfo",
    "PrintDocumentService",
    "PrintDocumentTypeInfo",
    "PrintDocumentTypeSpec",
    "PrintFile",
    "PrintOperation",
    "PrintOperationLine",
    "PrintTemplateInfo",
    "PrintTemplateRegistry",
    "PrintTemplateSpec",
    "PrintVariable",
    "PrintVariableProvider",
]
