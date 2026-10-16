from django.contrib.auth import get_user_model
from django.db.models import ProtectedError, Q
from django.utils.translation import gettext_lazy as _
from rest_framework import mixins, status, viewsets
from rest_framework.decorators import action
from rest_framework.exceptions import NotFound, PermissionDenied, ValidationError
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response
from rest_framework.throttling import ScopedRateThrottle
from rest_framework.views import APIView
from rest_framework_simplejwt.exceptions import TokenError
from rest_framework_simplejwt.tokens import RefreshToken
from rest_framework_simplejwt.views import TokenObtainPairView

from modules.common.backend import permissions_catalog
from modules.common.backend.permissions import PermissionRequired
from modules.core.backend import currency_config, scoping, serializers, shifts
from modules.core.backend.filters import ShiftFilter
from modules.core.backend.models import (
    BankSettings,
    Branch,
    CashDesk,
    Currency,
    CurrencyRate,
    CurrencyTemplate,
    Role,
    Shift,
)
from modules.core.backend.permission_codes import PermissionCode

User = get_user_model()


def _cash_desk_currencies_payload(cash_desk):
    """Return the effective currencies of ``cash_desk`` and where they come from."""
    effective = currency_config.effective_currency_config(cash_desk.id)
    currencies = (
        Currency.objects.filter(code__in=effective.codes)
        .prefetch_related("translations")
        .order_by("code")
    )
    return {
        "cash_desk": cash_desk.id,
        "configured": effective.source == currency_config.OWN,
        "source": effective.source,
        "template_branch_id": effective.template_branch_id,
        "currencies": serializers.CurrencySerializer(currencies, many=True).data,
    }


def _can_configure_currencies(user, branch_id):
    """Whether ``user`` may configure currencies of ``branch_id`` (``None`` = bank).

    The bank-wide permission grants everything; the branch-level permission is
    limited to the branches the user may access and never covers the bank default.
    """
    if user.has_permission(PermissionCode.CURRENCIES_CONFIG_MANAGE):
        return True
    if branch_id is None:
        return False
    if not user.has_permission(PermissionCode.CURRENCIES_CONFIG_MANAGE_BRANCH):
        return False
    branch_ids = scoping.accessible_branch_ids(user)
    return branch_ids is not None and branch_id in branch_ids


class LoginView(TokenObtainPairView):
    """Obtain a JWT access/refresh pair using an email and a password."""

    serializer_class = serializers.EmailTokenObtainPairSerializer
    throttle_classes = [ScopedRateThrottle]
    throttle_scope = "login"


class LogoutView(APIView):
    """Blacklist the supplied refresh token, ending the session server-side."""

    permission_classes = [IsAuthenticated]

    def post(self, request):
        refresh = request.data.get("refresh")
        if not refresh:
            raise ValidationError({"refresh": _("This field is required.")})
        try:
            RefreshToken(refresh).blacklist()
        except TokenError:
            # The token is already expired or blacklisted: nothing else to do.
            pass
        return Response(status=status.HTTP_205_RESET_CONTENT)


class MeView(APIView):
    """Read or update the profile of the currently authenticated user."""

    permission_classes = [IsAuthenticated]

    def get(self, request):
        return Response(serializers.UserSerializer(request.user).data)

    def patch(self, request):
        serializer = serializers.UserSelfUpdateSerializer(
            request.user, data=request.data, partial=True
        )
        serializer.is_valid(raise_exception=True)
        serializer.save()
        return Response(serializers.UserSerializer(request.user).data)


class ChangePasswordView(APIView):
    """Change the password of the currently authenticated user."""

    permission_classes = [IsAuthenticated]

    def post(self, request):
        serializer = serializers.ChangePasswordSerializer(
            data=request.data, context={"request": request}
        )
        serializer.is_valid(raise_exception=True)
        serializer.save()
        return Response({"detail": _("Password has been changed.")})


