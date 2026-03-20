"""Core data models for the NIST STRM library.

Implements the OLIR data model from IR 8278Ar1 and supporting structures.
"""

from __future__ import annotations

import hashlib
import re
from datetime import date, datetime
from typing import Any

from pydantic import BaseModel, Field, field_validator, model_validator

from nist_strm.enums import (
    AnalysisSourceType,
    AuthorityCategory,
    OLIRStatus,
    Rationale,
    SecurityControlBaseline,
    SetTheoryRelationship,
    SourceType,
    ValidationStatus,
)


# ---------------------------------------------------------------------------
# Framework element modeling
# ---------------------------------------------------------------------------


class FrameworkDocument(BaseModel):
    """A reference or focal document (framework, standard, regulation)."""

    id: str
    title: str
    short_name: str = Field(max_length=30)
    version: str
    author: str
    url: str
    date: date
    identifier_pattern: str | None = Field(
        default=None,
        description="Regex pattern for validating element identifiers in this framework.",
    )

    @field_validator("short_name")
    @classmethod
    def validate_short_name_length(cls, v: str) -> str:
        if len(v) > 30:
            raise ValueError("Reference Document Short Name must be ≤30 characters")
        return v


class FrameworkElement(BaseModel):
    """An individual element (control, subcategory, requirement) within a framework."""

    id: str
    document_id: str
    element_type: str = Field(
        description="E.g. 'function', 'category', 'subcategory', 'control', 'enhancement'",
    )
    identifier: str = Field(description="Original identifier, e.g. 'GV.OC-01', 'AC-2(1)'")
    text: str = Field(description="Full text/description of the element")
    parent_id: str | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)


# ---------------------------------------------------------------------------
# Confidence scoring (CVSS-inspired vector strings)
# ---------------------------------------------------------------------------


