"""REST API of the ``operations`` module.

The cash desk and the shift of a posted operation are never taken from the
request: they are resolved from the cashier's open shift through the ``core``
contract. Reads are narrowed to the cash desks the caller may access.
"""

from __future__ import annotations

from django.utils.translation import gettext_lazy as _
from drf_spectacular.types import OpenApiTypes
from drf_spectacular.utils import extend_schema
from rest_framework import mixins, status, viewsets
from rest_framework.decorators import action
from rest_framework.exceptions import PermissionDenied, ValidationError
from rest_framework.response import Response
from rest_framework.views import APIView

from modules.common.backend.permissions import PermissionRequired
from modules.common.contracts import registry
from modules.core.contracts import ORG_DIRECTORY, REFERENCE_DIRECTORY
from modules.operations.backend import config, serializers
from modules.operations.backend.engine import post_operation, reverse_operation
from modules.operations.backend.filters import CashBalanceFilter, OperationFilter
from modules.operations.backend.models import (
    CashBalance,
    Operation,
    OperationsSettings,
    OperationType,
)
from modules.operations.backend.permission_codes import PermissionCode
from modules.operations.contracts import SlotValue


def _org_directory():
    return registry.get(ORG_DIRECTORY)


def _reference_directory():
    return registry.get(REFERENCE_DIRECTORY)


def _ensure_cash_desk_access(user, cash_desk_id):
    if not _org_directory().user_can_access_cash_desk(user.id, cash_desk_id):
        raise PermissionDenied(_("The cash desk is not available to you."))


def _cash_desk_operations_payload(cash_desk_id):
    configured = config.configured_operation_codes(cash_desk_id)
    operation_types = config.allowed_operation_types(cash_desk_id)
    return {
        "cash_desk_id": cash_desk_id,
        "configured": configured is not None,
        "operations": serializers.OperationTypeOptionSerializer(operation_types, many=True).data,
    }


def _current_shift(user):
    shift = _org_directory().get_open_shift(user.id)
    if shift is None:
        raise ValidationError(_("You have no open shift."))
    return shift


class OperationTypeViewSet(viewsets.ReadOnlyModelViewSet):
    """Read-only catalogue of operation types (for pickers and configuration)."""

    queryset = OperationType.objects.prefetch_related("slots").all()
    serializer_class = serializers.OperationTypeSerializer
    permission_classes = [PermissionRequired]
    required_permission = PermissionCode.VIEW
    lookup_field = "code"
    filterset_fields = ("kind", "is_external", "requires_client", "is_active")
    search_fields = ("code", "name")
    ordering_fields = ("name", "code")
    ordering = ("name",)


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
        "reverse": PermissionCode.REVERSE,
    }
    filterset_class = OperationFilter
    ordering_fields = ("posted_at", "number", "id")
    ordering = ("-posted_at", "-id")

    def get_queryset(self):
        queryset = super().get_queryset()
        cash_desk_ids = _org_directory().accessible_cash_desk_ids(self.request.user.id)
        if cash_desk_ids is not None:
            queryset = queryset.filter(cash_desk_id__in=cash_desk_ids)
        return queryset

    def get_serializer_class(self):
        if self.action == "create":
            return serializers.PostOperationSerializer
        return serializers.OperationSerializer

    def create(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data
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
            )
            for line in data["lines"]
        )

        allowed_currencies = _reference_directory().cash_desk_currency_codes(shift.cash_desk_id)
        if allowed_currencies is not None:
            for line in lines:
                if line.currency not in allowed_currencies:
                    raise ValidationError(
                        _("The currency %(currency)s is not available at this cash desk.")
                        % {"currency": line.currency}
                    )

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
        )
        return Response(
            serializers.OperationSerializer(operation).data,
            status=status.HTTP_201_CREATED,
        )

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


class OperationsSettingsView(APIView):
    """Read and update the bank-wide operations settings (a singleton)."""

    @extend_schema(responses=serializers.OperationsSettingsSerializer)
    def get(self, request):
        if not request.user.has_permission(PermissionCode.VIEW):
            raise PermissionDenied(_("You do not have permission to perform this action."))
        settings = OperationsSettings.load()
        return Response(serializers.OperationsSettingsSerializer(settings).data)

    @extend_schema(
        request=serializers.OperationsSettingsSerializer,
        responses=serializers.OperationsSettingsSerializer,
    )
    def patch(self, request):
        if not request.user.has_permission(PermissionCode.CONFIG_MANAGE):
            raise PermissionDenied(_("You do not have permission to perform this action."))
        settings = OperationsSettings.load()
        serializer = serializers.OperationsSettingsSerializer(
            settings, data=request.data, partial=True
        )
        serializer.is_valid(raise_exception=True)
        serializer.save()
        return Response(serializer.data)


class CashDeskOperationsView(APIView):
    """Read and update which operation types are available at a cash desk."""

    @extend_schema(responses={200: OpenApiTypes.OBJECT})
    def get(self, request, cash_desk_id):
        if not request.user.has_permission(PermissionCode.VIEW):
            raise PermissionDenied(_("You do not have permission to perform this action."))
        _ensure_cash_desk_access(request.user, cash_desk_id)
        return Response(_cash_desk_operations_payload(cash_desk_id))

    @extend_schema(
        request=serializers.CashDeskOperationsSerializer,
        responses={200: OpenApiTypes.OBJECT},
    )
    def put(self, request, cash_desk_id):
        if not request.user.has_permission(PermissionCode.CONFIG_MANAGE):
            raise PermissionDenied(_("You do not have permission to perform this action."))
        _ensure_cash_desk_access(request.user, cash_desk_id)
        serializer = serializers.CashDeskOperationsSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        config.set_operation_types(cash_desk_id, serializer.validated_data["operations"])
        return Response(_cash_desk_operations_payload(cash_desk_id))


class WorkplaceView(APIView):
    """The cashier screen context: shift, balances, operations and currencies."""

    @extend_schema(responses={200: OpenApiTypes.OBJECT})
    def get(self, request):
        if not request.user.has_permission(PermissionCode.VIEW):
            raise PermissionDenied(_("You do not have permission to perform this action."))

        shift = _org_directory().get_open_shift(request.user.id)
        if shift is None:
            return Response(
                {
                    "shift_id": None,
                    "cash_desk_id": None,
                    "currencies": [],
                    "rates": [],
                    "balances": [],
                    "operations": [],
                }
            )

        cash_desk_id = shift.cash_desk_id
        references = _reference_directory()
        allowed = references.cash_desk_currency_codes(cash_desk_id)
        currencies = [
            currency
            for currency in references.currencies()
            if allowed is None or currency.code in allowed
        ]
        rates = references.cash_desk_rates(cash_desk_id)
        balances = CashBalance.objects.filter(cash_desk_id=cash_desk_id).order_by("currency")
        return Response(
            {
                "shift_id": shift.id,
                "cash_desk_id": cash_desk_id,
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
                        "value": str(rate.value),
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
