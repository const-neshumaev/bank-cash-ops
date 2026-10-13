from django.contrib import admin
from django.contrib.auth.admin import UserAdmin as DjangoUserAdmin
from django.utils.translation import gettext_lazy as _

from modules.core.backend.models import Branch, BranchAccess, CashDesk, Role, Shift, User


@admin.register(Role)
class RoleAdmin(admin.ModelAdmin):
    """Administration of the data-driven roles."""

    list_display = ("name", "code", "is_system", "users_count")
    list_filter = ("is_system",)
    search_fields = ("name", "code")
    readonly_fields = ("created_at", "updated_at")

    @admin.display(description=_("users"))
    def users_count(self, obj):
        return obj.users.count()


class BranchAccessInline(admin.TabularInline):
    """Edit a user's branch access grants from the user page."""

    model = BranchAccess
    extra = 1
    autocomplete_fields = ("branch",)


@admin.register(User)
class UserAdmin(DjangoUserAdmin):
    """Administration of the custom user model inside the Django admin."""

    ordering = ("last_name", "first_name")
    inlines = (BranchAccessInline,)
    list_display = ("email", "full_name", "is_active", "is_staff", "last_login")
    list_filter = ("roles", "is_active", "is_staff", "is_superuser")
    search_fields = ("email", "first_name", "last_name", "middle_name", "phone")
    readonly_fields = ("last_login", "date_joined")
    filter_horizontal = ("roles",)
    fieldsets = (
        (None, {"fields": ("email", "password")}),
        (
            _("Personal information"),
            {"fields": ("last_name", "first_name", "middle_name", "phone")},
        ),
        (_("Roles"), {"fields": ("roles",)}),
        (
            _("Permissions"),
            {"fields": ("is_active", "is_staff", "is_superuser", "groups", "user_permissions")},
        ),
        (_("Important dates"), {"fields": ("last_login", "date_joined")}),
    )
    add_fieldsets = (
        (
            None,
            {
                "classes": ("wide",),
                "fields": (
                    "email",
                    "last_name",
                    "first_name",
                    "roles",
                    "password1",
                    "password2",
                ),
            },
        ),
    )

    @admin.display(description=_("full name"))
    def full_name(self, obj):
        return obj.full_name


@admin.register(BranchAccess)
class BranchAccessAdmin(admin.ModelAdmin):
    """Administration of the branch access grants."""

    list_display = ("user", "branch", "include_descendants")
    list_filter = ("include_descendants", "branch")
    search_fields = ("user__email", "user__last_name", "branch__name", "branch__code")
    autocomplete_fields = ("user", "branch")


@admin.register(Branch)
class BranchAdmin(admin.ModelAdmin):
    """Administration of the bank branch hierarchy."""

    list_display = ("name", "code", "parent", "is_head_office", "is_active")
    list_filter = ("is_head_office", "is_active")
    search_fields = ("name", "code", "address")
    readonly_fields = ("created_at", "updated_at")


@admin.register(CashDesk)
class CashDeskAdmin(admin.ModelAdmin):
    """Administration of the cashier workstations."""

    list_display = ("name", "code", "branch", "mac_address", "is_active")
    list_filter = ("is_active", "branch")
    search_fields = ("name", "code", "mac_address", "hostname")
    readonly_fields = ("created_at", "updated_at")


@admin.register(Shift)
class ShiftAdmin(admin.ModelAdmin):
    """Administration of the cashier shifts."""

    list_display = ("id", "cashier", "cash_desk", "status", "opened_at", "closed_at", "closed_by")
    list_filter = ("status", "cash_desk")
    search_fields = ("cashier__email", "cashier__last_name", "cash_desk__name", "cash_desk__code")
    readonly_fields = ("opened_at", "created_at", "updated_at")
