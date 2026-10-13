from django.contrib.auth.models import AbstractUser
from django.core.exceptions import ValidationError
from django.core.validators import RegexValidator
from django.db import models
from django.utils.functional import cached_property
from django.utils.translation import gettext_lazy as _

from modules.common.backend.models import TimeStampedModel
from modules.core.backend.managers import UserManager
from modules.core.backend.permission_codes import PermissionCode

mac_address_validator = RegexValidator(
    regex=r"^([0-9A-Fa-f]{2}:){5}[0-9A-Fa-f]{2}$",
    message=_("Enter a MAC address in the form AA:BB:CC:DD:EE:FF."),
)


class Role(TimeStampedModel):
    """A named set of permissions that can be assigned to users.

    Roles are data: administrators create and edit them, so the set of roles is
    not fixed by the code. The permission codes a role grants are stored as a
    validated list drawn from the catalog in
    :mod:`modules.core.backend.permission_codes`.
    """

    code = models.SlugField(_("code"), max_length=64, unique=True)
    name = models.CharField(_("name"), max_length=150)
    description = models.TextField(_("description"), blank=True)
    permissions = models.JSONField(_("permissions"), default=list, blank=True)
    is_system = models.BooleanField(
        _("system role"),
        default=False,
        help_text=_("System roles are shipped with the product and cannot be deleted."),
    )

    class Meta:
        verbose_name = _("role")
        verbose_name_plural = _("roles")
        ordering = ("name",)

    def __str__(self):
        return self.name


