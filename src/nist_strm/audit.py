"""Hash-chained audit trail for STRM mapping operations.

Implements immutable, append-only audit logging per AU-9/AU-10 requirements,
with hash chaining for tamper detection.
"""

from __future__ import annotations

import hashlib
import json
from datetime import datetime, timezone
from typing import Any

from pydantic import BaseModel, Field


class AuditEvent(BaseModel):
    """A single audit trail event with hash-chain integrity."""

    event_id: str
    timestamp: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    event_type: str = Field(
        description="E.g. 'mapping_created', 'mapping_modified', 'mapping_deleted', "
        "'validation_performed', 'export_generated'",
    )
    actor_id: str
    actor_type: str = Field(default="Person", description="Person, Organization, or SoftwareAgent")
    target_id: str | None = None
    details: dict[str, Any] = Field(default_factory=dict)
    previous_hash: str = Field(default="0" * 64)
    event_hash: str = ""

    def compute_hash(self) -> str:
        """Compute SHA-256 hash of this event for chain integrity."""
        payload = {
            "event_id": self.event_id,
            "timestamp": self.timestamp.isoformat(),
            "event_type": self.event_type,
            "actor_id": self.actor_id,
            "target_id": self.target_id,
            "details": self.details,
            "previous_hash": self.previous_hash,
        }
        content = json.dumps(payload, sort_keys=True, default=str)
        return hashlib.sha256(content.encode("utf-8")).hexdigest()


class AuditTrail:
    """Append-only, hash-chained audit trail.

    Each event includes a SHA-256 hash of itself plus the previous event's hash,
    forming a tamper-evident chain (AU-9 compliance).
    """

    def __init__(self) -> None:
        self._events: list[AuditEvent] = []
        self._last_hash: str = "0" * 64

    def append(self, event: AuditEvent) -> AuditEvent:
        """Append an event to the audit trail with hash chaining."""
        event.previous_hash = self._last_hash
        event.event_hash = event.compute_hash()
        self._last_hash = event.event_hash
        self._events.append(event)
        return event

    def verify_chain(self) -> bool:
        """Verify the integrity of the entire hash chain.

        Returns True if all hashes are valid and properly chained.
        """
        expected_prev = "0" * 64
        for event in self._events:
            if event.previous_hash != expected_prev:
                return False
            if event.event_hash != event.compute_hash():
                return False
            expected_prev = event.event_hash
        return True

    @property
    def events(self) -> list[AuditEvent]:
        return list(self._events)

    def __len__(self) -> int:
        return len(self._events)

    def to_jsonl(self) -> str:
        """Export to JSONL format (one JSON object per line)."""
        lines = []
        for event in self._events:
            lines.append(event.model_dump_json())
        return "\n".join(lines)

    def get_events_for_target(self, target_id: str) -> list[AuditEvent]:
        """Get all audit events related to a specific target (mapping, element, etc.)."""
        return [e for e in self._events if e.target_id == target_id]

    def get_events_by_actor(self, actor_id: str) -> list[AuditEvent]:
        """Get all audit events performed by a specific actor."""
        return [e for e in self._events if e.actor_id == actor_id]

    def get_events_by_type(self, event_type: str) -> list[AuditEvent]:
        """Get all audit events of a specific type."""
        return [e for e in self._events if e.event_type == event_type]
