"""Opening and closing a shift publishes outbox events."""

import pytest
from django.contrib.auth import get_user_model

from modules.common.backend.models import OutboxEvent
from modules.core.backend import shifts
from modules.core.backend.models import Branch, CashDesk

User = get_user_model()

pytestmark = pytest.mark.django_db


@pytest.fixture
def cash_desk():
    head = Branch.objects.create(code="HQ", name="Головной офис", is_head_office=True)
    branch = Branch.objects.create(code="B1", name="Отделение 1", parent=head)
    return CashDesk.objects.create(branch=branch, code="C1", name="Касса 1")


@pytest.fixture
def cashier():
    return User.objects.create_superuser(email="cashier@example.com", password="secret-pass-123")


def test_opening_a_shift_publishes_an_event(cashier, cash_desk):
    shift = shifts.open_shift(cashier=cashier, cash_desk=cash_desk)

    event = OutboxEvent.objects.get(topic="core.shift.opened")
    assert event.payload["shift_id"] == shift.id
    assert event.payload["cash_desk_id"] == cash_desk.id


def test_closing_a_shift_publishes_an_event(cashier, cash_desk):
    shift = shifts.open_shift(cashier=cashier, cash_desk=cash_desk)

    shifts.close_shift(shift=shift, closed_by=cashier)

    event = OutboxEvent.objects.get(topic="core.shift.closed")
    assert event.payload["shift_id"] == shift.id
    assert event.payload["closed_by_id"] == cashier.id
