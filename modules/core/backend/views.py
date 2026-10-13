from django.contrib.auth import get_user_model
from django.db.models import ProtectedError, Q
from django.utils.translation import gettext_lazy as _
from rest_framework import mixins, status, viewsets
from rest_framework.decorators import action
from rest_framework.exceptions import PermissionDenied, ValidationError
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.throttling import ScopedRateThrottle
from rest_framework.views import APIView
from rest_framework_simplejwt.exceptions import TokenError
from rest_framework_simplejwt.tokens import RefreshToken
from rest_framework_simplejwt.views import TokenObtainPairView

from modules.core.backend import serializers, shifts
from modules.core.backend.filters import ShiftFilter
from modules.core.backend.models import Branch, CashDesk, Role, Shift
from modules.core.backend.permission_codes import CATALOG, PermissionCode
from modules.core.backend.permissions import PermissionRequired

User = get_user_model()


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
        return Response(serializers.PermissionSerializer(CATALOG, many=True).data)


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
        serializer = serializers.UserUpdateSerializer(
            instance, data=request.data, partial=partial
        )
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
            raise ValidationError(
                {"detail": _("The role is assigned to users.")}
            ) from None
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
    }
    filterset_fields = ["is_head_office", "is_active", "parent"]
    search_fields = ["name", "code", "address"]
    ordering_fields = ["name", "code"]
    ordering = ["name"]

    def get_permissions(self):
        # Picking a branch in the workplace dialog must stay available to every
        # authenticated user, including cashiers without structure permissions.
        if self.action == "selectable":
            return [IsAuthenticated()]
        return super().get_permissions()

    @action(detail=False, methods=["get"])
    def selectable(self, request):
        """List active branches that have at least one active cash desk."""
        queryset = (
            Branch.objects.filter(is_active=True, cash_desks__is_active=True)
            .distinct()
            .order_by("name")
        )
        search = request.query_params.get("search")
        if search:
            queryset = queryset.filter(Q(name__icontains=search) | Q(code__icontains=search))
        page = self.paginate_queryset(queryset)
        serializer = serializers.BranchOptionSerializer(page, many=True)
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
    }
    filterset_fields = ["branch", "is_active"]
    search_fields = ["name", "code", "mac_address", "hostname"]
    ordering_fields = ["name", "code"]
    ordering = ["name"]

    def get_permissions(self):
        # Picking a cash desk in the workplace dialog must stay available to
        # every authenticated user, including cashiers without structure rights.
        if self.action == "selectable":
            return [IsAuthenticated()]
        return super().get_permissions()

    @action(detail=False, methods=["get"])
    def selectable(self, request):
        """List active cash desks, optionally narrowed to a single branch."""
        queryset = (
            CashDesk.objects.filter(is_active=True, branch__is_active=True)
            .select_related("branch")
            .order_by("branch__name", "name")
        )
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

    def destroy(self, request, *args, **kwargs):
        cash_desk = self.get_object()
        try:
            cash_desk.delete()
        except ProtectedError:
            raise ValidationError({"detail": _("The cash desk has shifts.")}) from None
        return Response(status=status.HTTP_204_NO_CONTENT)


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
        # Only list and retrieve are scoped: the close/force-close actions need
        # the unscoped queryset so they can return a precise 403/404.
        if self.action in ("list", "retrieve"):
            return shifts.visible_shifts(user=self.request.user, queryset=queryset)
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
        shift = (
            self.get_queryset()
            .filter(cashier=request.user, status=Shift.Status.OPEN)
            .first()
        )
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
