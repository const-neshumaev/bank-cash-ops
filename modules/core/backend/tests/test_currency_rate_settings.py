"""Currency rate setting: scopes, validity, versioning and permissions."""

from datetime import datetime, time, timedelta
from decimal import Decimal
from types import SimpleNamespace

import pytest
from django.contrib.auth import get_user_model
from django.utils import timezone
from rest_framework.test import APIClient

from modules.common.contracts import registry
from modules.core.backend.models import (
    BankSettings,
    Branch,
    BranchAccess,
    CashDesk,
    CurrencyRate,
    Role,
    Shift,
)
from modules.core.contracts import CASH_DESK_CONFIG
from modules.references.backend.models import CurrencyRateType

User = get_user_model()

pytestmark = pytest.mark.django_db

RATES_URL = "/api/currency-rates/"
RATE_TYPES_URL = "/api/references/rate-types/"


@pytest.fixture
def org():
    head = Branch.objects.create(code="HQ", name="Головной офис", is_head_office=True)
    branch = Branch.objects.create(code="B1", name="Отделение 1", parent=head)
    sibling = Branch.objects.create(code="B2", name="Отделение 2", parent=head)
    desk = CashDesk.objects.create(branch=branch, code="C1", name="Касса 1")
    second_desk = CashDesk.objects.create(branch=branch, code="C2", name="Касса 2")
    sibling_desk = CashDesk.objects.create(branch=sibling, code="C3", name="Касса 3")
    return SimpleNamespace(
        head=head,
        branch=branch,
        sibling=sibling,
        desk=desk,
        second_desk=second_desk,
        sibling_desk=sibling_desk,
    )


@pytest.fixture
def admin():
    return User.objects.create_superuser(email="admin@example.com", password="secret-pass-123")


@pytest.fixture
def admin_client(admin):
    client = APIClient()
    client.force_authenticate(admin)
    return client


def _authenticated(user):
    client = APIClient()
    client.force_authenticate(user)
    return client


def _user_with_role(email, role_code, branch=None):
    user = User.objects.create_user(email=email, password="secret-pass-123")
    user.roles.set(Role.objects.filter(code=role_code))
    if branch is not None:
        BranchAccess.objects.create(user=user, branch=branch, include_descendants=True)
    return user


def _buy_payload(**overrides):
    data = {
        "currency": "USD",
        "base_currency": "BYN",
        "rate_type": "buy",
        "value": "3.200000",
        "effective_from": (timezone.now() + timedelta(minutes=5)).isoformat(),
    }
    data.update(overrides)
    return data


def _official_payload(**overrides):
    data = {
        "currency": "USD",
        "base_currency": "BYN",
        "rate_type": "official",
        "value": "3.100000",
        "effective_date": timezone.localdate().isoformat(),
    }
    data.update(overrides)
    return data


def test_rate_units_default_to_one_and_normalize_the_contract(admin_client):
    response = admin_client.post(RATES_URL, _buy_payload(), format="json")

    assert response.status_code == 201, response.content
    assert response.data["units"] == 1
    first_moment = timezone.now() + timedelta(minutes=6)
    assert registry.get(CASH_DESK_CONFIG).rate("USD", "buy", at=first_moment) == Decimal("3.200000")

    response = admin_client.post(
        RATES_URL,
        _buy_payload(
            units=100,
            value="350.000000",
            effective_from=(timezone.now() + timedelta(minutes=10)).isoformat(),
        ),
        format="json",
    )
    assert response.status_code == 201, response.content
    assert response.data["units"] == 100
    assert registry.get(CASH_DESK_CONFIG).rate(
        "USD", "buy", at=timezone.now() + timedelta(minutes=15)
    ) == Decimal("3.500000")


def test_bulk_rates_accept_units(admin_client):
    response = admin_client.post(
        f"{RATES_URL}bulk/",
        {
            "rate_type": "buy",
            "effective_from": (timezone.now() + timedelta(minutes=5)).isoformat(),
            "items": [{"currency": "USD", "units": 100, "value": "350.000000"}],
        },
        format="json",
    )

    assert response.status_code == 201, response.content
    assert response.data[0]["units"] == 100


