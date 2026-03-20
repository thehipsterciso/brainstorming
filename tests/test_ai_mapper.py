"""Tests for AI-powered STRM mapping engine.

All tests mock the Anthropic client so no API key is required.
"""

from __future__ import annotations

import json
from datetime import date, datetime, timezone
from typing import Any
from unittest.mock import MagicMock, patch

import pytest

from nist_strm.audit import AuditTrail
from nist_strm.engine import STRMEngine
from nist_strm.enums import (
    AnalysisSourceType,
    Rationale,
    SetTheoryRelationship,
    ValidationStatus,
)
from nist_strm.models import FrameworkDocument, FrameworkElement


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


def _make_engine() -> STRMEngine:
    """Create an engine with two documents and elements for testing."""
    engine = STRMEngine()

    dcam_doc = FrameworkDocument(
        id="dcam",
        title="EDM Council DCAM",
        short_name="DCAM",
        version="2.0",
        author="EDM Council",
        url="https://edmcouncil.org/dcam",
        date=date(2023, 1, 1),
    )
    dmbok_doc = FrameworkDocument(
        id="dmbok",
        title="DAMA DMBOK2",
        short_name="DMBOK2",
        version="2.0",
        author="DAMA International",
        url="https://dama.org/dmbok",
        date=date(2017, 1, 1),
    )
    engine.register_document(dcam_doc)
    engine.register_document(dmbok_doc)

    dcam_elements = [
        FrameworkElement(
            id="dcam-1.1",
            document_id="dcam",
            element_type="capability",
            identifier="1.1",
            text="Data Management Strategy: Establish and maintain an enterprise data management strategy that aligns with business objectives.",
        ),
        FrameworkElement(
            id="dcam-2.1",
            document_id="dcam",
            element_type="capability",
            identifier="2.1",
            text="Data Quality Assessment: Define and implement data quality measurement processes.",
        ),
    ]

    dmbok_elements = [
        FrameworkElement(
            id="dmbok-1.3",
            document_id="dmbok",
            element_type="topic",
            identifier="1.3",
            text="Data Management Strategy: Planning and execution of data management programs aligned to organizational strategy.",
        ),
        FrameworkElement(
            id="dmbok-13.1",
            document_id="dmbok",
            element_type="topic",
            identifier="13.1",
            text="Data Quality Management: Defining business rules, measuring, monitoring, and improving data quality.",
        ),
    ]

    engine.register_elements(dcam_elements)
    engine.register_elements(dmbok_elements)
    return engine


def _mock_tool_response(
    relationship: str = "subset of",
    rationale: str = "semantic",
    strength: int = 7,
    confidence: float = 0.85,
    analysis: str = "Both elements address data management strategy alignment.",
    focal_coverage: str = "Strategy establishment covered by reference.",
    reference_coverage: str = "Planning and execution partially covered by focal.",
) -> MagicMock:
    """Create a mock Anthropic API response with a tool use block."""
    tool_input = {
        "relationship": relationship,
        "rationale": rationale,
        "strength": strength,
        "confidence": confidence,
        "analysis": analysis,
        "focal_coverage": focal_coverage,
        "reference_coverage": reference_coverage,
    }

    tool_block = MagicMock()
    tool_block.type = "tool_use"
    tool_block.name = "record_strm_mapping"
    tool_block.input = tool_input

    usage = MagicMock()
    usage.input_tokens = 500
    usage.output_tokens = 200

    response = MagicMock()
    response.content = [tool_block]
    response.usage = usage
    return response


@pytest.fixture
def engine():
    return _make_engine()


@pytest.fixture
def mock_anthropic():
    """Patch _anthropic module so AIMapper can be instantiated without an API key."""
    mock_mod = MagicMock()
    mock_client = MagicMock()
    mock_mod.Anthropic.return_value = mock_client
    with patch("nist_strm.ai_mapper._anthropic", mock_mod):
        yield mock_client


# ---------------------------------------------------------------------------
# Tests: AIMapper initialization
# ---------------------------------------------------------------------------


