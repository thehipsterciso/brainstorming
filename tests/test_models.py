"""Tests for core STRM data models."""

import pytest
from datetime import date, datetime, timezone

from nist_strm.enums import (
    AnalysisSourceType,
    Rationale,
    SetTheoryRelationship,
    ValidationStatus,
)
from nist_strm.models import (
    AIProvenance,
    ConceptPair,
    ConfidenceVector,
    FrameworkDocument,
    HumanValidation,
    MappingRecord,
    OLIRGeneralInfo,
    ProvenanceRecord,
)


class TestConfidenceVector:
    def test_equal_must_score_10(self):
        with pytest.raises(ValueError, match="must score 10"):
            ConfidenceVector(
                relationship=SetTheoryRelationship.EQUAL,
                rationale=Rationale.SEMANTIC,
                strength=8,
            )

    def test_equal_strength_10_valid(self):
        cv = ConfidenceVector(
            relationship=SetTheoryRelationship.EQUAL,
            rationale=Rationale.SEMANTIC,
            strength=10,
        )
        assert cv.strength == 10

    def test_not_related_must_score_0(self):
        with pytest.raises(ValueError):
            ConfidenceVector(
                relationship=SetTheoryRelationship.NOT_RELATED_TO,
                rationale=Rationale.SYNTACTIC,
                strength=5,
            )

    def test_nomenclature_base(self):
        cv = ConfidenceVector(
            relationship=SetTheoryRelationship.SUBSET_OF,
            rationale=Rationale.FUNCTIONAL,
            strength=8,
        )
        assert cv.nomenclature == "STRM-B"

    def test_nomenclature_with_evidence(self):
        cv = ConfidenceVector(
            relationship=SetTheoryRelationship.SUBSET_OF,
            rationale=Rationale.SEMANTIC,
            peer_reviewed=True,
        )
        assert cv.nomenclature == "STRM-BE"

    def test_nomenclature_with_temporal(self):
        cv = ConfidenceVector(
            relationship=SetTheoryRelationship.INTERSECTS_WITH,
            rationale=Rationale.FUNCTIONAL,
            decay_factor=0.95,
        )
        assert cv.nomenclature == "STRM-BET"

    def test_vector_string_roundtrip(self):
        original = ConfidenceVector(
            relationship=SetTheoryRelationship.SUBSET_OF,
            rationale=Rationale.SEMANTIC,
            strength=8,
            source_text_specificity="H",
            analyst_expertise="M",
            peer_reviewed=True,
            framework_version_current=True,
            decay_factor=0.95,
        )
        vector_str = original.to_vector_string()
        assert vector_str.startswith("STRM:1.0/")
        parsed = ConfidenceVector.from_vector_string(vector_str)
        assert parsed.relationship == original.relationship
        assert parsed.rationale == original.rationale
        assert parsed.strength == original.strength
        assert parsed.peer_reviewed == original.peer_reviewed
        assert parsed.decay_factor == original.decay_factor

    def test_vector_string_minimal(self):
        cv = ConfidenceVector(
            relationship=SetTheoryRelationship.EQUAL,
            rationale=Rationale.SYNTACTIC,
            strength=10,
        )
        assert cv.to_vector_string() == "STRM:1.0/RT:EQ/RA:SY/ST:10"


