from django.contrib.auth.models import AbstractUser
from django.db import models
from django.utils.translation import gettext_lazy as _

from modules.core.backend.managers import UserManager


class User(AbstractUser):
    """Application user that authenticates with an email address.

    The legacy ``username`` field is removed; users are identified by their
    unique email. A free-form ``role`` describes what the person is allowed to
    do inside the bank and is the foundation of the modular permission model.
    """

    class Role(models.TextChoices):
        ADMIN = "admin", _("Administrator")
        MANAGER = "manager", _("Manager")
        CASHIER = "cashier", _("Cashier")
        OPERATOR = "operator", _("Operator")
        AUDITOR = "auditor", _("Auditor")

    username = None
    email = models.EmailField(_("email address"), unique=True)
    first_name = models.CharField(_("first name"), max_length=150)
    last_name = models.CharField(_("last name"), max_length=150)
    middle_name = models.CharField(_("middle name"), max_length=150, blank=True)
    phone = models.CharField(_("phone number"), max_length=32, blank=True)
    role = models.CharField(
        _("role"),
        max_length=32,
        choices=Role.choices,
        default=Role.CASHIER,
    )

    USERNAME_FIELD = "email"
    REQUIRED_FIELDS = ["first_name", "last_name"]

    objects = UserManager()

    class Meta:
        verbose_name = _("user")
        verbose_name_plural = _("users")
        ordering = ("last_name", "first_name", "email")

    def __str__(self):
        return self.full_name or self.email

    @property
    def full_name(self):
        """Return the display name built from the available name parts."""
        parts = [self.last_name, self.first_name, self.middle_name]
        return " ".join(part for part in parts if part).strip()

    @property
    def is_admin(self):
        """Whether the user is allowed to administer the system."""
        return bool(self.is_superuser or self.role == self.Role.ADMIN)