class TestAIMapperInit:
    def test_init_with_defaults(self, engine, mock_anthropic):
        from nist_strm.ai_mapper import AIMapper

        mapper = AIMapper(engine)
        assert mapper._model == "claude-sonnet-4-6"
        assert mapper._temperature == 0.0

    def test_init_custom_model(self, engine, mock_anthropic):
        from nist_strm.ai_mapper import AIMapper

        mapper = AIMapper(engine, model="claude-opus-4-6")
        assert mapper._model == "claude-opus-4-6"

    def test_init_without_anthropic_raises(self, engine):
        from nist_strm.ai_mapper import AIMapper

        with patch("nist_strm.ai_mapper._anthropic", None):
            with pytest.raises(ImportError, match="anthropic"):
                AIMapper(engine)

    def test_system_prompt_setter(self, engine, mock_anthropic):
        from nist_strm.ai_mapper import AIMapper

        mapper = AIMapper(engine)
        original_hash = mapper._system_prompt_hash
        mapper.system_prompt = "Custom prompt"
        assert mapper._system_prompt == "Custom prompt"
        assert mapper._system_prompt_hash != original_hash


# ---------------------------------------------------------------------------
# Tests: Single pair analysis
# ---------------------------------------------------------------------------


class TestAnalyzePair:
    def test_analyze_pair_produces_mapping(self, engine, mock_anthropic):
        from nist_strm.ai_mapper import AIMapper

        mock_anthropic.messages.create.return_value = _mock_tool_response()

        mapper = AIMapper(engine)
        focal = engine.elements["dcam-1.1"]
        ref = engine.elements["dmbok-1.3"]

        result = mapper.analyze_pair(focal, ref)

        assert result.mapping.relationship == SetTheoryRelationship.SUBSET_OF
        assert result.mapping.rationale == Rationale.SEMANTIC
        assert result.mapping.strength == 7
        assert result.tokens_used == 700
        assert not result.skipped

    def test_analyze_pair_has_ai_provenance(self, engine, mock_anthropic):
        from nist_strm.ai_mapper import AIMapper

        mock_anthropic.messages.create.return_value = _mock_tool_response()

        mapper = AIMapper(engine)
        focal = engine.elements["dcam-1.1"]
        ref = engine.elements["dmbok-1.3"]

        result = mapper.analyze_pair(focal, ref)
        prov = result.mapping.ai_provenance

        assert prov is not None
        assert prov.ai_model_name == "claude-sonnet-4-6"
        assert prov.ai_provider == "Anthropic"
        assert prov.ai_confidence_score == 0.85
        assert prov.confidence_method == "self-assessed"
        assert prov.temperature_setting == 0.0
        assert prov.tokens_consumed == 700
        assert prov.system_prompt_hash is not None

    def test_analyze_pair_has_w3c_provenance(self, engine, mock_anthropic):
        from nist_strm.ai_mapper import AIMapper

        mock_anthropic.messages.create.return_value = _mock_tool_response()

        mapper = AIMapper(engine)
        focal = engine.elements["dcam-1.1"]
        ref = engine.elements["dmbok-1.3"]

        result = mapper.analyze_pair(focal, ref)
        prov = result.mapping.provenance

        assert prov is not None
        assert prov.activity_type == "AIAssistedMapping"
        assert prov.agent_type == "SoftwareAgent"
        assert prov.agent_id == "anthropic:claude-sonnet-4-6"
        assert prov.plan_id == "NIST-IR-8477-STRM"
        assert set(prov.input_entity_ids) == {"dcam-1.1", "dmbok-1.3"}

    def test_analyze_pair_has_confidence_vector(self, engine, mock_anthropic):
        from nist_strm.ai_mapper import AIMapper

        mock_anthropic.messages.create.return_value = _mock_tool_response()

        mapper = AIMapper(engine)
        focal = engine.elements["dcam-1.1"]
        ref = engine.elements["dmbok-1.3"]

        result = mapper.analyze_pair(focal, ref)
        cv = result.mapping.confidence

        assert cv is not None
        assert cv.nomenclature == "STRM-BE"
        assert cv.peer_reviewed is False

    def test_analyze_pair_source_type_is_ai_generated(self, engine, mock_anthropic):
        from nist_strm.ai_mapper import AIMapper

        mock_anthropic.messages.create.return_value = _mock_tool_response()

        mapper = AIMapper(engine)
        focal = engine.elements["dcam-1.1"]
        ref = engine.elements["dmbok-1.3"]

        result = mapper.analyze_pair(focal, ref)
        assert result.mapping.source_type == AnalysisSourceType.AI_GENERATED

    def test_analyze_pair_human_validation_pending(self, engine, mock_anthropic):
        from nist_strm.ai_mapper import AIMapper

        mock_anthropic.messages.create.return_value = _mock_tool_response()

        mapper = AIMapper(engine)
        focal = engine.elements["dcam-1.1"]
        ref = engine.elements["dmbok-1.3"]

        result = mapper.analyze_pair(focal, ref)
        hv = result.mapping.human_validation

        assert hv is not None
        assert hv.status == ValidationStatus.PENDING
        assert hv.reviewer_id == "PENDING"

    def test_analyze_pair_equal_relationship(self, engine, mock_anthropic):
        from nist_strm.ai_mapper import AIMapper

        mock_anthropic.messages.create.return_value = _mock_tool_response(
            relationship="equal",
            strength=10,
            confidence=0.95,
        )

        mapper = AIMapper(engine)
        focal = engine.elements["dcam-1.1"]
        ref = engine.elements["dmbok-1.3"]

        result = mapper.analyze_pair(focal, ref)
        assert result.mapping.relationship == SetTheoryRelationship.EQUAL
        assert result.mapping.strength == 10

    def test_analyze_pair_not_related(self, engine, mock_anthropic):
        from nist_strm.ai_mapper import AIMapper

        mock_anthropic.messages.create.return_value = _mock_tool_response(
            relationship="not related to",
            strength=0,
            confidence=0.90,
        )

        mapper = AIMapper(engine)
        focal = engine.elements["dcam-1.1"]
        ref = engine.elements["dmbok-13.1"]

        result = mapper.analyze_pair(focal, ref)
        assert result.mapping.relationship == SetTheoryRelationship.NOT_RELATED_TO
        assert result.mapping.strength == 0

    def test_analyze_pair_comments_include_analysis(self, engine, mock_anthropic):
        from nist_strm.ai_mapper import AIMapper

        mock_anthropic.messages.create.return_value = _mock_tool_response(
            analysis="Detailed analysis here.",
            focal_coverage="Full coverage.",
            reference_coverage="Partial coverage.",
        )

        mapper = AIMapper(engine)
        focal = engine.elements["dcam-1.1"]
        ref = engine.elements["dmbok-1.3"]

        result = mapper.analyze_pair(focal, ref)
        assert "Detailed analysis here." in result.mapping.comments
        assert "Focal coverage: Full coverage." in result.mapping.comments
        assert "Reference coverage: Partial coverage." in result.mapping.comments

    def test_analyze_pair_with_audit_trail(self, engine, mock_anthropic):
        from nist_strm.ai_mapper import AIMapper

        mock_anthropic.messages.create.return_value = _mock_tool_response()

        trail = AuditTrail()
        mapper = AIMapper(engine, audit_trail=trail)
        focal = engine.elements["dcam-1.1"]
        ref = engine.elements["dmbok-1.3"]

        mapper.analyze_pair(focal, ref)

        assert len(trail) == 1
        event = trail.events[0]
        assert event.event_type == "ai_mapping_created"
        assert event.actor_type == "SoftwareAgent"
        assert event.details["relationship"] == "subset of"


