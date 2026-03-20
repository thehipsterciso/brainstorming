"""Tests for the STRM Engine."""

import pytest
from datetime import date

from nist_strm.enums import Rationale, SetTheoryRelationship
from nist_strm.engine import STRMEngine
from nist_strm.models import FrameworkDocument, FrameworkElement, OLIRGeneralInfo


@pytest.fixture
def engine():
    """Create an engine with two documents and sample elements."""
    e = STRMEngine()

    csf = FrameworkDocument(
        id="csf2",
        title="NIST Cybersecurity Framework 2.0",
        short_name="CSF 2.0",
        version="2.0",
        author="NIST",
        url="https://www.nist.gov/cyberframework",
        date=date(2024, 2, 26),
        identifier_pattern=r"^[A-Z]{2}\.[A-Z]{2}-\d{2}$",
    )
    sp = FrameworkDocument(
        id="sp800-53",
        title="NIST SP 800-53 Rev 5",
        short_name="SP 800-53r5",
        version="5.0",
        author="NIST",
        url="https://csrc.nist.gov/publications/detail/sp/800-53/rev-5/final",
        date=date(2020, 9, 23),
        identifier_pattern=r"^[A-Z]{2}-\d+(\(\d+\))?$",
    )
    e.register_document(csf)
    e.register_document(sp)

    e.register_elements([
        FrameworkElement(
            id="csf2-gvoc01",
            document_id="csf2",
            element_type="subcategory",
            identifier="GV.OC-01",
            text="The organizational context is understood",
        ),
        FrameworkElement(
            id="csf2-prac01",
            document_id="csf2",
            element_type="subcategory",
            identifier="PR.AC-01",
            text="Identities and credentials are managed",
        ),
        FrameworkElement(
            id="sp-ac1",
            document_id="sp800-53",
            element_type="control",
            identifier="AC-1",
            text="Policy and Procedures",
        ),
        FrameworkElement(
            id="sp-ac2",
            document_id="sp800-53",
            element_type="control",
            identifier="AC-2",
            text="Account Management",
        ),
        FrameworkElement(
            id="sp-ac2-1",
            document_id="sp800-53",
            element_type="enhancement",
            identifier="AC-2(1)",
            text="Automated System Account Management",
            parent_id="sp-ac2",
        ),
    ])
    return e


class TestDocumentRegistration:
    def test_register_document(self, engine):
        assert "csf2" in engine.documents
        assert "sp800-53" in engine.documents

    def test_register_element_to_unknown_doc_fails(self, engine):
        with pytest.raises(ValueError, match="not registered"):
            engine.register_element(
                FrameworkElement(
                    id="bad",
                    document_id="nonexistent",
                    element_type="control",
                    identifier="X-1",
                    text="Bad",
                )
            )

    def test_identifier_pattern_validation(self, engine):
        with pytest.raises(ValueError, match="does not match"):
            engine.register_element(
                FrameworkElement(
                    id="bad-id",
                    document_id="csf2",
                    element_type="subcategory",
                    identifier="INVALID",
                    text="Bad",
                )
            )


class TestMappingCreation:
    def test_create_basic_mapping(self, engine):
        m = engine.create_mapping(
            focal_element_id="csf2-gvoc01",
            reference_element_id="sp-ac1",
            relationship=SetTheoryRelationship.SUBSET_OF,
            rationale=Rationale.SEMANTIC,
            strength=8,
        )
        assert m.relationship == SetTheoryRelationship.SUBSET_OF
        assert m.rationale == Rationale.SEMANTIC
        assert m.strength == 8
        assert m.concept_pair.focal_element_description == "The organizational context is understood"

    def test_multiple_rationales_same_pair(self, engine):
        engine.create_mapping(
            focal_element_id="csf2-gvoc01",
            reference_element_id="sp-ac1",
            relationship=SetTheoryRelationship.INTERSECTS_WITH,
            rationale=Rationale.SYNTACTIC,
        )
        engine.create_mapping(
            focal_element_id="csf2-gvoc01",
            reference_element_id="sp-ac1",
            relationship=SetTheoryRelationship.EQUAL,
            rationale=Rationale.SEMANTIC,
            strength=10,
        )
        pairs = engine.get_concept_pair_mappings("csf2-gvoc01", "sp-ac1")
        assert len(pairs) == 2
        rationales = {m.rationale for m in pairs}
        assert rationales == {Rationale.SYNTACTIC, Rationale.SEMANTIC}


