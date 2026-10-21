from django.contrib.auth import get_user_model
from django.contrib.auth.password_validation import validate_password
from django.core.exceptions import ValidationError as DjangoValidationError
from django.utils import timezone
from django.utils.translation import gettext_lazy as _
from rest_framework import serializers
from rest_framework_simplejwt.serializers import TokenObtainPairSerializer

from modules.common.backend import permissions_catalog
from modules.common.contracts import registry
from modules.core.backend.models import (
    BankSettings,
    BaseValue,
    Branch,
    BranchAccess,
    CashDesk,
    CurrencyRate,
    Role,
    Shift,
)
from modules.references.contracts import (
    REFERENCE_DIRECTORY,
    CurrencyRatePrinciple,
    RateTypeValidity,
    SystemRateTypeCode,
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


class LanguageChoiceMixin:
    """Validate a user's language choice against the bank's enabled languages."""

    def validate_language(self, value):
        if not value:
            return value
        if value not in BankSettings.load().enabled_languages:
            raise serializers.ValidationError(_("Unsupported language."))
        return value


class BankSettingsSerializer(serializers.ModelSerializer):
    """Read and update representation of the bank-wide settings."""

    class Meta:
        model = BankSettings
        fields = (
            "default_language",
            "enabled_languages",
            "base_currency",
            "conversion_mode",
            "updated_at",
        )
        read_only_fields = ("updated_at",)

    def validate_base_currency(self, value):
        code = (value or "").strip().upper()
        if not code:
            raise serializers.ValidationError(_("The base currency is required."))
        if registry.get(REFERENCE_DIRECTORY).get_currency(code) is None:
            raise serializers.ValidationError(_("Unknown currency."))
        return code

    def validate(self, attrs):
        attrs = super().validate(attrs)
        new_code = attrs.get("base_currency")
        previous = getattr(self.instance, "base_currency", None)
        if new_code and previous and new_code != previous:
            if CurrencyRate.objects.exclude(base_currency=new_code).exists():
                raise serializers.ValidationError(
                    {
                        "base_currency": _(
                            "The base currency cannot be changed while currency rates "
                            "with another base currency exist."
                        )
                    }
                )
            if BaseValue.objects.exclude(currency_code=new_code).exists():
                raise serializers.ValidationError(
                    {
                        "base_currency": _(
                            "The base currency cannot be changed while base values "
                            "in another currency exist."
                        )
                    }
                )
        return attrs

    def update(self, instance, validated_data):
        for field, value in validated_data.items():
            setattr(instance, field, value)
        try:
            instance.clean()
        except DjangoValidationError as exc:
            raise serializers.ValidationError(
                exc.message_dict if hasattr(exc, "message_dict") else exc.messages
            ) from None
        instance.save()
        return instance


class BaseValueSerializer(serializers.ModelSerializer):
    """Read and write representation of a base value.

    The currency code is a snapshot taken from the bank settings on creation, so
    it is read-only. A row that has already taken effect is immutable.
    """

    class Meta:
        model = BaseValue
        fields = (
            "id",
            "effective_from",
            "amount",
            "currency_code",
            "created_at",
            "updated_at",
        )
        read_only_fields = ("currency_code", "created_at", "updated_at")

    def validate_amount(self, value):
        if value <= 0:
            raise serializers.ValidationError(_("The amount must be greater than zero."))
        return value

    def validate(self, attrs):
        attrs = super().validate(attrs)
        instance = self.instance
        if instance is not None and instance.effective_from <= timezone.localdate():
            changed = any(
                field in attrs and attrs[field] != getattr(instance, field)
                for field in ("effective_from", "amount")
            )
            if changed:
                raise serializers.ValidationError(_("An effective base value cannot be changed."))
        return attrs


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
            "language",
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


class UserCreateSerializer(LanguageChoiceMixin, serializers.ModelSerializer):
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
            "language",
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


class UserUpdateSerializer(LanguageChoiceMixin, serializers.ModelSerializer):
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
            "language",
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


class UserSelfUpdateSerializer(LanguageChoiceMixin, serializers.ModelSerializer):
    """Fields a user is allowed to change on their own profile."""

    class Meta:
        model = User
        fields = ("first_name", "last_name", "middle_name", "phone", "language")


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
            "uses_individual_rates",
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
            "uses_individual_rates",
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


class CurrencyRefSerializer(serializers.Serializer):
    """Read-only representation of a currency resolved from the catalogue."""

    code = serializers.CharField()
    name = serializers.CharField()
    symbol = serializers.CharField(allow_blank=True)
    minor_units = serializers.IntegerField()


class CashDeskCurrenciesSerializer(serializers.Serializer):
    """Input for replacing the currencies enabled on a cash desk."""

    currencies = serializers.ListField(child=serializers.CharField(max_length=8), allow_empty=True)


def _checked_currency(value):
    """Normalise a currency code and ensure it belongs to the catalogue."""
    code = (value or "").strip().upper()
    if registry.get(REFERENCE_DIRECTORY).get_currency(code) is None:
        raise serializers.ValidationError(_("Unknown currency."))
    return code


def _checked_rate_type(value):
    """Return the rate type DTO or raise a field error."""
    rate_type = registry.get(REFERENCE_DIRECTORY).get_rate_type((value or "").strip())
    if rate_type is None:
        raise serializers.ValidationError(_("Unknown rate type."))
    if not rate_type.is_active:
        raise serializers.ValidationError(_("The rate type is inactive."))
    return rate_type


def _validate_scope(rate_type, branch, cash_desk):
    """Validate the scope of a rate and the bank-only national bank rate."""
    if branch is not None and cash_desk is not None:
        raise serializers.ValidationError(
            _("A rate belongs to one scope: bank, branch or cash desk.")
        )
    if rate_type.principle == CurrencyRatePrinciple.OFFICIAL and (
        branch is not None or cash_desk is not None
    ):
        raise serializers.ValidationError(
            {"rate_type": _("The national bank rate is set for the whole bank.")}
        )


def _resolve_effective_fields(attrs, rate_type, instance=None):
    """Normalise the pair of effective fields according to the rate type."""
    if rate_type.validity == RateTypeValidity.CALENDAR_DAY:
        effective_date = attrs.get("effective_date")
        if effective_date is None and attrs.get("effective_from") is not None:
            effective_date = timezone.localtime(attrs["effective_from"]).date()
        if effective_date is None and instance is not None:
            effective_date = (
                instance.effective_date or timezone.localtime(instance.effective_from).date()
            )
        if effective_date is None:
            raise serializers.ValidationError(
                {"effective_date": _("A calendar-day rate requires a date.")}
            )
        attrs["effective_date"] = effective_date
        attrs.pop("effective_from", None)
    else:
        if attrs.get("effective_date") is not None:
            raise serializers.ValidationError(
                {"effective_date": _("Only a calendar-day rate has a date.")}
            )
        effective_from = attrs.get("effective_from")
        if effective_from is None and instance is not None:
            effective_from = instance.effective_from
        if effective_from is None:
            raise serializers.ValidationError(
                {"effective_from": _("A since-set rate requires a date and time.")}
            )
        attrs["effective_from"] = effective_from


class CurrencyRateSerializer(serializers.ModelSerializer):
    """Read and write representation of a currency rate.

    The currencies and the rate type are plain codes. The effective fields depend
    on the rate type: ``calendar_day`` uses ``effective_date``, ``since_set`` uses
    ``effective_from``. A rate belongs to exactly one of the bank, a branch or a
    cash desk.
    """

    rate_type = serializers.CharField(max_length=64)
    base_currency = serializers.CharField(max_length=8, required=False, allow_blank=True)
    units = serializers.IntegerField(min_value=1, required=False, default=1)
    effective_date = serializers.DateField(required=False, allow_null=True, default=None)
    effective_from = serializers.DateTimeField(required=False, allow_null=True, default=None)
    branch = serializers.PrimaryKeyRelatedField(
        queryset=Branch.objects.all(), required=False, allow_null=True, default=None
    )
    cash_desk = serializers.PrimaryKeyRelatedField(
        queryset=CashDesk.objects.all(), required=False, allow_null=True, default=None
    )
    created_by = serializers.PrimaryKeyRelatedField(read_only=True)
    created_by_email = serializers.CharField(
        source="created_by.email", read_only=True, default=None
    )
    branch_name = serializers.CharField(source="branch.name", read_only=True, default=None)
    cash_desk_name = serializers.CharField(source="cash_desk.name", read_only=True, default=None)
    scope = serializers.CharField(read_only=True)
    is_current = serializers.BooleanField(read_only=True)

    class Meta:
        model = CurrencyRate
        fields = (
            "id",
            "currency",
            "base_currency",
            "rate_type",
            "units",
            "value",
            "branch",
            "branch_name",
            "cash_desk",
            "cash_desk_name",
            "scope",
            "effective_date",
            "effective_from",
            "is_current",
            "superseded_at",
            "created_by",
            "created_by_email",
            "created_at",
            "updated_at",
        )
        read_only_fields = (
            "id",
            "scope",
            "is_current",
            "superseded_at",
            "created_by",
            "created_by_email",
            "created_at",
            "updated_at",
        )

    def validate_currency(self, value):
        return _checked_currency(value)

    def validate_base_currency(self, value):
        return _checked_currency(value) if value else value

    def validate_rate_type(self, value):
        return _checked_rate_type(value).code

    def validate(self, attrs):
        instance = self.instance
        rate_type_code = attrs.get("rate_type", getattr(instance, "rate_type", None))
        rate_type = _checked_rate_type(rate_type_code)

        branch = attrs.get("branch", getattr(instance, "branch", None))
        cash_desk = attrs.get("cash_desk", getattr(instance, "cash_desk", None))
        _validate_scope(rate_type, branch, cash_desk)

        bank_settings = BankSettings.load()
        currency = attrs.get("currency", getattr(instance, "currency", None))
        base_currency = attrs.get(
            "base_currency",
            getattr(instance, "base_currency", None) or bank_settings.base_currency,
        )
        if currency is not None and currency == base_currency:
            raise serializers.ValidationError(
                {"base_currency": _("The base currency must differ from the currency.")}
            )
        if not attrs.get("base_currency") and instance is None:
            attrs["base_currency"] = base_currency

        if rate_type.principle == CurrencyRatePrinciple.CONVERSION:
            if (
                bank_settings.conversion_mode == BankSettings.ConversionMode.VIA_BASE
                and base_currency != bank_settings.base_currency
            ):
                raise serializers.ValidationError(
                    {
                        "base_currency": _(
                            "Conversion through the base currency requires the bank's "
                            "base currency as the quote currency."
                        )
                    }
                )
        elif base_currency != bank_settings.base_currency:
            raise serializers.ValidationError(
                {
                    "base_currency": _(
                        "Only the bank's base currency can be used as the quote currency "
                        "for this rate type."
                    )
                }
            )

        units = attrs.get("units", getattr(instance, "units", 1))
        if units is None or units < 1:
            raise serializers.ValidationError(
                {"units": _("The number of units must be at least one.")}
            )

        value = attrs.get("value", getattr(instance, "value", None))
        if value is not None and value <= 0:
            raise serializers.ValidationError(
                {"value": _("The rate value must be greater than zero.")}
            )

        _resolve_effective_fields(attrs, rate_type, instance)
        return attrs


class CurrencyRateBulkItemSerializer(serializers.Serializer):
    """A single currency value in a bulk rate-setting request."""

    currency = serializers.CharField(max_length=8)
    units = serializers.IntegerField(min_value=1, required=False, default=1)
    value = serializers.DecimalField(max_digits=18, decimal_places=6)


class CurrencyRateBulkSerializer(serializers.Serializer):
    """Set many rates of one type and scope in a single request."""

    rate_type = serializers.CharField(max_length=64)
    base_currency = serializers.CharField(max_length=8, required=False, allow_blank=True)
    branch = serializers.PrimaryKeyRelatedField(
        queryset=Branch.objects.all(), required=False, allow_null=True, default=None
    )
    cash_desk = serializers.PrimaryKeyRelatedField(
        queryset=CashDesk.objects.all(), required=False, allow_null=True, default=None
    )
    effective_date = serializers.DateField(required=False, allow_null=True)
    effective_from = serializers.DateTimeField(required=False, allow_null=True)
    items = CurrencyRateBulkItemSerializer(many=True)

    def validate(self, attrs):
        rate_type = _checked_rate_type(attrs["rate_type"])
        branch = attrs.get("branch")
        cash_desk = attrs.get("cash_desk")
        _validate_scope(rate_type, branch, cash_desk)

        bank_settings = BankSettings.load()
        base_currency = _checked_currency(attrs.get("base_currency") or bank_settings.base_currency)
        attrs["base_currency"] = base_currency

        if rate_type.principle == CurrencyRatePrinciple.CONVERSION:
            if (
                bank_settings.conversion_mode == BankSettings.ConversionMode.VIA_BASE
                and base_currency != bank_settings.base_currency
            ):
                raise serializers.ValidationError(
                    {
                        "base_currency": _(
                            "Conversion through the base currency requires the bank's "
                            "base currency as the quote currency."
                        )
                    }
                )
        elif base_currency != bank_settings.base_currency:
            raise serializers.ValidationError(
                {
                    "base_currency": _(
                        "Only the bank's base currency can be used as the quote currency "
                        "for this rate type."
                    )
                }
            )

        items = attrs.get("items") or []
        if not items:
            raise serializers.ValidationError({"items": _("At least one rate is required.")})
        seen: set[str] = set()
        checked_items = []
        for item in items:
            currency = _checked_currency(item["currency"])
            if currency == base_currency:
                raise serializers.ValidationError(
                    {"items": _("The base currency must differ from the currency.")}
                )
            if currency in seen:
                raise serializers.ValidationError(
                    {"items": _("Each currency can appear only once.")}
                )
            if item["value"] <= 0:
                raise serializers.ValidationError(
                    {"items": _("The rate value must be greater than zero.")}
                )
            seen.add(currency)
            checked_items.append(
                {
                    "currency": currency,
                    "units": item.get("units", 1),
                    "value": item["value"],
                }
            )
        attrs["items"] = checked_items

        _resolve_effective_fields(attrs, rate_type)
        return attrs


class ConversionPairSerializer(serializers.Serializer):
    """One direct conversion pair with its buy and sell quotes."""

    currency = serializers.CharField(max_length=8)
    base_currency = serializers.CharField(max_length=8)
    units = serializers.IntegerField(min_value=1, required=False, default=1)
    buy = serializers.DecimalField(max_digits=18, decimal_places=6)
    sell = serializers.DecimalField(max_digits=18, decimal_places=6)


class ConversionBulkSerializer(serializers.Serializer):
    """Set direct conversion pairs (buy and sell) in one atomic request."""

    branch = serializers.PrimaryKeyRelatedField(
        queryset=Branch.objects.all(), required=False, allow_null=True, default=None
    )
    cash_desk = serializers.PrimaryKeyRelatedField(
        queryset=CashDesk.objects.all(), required=False, allow_null=True, default=None
    )
    effective_date = serializers.DateField(required=False, allow_null=True)
    effective_from = serializers.DateTimeField(required=False, allow_null=True)
    pairs = ConversionPairSerializer(many=True)

    def validate(self, attrs):
        bank_settings = BankSettings.load()
        if bank_settings.conversion_mode != BankSettings.ConversionMode.DIRECT:
            raise serializers.ValidationError(
                _("Direct conversion is not enabled for the bank.")
            )

        pairs = attrs.get("pairs") or []
        if not pairs:
            raise serializers.ValidationError(
                {"pairs": _("At least one conversion pair is required.")}
            )

        seen: set[tuple[str, str]] = set()
        checked: list[dict] = []
        for pair in pairs:
            source = _checked_currency(pair["currency"])
            target = _checked_currency(pair["base_currency"])
            if source == target:
                raise serializers.ValidationError(
                    {"pairs": _("The conversion pair currencies must differ.")}
                )
            if (source, target) in seen:
                raise serializers.ValidationError(
                    {"pairs": _("Each conversion pair can appear only once.")}
                )
            if pair["buy"] <= 0 or pair["sell"] <= 0:
                raise serializers.ValidationError(
                    {"pairs": _("The rate value must be greater than zero.")}
                )
            seen.add((source, target))
            checked.append(
                {
                    "currency": source,
                    "base_currency": target,
                    "units": pair.get("units", 1),
                    "buy": pair["buy"],
                    "sell": pair["sell"],
                }
            )
        attrs["pairs"] = checked

        buy_type = _checked_rate_type(SystemRateTypeCode.CONVERSION_BUY)
        _validate_scope(buy_type, attrs.get("branch"), attrs.get("cash_desk"))
        _resolve_effective_fields(attrs, buy_type)
        return attrs


class RateResolveQuerySerializer(serializers.Serializer):
    """Query parameters of the single-rate resolution endpoint."""

    currency = serializers.CharField(max_length=8)
    target_currency = serializers.CharField(max_length=8, required=False, allow_blank=True)
    rate_type = serializers.CharField(max_length=64)
    cash_desk = serializers.PrimaryKeyRelatedField(
        queryset=CashDesk.objects.all(), required=False, allow_null=True, default=None
    )
    at = serializers.DateTimeField(required=False, allow_null=True)

    def validate_currency(self, value):
        return _checked_currency(value)

    def validate_target_currency(self, value):
        return _checked_currency(value) if value else value

    def validate_rate_type(self, value):
        return _checked_rate_type(value).code
