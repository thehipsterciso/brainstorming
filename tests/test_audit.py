"""Tests for the audit trail module."""

import pytest
from datetime import datetime, timezone

from nist_strm.audit import AuditEvent, AuditTrail


class TestAuditTrail:
    def test_append_and_chain(self):
        trail = AuditTrail()
        e1 = AuditEvent(
            event_id="evt-001",
            event_type="mapping_created",
            actor_id="analyst-1",
            target_id="mapping-001",
        )
        e2 = AuditEvent(
            event_id="evt-002",
            event_type="mapping_modified",
            actor_id="analyst-2",
            target_id="mapping-001",
        )
        trail.append(e1)
        trail.append(e2)
        assert len(trail) == 2
        assert e1.previous_hash == "0" * 64
        assert e2.previous_hash == e1.event_hash
        assert e2.previous_hash != "0" * 64

    def test_verify_valid_chain(self):
        trail = AuditTrail()
        for i in range(5):
            trail.append(
                AuditEvent(
                    event_id=f"evt-{i}",
                    event_type="mapping_created",
                    actor_id="analyst",
                    target_id=f"mapping-{i}",
                )
            )
        assert trail.verify_chain()

    def test_detect_tampering(self):
        trail = AuditTrail()
        for i in range(3):
            trail.append(
                AuditEvent(
                    event_id=f"evt-{i}",
                    event_type="mapping_created",
                    actor_id="analyst",
                )
            )
        # Tamper with middle event
        trail.events[1].event_hash = "tampered" + "0" * 57
        assert not trail.verify_chain()

    def test_to_jsonl(self):
        trail = AuditTrail()
        trail.append(
            AuditEvent(
                event_id="evt-001",
                event_type="mapping_created",
                actor_id="analyst-1",
            )
        )
        jsonl = trail.to_jsonl()
        assert "evt-001" in jsonl
        assert "\n" not in jsonl  # single event = no newline

    def test_query_by_target(self):
        trail = AuditTrail()
        trail.append(AuditEvent(event_id="e1", event_type="created", actor_id="a", target_id="m1"))
        trail.append(AuditEvent(event_id="e2", event_type="modified", actor_id="a", target_id="m2"))
        trail.append(AuditEvent(event_id="e3", event_type="deleted", actor_id="a", target_id="m1"))
        assert len(trail.get_events_for_target("m1")) == 2

    def test_query_by_actor(self):
        trail = AuditTrail()
        trail.append(AuditEvent(event_id="e1", event_type="created", actor_id="alice"))
        trail.append(AuditEvent(event_id="e2", event_type="created", actor_id="bob"))
        assert len(trail.get_events_by_actor("alice")) == 1

    def test_query_by_type(self):
        trail = AuditTrail()
        trail.append(AuditEvent(event_id="e1", event_type="mapping_created", actor_id="a"))
        trail.append(AuditEvent(event_id="e2", event_type="mapping_modified", actor_id="a"))
        trail.append(AuditEvent(event_id="e3", event_type="mapping_created", actor_id="a"))
        assert len(trail.get_events_by_type("mapping_created")) == 2