def test_the_bank_can_switch_to_direct_conversion(admin_client):
    response = admin_client.patch("/api/settings/", {"conversion_mode": "direct"}, format="json")

    assert response.status_code == 200, response.content
    assert response.data["conversion_mode"] == "direct"
    assert BankSettings.load().conversion_mode == BankSettings.ConversionMode.DIRECT


def test_a_direct_conversion_pair_is_resolved(admin_client):
    settings_obj = BankSettings.load()
    settings_obj.conversion_mode = BankSettings.ConversionMode.DIRECT
    settings_obj.save(update_fields=["conversion_mode"])

    response = admin_client.post(
        RATES_URL,
        {
            "currency": "EUR",
            "base_currency": "USD",
            "rate_type": "conversion",
            "units": 1,
            "value": "1.100000",
            "effective_from": (timezone.now() - timedelta(minutes=1)).isoformat(),
        },
        format="json",
    )
    assert response.status_code == 201, response.content

    resolved = admin_client.get(
        f"{RATES_URL}resolve/",
        {
            "currency": "EUR",
            "target_currency": "USD",
            "rate_type": "conversion",
        },
    )

    assert resolved.status_code == 200, resolved.content
    assert resolved.data["base_currency"] == "USD"
    assert resolved.data["value"] == "1.100000"
    assert registry.get(CASH_DESK_CONFIG).rate(
        "EUR", "conversion", target_currency="USD"
    ) == Decimal("1.100000")

    current = admin_client.get(
        f"{RATES_URL}current/",
        {"rate_type": "conversion", "base_currency": "USD"},
    )
    assert current.status_code == 200
    assert len(current.data["results"]) == 1
    assert current.data["results"][0]["base_currency"] == "USD"


def test_a_foreign_quote_currency_is_rejected_for_a_buy_rate(admin_client):
    response = admin_client.post(
        RATES_URL,
        _buy_payload(currency="EUR", base_currency="USD"),
        format="json",
    )

    assert response.status_code == 400
    assert "base_currency" in response.data


def test_a_direct_pair_is_rejected_in_via_base_mode(admin_client):
    response = admin_client.post(
        RATES_URL,
        {
            "currency": "EUR",
            "base_currency": "USD",
            "rate_type": "conversion",
            "value": "1.100000",
            "effective_from": (timezone.now() + timedelta(minutes=5)).isoformat(),
        },
        format="json",
    )

    assert response.status_code == 400
    assert "base_currency" in response.data


def test_switching_back_to_via_base_ignores_direct_rates(admin_client):
    settings_obj = BankSettings.load()
    settings_obj.conversion_mode = BankSettings.ConversionMode.DIRECT
    settings_obj.save(update_fields=["conversion_mode"])
    CurrencyRate.objects.create(
        currency="EUR",
        base_currency="USD",
        rate_type="conversion",
        value=Decimal("1.1"),
        effective_from=timezone.now() - timedelta(minutes=1),
    )

    response = admin_client.patch("/api/settings/", {"conversion_mode": "via_base"}, format="json")

    assert response.status_code == 200, response.content
    settings_obj.refresh_from_db()
    assert settings_obj.conversion_mode == BankSettings.ConversionMode.VIA_BASE

    resolved = admin_client.get(
        f"{RATES_URL}resolve/",
        {
            "currency": "EUR",
            "target_currency": "USD",
            "rate_type": "conversion",
        },
    )
    assert resolved.status_code == 404

    current = admin_client.get(
        f"{RATES_URL}current/",
        {"rate_type": "conversion", "base_currency": "USD"},
    )
    assert current.status_code == 200
    assert current.data["results"] == []


def _direct_mode():
    settings_obj = BankSettings.load()
    settings_obj.conversion_mode = BankSettings.ConversionMode.DIRECT
    settings_obj.save(update_fields=["conversion_mode"])


