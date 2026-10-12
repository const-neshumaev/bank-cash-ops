"""Concrete implementations of the ``core`` module's public contracts."""

from __future__ import annotations

from modules.core.backend.models import User
from modules.core.contracts.dto import UserDTO


class UserDirectoryService:
    """In-process implementation of the ``UserDirectory`` contract."""

    def get_user(self, user_id: int) -> UserDTO | None:
        user = User.objects.filter(pk=user_id).prefetch_related("roles").first()
        return self._to_dto(user) if user is not None else None

    def is_admin(self, user_id: int) -> bool:
        user = User.objects.filter(pk=user_id).prefetch_related("roles").first()
        return bool(user and user.is_active and user.is_admin)

    def has_permission(self, user_id: int, permission: str) -> bool:
        user = User.objects.filter(pk=user_id).prefetch_related("roles").first()
        return bool(user and user.is_active and user.has_permission(permission))

    @staticmethod
    def _to_dto(user: User) -> UserDTO:
        return UserDTO(
            id=user.id,
            email=user.email,
            role_codes=tuple(sorted(role.code for role in user.roles.all())),
            is_active=user.is_active,
        )
