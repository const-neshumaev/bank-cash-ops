from django.contrib import admin
from django.contrib.auth.admin import UserAdmin as DjangoUserAdmin
from django.utils.translation import gettext_lazy as _

from modules.core.backend.models import User


@admin.register(User)
class UserAdmin(DjangoUserAdmin):
    """Administration of the custom user model inside the Django admin."""

    ordering = ("last_name", "first_name")
    list_display = ("email", "full_name", "role", "is_active", "is_staff", "last_login")
    list_filter = ("role", "is_active", "is_staff", "is_superuser")
    search_fields = ("email", "first_name", "last_name", "middle_name", "phone")
    readonly_fields = ("last_login", "date_joined")
    fieldsets = (
        (None, {"fields": ("email", "password")}),
        (
            _("Personal information"),
            {"fields": ("last_name", "first_name", "middle_name", "phone")},
        ),
        (_("Role"), {"fields": ("role",)}),
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
                    "role",
                    "password1",
                    "password2",
                ),
            },
        ),
    )

    @admin.display(description=_("full name"))
    def full_name(self, obj):
        return obj.full_name
