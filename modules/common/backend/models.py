from __future__ import annotations

import uuid

from django.db import models
from django.utils.translation import gettext_lazy as _

from modules.common.backend.schemas import qualified_table


class TimeStampedModel(models.Model):
    """Abstract base that records creation and modification timestamps."""

    created_at = models.DateTimeField(_("created at"), auto_now_add=True)
    updated_at = models.DateTimeField(_("updated at"), auto_now=True)

    class Meta:
        abstract = True


class OutboxEvent(models.Model):
    """A domain event written in the transaction of the change that produced it.

    The outbox pattern keeps consistency between modules without shared
    transactions: a module publishes an event here in the same transaction as
    its change, and the dispatcher delivers it to the subscribers afterwards.
    ``event_id`` lets a subscriber stay idempotent across redeliveries.
    """

    event_id = models.UUIDField(_("event id"), default=uuid.uuid4, unique=True, editable=False)
    topic = models.CharField(_("topic"), max_length=128)
    payload = models.JSONField(_("payload"), default=dict)
    delivered_at = models.DateTimeField(_("delivered at"), null=True, blank=True)
    attempts = models.PositiveIntegerField(_("attempts"), default=0)
    last_error = models.TextField(_("last error"), blank=True)
    created_at = models.DateTimeField(_("created at"), auto_now_add=True)

    class Meta:
        verbose_name = _("outbox event")
        verbose_name_plural = _("outbox events")
        db_table = qualified_table("common", "common_outboxevent")
        ordering = ("id",)
        indexes = (models.Index(fields=["delivered_at", "id"]),)

    def __str__(self):
        return f"{self.topic} ({self.event_id})"