def _conversion_payload(**overrides):
    data = {
        "effective_from": (timezone.now() + timedelta(minutes=5)).isoformat(),
        "pairs": [
            {
                "currency": "EUR",
                "base_currency": "USD",
                "units": 1,
                "buy": "1.080000",
                "sell": "1.120000",
            }
        ],
    }
    data.update(overrides)
    return data


def test_conversion_bulk_sets_both_quotes_of_a_pair(admin_client):
    _direct_mode()

    response = admin_client.post(
        f"{RATES_URL}conversion-bulk/", _conversion_payload(), format="json"
    )

    assert response.status_code == 201, response.content
    assert len(response.data) == 2
    by_type = {row["rate_type"]: row for row in response.data}
    assert set(by_type) == {"conversion_buy", "conversion_sell"}
    buy = CurrencyRate.objects.get(rate_type="conversion_buy")
    sell = CurrencyRate.objects.get(rate_type="conversion_sell")
    assert (buy.currency, buy.base_currency) == ("EUR", "USD")
    assert (sell.currency, sell.base_currency) == ("EUR", "USD")
    assert buy.value == Decimal("1.080000")
    assert sell.value == Decimal("1.120000")
    assert buy.units == sell.units == 1


def test_a_conversion_pair_is_resolved_per_side(admin_client):
    _direct_mode()
    admin_client.post(f"{RATES_URL}conversion-bulk/", _conversion_payload(), format="json")

    at = timezone.now() + timedelta(minutes=6)
    resolved = admin_client.get(
        f"{RATES_URL}resolve/",
        {
            "currency": "EUR",
            "target_currency": "USD",
            "rate_type": "conversion_buy",
            "at": at.isoformat(),
        },
    )

    assert resolved.status_code == 200, resolved.content
    assert resolved.data["value"] == "1.080000"
    config = registry.get(CASH_DESK_CONFIG)
    assert config.rate("EUR", "conversion_buy", target_currency="USD", at=at) == Decimal(
        "1.080000"
    )
    assert config.rate("EUR", "conversion_sell", target_currency="USD", at=at) == Decimal(
        "1.120000"
    )


def test_a_new_conversion_quote_takes_effect_later(admin_client):
    _direct_mode()
    admin_client.post(f"{RATES_URL}conversion-bulk/", _conversion_payload(), format="json")
    admin_client.post(
        f"{RATES_URL}conversion-bulk/",
        _conversion_payload(
            effective_from=(timezone.now() + timedelta(minutes=20)).isoformat(),
            pairs=[
                {
                    "currency": "EUR",
                    "base_currency": "USD",
                    "units": 1,
                    "buy": "1.090000",
                    "sell": "1.130000",
                }
            ],
        ),
        format="json",
    )

    config = registry.get(CASH_DESK_CONFIG)
    assert config.rate(
        "EUR", "conversion_buy", target_currency="USD", at=timezone.now() + timedelta(minutes=6)
    ) == Decimal("1.080000")
    assert config.rate(
        "EUR", "conversion_buy", target_currency="USD", at=timezone.now() + timedelta(minutes=25)
    ) == Decimal("1.090000")


def test_conversion_bulk_requires_the_direct_mode(admin_client):
    response = admin_client.post(
        f"{RATES_URL}conversion-bulk/", _conversion_payload(), format="json"
    )

    assert response.status_code == 400
    assert not CurrencyRate.objects.exists()


def test_conversion_bulk_rejects_a_duplicate_pair(admin_client):
    _direct_mode()
    pair = {
        "currency": "EUR",
        "base_currency": "USD",
        "units": 1,
        "buy": "1.080000",
        "sell": "1.120000",
    }

    response = admin_client.post(
        f"{RATES_URL}conversion-bulk/", _conversion_payload(pairs=[pair, pair]), format="json"
    )

    assert response.status_code == 400
    assert "pairs" in response.data
    assert not CurrencyRate.objects.exists()


