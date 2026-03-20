"""Tests for STRM enumeration types."""

import pytest

from nist_strm.enums import (
    Rationale,
    SetTheoryRelationship,
    SupportiveRelationshipType,
    ValidationStatus,
)


class TestSetTheoryRelationship:
    def test_all_five_types_exist(self):
        assert len(SetTheoryRelationship) == 5

    def test_values_match_nist_spec(self):
        assert SetTheoryRelationship.SUBSET_OF.value == "subset of"
        assert SetTheoryRelationship.INTERSECTS_WITH.value == "intersects with"
        assert SetTheoryRelationship.EQUAL.value == "equal"
        assert SetTheoryRelationship.SUPERSET_OF.value == "superset of"
        assert SetTheoryRelationship.NOT_RELATED_TO.value == "not related to"

    def test_inverse_symmetry(self):
        assert SetTheoryRelationship.SUBSET_OF.inverse == SetTheoryRelationship.SUPERSET_OF
        assert SetTheoryRelationship.SUPERSET_OF.inverse == SetTheoryRelationship.SUBSET_OF
        assert SetTheoryRelationship.EQUAL.inverse == SetTheoryRelationship.EQUAL
        assert SetTheoryRelationship.INTERSECTS_WITH.inverse == SetTheoryRelationship.INTERSECTS_WITH
        assert SetTheoryRelationship.NOT_RELATED_TO.inverse == SetTheoryRelationship.NOT_RELATED_TO

    def test_double_inverse_identity(self):
        for r in SetTheoryRelationship:
            assert r.inverse.inverse == r

    def test_to_supportive_table7(self):
        assert SetTheoryRelationship.SUBSET_OF.to_supportive() == SupportiveRelationshipType.SUPPORTS
        assert SetTheoryRelationship.EQUAL.to_supportive() == SupportiveRelationshipType.EQUIVALENT
        assert SetTheoryRelationship.SUPERSET_OF.to_supportive() == SupportiveRelationshipType.IS_SUPPORTED_BY
        assert SetTheoryRelationship.NOT_RELATED_TO.to_supportive() == SupportiveRelationshipType.NO_RELATIONSHIP

    def test_intersects_with_no_supportive_conversion(self):
        assert SetTheoryRelationship.INTERSECTS_WITH.to_supportive() is None


class TestRationale:
    def test_all_three_qualifiers_exist(self):
        assert len(Rationale) == 3

    def test_values(self):
        assert Rationale.SYNTACTIC.value == "syntactic"
        assert Rationale.SEMANTIC.value == "semantic"
        assert Rationale.FUNCTIONAL.value == "functional"