# ---------------------------------------------------------------------------
# Tests: Full framework mapping
# ---------------------------------------------------------------------------


class TestMapFrameworks:
    def test_map_frameworks_all_pairs(self, engine, mock_anthropic):
        from nist_strm.ai_mapper import AIMapper

        mock_anthropic.messages.create.return_value = _mock_tool_response()

        mapper = AIMapper(engine)
        result = mapper.map_frameworks("dcam", "dmbok")

        # 2 focal x 2 reference = 4 pairs
        assert result.total_pairs == 4
        assert result.analyzed_pairs == 4
        assert len(result.mappings) == 4
        assert result.total_tokens == 4 * 700
        assert result.completed_at is not None
        assert result.model_name == "claude-sonnet-4-6"

    def test_map_frameworks_skip_not_related(self, engine, mock_anthropic):
        from nist_strm.ai_mapper import AIMapper

        # Return NOT_RELATED_TO for all pairs
        mock_anthropic.messages.create.return_value = _mock_tool_response(
            relationship="not related to",
            strength=0,
            confidence=0.9,
        )

        mapper = AIMapper(engine)
        result = mapper.map_frameworks("dcam", "dmbok", skip_not_related=True)

        assert result.analyzed_pairs == 4
        assert len(result.mappings) == 0
        assert result.skipped_pairs == 4

    def test_map_frameworks_min_confidence(self, engine, mock_anthropic):
        from nist_strm.ai_mapper import AIMapper

        mock_anthropic.messages.create.return_value = _mock_tool_response(
            confidence=0.3,
        )

        mapper = AIMapper(engine)
        result = mapper.map_frameworks("dcam", "dmbok", min_confidence=0.5)

        assert result.analyzed_pairs == 4
        assert len(result.mappings) == 0
        assert result.skipped_pairs == 4

    def test_map_frameworks_auto_add_to_engine(self, engine, mock_anthropic):
        from nist_strm.ai_mapper import AIMapper

        mock_anthropic.messages.create.return_value = _mock_tool_response()

        mapper = AIMapper(engine)
        assert len(engine.mappings) == 0

        result = mapper.map_frameworks("dcam", "dmbok", auto_add_to_engine=True)

        assert len(engine.mappings) == 4

    def test_map_frameworks_invalid_doc_raises(self, engine, mock_anthropic):
        from nist_strm.ai_mapper import AIMapper

        mapper = AIMapper(engine)

        with pytest.raises(ValueError, match="not registered"):
            mapper.map_frameworks("nonexistent", "dmbok")

    def test_map_frameworks_audit_trail(self, engine, mock_anthropic):
        from nist_strm.ai_mapper import AIMapper

        mock_anthropic.messages.create.return_value = _mock_tool_response()

        trail = AuditTrail()
        mapper = AIMapper(engine, audit_trail=trail)
        mapper.map_frameworks("dcam", "dmbok")

        event_types = [e.event_type for e in trail.events]
        assert event_types[0] == "ai_batch_mapping_started"
        assert event_types[-1] == "ai_batch_mapping_completed"
        # 4 individual mapping events + start + end = 6
        assert len(trail) == 6

    def test_map_frameworks_handles_api_error(self, engine, mock_anthropic):
        from nist_strm.ai_mapper import AIMapper

        mock_anthropic.messages.create.side_effect = Exception("API rate limit")

        mapper = AIMapper(engine)
        result = mapper.map_frameworks("dcam", "dmbok")

        assert result.analyzed_pairs == 0
        assert result.skipped_pairs == 4
        assert len(result.errors) == 4
        assert all("API rate limit" in e for e in result.errors)

    def test_map_frameworks_progress_callback(self, engine, mock_anthropic):
        from nist_strm.ai_mapper import AIMapper

        mock_anthropic.messages.create.return_value = _mock_tool_response()

        progress_calls: list[tuple[int, int]] = []

        def on_progress(current, total, analysis):
            progress_calls.append((current, total))

        mapper = AIMapper(engine, on_progress=on_progress)
        mapper.map_frameworks("dcam", "dmbok")

        assert len(progress_calls) == 4
        assert progress_calls[0] == (1, 4)
        assert progress_calls[-1] == (4, 4)