def test_conversion_bulk_sets_several_pairs_at_once(admin_client):
    _direct_mode()

    response = admin_client.post(
        f"{RATES_URL}conversion-bulk/",
        _conversion_payload(
            pairs=[
                {
                    "currency": "EUR",
                    "base_currency": "USD",
                    "units": 1,
                    "buy": "1.080000",
                    "sell": "1.120000",
                },
                {
                    "currency": "USD",
                    "base_currency": "EUR",
                    "units": 1,
                    "buy": "0.890000",
                    "sell": "0.930000",
                },
            ]
        ),
        format="json",
    )

    assert response.status_code == 201, response.content
    assert CurrencyRate.objects.count() == 4
    pairs = set(CurrencyRate.objects.values_list("currency", "base_currency"))
    assert pairs == {("EUR", "USD"), ("USD", "EUR")}


def test_a_calendar_day_rate_is_stored_by_date(admin_client, admin):
    response = admin_client.post(RATES_URL, _official_payload(), format="json")

    assert response.status_code == 201, response.content
    rate = CurrencyRate.objects.get()
    assert rate.effective_date == timezone.localdate()
    assert rate.effective_from == timezone.make_aware(
        datetime.combine(rate.effective_date, time.min),
        timezone.get_current_timezone(),
    )
    assert rate.created_by == admin


def test_a_calendar_day_rate_cannot_be_repeated(admin_client):
    assert admin_client.post(RATES_URL, _official_payload(), format="json").status_code == 201

    response = admin_client.post(RATES_URL, _official_payload(value="3.300000"), format="json")

    assert response.status_code == 400
    assert "effective_date" in response.data


def test_bulk_set_replaces_a_calendar_day_rate_with_a_version(admin_client):
    assert admin_client.post(RATES_URL, _official_payload(), format="json").status_code == 201

    response = admin_client.post(
        f"{RATES_URL}bulk/",
        {
            "rate_type": "official",
            "effective_date": timezone.localdate().isoformat(),
            "items": [{"currency": "USD", "value": "3.500000"}],
        },
        format="json",
    )

    assert response.status_code == 201, response.content
    rows = CurrencyRate.objects.order_by("id")
    assert rows.count() == 2
    assert rows[0].superseded_at is not None
    assert rows[1].superseded_at is None
    assert rows[1].value == Decimal("3.500000")

    current = admin_client.get(f"{RATES_URL}current/", {"currency": "USD", "rate_type": "official"})
    assert current.status_code == 200
    assert len(current.data["results"]) == 1
    assert current.data["results"][0]["value"] == "3.500000"


def test_the_resolution_prefers_cash_desk_then_branch_then_bank(org):
    now = timezone.now() - timedelta(days=1)
    CurrencyRate.objects.create(
        currency="USD",
        base_currency="BYN",
        rate_type="buy",
        value=Decimal("3.0"),
        effective_from=now,
    )
    CurrencyRate.objects.create(
        currency="USD",
        base_currency="BYN",
        rate_type="buy",
        value=Decimal("3.1"),
        effective_from=now,
        branch=org.branch,
    )
    CurrencyRate.objects.create(
        currency="USD",
        base_currency="BYN",
        rate_type="buy",
        value=Decimal("3.2"),
        effective_from=now,
        cash_desk=org.desk,
    )
    directory = registry.get(CASH_DESK_CONFIG)

    assert directory.rate("USD", "buy", cash_desk_id=org.desk.id) == Decimal("3.2")
    assert directory.rate("USD", "buy", cash_desk_id=org.second_desk.id) == Decimal("3.1")
    assert directory.rate("USD", "buy", cash_desk_id=org.sibling_desk.id) == Decimal("3.0")
    assert directory.rate("USD", "buy") == Decimal("3.0")


def test_a_non_daily_calendar_day_type_falls_back_to_the_previous_date(org):
    type_ = CurrencyRateType.objects.create(
        code="official_optional",
        name="Курс Нацбанка (не ежедневный)",
        principle="official",
        validity="calendar_day",
        daily_required=False,
    )
    today = timezone.localdate()
    CurrencyRate.objects.create(
        currency="USD",
        base_currency="BYN",
        rate_type=type_.code,
        value=Decimal("3.0"),
        effective_date=today - timedelta(days=1),
    )

    row = registry.get(CASH_DESK_CONFIG).rate("USD", type_.code)

    assert row == Decimal("3.0")


