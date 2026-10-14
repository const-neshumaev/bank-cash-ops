"""The transactional outbox publishes and delivers events."""

import pytest

from modules.common.backend import outbox
from modules.common.backend.models import OutboxEvent

pytestmark = pytest.mark.django_db


@pytest.fixture(autouse=True)
def _clear_subscribers():
    outbox.clear_subscribers()
    yield
    outbox.clear_subscribers()


def test_publish_records_a_pending_event():
    outbox.publish("core.shift.opened", {"shift_id": 1})

    event = OutboxEvent.objects.get(topic="core.shift.opened")
    assert event.delivered_at is None
    assert event.attempts == 0


def test_dispatch_delivers_to_subscribers():
    received = []
    outbox.subscribe("core.shift.opened", lambda event_id, payload: received.append(payload))
    outbox.publish("core.shift.opened", {"shift_id": 7})

    delivered = outbox.dispatch_pending()

    assert delivered == 1
    assert received == [{"shift_id": 7}]
    assert OutboxEvent.objects.get(topic="core.shift.opened").delivered_at is not None


def test_a_prefix_pattern_matches():
    received = []
    outbox.subscribe("operations.*", lambda event_id, payload: received.append(payload))
    outbox.publish("operations.operation.posted", {"operation_id": 1})
    outbox.publish("core.shift.opened", {"shift_id": 1})

    outbox.dispatch_pending()

    assert received == [{"operation_id": 1}]


def test_a_failed_delivery_stays_pending():
    def _boom(event_id, payload):
        raise RuntimeError("boom")

    outbox.subscribe("core.shift.opened", _boom)
    outbox.publish("core.shift.opened", {"shift_id": 1})

    assert outbox.dispatch_pending() == 0
    event = OutboxEvent.objects.get(topic="core.shift.opened")
    assert event.delivered_at is None
    assert event.attempts == 1
    assert "boom" in event.last_error


def test_a_delivered_event_is_not_dispatched_again():
    calls = []
    outbox.subscribe("core.shift.opened", lambda event_id, payload: calls.append(event_id))
    outbox.publish("core.shift.opened", {"shift_id": 1})

    outbox.dispatch_pending()
    outbox.dispatch_pending()

    assert len(calls) == 1