class TestMappingRecord:
    def test_equal_strength_validation(self):
        with pytest.raises(ValueError, match="strength 10"):
            MappingRecord(
                id="test-001",
                concept_pair=ConceptPair(
                    focal_element_id="GV.OC-01",
                    reference_element_id="AC-1",
                ),
                relationship=SetTheoryRelationship.EQUAL,
                rationale=Rationale.SEMANTIC,
                strength=7,
            )

    def test_valid_mapping(self):
        m = MappingRecord(
            id="test-002",
            concept_pair=ConceptPair(
                focal_element_id="GV.OC-01",
                reference_element_id="AC-1",
            ),
            relationship=SetTheoryRelationship.SUBSET_OF,
            rationale=Rationale.FUNCTIONAL,
            strength=8,
        )
        assert m.relationship == SetTheoryRelationship.SUBSET_OF
        assert m.rationale == Rationale.FUNCTIONAL

    def test_olir_row_export(self):
        m = MappingRecord(
            id="test-003",
            concept_pair=ConceptPair(
                focal_element_id="GV.OC-01",
                focal_element_description="Test focal",
                reference_element_id="AC-1",
                reference_element_description="Test reference",
            ),
            relationship=SetTheoryRelationship.INTERSECTS_WITH,
            rationale=Rationale.SEMANTIC,
            strength=6,
        )
        row = m.to_olir_row()
        assert row["Focal Document Element"] == "GV.OC-01"
        assert row["Reference Document Element"] == "AC-1"
        assert row["Rationale"] == "semantic"
        assert row["Relationship"] == "intersects with"
        assert row["Strength of Relationship"] == 6

    def test_no_strength_exports_na(self):
        m = MappingRecord(
            id="test-004",
            concept_pair=ConceptPair(
                focal_element_id="A",
                reference_element_id="B",
            ),
            relationship=SetTheoryRelationship.SUBSET_OF,
            rationale=Rationale.SYNTACTIC,
        )
        row = m.to_olir_row()
        assert row["Strength of Relationship"] == "N/A"


class TestOLIRGeneralInfo:
    def test_version_format_validation(self):
        with pytest.raises(ValueError):
            OLIRGeneralInfo(
                reference_document="Test",
                reference_document_short_name="TEST",
                reference_document_version="1.0",
                reference_document_author="Author",
                reference_document_url="https://example.com",
                reference_document_date="01/01/2024",
                informative_reference_name="TEST-to-CSF (1.0)",
                informative_reference_short_name="TEST-CSF",
                informative_reference_version="1.0",  # invalid
                point_of_contact="test@example.com",
                informative_reference_developer="Test Dev",
                comprehensive="Yes",
            )

    def test_comprehensive_enum_validation(self):
        with pytest.raises(ValueError, match="'Yes' or 'No'"):
            OLIRGeneralInfo(
                reference_document="Test",
                reference_document_short_name="TEST",
                reference_document_version="1.0",
                reference_document_author="Author",
                reference_document_url="https://example.com",
                reference_document_date="01/01/2024",
                informative_reference_name="TEST-to-CSF",
                informative_reference_short_name="TEST-CSF",
                informative_reference_version="1.0.0",
                point_of_contact="test@example.com",
                informative_reference_developer="Dev",
                comprehensive="Maybe",
            )

    def test_short_name_max_length(self):
        with pytest.raises(ValueError):
            FrameworkDocument(
                id="test",
                title="Test",
                short_name="A" * 31,
                version="1.0",
                author="Author",
                url="https://example.com",
                date=date(2024, 1, 1),
            )


class TestProvenanceRecord:
    def test_prov_json_output(self):
        pr = ProvenanceRecord(
            activity_id="analysis-001",
            agent_id="analyst-jane",
            started_at=datetime(2026, 3, 15, 10, 0, tzinfo=timezone.utc),
            plan_id="methodology-v1",
        )
        prov = pr.to_prov_json()
        assert "entity" in prov
        assert "activity" in prov
        assert "agent" in prov
        assert "wasGeneratedBy" in prov
        assert "wasAssociatedWith" in prov
        assoc = prov["wasAssociatedWith"]["_:wAW1"]
        assert assoc["prov:plan"] == "strm:methodology-v1"


class TestAIProvenance:
    def test_hash_prompt(self):
        h = AIProvenance.hash_prompt("test prompt")
        assert len(h) == 64
        assert h == AIProvenance.hash_prompt("test prompt")  # deterministic

    def test_invalid_hash_rejected(self):
        with pytest.raises(ValueError, match="SHA-256"):
            AIProvenance(
                ai_model_name="test-model",
                system_prompt_hash="not-a-valid-hash",
            )

    def test_valid_hash_accepted(self):
        h = AIProvenance.hash_prompt("test")
        ai = AIProvenance(
            ai_model_name="claude-3.5-sonnet",
            ai_model_version="20241022",
            system_prompt_hash=h,
        )
        assert ai.system_prompt_hash == h