class ConfidenceVector(BaseModel):
    """CVSS-inspired layered confidence scoring for STRM mappings.

    Nomenclature:
        STRM-B  = base only (relationship + rationale + strength)
        STRM-BE = base + evidence quality
        STRM-BET = base + evidence + temporal
    """

    # Base dimensions (always assessed)
    relationship: SetTheoryRelationship
    rationale: Rationale
    strength: int | None = Field(default=None, ge=0, le=10)

    # Evidence quality dimensions (optional)
    source_text_specificity: str | None = Field(
        default=None,
        description="H(igh), M(edium), L(ow) — how specific the source text is",
    )
    analyst_expertise: str | None = Field(
        default=None,
        description="H(igh), M(edium), L(ow) — domain expertise of the analyst",
    )
    peer_reviewed: bool | None = Field(
        default=None,
        description="Whether the mapping has been peer-reviewed (IR 8477 recommendation)",
    )

    # Temporal dimensions (optional)
    framework_version_current: bool | None = Field(
        default=None,
        description="Whether both frameworks are at their latest version",
    )
    last_review_date: date | None = None
    decay_factor: float | None = Field(
        default=None,
        ge=0.0,
        le=1.0,
        description="Temporal decay (1.0 = fully current, 0.0 = completely stale)",
    )

    @model_validator(mode="after")
    def validate_strength_constraints(self) -> ConfidenceVector:
        if self.strength is not None:
            if self.relationship == SetTheoryRelationship.EQUAL and self.strength != 10:
                raise ValueError("Equal relationships must score 10 when strength is provided")
            if self.relationship == SetTheoryRelationship.NOT_RELATED_TO and self.strength not in (
                0,
                None,
            ):
                raise ValueError("Not Related To relationships must score 0 or N/A")
        return self

    @property
    def nomenclature(self) -> str:
        has_evidence = any(
            v is not None
            for v in [self.source_text_specificity, self.analyst_expertise, self.peer_reviewed]
        )
        has_temporal = any(
            v is not None
            for v in [self.framework_version_current, self.last_review_date, self.decay_factor]
        )
        if has_temporal:
            return "STRM-BET"
        if has_evidence:
            return "STRM-BE"
        return "STRM-B"

    def to_vector_string(self) -> str:
        """Encode as a compact, machine-parseable vector string."""
        rt_map = {
            SetTheoryRelationship.SUBSET_OF: "SB",
            SetTheoryRelationship.INTERSECTS_WITH: "IX",
            SetTheoryRelationship.EQUAL: "EQ",
            SetTheoryRelationship.SUPERSET_OF: "SP",
            SetTheoryRelationship.NOT_RELATED_TO: "NR",
        }
        ra_map = {
            Rationale.SYNTACTIC: "SY",
            Rationale.SEMANTIC: "SE",
            Rationale.FUNCTIONAL: "FN",
        }
        parts = [
            f"STRM:1.0",
            f"RT:{rt_map[self.relationship]}",
            f"RA:{ra_map[self.rationale]}",
        ]
        if self.strength is not None:
            parts.append(f"ST:{self.strength}")
        if self.source_text_specificity is not None:
            parts.append(f"TX:{self.source_text_specificity}")
        if self.analyst_expertise is not None:
            parts.append(f"AE:{self.analyst_expertise}")
        if self.peer_reviewed is not None:
            parts.append(f"PR:{'Y' if self.peer_reviewed else 'N'}")
        if self.framework_version_current is not None:
            parts.append(f"VC:{'Y' if self.framework_version_current else 'N'}")
        if self.decay_factor is not None:
            parts.append(f"DF:{self.decay_factor:.2f}")
        return "/".join(parts)

    @classmethod
    def from_vector_string(cls, vector: str) -> ConfidenceVector:
        """Parse a STRM vector string back into a ConfidenceVector."""
        rt_rev = {"SB": "subset of", "IX": "intersects with", "EQ": "equal", "SP": "superset of", "NR": "not related to"}
        ra_rev = {"SY": "syntactic", "SE": "semantic", "FN": "functional"}

        parts = vector.split("/")
        if not parts[0].startswith("STRM:"):
            raise ValueError(f"Invalid STRM vector string: {vector}")

        fields: dict[str, Any] = {}
        for part in parts[1:]:
            key, val = part.split(":", 1)
            if key == "RT":
                fields["relationship"] = SetTheoryRelationship(rt_rev[val])
            elif key == "RA":
                fields["rationale"] = Rationale(ra_rev[val])
            elif key == "ST":
                fields["strength"] = int(val)
            elif key == "TX":
                fields["source_text_specificity"] = val
            elif key == "AE":
                fields["analyst_expertise"] = val
            elif key == "PR":
                fields["peer_reviewed"] = val == "Y"
            elif key == "VC":
                fields["framework_version_current"] = val == "Y"
            elif key == "DF":
                fields["decay_factor"] = float(val)
        return cls(**fields)


# ---------------------------------------------------------------------------
# Core mapping record
# ---------------------------------------------------------------------------


class ConceptPair(BaseModel):
    """A pair of framework elements being compared."""

    focal_element_id: str
    focal_element_description: str | None = None
    reference_element_id: str
    reference_element_description: str | None = None


class MappingRecord(BaseModel):
    """A single STRM mapping between two framework elements.

    This is the core unit of work in the STRM library, corresponding
    to one row in an OLIR template.
    """

    id: str
    concept_pair: ConceptPair
    relationship: SetTheoryRelationship
    rationale: Rationale
    strength: int | None = Field(default=None, ge=0, le=10)
    security_control_baseline: SecurityControlBaseline | None = None
    comments: str | None = None
    confidence: ConfidenceVector | None = None
    provenance: ProvenanceRecord | None = None
    ai_provenance: AIProvenance | None = None
    human_validation: HumanValidation | None = None
    source_type: AnalysisSourceType = AnalysisSourceType.HUMAN_AUTHORED

    @model_validator(mode="after")
    def validate_strength_constraints(self) -> MappingRecord:
        if self.strength is not None:
            if self.relationship == SetTheoryRelationship.EQUAL and self.strength != 10:
                raise ValueError("Equal relationships must have strength 10")
            if self.relationship == SetTheoryRelationship.NOT_RELATED_TO and self.strength not in (
                0,
                None,
            ):
                raise ValueError("Not Related To relationships must have strength 0 or N/A")
        return self

    def to_olir_row(self) -> dict[str, str | int | None]:
        """Serialize to the flat OLIR template row format."""
        row: dict[str, str | int | None] = {
            "Focal Document Element": self.concept_pair.focal_element_id,
            "Focal Document Element Description": self.concept_pair.focal_element_description,
            "Reference Document Element": self.concept_pair.reference_element_id,
            "Reference Document Element Description": self.concept_pair.reference_element_description,
            "Rationale": self.rationale.value,
            "Relationship": self.relationship.value,
            "Strength of Relationship": self.strength if self.strength is not None else "N/A",
            "Comments": self.comments,
        }
        if self.security_control_baseline is not None:
            row["Security Control Baseline"] = self.security_control_baseline.value
        return row