class PermissionCatalogView(APIView):
    """List the permission catalog so the administration UI can render it."""

    permission_classes = [PermissionRequired]
    required_permission = PermissionCode.ROLES_VIEW

    def get(self, request):
        entries = permissions_catalog.all_entries()
        return Response(serializers.PermissionSerializer(entries, many=True).data)


class BankSettingsView(APIView):
    """Read the bank-wide settings: the offered languages and the default one.

    Public on purpose: the SPA reads it before authentication to render the login
    screen in the bank's default language (see ADR 0015).
    """

    permission_classes = [AllowAny]

    def get(self, request):
        return Response(serializers.BankSettingsSerializer(BankSettings.load()).data)


class UserViewSet(viewsets.ModelViewSet):
    """CRUD administration of users."""

    queryset = User.objects.prefetch_related("roles").all()
    permission_classes = [PermissionRequired]
    permission_map = {
        "list": PermissionCode.USERS_VIEW,
        "retrieve": PermissionCode.USERS_VIEW,
        "create": PermissionCode.USERS_MANAGE,
        "update": PermissionCode.USERS_MANAGE,
        "partial_update": PermissionCode.USERS_MANAGE,
        "destroy": PermissionCode.USERS_MANAGE,
        "activate": PermissionCode.USERS_MANAGE,
        "deactivate": PermissionCode.USERS_MANAGE,
    }
    filterset_fields = ["is_active", "roles"]
    search_fields = ["email", "first_name", "last_name", "middle_name", "phone"]
    ordering_fields = ["email", "last_name", "first_name", "date_joined"]
    ordering = ["last_name", "first_name"]

    def get_serializer_class(self):
        if self.action == "create":
            return serializers.UserCreateSerializer
        if self.action in ("update", "partial_update"):
            return serializers.UserUpdateSerializer
        return serializers.UserSerializer

    def create(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        user = serializer.save()
        return Response(
            serializers.UserSerializer(user).data,
            status=status.HTTP_201_CREATED,
        )

    def update(self, request, *args, **kwargs):
        partial = kwargs.pop("partial", False)
        instance = self.get_object()
        serializer = serializers.UserUpdateSerializer(instance, data=request.data, partial=partial)
        serializer.is_valid(raise_exception=True)
        user = serializer.save()
        return Response(serializers.UserSerializer(user).data)

    def destroy(self, request, *args, **kwargs):
        """Deactivate a user by default, or delete it permanently on request.

        Pass ``?permanent=true`` to remove the record from the database. The
        soft delete is the default so that cash operations stay auditable.
        """
        user = self.get_object()
        if user == request.user:
            raise ValidationError({"detail": _("You cannot delete your own account.")})

        permanent = request.query_params.get("permanent", "").lower() in {"1", "true", "yes"}
        if permanent:
            user.delete()
        else:
            user.is_active = False
            user.save(update_fields=["is_active"])
        return Response(status=status.HTTP_204_NO_CONTENT)

    @action(detail=True, methods=["post"])
    def activate(self, request, pk=None):
        user = self.get_object()
        if not user.is_active:
            user.is_active = True
            user.save(update_fields=["is_active"])
        return Response(serializers.UserSerializer(user).data)

    @action(detail=True, methods=["post"])
    def deactivate(self, request, pk=None):
        user = self.get_object()
        if user == request.user:
            raise ValidationError({"detail": _("You cannot deactivate your own account.")})
        if user.is_active:
            user.is_active = False
            user.save(update_fields=["is_active"])
        return Response(serializers.UserSerializer(user).data)


class RoleViewSet(viewsets.ModelViewSet):
    """CRUD administration of the data-driven roles."""

    queryset = Role.objects.all()
    serializer_class = serializers.RoleSerializer
    permission_classes = [PermissionRequired]
    permission_map = {
        "list": PermissionCode.ROLES_VIEW,
        "retrieve": PermissionCode.ROLES_VIEW,
        "create": PermissionCode.ROLES_MANAGE,
        "update": PermissionCode.ROLES_MANAGE,
        "partial_update": PermissionCode.ROLES_MANAGE,
        "destroy": PermissionCode.ROLES_MANAGE,
    }
    filterset_fields = ["is_system"]
    search_fields = ["name", "code"]
    ordering_fields = ["name", "code"]
    ordering = ["name"]

    def destroy(self, request, *args, **kwargs):
        role = self.get_object()
        if role.is_system:
            raise ValidationError({"detail": _("A system role cannot be deleted.")})
        try:
            role.delete()
        except ProtectedError:
            raise ValidationError({"detail": _("The role is assigned to users.")}) from None
        return Response(status=status.HTTP_204_NO_CONTENT)


class BranchViewSet(viewsets.ModelViewSet):
    """CRUD administration of the bank branch hierarchy."""

    queryset = Branch.objects.select_related("parent").all()
    serializer_class = serializers.BranchSerializer
    permission_classes = [PermissionRequired]
    permission_map = {
        "list": PermissionCode.STRUCTURE_VIEW,
        "retrieve": PermissionCode.STRUCTURE_VIEW,
        "create": PermissionCode.STRUCTURE_MANAGE,
        "update": PermissionCode.STRUCTURE_MANAGE,
        "partial_update": PermissionCode.STRUCTURE_MANAGE,
        "destroy": PermissionCode.STRUCTURE_MANAGE,
        "catalog": PermissionCode.USERS_MANAGE,
    }
    filterset_fields = ["is_head_office", "is_active", "parent"]
    search_fields = ["name", "code", "address"]
    ordering_fields = ["name", "code"]
    ordering = ["name"]

    def get_queryset(self):
        queryset = super().get_queryset()
        # The catalog is intentionally unscoped: assigning access needs the full
        # branch tree, see the ``catalog`` action below.
        if self.action == "catalog":
            return queryset
        return scoping.scope_by_branch(queryset, self.request.user)

    def get_permissions(self):
        # Picking a branch in the workplace dialog must stay available to every
        # authenticated user, including cashiers without structure permissions.
        if self.action == "selectable":
            return [IsAuthenticated()]
        return super().get_permissions()

    @action(detail=False, methods=["get"])
    def selectable(self, request):
        """List accessible active branches that have an active cash desk."""
        queryset = (
            Branch.objects.filter(is_active=True, cash_desks__is_active=True)
            .distinct()
            .order_by("name")
        )
        queryset = scoping.scope_by_branch(queryset, request.user)
        search = request.query_params.get("search")
        if search:
            queryset = queryset.filter(Q(name__icontains=search) | Q(code__icontains=search))
        page = self.paginate_queryset(queryset)
        serializer = serializers.BranchOptionSerializer(page, many=True)
        return self.get_paginated_response(serializer.data)

    @action(detail=False, methods=["get"])
    def catalog(self, request):
        """List every branch for assigning access (permission ``core.users.manage``).

        The caller's own branch scope is ignored on purpose: configuring a user's
        access requires the full branch tree, otherwise an administrator with an
        empty scope could not assign anything.
        """
        queryset = Branch.objects.select_related("parent").order_by("name")
        search = request.query_params.get("search")
        if search:
            queryset = queryset.filter(Q(name__icontains=search) | Q(code__icontains=search))
        page = self.paginate_queryset(queryset)
        serializer = serializers.BranchSerializer(page, many=True)
        return self.get_paginated_response(serializer.data)

    def destroy(self, request, *args, **kwargs):
        branch = self.get_object()
        try:
            branch.delete()
        except ProtectedError:
            raise ValidationError(
                {"detail": _("The branch has nested branches or cash desks.")}
            ) from None
        return Response(status=status.HTTP_204_NO_CONTENT)


class CashDeskViewSet(viewsets.ModelViewSet):
    """CRUD administration of the cashier workstations."""

    queryset = CashDesk.objects.select_related("branch").all()
    serializer_class = serializers.CashDeskSerializer
    permission_classes = [PermissionRequired]
    permission_map = {
        "list": PermissionCode.STRUCTURE_VIEW,
        "retrieve": PermissionCode.STRUCTURE_VIEW,
        "create": PermissionCode.STRUCTURE_MANAGE,
        "update": PermissionCode.STRUCTURE_MANAGE,
        "partial_update": PermissionCode.STRUCTURE_MANAGE,
        "destroy": PermissionCode.STRUCTURE_MANAGE,
        "currencies": PermissionCode.STRUCTURE_VIEW,
    }
    filterset_fields = ["branch", "is_active"]
    search_fields = ["name", "code", "mac_address", "hostname"]
    ordering_fields = ["name", "code"]
    ordering = ["name"]

    def get_queryset(self):
        queryset = super().get_queryset()
        return scoping.scope_by_branch(queryset, self.request.user, "branch_id")

    def get_permissions(self):
        # Picking a cash desk in the workplace dialog must stay available to
        # every authenticated user, including cashiers without structure rights.
        if self.action == "selectable":
            return [IsAuthenticated()]
        return super().get_permissions()

    @action(detail=False, methods=["get"])
    def selectable(self, request):
        """List accessible active cash desks, optionally narrowed to a branch."""
        queryset = (
            CashDesk.objects.filter(is_active=True, branch__is_active=True)
            .select_related("branch")
            .order_by("branch__name", "name")
        )
        queryset = scoping.scope_by_branch(queryset, request.user, "branch_id")
        branch = request.query_params.get("branch")
        if branch:
            if not branch.isdigit():
                raise ValidationError({"branch": _("A valid integer is required.")})
            queryset = queryset.filter(branch_id=int(branch))
        search = request.query_params.get("search")
        if search:
            queryset = queryset.filter(Q(name__icontains=search) | Q(code__icontains=search))
        page = self.paginate_queryset(queryset)
        serializer = serializers.CashDeskOptionSerializer(page, many=True)
        return self.get_paginated_response(serializer.data)

    @action(detail=True, methods=["get", "put"], url_path="currencies")
    def currencies(self, request, pk=None):
        """Read the effective currencies of a cash desk, or replace its own set.

        A ``PUT`` with an empty list removes the cash desk's override so it falls
        back to the effective template.
        """
        cash_desk = self.get_object()
        if request.method == "PUT":
            if not _can_configure_currencies(request.user, cash_desk.branch_id):
                raise PermissionDenied(_("You do not have permission to perform this action."))
            serializer = serializers.CashDeskCurrenciesSerializer(data=request.data)
            serializer.is_valid(raise_exception=True)
            currency_config.set_cash_desk_currencies(
                cash_desk, serializer.validated_data["currencies"]
            )
        return Response(_cash_desk_currencies_payload(cash_desk))

    def destroy(self, request, *args, **kwargs):
        cash_desk = self.get_object()
        try:
            cash_desk.delete()
        except ProtectedError:
            raise ValidationError({"detail": _("The cash desk has shifts.")}) from None
        return Response(status=status.HTTP_204_NO_CONTENT)


class CurrencyViewSet(viewsets.ModelViewSet):
    """CRUD administration of the currency reference data."""

    queryset = Currency.objects.prefetch_related("translations")
    serializer_class = serializers.CurrencySerializer
    permission_classes = [PermissionRequired]
    permission_map = {
        "list": PermissionCode.STRUCTURE_VIEW,
        "retrieve": PermissionCode.STRUCTURE_VIEW,
        "create": PermissionCode.STRUCTURE_MANAGE,
        "update": PermissionCode.STRUCTURE_MANAGE,
        "partial_update": PermissionCode.STRUCTURE_MANAGE,
        "destroy": PermissionCode.STRUCTURE_MANAGE,
    }
    lookup_field = "code"
    filterset_fields = ["is_active"]
    search_fields = ["code", "name"]
    ordering_fields = ["code", "name"]
    ordering = ["code"]

    def destroy(self, request, *args, **kwargs):
        currency = self.get_object()
        try:
            currency.delete()
        except ProtectedError:
            raise ValidationError({"detail": _("The currency is used by a cash desk.")}) from None
        return Response(status=status.HTTP_204_NO_CONTENT)


class CurrencyRateViewSet(viewsets.ModelViewSet):
    """CRUD administration of the currency rates."""

    queryset = CurrencyRate.objects.select_related("currency", "base_currency", "cash_desk").all()
    serializer_class = serializers.CurrencyRateSerializer
    permission_classes = [PermissionRequired]
    permission_map = {
        "list": PermissionCode.STRUCTURE_VIEW,
        "retrieve": PermissionCode.STRUCTURE_VIEW,
        "create": PermissionCode.STRUCTURE_MANAGE,
        "update": PermissionCode.STRUCTURE_MANAGE,
        "partial_update": PermissionCode.STRUCTURE_MANAGE,
        "destroy": PermissionCode.STRUCTURE_MANAGE,
    }
    filterset_fields = ["currency", "base_currency", "rate_type", "cash_desk"]
    ordering_fields = ["currency", "rate_type", "effective_from"]
    ordering = ["currency", "rate_type", "-effective_from"]


class ShiftViewSet(
    mixins.ListModelMixin,
    mixins.RetrieveModelMixin,
    mixins.CreateModelMixin,
    viewsets.GenericViewSet,
):
    """Open, list and close cashier shifts."""

    queryset = Shift.objects.select_related("cash_desk", "cashier", "closed_by").all()
    permission_classes = [PermissionRequired]
    permission_map = {
        "list": PermissionCode.SHIFTS_VIEW,
        "retrieve": PermissionCode.SHIFTS_VIEW,
        "current": PermissionCode.SHIFTS_VIEW,
        "create": PermissionCode.SHIFTS_OPEN,
        "close": PermissionCode.SHIFTS_CLOSE,
        "force_close": PermissionCode.SHIFTS_MANAGE,
    }
    filterset_class = ShiftFilter
    ordering_fields = ["opened_at", "closed_at"]
    ordering = ["-opened_at"]

    def get_queryset(self):
        queryset = super().get_queryset()
        # list/retrieve use the full visibility rule (branch scope + role scope).
        if self.action in ("list", "retrieve"):
            return shifts.visible_shifts(user=self.request.user, queryset=queryset)
        # force-close stays within the accessible branches, so a manager cannot
        # close a shift outside their scope (a precise 404 otherwise).
        if self.action == "force_close":
            return scoping.scope_by_branch(queryset, self.request.user, "cash_desk__branch_id")
        # close acts on one's own shift: it keeps the unscoped queryset and
        # reports a precise 403/404.
        return queryset

    def get_serializer_class(self):
        if self.action == "create":
            return serializers.ShiftOpenSerializer
        return serializers.ShiftSerializer

    def create(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        shift = shifts.open_shift(
            cashier=request.user,
            cash_desk=serializer.validated_data["cash_desk"],
        )
        return Response(
            serializers.ShiftSerializer(shift).data,
            status=status.HTTP_201_CREATED,
        )

    @action(detail=False, methods=["get"])
    def current(self, request):
        """Return the open shift of the authenticated user, if any."""
        shift = self.get_queryset().filter(cashier=request.user, status=Shift.Status.OPEN).first()
        if shift is None:
            return Response(None)
        return Response(serializers.ShiftSerializer(shift).data)

    @action(detail=True, methods=["post"])
    def close(self, request, pk=None):
        """Close one's own open shift."""
        shift = self.get_object()
        if shift.cashier_id != request.user.id:
            raise PermissionDenied(_("You can only close your own shift."))
        shift = shifts.close_shift(shift=shift, closed_by=request.user)
        return Response(serializers.ShiftSerializer(shift).data)

    @action(detail=True, methods=["post"], url_path="force-close")
    def force_close(self, request, pk=None):
        """Close any open shift, including someone else's."""
        shift = self.get_object()
        shift = shifts.close_shift(shift=shift, closed_by=request.user)
        return Response(serializers.ShiftSerializer(shift).data)


def _currency_template_payload(template, branch_id):
    """Return a currency template payload; ``defined`` is false when none exists."""
    if template is None:
        return {"branch_id": branch_id, "defined": False, "currencies": []}
    return {
        "branch_id": branch_id,
        "defined": True,
        "currencies": serializers.CurrencySerializer(
            template.currencies.order_by("code"), many=True
        ).data,
    }


def _branch_template_or_404(user, branch_id):
    """Return the branch, or raise ``NotFound`` when it is unknown or out of scope.

    A holder of the bank-wide currency permission may read any existing branch;
    everyone else is limited to the branches they may access.
    """
    branch = Branch.objects.filter(pk=branch_id).first()
    if branch is None:
        raise NotFound(_("No branch matches the given query."))
    if user.has_permission(PermissionCode.CURRENCIES_CONFIG_MANAGE):
        return branch
    branch_ids = scoping.accessible_branch_ids(user)
    if branch_ids is not None and branch_id not in branch_ids:
        raise NotFound(_("No branch matches the given query."))
    return branch


class CurrencyTemplateListView(APIView):
    """List the currency templates visible to the caller (bank and branches)."""

    permission_classes = [PermissionRequired]
    required_permission = PermissionCode.STRUCTURE_VIEW

    def get(self, request):
        queryset = CurrencyTemplate.objects.prefetch_related("currencies")
        branch_ids = scoping.accessible_branch_ids(request.user)
        if branch_ids is not None:
            queryset = queryset.filter(Q(branch__isnull=True) | Q(branch_id__in=branch_ids))
        return Response(
            {
                "results": [
                    {
                        "branch_id": template.branch_id,
                        "currencies": serializers.CurrencySerializer(
                            template.currencies.order_by("code"), many=True
                        ).data,
                    }
                    for template in queryset.order_by("branch_id")
                ]
            }
        )


class BankCurrencyTemplateView(APIView):
    """Read, set or remove the bank-wide currency template."""

    permission_classes = [PermissionRequired]
    required_permission = PermissionCode.STRUCTURE_VIEW

    def get(self, request):
        template = (
            CurrencyTemplate.objects.prefetch_related("currencies")
            .filter(branch__isnull=True)
            .first()
        )
        return Response(_currency_template_payload(template, None))

    def put(self, request):
        if not _can_configure_currencies(request.user, None):
            raise PermissionDenied(_("You do not have permission to perform this action."))
        serializer = serializers.CashDeskCurrenciesSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        template = currency_config.set_template_currencies(
            None, serializer.validated_data["currencies"]
        )
        return Response(_currency_template_payload(template, None))

    def delete(self, request):
        if not _can_configure_currencies(request.user, None):
            raise PermissionDenied(_("You do not have permission to perform this action."))
        currency_config.delete_template(None)
        return Response(status=status.HTTP_204_NO_CONTENT)


class BranchCurrencyTemplateView(APIView):
    """Read, set or remove the currency template of a single branch."""

    permission_classes = [PermissionRequired]
    required_permission = PermissionCode.STRUCTURE_VIEW

    def get(self, request, branch_id):
        _branch_template_or_404(request.user, branch_id)
        template = (
            CurrencyTemplate.objects.prefetch_related("currencies")
            .filter(branch_id=branch_id)
            .first()
        )
        return Response(_currency_template_payload(template, branch_id))

    def put(self, request, branch_id):
        if not _can_configure_currencies(request.user, branch_id):
            raise PermissionDenied(_("You do not have permission to perform this action."))
        _branch_template_or_404(request.user, branch_id)
        serializer = serializers.CashDeskCurrenciesSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        template = currency_config.set_template_currencies(
            branch_id, serializer.validated_data["currencies"]
        )
        return Response(_currency_template_payload(template, branch_id))

    def delete(self, request, branch_id):
        if not _can_configure_currencies(request.user, branch_id):
            raise PermissionDenied(_("You do not have permission to perform this action."))
        currency_config.delete_template(branch_id)
        return Response(status=status.HTTP_204_NO_CONTENT)
