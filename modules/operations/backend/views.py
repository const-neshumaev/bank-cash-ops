"""REST API of the ``operations`` module.

The cash desk and the shift of a posted operation are never taken from the
request: they are resolved from the cashier's open shift through the ``core``
contract. Reads are narrowed to the cash desks the caller may access.
"""

from __future__ import annotations

import logging

from django.db import transaction
from django.db.models import Q
from django.utils import timezone
from django.utils.translation import gettext_lazy as _
from drf_spectacular.types import OpenApiTypes
from drf_spectacular.utils import extend_schema
from rest_framework import mixins, status, viewsets
from rest_framework.decorators import action
from rest_framework.exceptions import NotFound, PermissionDenied, ValidationError
from rest_framework.response import Response
from rest_framework.views import APIView

from modules.common.backend.permissions import PermissionRequired
from modules.common.contracts import registry
from modules.core.contracts import BANK_SETTINGS, CASH_DESK_CONFIG, ORG_DIRECTORY
from modules.operations.backend import config, serializers
from modules.operations.backend import history as history_service
from modules.operations.backend.engine import post_operation, reverse_operation
from modules.operations.backend.filters import CashBalanceFilter, OperationFilter
from modules.operations.backend.models import (
    CashBalance,
    Operation,
    OperationPrintConfig,
    OperationTemplate,
    OperationType,
)
from modules.operations.backend.permission_codes import PermissionCode
from modules.operations.backend.preparation import prepare_operation
from modules.operations.backend.printing import (
    operation_ids_with_documents,
    render_print_documents,
)
from modules.operations.backend.thresholds import THRESHOLD_TYPES
from modules.operations.contracts import SlotValue
from modules.printing.contracts import PRINT_DOCUMENT_SERVICE
from modules.references.contracts import REFERENCE_DIRECTORY

logger = logging.getLogger(__name__)


def _org_directory():
    return registry.get(ORG_DIRECTORY)


def _reference_directory():
    return registry.get(REFERENCE_DIRECTORY)


def _cash_desk_config():
    return registry.get(CASH_DESK_CONFIG)


def _can_view_cash_desk_config(user, cash_desk_id) -> bool:
    """Whether ``user`` may read the configuration of a cash desk."""
    if user.has_permission(PermissionCode.CONFIG_MANAGE):
        return True
    return _org_directory().user_can_access_cash_desk(user.id, cash_desk_id)


def _can_configure_operations(user, branch_id) -> bool:
    """Whether ``user`` may configure operations of ``branch_id`` (``None`` = bank).

    The bank-wide permission grants everything; the branch-level permission is
    limited to the branches the user may access and never covers the bank default.
    """
    if user.has_permission(PermissionCode.CONFIG_MANAGE):
        return True
    if branch_id is None:
        return False
    if not user.has_permission(PermissionCode.CONFIG_MANAGE_BRANCH):
        return False
    branch_ids = _org_directory().accessible_branch_ids(user.id)
    return branch_ids is not None and branch_id in branch_ids


def _ensure_branch_readable(user, branch_id) -> None:
    """Raise ``NotFound`` when a branch template is outside the user's scope."""
    branch_ids = _org_directory().accessible_branch_ids(user.id)
    if branch_ids is not None and branch_id not in branch_ids:
        raise NotFound(_("No such branch."))


def _cash_desk_operations_payload(cash_desk_id):
    effective = config.effective_operation_config(cash_desk_id)
    operation_types = config.allowed_operation_types(cash_desk_id)
    return {
        "cash_desk_id": cash_desk_id,
        "configured": effective.source == config.OWN,
        "source": effective.source,
        "template_branch_id": effective.template_branch_id,
        "operations": serializers.OperationTypeOptionSerializer(operation_types, many=True).data,
    }


def _operation_template_payload(branch_id):
    """Return an operation template payload; ``defined`` is false when none exists."""
    template = (
        OperationTemplate.objects.prefetch_related("operation_types")
        .filter(branch_id=branch_id)
        .first()
    )
    if template is None:
        return {"branch_id": branch_id, "defined": False, "operations": []}
    return {
        "branch_id": branch_id,
        "defined": True,
        "operations": serializers.OperationTypeOptionSerializer(
            template.operation_types.order_by("name"), many=True
        ).data,
    }


