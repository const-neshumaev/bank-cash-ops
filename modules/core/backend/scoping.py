"""Branch-scoped visibility rules for the ``core`` module.

A user only sees the branches granted through :class:`BranchAccess` records;
superusers see every branch. The rules live here so that the API, the filters
and the domain services all share a single source of truth.

Access is independent of a branch being active: deactivating a branch must not
hide the work already done there. Activity is checked separately, only where a
write actually happens (opening a shift, ``selectable`` pickers).
"""

from __future__ import annotations

from modules.core.backend.models import Branch, User


def _children_by_parent() -> dict[int | None, list[int]]:
    """Return a ``parent_id -> child_ids`` map for the whole branch tree."""
    children: dict[int | None, list[int]] = {}
    for branch_id, parent_id in Branch.objects.values_list("id", "parent_id"):
        children.setdefault(parent_id, []).append(branch_id)
    return children


def _expand_with_descendants(root_ids: set[int], children: dict) -> set[int]:
    """Return ``root_ids`` together with every transitive child id."""
    result: set[int] = set()
    stack = list(root_ids)
    while stack:
        node = stack.pop()
        if node in result:
            continue
        result.add(node)
        stack.extend(children.get(node, ()))
    return result


def accessible_branch_ids(user: User) -> set[int] | None:
    """Return the ids of the branches ``user`` is allowed to see.

    Returns ``None`` for a superuser (every branch is visible). A user without
    any access record gets an empty set (deny-by-default). Inactive branches
    stay visible so that history remains readable.
    """
    if user.is_superuser:
        return None

    direct: set[int] = set()
    recursive: set[int] = set()
    for access in user.branch_access.all():
        if access.include_descendants:
            recursive.add(access.branch_id)
        else:
            direct.add(access.branch_id)

    if not recursive:
        return direct
    return direct | _expand_with_descendants(recursive, _children_by_parent())


def scope_by_branch(queryset, user: User, field: str = "pk"):
    """Narrow ``queryset`` to the branches ``user`` is allowed to see.

    ``field`` is the lookup that points at a branch, e.g. ``branch_id`` for a
    cash desk or ``cash_desk__branch_id`` for a shift. A superuser keeps the
    queryset untouched.
    """
    branch_ids = accessible_branch_ids(user)
    if branch_ids is None:
        return queryset
    return queryset.filter(**{f"{field}__in": branch_ids})


def can_access_branch(user: User, branch: Branch) -> bool:
    """Return whether ``user`` is allowed to work with ``branch``."""
    branch_ids = accessible_branch_ids(user)
    return branch_ids is None or branch.pk in branch_ids
