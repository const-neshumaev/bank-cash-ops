from django.contrib.auth import get_user_model
from django.contrib.auth.password_validation import validate_password
from django.utils.translation import gettext_lazy as _
from rest_framework import serializers
from rest_framework_simplejwt.serializers import TokenObtainPairSerializer

from modules.common.backend import permissions_catalog
from modules.core.backend.models import (
    Branch,
    BranchAccess,
    CashDesk,
    Currency,
    CurrencyRate,
    CurrencyTemplate,
    Role,
    Shift,
)

User = get_user_model()


def _replace_branch_access(user, entries):
    """Replace the user's branch access grants with ``entries``.

    ``entries`` is a list of validated dicts with a ``branch`` and an optional
    ``include_descendants`` key. The list is treated as the full desired state.
    """
    BranchAccess.objects.filter(user=user).delete()
    BranchAccess.objects.bulk_create(
        BranchAccess(
            user=user,
            branch=entry["branch"],
            include_descendants=entry.get("include_descendants", False),
        )
        for entry in entries
    )


class BranchAccessSerializer(serializers.ModelSerializer):
    """Read and write representation of a branch access grant."""

    class Meta:
        model = BranchAccess
        fields = ("branch", "include_descendants")


class PermissionSerializer(serializers.Serializer):
    """Read-only representation of a permission catalog entry."""

    code = serializers.CharField(read_only=True)
    name = serializers.CharField(read_only=True)


class RoleSerializer(serializers.ModelSerializer):
    """Read and write representation of a role."""

    permissions = serializers.ListField(
        child=serializers.CharField(),
        allow_empty=True,
        required=False,
    )
    users_count = serializers.IntegerField(source="users.count", read_only=True)

    class Meta:
        model = Role
        fields = (
            "id",
            "code",
            "name",
            "description",
            "permissions",
            "is_system",
            "users_count",
            "created_at",
            "updated_at",
        )
        read_only_fields = ("is_system", "created_at", "updated_at")
        extra_kwargs = {"code": {"required": False, "allow_blank": True}}

    def validate_permissions(self, value):
        unknown = sorted(code for code in value if not permissions_catalog.is_known_code(code))
        if unknown:
            raise serializers.ValidationError(
                _("Unknown permission codes: %(codes)s.") % {"codes": ", ".join(unknown)}
            )
        return value


class UserSerializer(serializers.ModelSerializer):
    """Read-only representation of a user."""

    full_name = serializers.CharField(read_only=True)
    roles = serializers.SlugRelatedField(many=True, slug_field="code", read_only=True)
    roles_display = serializers.SerializerMethodField()
    permissions = serializers.SerializerMethodField()
    branch_access = BranchAccessSerializer(many=True, read_only=True)

    class Meta:
        model = User
        fields = (
            "id",
            "email",
            "first_name",
            "last_name",
            "middle_name",
            "full_name",
            "roles",
            "roles_display",
            "permissions",
            "branch_access",
            "phone",
            "is_active",
            "is_staff",
            "is_superuser",
            "date_joined",
            "last_login",
        )
        read_only_fields = ("id", "date_joined", "last_login", "is_staff", "is_superuser")

    def get_roles_display(self, obj) -> list[str]:
        return [role.name for role in obj.roles.all()]

    def get_permissions(self, obj) -> list[str]:
        return sorted(obj.permission_codes)


class UserCreateSerializer(serializers.ModelSerializer):
    """Create a new user (permission ``core.users.manage``)."""

    password = serializers.CharField(write_only=True, style={"input_type": "password"})
    password_confirm = serializers.CharField(write_only=True, style={"input_type": "password"})
    roles = serializers.SlugRelatedField(
        many=True,
        slug_field="code",
        queryset=Role.objects.all(),
        required=False,
    )
    branch_access = BranchAccessSerializer(many=True, required=False)

    class Meta:
        model = User
        fields = (
            "email",
            "password",
            "password_confirm",
            "first_name",
            "last_name",
            "middle_name",
            "phone",
            "roles",
            "branch_access",
            "is_active",
        )

    def validate(self, attrs):
        password_confirm = attrs.pop("password_confirm", None)
        password = attrs.get("password")
        if password != password_confirm:
            raise serializers.ValidationError({"password_confirm": _("Passwords do not match.")})
        validate_password(password)
        return attrs

    def create(self, validated_data):
        roles = validated_data.pop("roles", [])
        branch_access = validated_data.pop("branch_access", [])
        password = validated_data.pop("password")
        user = User.objects.create_user(password=password, **validated_data)
        user.roles.set(roles)
        _replace_branch_access(user, branch_access)
        user.is_staff = user.is_admin
        user.save(update_fields=["is_staff"])
        return user