def _current_shift(user):
    shift = _org_directory().get_open_shift(user.id)
    if shift is None:
        raise ValidationError(_("You have no open shift."))
    return shift


def _print_service():
    return registry.get(PRINT_DOCUMENT_SERVICE)


def _print_template_payload(template) -> dict:
    return {
        "code": template.code,
        "name": template.name,
        "document_type": template.document_type,
        "document_type_name": template.document_type_name,
        "description": template.description,
        "has_file": template.has_file,
        "file_name": template.file_name,
        "is_active": template.is_active,
        "variables": [
            {
                "code": variable.code,
                "description": str(variable.description),
                "example": variable.example,
            }
            for variable in template.variables
        ],
    }


def _print_document_types_payload() -> list[dict]:
    document_types = _print_service().document_types()
    return [
        {
            "code": document_type.code,
            "name": document_type.name,
            "description": document_type.description,
            "numbering_scope": document_type.numbering_scope,
            "is_active": document_type.is_active,
            "templates": [
                _print_template_payload(template) for template in document_type.templates
            ],
        }
        for document_type in document_types
    ]


def _print_names_context(context: dict) -> dict:
    """Add the printable names used by the nested print-config serializer."""
    try:
        document_types = _print_service().document_types()
    except LookupError:
        return context
    context["print_document_type_names"] = {
        document_type.code: document_type.name for document_type in document_types
    }
    context["print_template_names"] = {
        template.code: template.name
        for document_type in document_types
        for template in document_type.templates
    }
    return context


class OperationTypeViewSet(
    mixins.ListModelMixin,
    mixins.RetrieveModelMixin,
    mixins.UpdateModelMixin,
    viewsets.GenericViewSet,
):
    """Catalogue of operation types and their administrator-managed settings.

    Reading and the settings history require ``operations.view``; changing the
    client-data policy, threshold or activity requires
    ``operations.types.manage``. The declarative metadata is read-only.
    """

    queryset = OperationType.objects.prefetch_related(
        "slots", "translations", "print_configs"
    ).all()
    serializer_class = serializers.OperationTypeSerializer
    permission_classes = [PermissionRequired]
    required_permission = PermissionCode.VIEW
    permission_map = {
        "list": PermissionCode.VIEW,
        "retrieve": PermissionCode.VIEW,
        "update": PermissionCode.TYPES_MANAGE,
        "partial_update": PermissionCode.TYPES_MANAGE,
        "history": PermissionCode.VIEW,
        "print_configs": PermissionCode.VIEW,
    }
    lookup_field = "code"
    filterset_fields = ("kind", "is_external", "client_data_policy", "is_active")
    search_fields = ("code", "name")
    ordering_fields = ("name", "code")
    ordering = ("name",)

    def get_serializer_class(self):
        if self.action == "history":
            return serializers.OperationTypeHistorySerializer
        if self.action == "print_configs":
            return serializers.OperationPrintConfigSerializer
        return super().get_serializer_class()

    def get_serializer_context(self):
        return _print_names_context(super().get_serializer_context())

    def update(self, request, *args, **kwargs):
        partial = kwargs.pop("partial", False)
        instance = self.get_object()
        before = history_service.snapshot(instance)
        serializer = self.get_serializer(instance, data=request.data, partial=partial)
        serializer.is_valid(raise_exception=True)
        with transaction.atomic():
            self.perform_update(serializer)
            history_service.record_settings_change(instance, before=before, user=request.user)
        return Response(serializer.data)

    @action(detail=True, methods=["get"])
    def history(self, request, code=None):
        """Return the settings change history of one operation type."""
        operation_type = self.get_object()
        queryset = operation_type.settings_changes.all()
        page = self.paginate_queryset(queryset)
        serializer = self.get_serializer(page if page is not None else queryset, many=True)
        if page is not None:
            return self.get_paginated_response(serializer.data)
        return Response(serializer.data)

    @action(detail=True, methods=["get", "put"], url_path="print-configs")
    def print_configs(self, request, code=None):
        """Read or replace the printed documents configured for the type."""
        operation_type = self.get_object()
        if request.method == "PUT":
            if not request.user.has_permission(PermissionCode.TYPES_MANAGE):
                raise PermissionDenied(_("You do not have permission to perform this action."))
            rows = self._validate_print_configs(request.data.get("configs", []))
            with transaction.atomic():
                operation_type.print_configs.all().delete()
                OperationPrintConfig.objects.bulk_create(
                    [
                        OperationPrintConfig(operation_type=operation_type, **row)
                        for row in rows
                    ]
                )
        configs = OperationPrintConfig.objects.filter(operation_type=operation_type)
        serializer = self.get_serializer(configs, many=True)
        return Response(serializer.data)

    @staticmethod
    def _validate_print_configs(rows) -> list[dict]:
        """Check the bindings against the document types declared by ``printing``."""
        if not isinstance(rows, list):
            raise ValidationError({"configs": _("A list of print documents is expected.")})
        document_types = {item.code: item for item in _print_service().document_types()}
        result: list[dict] = []
        seen: set[str] = set()
        for row in rows:
            if not isinstance(row, dict):
                raise ValidationError({"configs": _("Invalid print document entry.")})
            document_type = str(row.get("document_type") or "").strip()
            template = str(row.get("template") or "").strip()
            if document_type not in document_types:
                raise ValidationError(
                    {
                        "document_type": _("Unknown print document type '%(code)s'.")
                        % {"code": document_type}
                    }
                )
            available = {
                item.code for item in document_types[document_type].templates if item.is_active
            }
            if template not in available:
                raise ValidationError(
                    {"template": _("Unknown print template '%(code)s'.") % {"code": template}}
                )
            if document_type in seen:
                raise ValidationError(
                    {"document_type": _("The print document type is selected more than once.")}
                )
            seen.add(document_type)
            result.append(
                {
                    "document_type": document_type,
                    "template_code": template,
                    "is_active": bool(row.get("is_active", True)),
                }
            )
        return result