# ---------------------------------------------------------------------------
# Provenance models
# ---------------------------------------------------------------------------


class ProvenanceRecord(BaseModel):
    """W3C PROV-compatible provenance for a mapping decision.

    Maps AU-3 requirements to PROV properties.
    """

    activity_id: str = Field(description="Unique ID for the mapping activity")
    activity_type: str = Field(default="MappingAnalysis", description="What event (AU-3)")
    started_at: datetime | None = Field(default=None, description="When (AU-3)")
    ended_at: datetime | None = None
    location: str | None = Field(default=None, description="Where (AU-3)")
    agent_id: str = Field(description="Identity (AU-3) — who performed the mapping")
    agent_type: str = Field(
        default="Person",
        description="prov:Person, prov:Organization, or prov:SoftwareAgent",
    )
    plan_id: str | None = Field(
        default=None,
        description="Methodology/plan reference (prov:hadPlan)",
    )
    input_entity_ids: list[str] = Field(
        default_factory=list,
        description="Source entities (AU-3 'source')",
    )
    derived_from: list[str] = Field(
        default_factory=list,
        description="Prior mappings this was derived from (prov:wasDerivedFrom)",
    )

    def to_prov_json(self) -> dict[str, Any]:
        """Serialize to W3C PROV-JSON format."""
        prov: dict[str, Any] = {
            "entity": {
                f"strm:{self.activity_id}-result": {
                    "prov:type": "strm:MappingDecision",
                }
            },
            "activity": {
                f"strm:{self.activity_id}": {
                    "prov:type": f"strm:{self.activity_type}",
                }
            },
            "agent": {
                f"strm:{self.agent_id}": {
                    "prov:type": f"prov:{self.agent_type}",
                }
            },
            "wasGeneratedBy": {
                "_:wGB1": {
                    "prov:entity": f"strm:{self.activity_id}-result",
                    "prov:activity": f"strm:{self.activity_id}",
                }
            },
            "wasAssociatedWith": {
                "_:wAW1": {
                    "prov:activity": f"strm:{self.activity_id}",
                    "prov:agent": f"strm:{self.agent_id}",
                }
            },
        }
        activity = prov["activity"][f"strm:{self.activity_id}"]
        if self.started_at:
            activity["prov:startTime"] = self.started_at.isoformat()
        if self.ended_at:
            activity["prov:endTime"] = self.ended_at.isoformat()
        if self.plan_id:
            assoc = prov["wasAssociatedWith"]["_:wAW1"]
            assoc["prov:plan"] = f"strm:{self.plan_id}"
        if self.input_entity_ids:
            prov["used"] = {}
            for i, eid in enumerate(self.input_entity_ids):
                prov["used"][f"_:u{i}"] = {
                    "prov:activity": f"strm:{self.activity_id}",
                    "prov:entity": eid,
                }
        if self.derived_from:
            prov["wasDerivedFrom"] = {}
            for i, did in enumerate(self.derived_from):
                prov["wasDerivedFrom"][f"_:wDF{i}"] = {
                    "prov:generatedEntity": f"strm:{self.activity_id}-result",
                    "prov:usedEntity": did,
                }
        return prov


# ---------------------------------------------------------------------------
# AI-assisted analysis tracking
# ---------------------------------------------------------------------------