def test_a_daily_since_set_type_requires_a_rate_set_today(org):
    type_ = CurrencyRateType.objects.create(
        code="buy_daily",
        name="Курс покупки (ежедневный)",
        principle="buy",
        validity="since_set",
        daily_required=True,
    )
    CurrencyRate.objects.create(
        currency="USD",
        base_currency="BYN",
        rate_type=type_.code,
        value=Decimal("3.0"),
        effective_from=timezone.now() - timedelta(days=1),
    )

    assert registry.get(CASH_DESK_CONFIG).rate("USD", type_.code) is None

    CurrencyRate.objects.create(
        currency="USD",
        base_currency="BYN",
        rate_type=type_.code,
        value=Decimal("3.2"),
        effective_from=timezone.now(),
    )
    assert registry.get(CASH_DESK_CONFIG).rate("USD", type_.code) == Decimal("3.2")


def test_a_child_branch_inherits_the_parent_branch_rate(org):
    now = timezone.now() - timedelta(days=1)
    CurrencyRate.objects.create(
        currency="USD",
        base_currency="BYN",
        rate_type="buy",
        value=Decimal("3.05"),
        effective_from=now,
        branch=org.head,
    )

    assert registry.get(CASH_DESK_CONFIG).rate(
        "USD", "buy", cash_desk_id=org.second_desk.id
    ) == Decimal("3.05")


def test_an_individual_cash_desk_does_not_fall_back(org):
    now = timezone.now() - timedelta(days=1)
    org.desk.uses_individual_rates = True
    org.desk.save(update_fields=["uses_individual_rates"])
    CurrencyRate.objects.create(
        currency="USD",
        base_currency="BYN",
        rate_type="buy",
        value=Decimal("3.0"),
        effective_from=now,
    )
    CurrencyRate.objects.create(
        currency="USD",
        base_currency="BYN",
        rate_type="buy",
        value=Decimal("3.1"),
        effective_from=now,
        branch=org.branch,
    )
    directory = registry.get(CASH_DESK_CONFIG)

    assert directory.rate("USD", "buy", cash_desk_id=org.desk.id) is None

    CurrencyRate.objects.create(
        currency="USD",
        base_currency="BYN",
        rate_type="buy",
        value=Decimal("3.2"),
        effective_from=now,
        cash_desk=org.desk,
    )
    assert directory.rate("USD", "buy", cash_desk_id=org.desk.id) == Decimal("3.2")


def test_an_individual_branch_blocks_bank_but_not_its_cash_desk(org):
    now = timezone.now() - timedelta(days=1)
    org.branch.uses_individual_rates = True
    org.branch.save(update_fields=["uses_individual_rates"])
    CurrencyRate.objects.create(
        currency="USD",
        base_currency="BYN",
        rate_type="buy",
        value=Decimal("3.0"),
        effective_from=now,
    )
    directory = registry.get(CASH_DESK_CONFIG)

    assert directory.rate("USD", "buy", cash_desk_id=org.second_desk.id) is None

    CurrencyRate.objects.create(
        currency="USD",
        base_currency="BYN",
        rate_type="buy",
        value=Decimal("3.1"),
        effective_from=now,
        branch=org.branch,
    )
    assert directory.rate("USD", "buy", cash_desk_id=org.second_desk.id) == Decimal("3.1")

    CurrencyRate.objects.create(
        currency="USD",
        base_currency="BYN",
        rate_type="buy",
        value=Decimal("3.2"),
        effective_from=now,
        cash_desk=org.desk,
    )
    assert directory.rate("USD", "buy", cash_desk_id=org.desk.id) == Decimal("3.2")