# ---------------------------------------------------------------------------
# Tests: Element filter
# ---------------------------------------------------------------------------


class TestElementFilter:
    def test_filter_by_element_type(self, engine):
        from nist_strm.ai_mapper import ElementFilter

        f = ElementFilter(element_types={"capability"})
        el = engine.elements["dcam-1.1"]
        assert f.should_include(el, set())

        el2 = engine.elements["dmbok-1.3"]
        assert not f.should_include(el2, set())  # type is "topic"

    def test_filter_by_text_length(self, engine):
        from nist_strm.ai_mapper import ElementFilter

        f = ElementFilter(min_text_length=1000)
        el = engine.elements["dcam-1.1"]
        assert not f.should_include(el, set())

    def test_filter_excludes_parents(self, engine):
        from nist_strm.ai_mapper import ElementFilter

        f = ElementFilter(exclude_parents_with_children=True)
        el = engine.elements["dcam-1.1"]
        # dcam-1.1 is in the child_ids set, meaning it has children
        assert not f.should_include(el, {"dcam-1.1"})
        # Not in child_ids, so it passes
        assert f.should_include(el, set())


# ---------------------------------------------------------------------------
# Tests: Single element mapping
# ---------------------------------------------------------------------------


class TestMapElement:
    def test_map_element_returns_analyses(self, engine, mock_anthropic):
        from nist_strm.ai_mapper import AIMapper

        mock_anthropic.messages.create.return_value = _mock_tool_response()

        mapper = AIMapper(engine)
        results = mapper.map_element("dcam-1.1", "dmbok")

        assert len(results) == 2  # 2 reference elements

    def test_map_element_skips_not_related(self, engine, mock_anthropic):
        from nist_strm.ai_mapper import AIMapper

        mock_anthropic.messages.create.return_value = _mock_tool_response(
            relationship="not related to",
            strength=0,
        )

        mapper = AIMapper(engine)
        results = mapper.map_element("dcam-1.1", "dmbok", skip_not_related=True)

        assert len(results) == 0

    def test_map_element_invalid_element_raises(self, engine, mock_anthropic):
        from nist_strm.ai_mapper import AIMapper

        mapper = AIMapper(engine)

        with pytest.raises(ValueError, match="not registered"):
            mapper.map_element("nonexistent", "dmbok")


