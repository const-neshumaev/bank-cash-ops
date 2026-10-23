"""URL configuration of the ``printing`` module.

The module is mounted under ``/api/printing/`` (see ``config/urls.py``).
"""

from django.urls import path
from rest_framework.routers import SimpleRouter

from modules.printing.backend.views import (
    OperationDocumentsView,
    PrintDocumentFileView,
    PrintDocumentTypeViewSet,
    PrintTemplateViewSet,
)

router = SimpleRouter()
router.register("templates", PrintTemplateViewSet, basename="print-template")
router.register("document-types", PrintDocumentTypeViewSet, basename="print-document-type")

urlpatterns = [
    path(
        "operations/<int:operation_id>/documents/",
        OperationDocumentsView.as_view(),
        name="operation-documents",
    ),
    path(
        "documents/<int:document_id>/file/",
        PrintDocumentFileView.as_view(),
        name="print-document-file",
    ),
    *router.urls,
]