class AIProvenance(BaseModel):
    """Model provenance for AI-assisted STRM mapping.

    Captures all metadata required by NIST AI 600-1 and EU AI Act Annex IV.
    """

    ai_model_name: str
    ai_model_version: str | None = None
    ai_provider: str | None = None
    system_prompt_hash: str | None = Field(
        default=None,
        description="SHA-256 hash of the system prompt",
    )
    system_prompt_text: str | None = None
    user_prompt_text: str | None = None
    ai_raw_output: str | None = None
    ai_confidence_score: float | None = Field(default=None, ge=0.0, le=1.0)
    confidence_method: str | None = Field(
        default=None,
        description="logprobs, calibrated, ensemble, or self-assessed",
    )
    temperature_setting: float | None = None
    tokens_consumed: int | None = None
    timestamp: datetime | None = None

    @field_validator("system_prompt_hash")
    @classmethod
    def validate_hash_format(cls, v: str | None) -> str | None:
        if v is not None and not re.match(r"^[a-f0-9]{64}$", v):
            raise ValueError("system_prompt_hash must be a 64-character hex SHA-256 hash")
        return v

    @staticmethod
    def hash_prompt(prompt: str) -> str:
        """Compute SHA-256 hash of a prompt string."""
        return hashlib.sha256(prompt.encode("utf-8")).hexdigest()


class HumanValidation(BaseModel):
    """Human validation record for AI-generated or any mapping."""

    reviewer_id: str
    review_timestamp: datetime
    status: ValidationStatus
    confidence_override: int | None = Field(default=None, ge=0, le=10)
    modifications_made: str | None = Field(
        default=None,
        description="Diff or description of changes from AI suggestion to final",
    )
    reviewer_qualifications: str | None = None


# ---------------------------------------------------------------------------
# OLIR submission models
# ---------------------------------------------------------------------------


class OLIRGeneralInfo(BaseModel):
    """OLIR General Information metadata (17 fields from IR 8278Ar1)."""

    reference_document: str
    reference_document_short_name: str = Field(max_length=30)
    reference_document_version: str
    reference_document_author: str
    reference_document_url: str
    reference_document_date: str = Field(
        description="MM/DD/YYYY format; day='00' if unknown",
    )
    informative_reference_name: str = Field(
        description="Format: [RefDoc]-to-[FocalDoc] (version)",
    )
    informative_reference_short_name: str = Field(max_length=30)
    informative_reference_version: str = Field(
        default="1.0.0",
        description="[major].[minor].[administrative]",
    )
    point_of_contact: str = Field(description="Must include email")
    informative_reference_developer: str
    comprehensive: str = Field(description="'Yes' or 'No'")
    summary: str | None = None
    target_audience: str | None = Field(default=None, description="Sector or 'General'")
    citations: str | None = None
    comments: str | None = None
    web_address: str = ""

    @field_validator("comprehensive")
    @classmethod
    def validate_comprehensive(cls, v: str) -> str:
        if v not in ("Yes", "No"):
            raise ValueError("Comprehensive must be 'Yes' or 'No'")
        return v

    @field_validator("informative_reference_version")
    @classmethod
    def validate_version_format(cls, v: str) -> str:
        if not re.match(r"^\d+\.\d+\.\d+$", v):
            raise ValueError("Version must be [major].[minor].[administrative] format")
        return v

    @field_validator("reference_document_date")
    @classmethod
    def validate_date_format(cls, v: str) -> str:
        if not re.match(r"^\d{2}/\d{2}/\d{4}$", v):
            raise ValueError("Date must be MM/DD/YYYY format")
        return v


class OLIRSubmission(BaseModel):
    """Complete OLIR submission containing general info and mapping records."""

    general_info: OLIRGeneralInfo
    mappings: list[MappingRecord] = Field(default_factory=list)
    status: OLIRStatus = OLIRStatus.WORK_IN_PROGRESS_DRAFT
    source_type: SourceType | None = None
    authority_category: AuthorityCategory | None = None

    def to_olir_rows(self) -> list[dict[str, str | int | None]]:
        """Serialize all mappings to OLIR template row format."""
        return [m.to_olir_row() for m in self.mappings]