class ThresholdTypeListView(APIView):
    """List the predefined threshold functions for the administration UI."""

    permission_classes = [PermissionRequired]
    required_permission = PermissionCode.VIEW

    def get(self, request):
        return Response(
            [
                {
                    "code": item.code,
                    "name": str(item.name),
                    "requires_currency": item.requires_currency,
                }
                for item in THRESHOLD_TYPES
            ]
        )


class CashBalanceViewSet(viewsets.ReadOnlyModelViewSet):
    """Read-only list of the cash on hand, narrowed to the caller's cash desks."""

    queryset = CashBalance.objects.all()
    serializer_class = serializers.CashBalanceSerializer
    permission_classes = [PermissionRequired]
    required_permission = PermissionCode.VIEW
    filterset_class = CashBalanceFilter
    ordering_fields = ("cash_desk_id", "currency")
    ordering = ("cash_desk_id", "currency")

    def get_queryset(self):
        queryset = super().get_queryset()
        cash_desk_ids = _org_directory().accessible_cash_desk_ids(self.request.user.id)
        if cash_desk_ids is not None:
            queryset = queryset.filter(cash_desk_id__in=cash_desk_ids)
        return queryset


class OperationViewSet(
    mixins.ListModelMixin,
    mixins.RetrieveModelMixin,
    mixins.CreateModelMixin,
    viewsets.GenericViewSet,
):
    """Post, list and reverse cash operations."""

    queryset = (
        Operation.objects.select_related("operation_type")
        .prefetch_related("lines", "movements")
        .all()
    )
    permission_classes = [PermissionRequired]
    permission_map = {
        "list": PermissionCode.VIEW,
        "retrieve": PermissionCode.VIEW,
        "create": PermissionCode.CREATE,
        "preview": PermissionCode.CREATE,
        "reverse": PermissionCode.REVERSE,
    }
    filterset_class = OperationFilter
    ordering_fields = ("posted_at", "number", "id")
    ordering = ("-posted_at", "-id")

    def list(self, request, *args, **kwargs):
        """List operations, marking which of them already have printed documents."""
        queryset = self.filter_queryset(self.get_queryset())
        page = self.paginate_queryset(queryset)
        rows = page if page is not None else list(queryset)
        context = self.get_serializer_context()
        context["print_operation_ids"] = operation_ids_with_documents(
            operation.id for operation in rows
        )
        serializer = self.get_serializer(rows, many=True, context=context)
        if page is not None:
            return self.get_paginated_response(serializer.data)
        return Response(serializer.data)

    def get_queryset(self):
        queryset = super().get_queryset()
        cash_desk_ids = _org_directory().accessible_cash_desk_ids(self.request.user.id)
        if cash_desk_ids is not None:
            queryset = queryset.filter(cash_desk_id__in=cash_desk_ids)
        return queryset

    def get_serializer_class(self):
        if self.action in ("create", "preview"):
            return serializers.PostOperationSerializer
        return serializers.OperationSerializer

    def _validate_post_request(self, request, data):
        """Apply the posting rules shared by the preview and the create action."""
        operation_type = data["operation_type"]

        if operation_type.permission_code and not request.user.has_permission(
            operation_type.permission_code
        ):
            raise PermissionDenied(_("You are not allowed to perform this operation."))

        shift = _current_shift(request.user)

        if not config.is_operation_allowed(shift.cash_desk_id, operation_type):
            raise ValidationError(_("The operation is not available at this cash desk."))

        lines = tuple(
            SlotValue(
                slot=line["slot"],
                currency=line["currency"],
                amount=line["amount"],
                rate=line.get("rate"),
                rate_is_individual=line.get("rate_is_individual", False),
            )
            for line in data["lines"]
        )

        allowed_currencies = _cash_desk_config().cash_desk_currency_codes(shift.cash_desk_id)
        for line in lines:
            if line.currency not in allowed_currencies:
                raise ValidationError(
                    _("The currency %(currency)s is not available at this cash desk.")
                    % {"currency": line.currency}
                )
        return operation_type, shift, lines

    @action(detail=False, methods=["post"])
    def preview(self, request):
        """Validate an operation and return the prepared lines and client policy."""
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data
        operation_type, shift, lines = self._validate_post_request(request, data)
        prepared = prepare_operation(
            operation_type=operation_type,
            cash_desk_id=shift.cash_desk_id,
            lines=lines,
            basis_slot=data["basis_slot"],
        )
        requirement = prepared.client_data
        return Response(
            {
                "operation_type": operation_type.code,
                "operation_type_name": operation_type.localized_name(),
                "lines": serializers.OperationLineSerializer(
                    prepared.lines, many=True
                ).data,
                "client_data": {
                    "policy": requirement.policy,
                    "required": requirement.required,
                    "reason": requirement.reason,
                    "amount": None if requirement.amount is None else str(requirement.amount),
                    "threshold": (
                        None if requirement.threshold is None else str(requirement.threshold)
                    ),
                    "currency": requirement.currency,
                },
            }
        )

    def create(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data
        operation_type, shift, lines = self._validate_post_request(request, data)

        operation = post_operation(
            operation_type=operation_type,
            cash_desk_id=shift.cash_desk_id,
            shift_id=shift.id,
            cashier_id=request.user.id,
            lines=lines,
            client_name=data["client_name"],
            client_document=data["client_document"],
            comment=data["comment"],
            idempotency_key=data["idempotency_key"],
            basis_slot=data["basis_slot"],
        )
        print_documents = ()
        try:
            print_documents = render_print_documents(operation, user_id=request.user.id)
        except Exception:  # a print failure must not undo a posted operation
            logger.exception("Could not render print documents for operation %s", operation.id)
        payload = serializers.OperationSerializer(
            operation, context=self.get_serializer_context()
        ).data
        payload["print_documents"] = serializers.PrintDocumentInfoSerializer(
            print_documents, many=True
        ).data
        return Response(payload, status=status.HTTP_201_CREATED)

    @action(detail=True, methods=["post"])
    def reverse(self, request, pk=None):
        """Reverse a posted operation (storno)."""
        operation = self.get_object()
        shift = _current_shift(request.user)
        reversal = reverse_operation(
            operation=operation,
            cashier_id=request.user.id,
            shift_id=shift.id,
            comment=request.data.get("comment", ""),
            idempotency_key=request.data.get("idempotency_key", ""),
        )
        return Response(
            serializers.OperationSerializer(reversal).data,
            status=status.HTTP_201_CREATED,
        )


class CashDeskOperationsView(APIView):
    """Read and update which operation types are effective at a cash desk.

    A ``PUT`` with an empty list removes the cash desk's override, so it falls back
    to the effective template (deny by default when no template applies).
    """

    @extend_schema(responses={200: OpenApiTypes.OBJECT})
    def get(self, request, cash_desk_id):
        if not request.user.has_permission(PermissionCode.VIEW):
            raise PermissionDenied(_("You do not have permission to perform this action."))
        if not _can_view_cash_desk_config(request.user, cash_desk_id):
            raise PermissionDenied(_("The cash desk is not available to you."))
        return Response(_cash_desk_operations_payload(cash_desk_id))

    @extend_schema(
        request=serializers.CashDeskOperationsSerializer,
        responses={200: OpenApiTypes.OBJECT},
    )
    def put(self, request, cash_desk_id):
        cash_desk = _org_directory().get_cash_desk(cash_desk_id)
        if cash_desk is None:
            raise NotFound(_("No cash desk matches the given query."))
        if not _can_configure_operations(request.user, cash_desk.branch_id):
            raise PermissionDenied(_("You do not have permission to perform this action."))
        serializer = serializers.CashDeskOperationsSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        config.set_operation_types(cash_desk_id, serializer.validated_data["operations"])
        return Response(_cash_desk_operations_payload(cash_desk_id))


class OperationTemplateListView(APIView):
    """List the operation templates visible to the caller (bank and branches)."""

    @extend_schema(responses={200: OpenApiTypes.OBJECT})
    def get(self, request):
        if not request.user.has_permission(PermissionCode.VIEW):
            raise PermissionDenied(_("You do not have permission to perform this action."))
        queryset = OperationTemplate.objects.prefetch_related("operation_types")
        branch_ids = _org_directory().accessible_branch_ids(request.user.id)
        if branch_ids is not None:
            queryset = queryset.filter(Q(branch_id__isnull=True) | Q(branch_id__in=branch_ids))
        return Response(
            {
                "results": [
                    serializers.OperationTemplateSerializer(template).data
                    for template in queryset.order_by("branch_id")
                ]
            }
        )


class BankOperationTemplateView(APIView):
    """Read, set or remove the bank-wide operation template."""

    @extend_schema(responses={200: OpenApiTypes.OBJECT})
    def get(self, request):
        if not request.user.has_permission(PermissionCode.VIEW):
            raise PermissionDenied(_("You do not have permission to perform this action."))
        return Response(_operation_template_payload(None))

    @extend_schema(
        request=serializers.CashDeskOperationsSerializer,
        responses={200: OpenApiTypes.OBJECT},
    )
    def put(self, request):
        if not _can_configure_operations(request.user, None):
            raise PermissionDenied(_("You do not have permission to perform this action."))
        serializer = serializers.CashDeskOperationsSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        config.set_template_operation_types(None, serializer.validated_data["operations"])
        return Response(_operation_template_payload(None))

    @extend_schema(responses={204: None})
    def delete(self, request):
        if not _can_configure_operations(request.user, None):
            raise PermissionDenied(_("You do not have permission to perform this action."))
        config.delete_template(None)
        return Response(status=status.HTTP_204_NO_CONTENT)


class BranchOperationTemplateView(APIView):
    """Read, set or remove the operation template of a single branch."""

    @extend_schema(responses={200: OpenApiTypes.OBJECT})
    def get(self, request, branch_id):
        if not request.user.has_permission(PermissionCode.VIEW):
            raise PermissionDenied(_("You do not have permission to perform this action."))
        _ensure_branch_readable(request.user, branch_id)
        return Response(_operation_template_payload(branch_id))

    @extend_schema(
        request=serializers.CashDeskOperationsSerializer,
        responses={200: OpenApiTypes.OBJECT},
    )
    def put(self, request, branch_id):
        if not _can_configure_operations(request.user, branch_id):
            raise PermissionDenied(_("You do not have permission to perform this action."))
        serializer = serializers.CashDeskOperationsSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        config.set_template_operation_types(branch_id, serializer.validated_data["operations"])
        return Response(_operation_template_payload(branch_id))

    @extend_schema(responses={204: None})
    def delete(self, request, branch_id):
        if not _can_configure_operations(request.user, branch_id):
            raise PermissionDenied(_("You do not have permission to perform this action."))
        config.delete_template(branch_id)
        return Response(status=status.HTTP_204_NO_CONTENT)


class PrintTemplateListView(APIView):
    """Available printed document types and print forms for configuration."""

    permission_classes = [PermissionRequired]
    required_permission = PermissionCode.VIEW

    @extend_schema(responses={200: OpenApiTypes.OBJECT})
    def get(self, request):
        return Response(_print_document_types_payload())


class WorkplaceView(APIView):
    """The cashier screen context: shift, balances, operations and currencies."""

    @extend_schema(responses={200: OpenApiTypes.OBJECT})
    def get(self, request):
        if not request.user.has_permission(PermissionCode.VIEW):
            raise PermissionDenied(_("You do not have permission to perform this action."))

        shift = _org_directory().get_open_shift(request.user.id)
        if shift is None:
            settings = registry.get(BANK_SETTINGS).get_settings(timezone.localdate())
            return Response(
                {
                    "shift_id": None,
                    "cash_desk_id": None,
                    "base_currency": settings.base_currency,
                    "conversion_mode": settings.conversion_mode,
                    "base_value": (
                        None if settings.base_value is None else str(settings.base_value)
                    ),
                    "base_value_date": (
                        None
                        if settings.base_value_date is None
                        else settings.base_value_date.isoformat()
                    ),
                    "currencies": [],
                    "rates": [],
                    "balances": [],
                    "operations": [],
                }
            )

        cash_desk_id = shift.cash_desk_id
        settings = registry.get(BANK_SETTINGS).get_settings(timezone.localdate())
        currencies_directory = _reference_directory()
        cash_desk_config = _cash_desk_config()
        allowed = cash_desk_config.cash_desk_currency_codes(cash_desk_id)
        currencies = [
            currency for currency in currencies_directory.currencies() if currency.code in allowed
        ]
        rates = cash_desk_config.cash_desk_rates(cash_desk_id)
        balances = CashBalance.objects.filter(cash_desk_id=cash_desk_id).order_by("currency")
        return Response(
            {
                "shift_id": shift.id,
                "cash_desk_id": cash_desk_id,
                "base_currency": settings.base_currency,
                "conversion_mode": settings.conversion_mode,
                "base_value": None if settings.base_value is None else str(settings.base_value),
                "base_value_date": (
                    None
                    if settings.base_value_date is None
                    else settings.base_value_date.isoformat()
                ),
                "currencies": [
                    {
                        "code": currency.code,
                        "name": currency.name,
                        "symbol": currency.symbol,
                        "minor_units": currency.minor_units,
                    }
                    for currency in currencies
                ],
                "rates": [
                    {
                        "currency": rate.currency_code,
                        "base_currency": rate.base_currency_code,
                        "rate_type": rate.rate_type,
                        "units": rate.units,
                        "value": str(rate.value),
                        "value_per_unit": str(rate.value_per_unit),
                        "effective_from": rate.effective_from.isoformat(),
                    }
                    for rate in rates
                ],
                "balances": serializers.CashBalanceSerializer(balances, many=True).data,
                "operations": serializers.WorkplaceOperationSerializer(
                    config.allowed_operation_types(cash_desk_id), many=True
                ).data,
            }
        )