class UserUpdateSerializer(serializers.ModelSerializer):
    """Update an existing user (permission ``core.users.manage``)."""

    roles = serializers.SlugRelatedField(
        many=True,
        slug_field="code",
        queryset=Role.objects.all(),
        required=False,
    )
    branch_access = BranchAccessSerializer(many=True, required=False)

    class Meta:
        model = User
        fields = (
            "email",
            "first_name",
            "last_name",
            "middle_name",
            "phone",
            "roles",
            "branch_access",
            "is_active",
        )

    def update(self, instance, validated_data):
        roles = validated_data.pop("roles", None)
        branch_access = validated_data.pop("branch_access", None)
        user = super().update(instance, validated_data)
        if roles is not None:
            user.roles.set(roles)
        if branch_access is not None:
            _replace_branch_access(user, branch_access)
        user.is_staff = user.is_admin
        user.save(update_fields=["is_staff"])
        return user


class UserSelfUpdateSerializer(serializers.ModelSerializer):
    """Fields a user is allowed to change on their own profile."""

    class Meta:
        model = User
        fields = ("first_name", "last_name", "middle_name", "phone")


class ChangePasswordSerializer(serializers.Serializer):
    """Validate and apply a password change for the current user."""

    old_password = serializers.CharField(write_only=True, style={"input_type": "password"})
    new_password = serializers.CharField(write_only=True, style={"input_type": "password"})
    new_password_confirm = serializers.CharField(write_only=True, style={"input_type": "password"})

    def validate_old_password(self, value):
        user = self.context["request"].user
        if not user.check_password(value):
            raise serializers.ValidationError(_("The current password is incorrect."))
        return value

    def validate(self, attrs):
        if attrs["new_password"] != attrs["new_password_confirm"]:
            raise serializers.ValidationError(
                {"new_password_confirm": _("Passwords do not match.")}
            )
        validate_password(attrs["new_password"], self.context["request"].user)
        return attrs

    def save(self, **kwargs):
        user = self.context["request"].user
        user.set_password(self.validated_data["new_password"])
        user.save(update_fields=["password"])
        return user


class EmailTokenObtainPairSerializer(TokenObtainPairSerializer):
    """JWT login serializer that embeds basic user information in the response."""

    @classmethod
    def get_token(cls, user):
        token = super().get_token(user)
        token["email"] = user.email
        token["roles"] = list(user.roles.values_list("code", flat=True))
        return token

    def validate(self, attrs):
        data = super().validate(attrs)
        data["user"] = UserSerializer(self.user, context=self.context).data
        return data


class BranchSerializer(serializers.ModelSerializer):
    """Read and write representation of a bank branch."""

    code = serializers.CharField(
        max_length=32,
        required=False,
        allow_blank=True,
        allow_null=True,
    )
    parent = serializers.PrimaryKeyRelatedField(
        queryset=Branch.objects.all(),
        allow_null=True,
        required=False,
    )
    parent_name = serializers.CharField(source="parent.name", read_only=True, default=None)
    children_count = serializers.IntegerField(source="children.count", read_only=True)

    class Meta:
        model = Branch
        fields = (
            "id",
            "parent",
            "parent_name",
            "code",
            "name",
            "address",
            "phone",
            "is_head_office",
            "is_active",
            "children_count",
            "created_at",
            "updated_at",
        )
        read_only_fields = ("created_at", "updated_at")

    def validate_code(self, value):
        """Store an omitted or blank code as ``None`` so it stays optional."""
        return (value or "").strip() or None

    def validate(self, attrs):
        instance = self.instance
        code = attrs.get("code")
        if code:
            queryset = Branch.objects.filter(code=code)
            if instance is not None:
                queryset = queryset.exclude(pk=instance.pk)
            if queryset.exists():
                raise serializers.ValidationError(
                    {"code": _("A branch with this code already exists.")}
                )

        parent = attrs.get("parent", getattr(instance, "parent", None))
        is_head_office = attrs.get("is_head_office", getattr(instance, "is_head_office", False))

        if is_head_office and parent is not None:
            raise serializers.ValidationError(
                {"parent": _("The head office cannot have a parent.")}
            )
        if not is_head_office and parent is None:
            raise serializers.ValidationError(
                {"parent": _("Only the head office can have no parent.")}
            )
        if instance is not None and parent is not None:
            if parent.pk == instance.pk or any(
                ancestor.pk == instance.pk for ancestor in parent.ancestors()
            ):
                raise serializers.ValidationError(
                    {"parent": _("A branch cannot be its own ancestor.")}
                )
        return attrs


class BranchOptionSerializer(serializers.ModelSerializer):
    """Compact branch representation used by select inputs."""

    class Meta:
        model = Branch
        fields = ("id", "name", "code")