class User(AbstractUser):
    """Application user that authenticates with an email address.

    The legacy ``username`` field is removed; users are identified by their
    unique email. A user may hold several roles, and the union of their
    permissions decides what the person is allowed to do.
    """

    username = None
    email = models.EmailField(_("email address"), unique=True)
    first_name = models.CharField(_("first name"), max_length=150)
    last_name = models.CharField(_("last name"), max_length=150)
    middle_name = models.CharField(_("middle name"), max_length=150, blank=True)
    phone = models.CharField(_("phone number"), max_length=32, blank=True)
    roles = models.ManyToManyField(
        "core.Role",
        related_name="users",
        blank=True,
        verbose_name=_("roles"),
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

    @cached_property
    def permission_codes(self) -> frozenset[str]:
        """Return the union of the permission codes granted by the user's roles."""
        codes: set[str] = set()
        for role in self.roles.all():
            codes.update(role.permissions or [])
        return frozenset(codes)

    def has_permission(self, code: str) -> bool:
        """Return whether the user is allowed to perform the action ``code``."""
        return bool(self.is_superuser or code in self.permission_codes)

    @property
    def is_admin(self):
        """Whether the user is allowed to administer the system."""
        return bool(self.is_superuser or self.has_permission(PermissionCode.USERS_MANAGE))


class Branch(TimeStampedModel):
    """A bank branch; branches form a tree up to a single head office."""

    parent = models.ForeignKey(
        "self",
        null=True,
        blank=True,
        on_delete=models.PROTECT,
        related_name="children",
        verbose_name=_("parent branch"),
    )
    code = models.CharField(_("code"), max_length=32, unique=True, null=True, blank=True)
    name = models.CharField(_("name"), max_length=255)
    address = models.CharField(_("address"), max_length=255, blank=True)
    phone = models.CharField(_("phone number"), max_length=32, blank=True)
    is_head_office = models.BooleanField(_("head office"), default=False)
    is_active = models.BooleanField(_("active"), default=True)

    class Meta:
        verbose_name = _("branch")
        verbose_name_plural = _("branches")
        ordering = ("name",)
        constraints = (
            models.UniqueConstraint(
                fields=["is_head_office"],
                condition=models.Q(is_head_office=True),
                name="core_unique_head_office",
            ),
        )

    def __str__(self):
        return self.name

    def ancestors(self):
        """Yield the parent chain from the immediate parent up to the root."""
        node = self.parent
        seen: set[int] = set()
        while node is not None:
            if node.pk in seen:
                break
            seen.add(node.pk)
            yield node
            node = node.parent

    def clean(self):
        """Validate the branch position in the hierarchy."""
        super().clean()
        # An empty code means "no internal bank identifier", stored as NULL so
        # several branches can omit it under the unique constraint.
        self.code = (self.code or "").strip() or None
        if self.is_head_office and self.parent_id is not None:
            raise ValidationError({"parent": _("The head office cannot have a parent.")})
        if not self.is_head_office and self.parent_id is None:
            raise ValidationError({"parent": _("Only the head office can have no parent.")})
        if self.pk is not None and self.parent_id is not None:
            if any(ancestor.pk == self.pk for ancestor in self.ancestors()):
                raise ValidationError({"parent": _("A branch cannot be its own ancestor.")})

    def save(self, *args, **kwargs):
        self.clean()
        return super().save(*args, **kwargs)


class CashDesk(TimeStampedModel):
    """A cashier workstation; one cash desk corresponds to one computer."""

    branch = models.ForeignKey(
        Branch,
        on_delete=models.PROTECT,
        related_name="cash_desks",
        verbose_name=_("branch"),
    )
    code = models.CharField(_("code"), max_length=32, unique=True, null=True, blank=True)
    name = models.CharField(_("name"), max_length=255)
    mac_address = models.CharField(
        _("MAC address"),
        max_length=17,
        unique=True,
        null=True,
        blank=True,
        validators=[mac_address_validator],
        help_text=_("Network address of the workstation, e.g. AA:BB:CC:DD:EE:FF."),
    )
    hostname = models.CharField(_("hostname"), max_length=255, blank=True)
    is_active = models.BooleanField(_("active"), default=True)

    class Meta:
        verbose_name = _("cash desk")
        verbose_name_plural = _("cash desks")
        ordering = ("branch__name", "name")

    def __str__(self):
        return self.name

    def clean(self):
        """Normalise the code and MAC address so uniqueness is consistent."""
        super().clean()
        # An empty code means "no internal bank identifier", stored as NULL so
        # several cash desks can omit it under the unique constraint.
        self.code = (self.code or "").strip() or None
        if self.mac_address:
            self.mac_address = self.mac_address.upper()

    def save(self, *args, **kwargs):
        self.clean()
        return super().save(*args, **kwargs)


class Shift(TimeStampedModel):
    """A cashier shift bound to a single cash desk for its whole lifetime.

    A shift is a server-side object independent of the browser session: it stays
    open across reconnects and logins until it is explicitly closed. At most one
    shift may be open per cashier and per cash desk.
    """

    class Status(models.TextChoices):
        OPEN = "open", _("Open")
        CLOSED = "closed", _("Closed")

    cash_desk = models.ForeignKey(
        CashDesk,
        on_delete=models.PROTECT,
        related_name="shifts",
        verbose_name=_("cash desk"),
    )
    cashier = models.ForeignKey(
        User,
        on_delete=models.PROTECT,
        related_name="shifts",
        verbose_name=_("cashier"),
    )
    status = models.CharField(
        _("status"),
        max_length=16,
        choices=Status.choices,
        default=Status.OPEN,
    )
    opened_at = models.DateTimeField(_("opened at"), auto_now_add=True)
    closed_at = models.DateTimeField(_("closed at"), null=True, blank=True)
    closed_by = models.ForeignKey(
        User,
        null=True,
        blank=True,
        on_delete=models.PROTECT,
        related_name="closed_shifts",
        verbose_name=_("closed by"),
    )

    class Meta:
        verbose_name = _("shift")
        verbose_name_plural = _("shifts")
        ordering = ("-opened_at",)
        constraints = (
            models.UniqueConstraint(
                fields=["cashier"],
                condition=models.Q(status="open"),
                name="core_unique_open_shift_per_cashier",
            ),
            models.UniqueConstraint(
                fields=["cash_desk"],
                condition=models.Q(status="open"),
                name="core_unique_open_shift_per_cash_desk",
            ),
        )

    def __str__(self):
        return f"{self.cash_desk} @ {self.opened_at:%Y-%m-%d %H:%M}"
