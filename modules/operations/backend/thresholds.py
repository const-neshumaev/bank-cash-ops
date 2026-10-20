"""Predefined client-data policies and threshold kinds.

The *policy* says when an operation type requires client data. The *threshold
kind* is a developer-defined function that turns a configured threshold into a
check at posting time. Only the configuration is implemented here; the checks in
the operation engine follow in a separate iteration.

Threshold kinds are code-defined on purpose: the engine must branch on stable
identifiers, while the display names are translated. Adding a new kind means
adding an entry below and a matching evaluator later.
"""

from __future__ import annotations

from dataclasses import dataclass

from django.core.exceptions import ValidationError
from django.utils.translation import gettext_lazy as _

from modules.common.contracts import registry
from modules.references.contracts import REFERENCE_DIRECTORY


class ClientDataPolicy:
    """Stable identifiers of the client-data policy of an operation type."""

    NEVER = "never"
    ALWAYS = "always"
    THRESHOLD = "threshold"

    CHOICES = (
        (NEVER, _("Never")),
        (ALWAYS, _("Always")),
        (THRESHOLD, _("Above threshold")),
    )
    VALUES = tuple(code for code, _name in CHOICES)


class ThresholdTypeCode:
    """Stable identifiers of the predefined threshold kinds."""

    BASE_VALUE = "base_value"
    CURRENCY = "currency"

    VALUES = (BASE_VALUE, CURRENCY)


@dataclass(frozen=True)
class ThresholdType:
    """Metadata of a threshold kind shown in the administration UI."""

    code: str
    name: str
    requires_currency: bool = False


THRESHOLD_TYPES: tuple[ThresholdType, ...] = (
    ThresholdType(
        ThresholdTypeCode.BASE_VALUE,
        _("Base values"),
    ),
    ThresholdType(
        ThresholdTypeCode.CURRENCY,
        _("Amount in a currency"),
        requires_currency=True,
    ),
)

THRESHOLD_TYPES_BY_CODE: dict[str, ThresholdType] = {item.code: item for item in THRESHOLD_TYPES}


def get_threshold_type(code: str) -> ThresholdType | None:
    """Return the threshold kind by its code, or ``None`` when it is unknown."""
    return THRESHOLD_TYPES_BY_CODE.get(code)


def threshold_errors(
    policy: str,
    threshold_type: str,
    threshold_value,
    threshold_currency: str,
) -> dict[str, str]:
    """Return validation errors of a client-data and threshold configuration.

    The function is shared by the DRF serializer and the model so that the API,
    the Django admin and startup synchronisation enforce the same rules. It
    returns a mapping suitable for either ``serializers.ValidationError`` or
    ``django.core.exceptions.ValidationError``.
    """
    errors: dict[str, str] = {}
    if policy not in ClientDataPolicy.VALUES:
        return {"client_data_policy": _("Unknown client data policy.")}
    if policy != ClientDataPolicy.THRESHOLD:
        return errors

    threshold = get_threshold_type(threshold_type)
    if threshold is None:
        errors["threshold_type"] = _("The threshold type is required.")

    if threshold_value is None:
        errors["threshold_value"] = _("The threshold value is required.")
    elif threshold_value <= 0:
        errors["threshold_value"] = _("The threshold value must be greater than zero.")

    currency = (threshold_currency or "").strip().upper()
    if threshold is not None and threshold.requires_currency:
        if not currency:
            errors["threshold_currency"] = _("The threshold currency is required.")
        else:
            directory = registry.get(REFERENCE_DIRECTORY)
            if directory.get_currency(currency) is None:
                errors["threshold_currency"] = _("Unknown currency.")
    elif threshold is not None and currency:
        errors["threshold_currency"] = _(
            "The threshold currency is only allowed for the currency threshold type."
        )

    return errors


def raise_threshold_errors(
    policy: str,
    threshold_type: str,
    threshold_value,
    threshold_currency: str,
) -> None:
    """Raise a Django validation error when the configuration is invalid."""
    errors = threshold_errors(policy, threshold_type, threshold_value, threshold_currency)
    if errors:
        raise ValidationError(errors)
