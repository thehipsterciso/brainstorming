"""NIST Set Theory Relationship Mapping (STRM) library.

Implements NIST IR 8477 STRM methodology and NIST IR 8278Ar1 OLIR data model.
"""

__version__ = "0.1.0"

from nist_strm.enums import (
    AnalysisSourceType,
    AuthorityCategory,
    ConceptRelationshipStyle,
    OLIRStatus,
    Rationale,
    RelationshipProperty,
    SecurityControlBaseline,
    SetTheoryRelationship,
    SourceType,
    SupportiveRelationshipType,
    ValidationStatus,
)
from nist_strm.models import (
    AIProvenance,
    ConceptPair,
    ConfidenceVector,
    FrameworkDocument,
    FrameworkElement,
    HumanValidation,
    MappingRecord,
    OLIRGeneralInfo,
    OLIRSubmission,
    ProvenanceRecord,
)
from nist_strm.engine import STRMEngine

# AI mapper is optional — requires `pip install nist-strm[ai]`
try:
    from nist_strm.ai_mapper import AIMapper, ElementFilter, MappingBatchResult
except ImportError:
    pass

__all__ = [
    # Enums
    "AnalysisSourceType",
    "AuthorityCategory",
    "ConceptRelationshipStyle",
    "OLIRStatus",
    "Rationale",
    "RelationshipProperty",
    "SecurityControlBaseline",
    "SetTheoryRelationship",
    "SourceType",
    "SupportiveRelationshipType",
    "ValidationStatus",
    # Models
    "AIProvenance",
    "ConceptPair",
    "ConfidenceVector",
    "FrameworkDocument",
    "FrameworkElement",
    "HumanValidation",
    "MappingRecord",
    "OLIRGeneralInfo",
    "OLIRSubmission",
    "ProvenanceRecord",
    # Engine
    "STRMEngine",
    # AI Mapper (optional)
    "AIMapper",
    "ElementFilter",
    "MappingBatchResult",
]
