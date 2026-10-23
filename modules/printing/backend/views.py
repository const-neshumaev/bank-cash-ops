"""REST API of the ``printing`` module."""

from __future__ import annotations

import zipfile
from io import BytesIO

from django.http import HttpResponse
from django.utils import timezone
from django.utils.http import content_disposition_header
from django.utils.translation import gettext_lazy as _
from rest_framework import mixins, viewsets
from rest_framework.decorators import action
from rest_framework.exceptions import NotFound, PermissionDenied, ValidationError
from rest_framework.parsers import FormParser, MultiPartParser
from rest_framework.response import Response
from rest_framework.views import APIView

from modules.common.backend.permissions import PermissionRequired
from modules.common.contracts import registry
from modules.core.contracts import ORG_DIRECTORY
from modules.printing.backend import serializers
from modules.printing.backend.models import PrintDocumentType, PrintTemplate
from modules.printing.backend.permission_codes import PermissionCode
from modules.printing.backend.rendering import print_document_service
from modules.printing.contracts import DOCX_CONTENT_TYPE

MAX_TEMPLATE_SIZE = 10 * 1024 * 1024


def _accessible_cash_desk_ids(user) -> set[int] | None:
    """Cash desks the user may see; ``None`` means every cash desk."""
    return registry.get(ORG_DIRECTORY).accessible_cash_desk_ids(user.id)


def _file_response(file_name: str, content: bytes) -> HttpResponse:
    response = HttpResponse(content, content_type=DOCX_CONTENT_TYPE)
    response["Content-Disposition"] = content_disposition_header(True, file_name)
    return response


def _read_docx(upload) -> bytes:
    """Validate the uploaded file and return its bytes."""
    name = (upload.name or "").lower()
    if not name.endswith(".docx"):
        raise ValidationError({"file": _("Upload a Word document (.docx).")})
    if upload.size > MAX_TEMPLATE_SIZE:
        raise ValidationError({"file": _("The template file is too large (maximum 10 MB).")})
    content = upload.read()
    try:
        with zipfile.ZipFile(BytesIO(content)) as archive:
            if "word/document.xml" not in archive.namelist():
                raise ValueError
    except (zipfile.BadZipFile, ValueError):
        raise ValidationError({"file": _("The file is not a valid Word document.")}) from None
    return content


class PrintTemplateViewSet(
    mixins.ListModelMixin,
    mixins.RetrieveModelMixin,
    viewsets.GenericViewSet,
):
    """Print forms available in the bank and their uploaded Word templates.

    Reading and downloading a template requires ``printing.templates.view``;
    uploading a new file requires ``printing.templates.manage``.
    """

    queryset = PrintTemplate.objects.prefetch_related("translations").all()
    serializer_class = serializers.PrintTemplateSerializer
    permission_classes = [PermissionRequired]
    required_permission = PermissionCode.TEMPLATES_VIEW
    permission_map = {
        "list": PermissionCode.TEMPLATES_VIEW,
        "retrieve": PermissionCode.TEMPLATES_VIEW,
        "file": PermissionCode.TEMPLATES_VIEW,
    }
    lookup_field = "code"
    filterset_fields = ("document_type", "is_active")
    search_fields = ("code", "name", "description")
    ordering_fields = ("name", "code")
    ordering = ("name",)

    @action(
        detail=True,
        methods=["get", "post"],
        url_path="file",
        parser_classes=[MultiPartParser, FormParser],
    )
    def file(self, request, code=None):
        """Download or replace the Word template of a print form."""
        template = self.get_object()
        if request.method == "POST":
            if not request.user.has_permission(PermissionCode.TEMPLATES_MANAGE):
                raise PermissionDenied(_("You do not have permission to perform this action."))
            upload = self._uploaded_file(request)
            content = _read_docx(upload)
            template.file = content
            template.file_name = upload.name
            template.file_size = len(content)
            template.file_updated_at = timezone.now()
            template.file_updated_by_id = request.user.id
            template.last_error = ""
            template.last_error_at = None
            template.save(
                update_fields=[
                    "file",
                    "file_name",
                    "file_size",
                    "file_updated_at",
                    "file_updated_by_id",
                    "last_error",
                    "last_error_at",
                    "updated_at",
                ]
            )
            return Response(self.get_serializer(template).data)

        if not template.file:
            raise NotFound(_("The template file has not been uploaded yet."))
        return _file_response(
            template.file_name or f"{template.code}.docx",
            bytes(template.file),
        )

    @staticmethod
    def _uploaded_file(request):
        serializer = serializers.PrintTemplateUploadSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        return serializer.validated_data["file"]


class PrintDocumentTypeViewSet(mixins.ListModelMixin, viewsets.GenericViewSet):
    """Printed document types (cash receipt, order, ...)."""

    queryset = PrintDocumentType.objects.prefetch_related("translations").all()
    serializer_class = serializers.PrintDocumentTypeSerializer
    permission_classes = [PermissionRequired]
    required_permission = PermissionCode.TEMPLATES_VIEW
    filterset_fields = ("is_active",)
    ordering = ("name",)


class OperationDocumentsView(APIView):
    """Documents printed for one operation (for reprinting)."""

    permission_classes = [PermissionRequired]
    required_permission = PermissionCode.PRINT

    def get(self, request, operation_id: int):
        documents = print_document_service.operation_documents(operation_id)
        cash_desk_ids = _accessible_cash_desk_ids(request.user)
        if cash_desk_ids is not None:
            documents = tuple(
                document for document in documents if document.cash_desk_id in cash_desk_ids
            )
        return Response(serializers.PrintDocumentInfoSerializer(documents, many=True).data)


class PrintDocumentFileView(APIView):
    """Download one rendered document."""

    permission_classes = [PermissionRequired]
    required_permission = PermissionCode.PRINT

    def get(self, request, document_id: int):
        document = print_document_service.document(document_id)
        if document is None:
            raise NotFound(_("No such document."))
        cash_desk_ids = _accessible_cash_desk_ids(request.user)
        if cash_desk_ids is not None and document.cash_desk_id not in cash_desk_ids:
            raise NotFound(_("No such document."))
        file = print_document_service.document_file(document_id)
        if file is None:
            raise NotFound(_("No such document."))
        return _file_response(file.file_name, file.content)