# ---------------------------------------------------------------------------
# Tests: Provenance serialization roundtrip
# ---------------------------------------------------------------------------


class TestProvenanceRoundtrip:
    def test_prov_json_roundtrip(self, engine, mock_anthropic):
        from nist_strm.ai_mapper import AIMapper

        mock_anthropic.messages.create.return_value = _mock_tool_response()

        mapper = AIMapper(engine)
        focal = engine.elements["dcam-1.1"]
        ref = engine.elements["dmbok-1.3"]

        result = mapper.analyze_pair(focal, ref)
        prov_json = result.mapping.provenance.to_prov_json()

        # Verify W3C PROV structure
        assert "entity" in prov_json
        assert "activity" in prov_json
        assert "agent" in prov_json
        assert "wasGeneratedBy" in prov_json
        assert "wasAssociatedWith" in prov_json
        assert "used" in prov_json  # input_entity_ids were set

    def test_confidence_vector_string(self, engine, mock_anthropic):
        from nist_strm.ai_mapper import AIMapper

        mock_anthropic.messages.create.return_value = _mock_tool_response()

        mapper = AIMapper(engine)
        focal = engine.elements["dcam-1.1"]
        ref = engine.elements["dmbok-1.3"]

        result = mapper.analyze_pair(focal, ref)
        cv = result.mapping.confidence
        vector_str = cv.to_vector_string()

        assert "STRM:1.0" in vector_str
        assert "RT:SB" in vector_str  # subset of
        assert "RA:SE" in vector_str  # semantic

        # Roundtrip
        from nist_strm.models import ConfidenceVector

        parsed = ConfidenceVector.from_vector_string(vector_str)
        assert parsed.relationship == cv.relationship
        assert parsed.rationale == cv.rationale
        assert parsed.strength == cv.strength


# ---------------------------------------------------------------------------
# Tests: OLIR export integration
# ---------------------------------------------------------------------------


class TestOLIRIntegration:
    def test_ai_mappings_export_to_olir_rows(self, engine, mock_anthropic):
        from nist_strm.ai_mapper import AIMapper

        mock_anthropic.messages.create.return_value = _mock_tool_response()

        mapper = AIMapper(engine)
        result = mapper.map_frameworks("dcam", "dmbok", auto_add_to_engine=True)

        # Verify mappings can be serialized to OLIR format
        for mapping in result.mappings:
            row = mapping.to_olir_row()
            assert "Focal Document Element" in row
            assert "Reference Document Element" in row
            assert "Relationship" in row
            assert "Rationale" in row
            assert row["Relationship"] == "subset of"
