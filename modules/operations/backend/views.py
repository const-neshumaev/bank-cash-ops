"""REST API of the ``operations`` module.

The cash desk and the shift of a posted operation are never taken from the
request: they are resolved from the cashier's open shift through the ``core``
contract. Reads are narrowed to the cash desks the caller may access.
"""

from __future__ import annotations

from django.db import transaction
from django.db.models import Q
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
from modules.core.contracts import CASH_DESK_CONFIG, ORG_DIRECTORY
from modules.operations.backend import config, serializers
from modules.operations.backend import history as history_service
from modules.operations.backend.engine import post_operation, reverse_operation
from modules.operations.backend.filters import CashBalanceFilter, OperationFilter
from modules.operations.backend.models import (
    CashBalance,
    Operation,
    OperationTemplate,
    OperationType,
)
from modules.operations.backend.permission_codes import PermissionCode
from modules.operations.backend.thresholds import THRESHOLD_TYPES
from modules.operations.contracts import SlotValue
from modules.references.contracts import REFERENCE_DIRECTORY


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

    queryset = OperationType.objects.prefetch_related("slots", "translations").all()
    serializer_class = serializers.OperationTypeSerializer
    permission_classes = [PermissionRequired]
    required_permission = PermissionCode.VIEW
    permission_map = {
        "list": PermissionCode.VIEW,
        "retrieve": PermissionCode.VIEW,
        "update": PermissionCode.TYPES_MANAGE,
        "partial_update": PermissionCode.TYPES_MANAGE,
        "history": PermissionCode.VIEW,
    }
    lookup_field = "code"
    filterset_fields = ("kind", "is_external", "client_data_policy", "is_active")
    search_fields = ("code", "name")
    ordering_fields = ("name", "code")
    ordering = ("name",)

    def get_serializer_class(self):
        if self.action == "history":
            return serializers.OperationTypeHistorySerializer
        return super().get_serializer_class()

    def update(self, request, *args, **kwargs):
        partial = kwargs.pop("partial", False)
        instance = self.get_object()
        before = history_service.snapshot(instance)
        serializer = self.get_serializer(instance, data=request.data, partial=partial)
        serializer.is_valid(raise_exception=True)
        with transaction.atomic():
            self.perform_update(serializer)
            history_service.record_settings_change(
                instance, before=before, user=request.user
            )
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

        allowed_currencies = _cash_desk_config().cash_desk_currency_codes(shift.cash_desk_id)
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