class CashDeskSerializer(serializers.ModelSerializer):
    """Read and write representation of a cashier workstation."""

    code = serializers.CharField(
        max_length=32,
        required=False,
        allow_blank=True,
        allow_null=True,
    )
    branch_name = serializers.CharField(source="branch.name", read_only=True)

    class Meta:
        model = CashDesk
        fields = (
            "id",
            "branch",
            "branch_name",
            "code",
            "name",
            "mac_address",
            "hostname",
            "is_active",
            "created_at",
            "updated_at",
        )
        read_only_fields = ("created_at", "updated_at")
        extra_kwargs = {"mac_address": {"required": False, "allow_null": True}}

    def validate_code(self, value):
        """Store an omitted or blank code as ``None`` so it stays optional."""
        return (value or "").strip() or None

    def validate(self, attrs):
        code = attrs.get("code")
        if code:
            queryset = CashDesk.objects.filter(code=code)
            if self.instance is not None:
                queryset = queryset.exclude(pk=self.instance.pk)
            if queryset.exists():
                raise serializers.ValidationError(
                    {"code": _("A cash desk with this code already exists.")}
                )
        return attrs

    def validate_mac_address(self, value):
        return value.upper() if value else value


class CashDeskOptionSerializer(serializers.ModelSerializer):
    """Compact cash desk representation used by select inputs."""

    class Meta:
        model = CashDesk
        fields = ("id", "name", "code", "branch")


class ShiftSerializer(serializers.ModelSerializer):
    """Read-only representation of a shift."""

    cashier = serializers.PrimaryKeyRelatedField(read_only=True)
    cashier_name = serializers.CharField(source="cashier.full_name", read_only=True)
    cash_desk = serializers.PrimaryKeyRelatedField(read_only=True)
    cash_desk_name = serializers.CharField(source="cash_desk.name", read_only=True)
    cash_desk_code = serializers.CharField(source="cash_desk.code", read_only=True)
    cash_desk_branch = serializers.IntegerField(source="cash_desk.branch_id", read_only=True)
    cash_desk_branch_name = serializers.CharField(source="cash_desk.branch.name", read_only=True)
    status_display = serializers.CharField(source="get_status_display", read_only=True)

    class Meta:
        model = Shift
        fields = (
            "id",
            "cashier",
            "cashier_name",
            "cash_desk",
            "cash_desk_name",
            "cash_desk_code",
            "cash_desk_branch",
            "cash_desk_branch_name",
            "status",
            "status_display",
            "opened_at",
            "closed_at",
            "closed_by",
        )


class ShiftOpenSerializer(serializers.Serializer):
    """Input for opening a shift: the cash desk the cashier starts working at."""

    cash_desk = serializers.PrimaryKeyRelatedField(queryset=CashDesk.objects.all())


class CurrencySerializer(serializers.ModelSerializer):
    """Read and write representation of a currency."""

    class Meta:
        model = Currency
        fields = ("code", "name", "symbol", "minor_units", "is_active")

    def validate_code(self, value):
        return (value or "").strip().upper()


class CashDeskCurrenciesSerializer(serializers.Serializer):
    """Input for replacing the currencies enabled on a cash desk."""

    currencies = serializers.ListField(child=serializers.CharField(max_length=8), allow_empty=True)


class CurrencyTemplateSerializer(serializers.ModelSerializer):
    """Read representation of a currency template (bank or branch)."""

    branch_id = serializers.IntegerField(read_only=True)
    currencies = CurrencySerializer(many=True, read_only=True)

    class Meta:
        model = CurrencyTemplate
        fields = ("id", "branch_id", "currencies")


class CurrencyRateSerializer(serializers.ModelSerializer):
    """Read and write representation of a currency rate."""

    currency = serializers.SlugRelatedField(slug_field="code", queryset=Currency.objects.all())
    base_currency = serializers.SlugRelatedField(slug_field="code", queryset=Currency.objects.all())
    cash_desk = serializers.PrimaryKeyRelatedField(
        queryset=CashDesk.objects.all(), required=False, allow_null=True, default=None
    )

    class Meta:
        model = CurrencyRate
        fields = (
            "id",
            "currency",
            "base_currency",
            "rate_type",
            "value",
            "cash_desk",
            "effective_from",
            "created_at",
            "updated_at",
        )
        read_only_fields = ("created_at", "updated_at")

    def validate(self, attrs):
        currency = attrs.get("currency", getattr(self.instance, "currency", None))
        base_currency = attrs.get("base_currency", getattr(self.instance, "base_currency", None))
        if currency is not None and currency == base_currency:
            raise serializers.ValidationError(
                {"base_currency": _("The base currency must differ from the currency.")}
            )
        return attrs
