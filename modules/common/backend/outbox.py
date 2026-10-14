"""Transactional outbox: publish domain events and deliver them to subscribers.

A module publishes an event in the same transaction as its business change
(:func:`publish`); a dispatcher then delivers pending events to every subscriber
whose topic pattern matches. Delivery is at-least-once, so subscribers must be
idempotent — they receive the ``event_id`` to deduplicate.

See ``docs/adr/0009-domain-events-outbox.md``.
"""

from __future__ import annotations

import logging
from collections.abc import Callable

from django.db import transaction
from django.utils import timezone

from modules.common.backend.models import OutboxEvent

logger = logging.getLogger(__name__)

#: A subscriber is called with ``(event_id, payload)``.
Handler = Callable[[str, dict], None]

_subscribers: list[tuple[str, Handler]] = []


def subscribe(topic_pattern: str, handler: Handler) -> None:
    """Register ``handler`` for a topic.

    A pattern ending with ``*`` matches every topic with that prefix (for
    example ``operations.*``); otherwise the topic must match exactly.
    """
    _subscribers.append((topic_pattern, handler))


def clear_subscribers() -> None:
    """Forget every subscriber (used by tests)."""
    _subscribers.clear()


def publish(topic: str, payload: dict) -> OutboxEvent:
    """Record an event; call this inside the transaction of the change."""
    return OutboxEvent.objects.create(topic=topic, payload=payload)


def dispatch_pending(limit: int = 100) -> int:
    """Deliver pending events to their subscribers; return how many were delivered.

    Rows are locked with ``SKIP LOCKED`` so several dispatchers can run safely.
    A delivery that raises is left pending with the error recorded, so a later
    run retries it.
    """
    delivered = 0
    with transaction.atomic():
        events = list(
            OutboxEvent.objects.filter(delivered_at__isnull=True)
            .order_by("id")
            .select_for_update(skip_locked=True)[:limit]
        )
        for event in events:
            handlers = [h for pattern, h in _subscribers if _matches(pattern, event.topic)]
            try:
                for handler in handlers:
                    handler(str(event.event_id), event.payload)
            except Exception as exc:
                event.attempts += 1
                event.last_error = str(exc)[:1000]
                event.save(update_fields=["attempts", "last_error"])
                logger.exception("Outbox delivery failed for topic '%s'", event.topic)
                continue
            event.attempts += 1
            event.delivered_at = timezone.now()
            event.save(update_fields=["attempts", "delivered_at"])
            delivered += 1
    return delivered


def _matches(pattern: str, topic: str) -> bool:
    if pattern.endswith("*"):
        return topic.startswith(pattern[:-1])
    return pattern == topic
