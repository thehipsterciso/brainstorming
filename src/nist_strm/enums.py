"""Enumerations for NIST STRM library.

All enum values are derived directly from NIST IR 8477 and IR 8278Ar1.
"""

from enum import Enum


class ConceptRelationshipStyle(str, Enum):
    """IR 8477 Section 4: Four concept relationship styles ordered
    from most subjective to most objective."""

    CONCEPT_CROSSWALK = "concept_crosswalk"
    SUPPORTIVE_RELATIONSHIP_MAPPING = "supportive_relationship_mapping"
    SET_THEORY_RELATIONSHIP_MAPPING = "set_theory_relationship_mapping"
    STRUCTURAL_RELATIONSHIP_MAPPING = "structural_relationship_mapping"


class Rationale(str, Enum):
    """IR 8477 Section 4.3: Three rationale qualifiers ordered
    from strictest to most interpretive."""

    SYNTACTIC = "syntactic"
    SEMANTIC = "semantic"
    FUNCTIONAL = "functional"


class SetTheoryRelationship(str, Enum):
    """IR 8477 Section 4.3: Five STRM relationship types."""

    SUBSET_OF = "subset of"
    INTERSECTS_WITH = "intersects with"
    EQUAL = "equal"
    SUPERSET_OF = "superset of"
    NOT_RELATED_TO = "not related to"

    @property
    def inverse(self) -> "SetTheoryRelationship":
        """Return the inverse relationship (swap A and B perspective)."""
        _inverses = {
            SetTheoryRelationship.SUBSET_OF: SetTheoryRelationship.SUPERSET_OF,
            SetTheoryRelationship.SUPERSET_OF: SetTheoryRelationship.SUBSET_OF,
            SetTheoryRelationship.EQUAL: SetTheoryRelationship.EQUAL,
            SetTheoryRelationship.INTERSECTS_WITH: SetTheoryRelationship.INTERSECTS_WITH,
            SetTheoryRelationship.NOT_RELATED_TO: SetTheoryRelationship.NOT_RELATED_TO,
        }
        return _inverses[self]

    def to_supportive(self) -> "SupportiveRelationshipType | None":
        """IR 8477 Table 7: Convert STRM to supportive relationship.

        Returns None for INTERSECTS_WITH (requires manual re-evaluation).
        """
        _mapping = {
            SetTheoryRelationship.SUBSET_OF: SupportiveRelationshipType.SUPPORTS,
            SetTheoryRelationship.EQUAL: SupportiveRelationshipType.EQUIVALENT,
            SetTheoryRelationship.SUPERSET_OF: SupportiveRelationshipType.IS_SUPPORTED_BY,
            SetTheoryRelationship.NOT_RELATED_TO: SupportiveRelationshipType.NO_RELATIONSHIP,
        }
        return _mapping.get(self)


class SupportiveRelationshipType(str, Enum):
    """IR 8477: Supportive relationship mapping types."""

    SUPPORTS = "supports"
    IS_SUPPORTED_BY = "is supported by"
    IDENTICAL = "identical"
    EQUIVALENT = "equivalent"
    CONTRARY = "contrary"
    NO_RELATIONSHIP = "no relationship"


class RelationshipProperty(str, Enum):
    """IR 8477: Relationship property qualifiers."""

    EXAMPLE_OF = "example of"
    INTEGRAL_TO = "integral to"
    PRECEDES = "precedes"


class SecurityControlBaseline(str, Enum):
    """IR 8278Ar1: SP 800-53 security control baseline values."""

    LOW = "Low"
    MODERATE = "Moderate"
    HIGH = "High"
    NOT_SELECTED = "Not Selected"
    WITHDRAWN = "Withdrawn"
    NOT_ASSOCIATED = "Not Associated"


class OLIRStatus(str, Enum):
    """IR 8278Ar1: OLIR submission maturity levels."""

    WORK_IN_PROGRESS_DRAFT = "work-in-progress draft"
    PRELIMINARY_DRAFT = "preliminary draft"
    DRAFT = "draft"
    FINAL = "final"


class SourceType(str, Enum):
    """IR 8278Ar1: OLIR provenance source type."""

    OWNER = "owner"
    NON_OWNER = "non-owner"


class AuthorityCategory(str, Enum):
    """IR 8278Ar1: OLIR provenance authority category."""

    BILATERAL = "bilateral"
    UNILATERAL = "unilateral"


class ValidationStatus(str, Enum):
    """Validation status for AI-assisted or human-reviewed mappings."""

    PENDING = "PENDING"
    VALIDATED = "VALIDATED"
    MODIFIED = "MODIFIED"
    REJECTED = "REJECTED"


class AnalysisSourceType(str, Enum):
    """Source type tracking for mapping provenance."""

    AI_GENERATED = "AI_GENERATED"
    HUMAN_AUTHORED = "HUMAN_AUTHORED"
    AI_ASSISTED_HUMAN_VALIDATED = "AI_ASSISTED_HUMAN_VALIDATED"
    HUMAN_AUTHORED_AI_AUGMENTED = "HUMAN_AUTHORED_AI_AUGMENTED"