def test_a_cashier_can_set_rates_only_for_the_open_shift_cash_desk(org):
    cashier = _user_with_role("cashier@example.com", "cashier", org.branch)
    client = _authenticated(cashier)

    response = client.post(RATES_URL, _buy_payload(cash_desk=org.desk.id), format="json")
    assert response.status_code == 403

    Shift.objects.create(cash_desk=org.desk, cashier=cashier, opened_at=timezone.now())
    response = client.post(RATES_URL, _buy_payload(cash_desk=org.desk.id), format="json")
    assert response.status_code == 201, response.content

    response = client.post(RATES_URL, _buy_payload(cash_desk=org.second_desk.id), format="json")
    assert response.status_code == 403


def test_a_branch_manager_sets_rates_within_the_branch_scope(org):
    manager = _user_with_role("manager@example.com", "branch_manager", org.branch)
    client = _authenticated(manager)

    response = client.post(RATES_URL, _buy_payload(branch=org.branch.id), format="json")
    assert response.status_code == 201, response.content

    response = client.post(
        RATES_URL, _buy_payload(currency="EUR", branch=org.sibling.id), format="json"
    )
    assert response.status_code == 403


def test_only_the_administrator_sets_the_national_bank_rate(org, admin_client):
    manager = _user_with_role("manager@example.com", "branch_manager", org.branch)
    client = _authenticated(manager)

    response = client.post(RATES_URL, _official_payload(), format="json")
    assert response.status_code == 403

    response = admin_client.post(RATES_URL, _official_payload(branch=org.branch.id), format="json")
    assert response.status_code == 400


def test_the_current_view_respects_the_branch_scope(org):
    now = timezone.now() - timedelta(days=1)
    CurrencyRate.objects.create(
        currency="USD",
        base_currency="BYN",
        rate_type="buy",
        value=Decimal("3.0"),
        effective_from=now,
    )
    CurrencyRate.objects.create(
        currency="EUR",
        base_currency="BYN",
        rate_type="buy",
        value=Decimal("3.1"),
        effective_from=now,
        branch=org.branch,
    )
    CurrencyRate.objects.create(
        currency="GBP",
        base_currency="BYN",
        rate_type="buy",
        value=Decimal("3.2"),
        effective_from=now,
        branch=org.sibling,
    )
    cashier = _user_with_role("cashier@example.com", "cashier", org.branch)
    client = _authenticated(cashier)

    response = client.get(f"{RATES_URL}current/")

    assert response.status_code == 200
    currencies = {row["currency"] for row in response.data["results"]}
    assert currencies == {"USD", "EUR"}


def test_current_respects_the_daily_requirement(admin_client):
    type_ = CurrencyRateType.objects.create(
        code="buy_daily_current",
        name="Курс покупки (ежедневный)",
        principle="buy",
        validity="since_set",
        daily_required=True,
    )
    CurrencyRate.objects.create(
        currency="USD",
        base_currency="BYN",
        rate_type=type_.code,
        value=Decimal("3.0"),
        effective_from=timezone.now() - timedelta(days=1),
    )

    response = admin_client.get(f"{RATES_URL}current/", {"rate_type": type_.code})
    assert response.status_code == 200
    assert response.data["results"] == []

    CurrencyRate.objects.create(
        currency="USD",
        base_currency="BYN",
        rate_type=type_.code,
        value=Decimal("3.2"),
        effective_from=timezone.now(),
    )
    response = admin_client.get(f"{RATES_URL}current/", {"rate_type": type_.code})
    assert response.status_code == 200
    assert len(response.data["results"]) == 1
    assert response.data["results"][0]["value"] == "3.200000"


def test_resolve_reports_a_missing_rate(admin_client):
    response = admin_client.get(f"{RATES_URL}resolve/", {"currency": "USD", "rate_type": "buy"})

    assert response.status_code == 404
    assert response.data["code"] == "rate_not_set"


def test_the_rate_validity_cannot_change_once_rates_exist(admin_client):
    rate_type = CurrencyRateType.objects.get(code="buy")
    assert admin_client.post(RATES_URL, _buy_payload(), format="json").status_code == 201

    response = admin_client.patch(
        f"{RATE_TYPES_URL}{rate_type.id}/", {"validity": "calendar_day"}, format="json"
    )

    assert response.status_code == 400
    assert "validity" in response.data