class TestInverseMapping:
    def test_inverse_swaps_correctly(self, engine):
        m = engine.create_mapping(
            focal_element_id="csf2-gvoc01",
            reference_element_id="sp-ac1",
            relationship=SetTheoryRelationship.SUBSET_OF,
            rationale=Rationale.FUNCTIONAL,
            strength=8,
        )
        inv = engine.create_inverse_mapping(m.id)
        assert inv.concept_pair.focal_element_id == "sp-ac1"
        assert inv.concept_pair.reference_element_id == "csf2-gvoc01"
        assert inv.relationship == SetTheoryRelationship.SUPERSET_OF
        assert inv.rationale == Rationale.FUNCTIONAL
        assert inv.strength == 8


class TestQuerying:
    def test_find_by_relationship(self, engine):
        engine.create_mapping("csf2-gvoc01", "sp-ac1", SetTheoryRelationship.EQUAL, Rationale.SEMANTIC, 10)
        engine.create_mapping("csf2-prac01", "sp-ac2", SetTheoryRelationship.SUBSET_OF, Rationale.FUNCTIONAL, 7)
        equals = engine.find_mappings(relationship=SetTheoryRelationship.EQUAL)
        assert len(equals) == 1

    def test_find_by_strength_range(self, engine):
        engine.create_mapping("csf2-gvoc01", "sp-ac1", SetTheoryRelationship.SUBSET_OF, Rationale.SEMANTIC, 8)
        engine.create_mapping("csf2-prac01", "sp-ac2", SetTheoryRelationship.INTERSECTS_WITH, Rationale.FUNCTIONAL, 3)
        strong = engine.find_mappings(min_strength=7)
        assert len(strong) == 1

    def test_get_mappings_between_documents(self, engine):
        engine.create_mapping("csf2-gvoc01", "sp-ac1", SetTheoryRelationship.SUBSET_OF, Rationale.SEMANTIC)
        engine.create_mapping("csf2-prac01", "sp-ac2", SetTheoryRelationship.EQUAL, Rationale.SEMANTIC, 10)
        mappings = engine.get_mappings_between_documents("csf2", "sp800-53")
        assert len(mappings) == 2


class TestConversion:
    def test_convert_subset_to_supportive(self, engine):
        m = engine.create_mapping("csf2-gvoc01", "sp-ac1", SetTheoryRelationship.SUBSET_OF, Rationale.SEMANTIC)
        result = engine.convert_to_supportive(m.id)
        assert result["supportive_relationship"] == "supports"

    def test_convert_intersects_fails(self, engine):
        m = engine.create_mapping("csf2-gvoc01", "sp-ac1", SetTheoryRelationship.INTERSECTS_WITH, Rationale.SYNTACTIC)
        with pytest.raises(ValueError, match="INTERSECTS_WITH"):
            engine.convert_to_supportive(m.id)


class TestStatistics:
    def test_statistics(self, engine):
        engine.create_mapping("csf2-gvoc01", "sp-ac1", SetTheoryRelationship.EQUAL, Rationale.SEMANTIC, 10)
        engine.create_mapping("csf2-prac01", "sp-ac2", SetTheoryRelationship.SUBSET_OF, Rationale.FUNCTIONAL, 7)
        stats = engine.statistics()
        assert stats["total_mappings"] == 2
        assert stats["total_documents"] == 2
        assert stats["total_elements"] == 5
        assert stats["strength_stats"]["mean"] == 8.5


class TestCPRTExport:
    def test_cprt_json_structure(self, engine):
        engine.create_mapping("csf2-gvoc01", "sp-ac1", SetTheoryRelationship.SUBSET_OF, Rationale.SEMANTIC, 8)
        cprt = engine.to_cprt_json()
        assert len(cprt["documents"]) == 2
        assert len(cprt["elements"]) == 5
        assert len(cprt["relationships"]) == 1
        assert len(cprt["relationship_types"]) == 5


class TestOLIRSubmission:
    def test_create_submission(self, engine):
        engine.create_mapping("csf2-gvoc01", "sp-ac1", SetTheoryRelationship.SUBSET_OF, Rationale.SEMANTIC, 8)
        info = OLIRGeneralInfo(
            reference_document="Test Framework",
            reference_document_short_name="TF",
            reference_document_version="1.0",
            reference_document_author="Author",
            reference_document_url="https://example.com",
            reference_document_date="01/01/2024",
            informative_reference_name="TF-to-CSF (1.0)",
            informative_reference_short_name="TF-CSF",
            informative_reference_version="1.0.0",
            point_of_contact="test@example.com",
            informative_reference_developer="Dev",
            comprehensive="Yes",
            web_address="https://example.com/olir",
        )
        submission = engine.create_olir_submission(info, "csf2", "sp800-53")
        assert len(submission.mappings) == 1
        rows = submission.to_olir_rows()
        assert rows[0]["Rationale"] == "semantic"
