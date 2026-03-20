"""AI-powered STRM mapping engine using Claude.

Iteratively analyzes element pairs between two frameworks, determining
set-theory relationships with full provenance and rationale per NIST IR 8477.
"""

from __future__ import annotations

import json
import logging
import uuid
from datetime import datetime, timezone
from typing import Any, Callable

from pydantic import BaseModel, Field

from nist_strm.audit import AuditEvent, AuditTrail
from nist_strm.engine import STRMEngine
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
    FrameworkElement,
    HumanValidation,
    MappingRecord,
    ProvenanceRecord,
)

try:
    import anthropic as _anthropic
except ImportError:
    _anthropic = None  # type: ignore[assignment]

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Structured response schema for Claude
# ---------------------------------------------------------------------------

_STRM_ANALYSIS_TOOL = {
    "name": "record_strm_mapping",
    "description": (
        "Record the NIST IR 8477 Set Theory Relationship Mapping analysis "
        "between two framework elements."
    ),
    "input_schema": {
        "type": "object",
        "properties": {
            "relationship": {
                "type": "string",
                "enum": [
                    "subset of",
                    "intersects with",
                    "equal",
                    "superset of",
                    "not related to",
                ],
                "description": (
                    "The set-theory relationship of the focal element to the "
                    "reference element per NIST IR 8477 Section 4.3."
                ),
            },
            "rationale": {
                "type": "string",
                "enum": ["syntactic", "semantic", "functional"],
                "description": (
                    "The rationale qualifier: syntactic (character/token match), "
                    "semantic (meaning equivalence), or functional (practical "
                    "outcome equivalence)."
                ),
            },
            "strength": {
                "type": "integer",
                "minimum": 0,
                "maximum": 10,
                "description": (
                    "Strength of relationship (0-10). Must be 10 for 'equal', "
                    "must be 0 for 'not related to'."
                ),
            },
            "confidence": {
                "type": "number",
                "minimum": 0.0,
                "maximum": 1.0,
                "description": "Your confidence in this assessment (0.0-1.0).",
            },
            "analysis": {
                "type": "string",
                "description": (
                    "Detailed rationale explaining why this relationship was "
                    "determined. Reference specific text from both elements. "
                    "Explain what overlaps, what diverges, and why."
                ),
            },
            "focal_coverage": {
                "type": "string",
                "description": (
                    "What aspects of the focal element are covered by the "
                    "reference element."
                ),
            },
            "reference_coverage": {
                "type": "string",
                "description": (
                    "What aspects of the reference element are covered by the "
                    "focal element."
                ),
            },
        },
        "required": [
            "relationship",
            "rationale",
            "strength",
            "confidence",
            "analysis",
            "focal_coverage",
            "reference_coverage",
        ],
    },
}


# ---------------------------------------------------------------------------
# System prompt for STRM analysis
# ---------------------------------------------------------------------------

_SYSTEM_PROMPT = """\
You are a NIST IR 8477 Set Theory Relationship Mapping (STRM) analyst. Your role
is to perform rigorous, defensible mapping analysis between framework elements.

## STRM Methodology (IR 8477 Section 4.3)

You must determine the SET-THEORY RELATIONSHIP between a Focal Element and a
Reference Element using these five relationship types:

1. **SUBSET OF** — The focal element is entirely contained within the reference
   element. Everything the focal element requires is also required by the
   reference element, but the reference element covers additional scope.

2. **SUPERSET OF** — The focal element entirely contains the reference element.
   Everything the reference element requires is also required by the focal
   element, but the focal element covers additional scope.

3. **EQUAL** — The focal and reference elements are semantically equivalent.
   They address the same requirements with the same scope. Strength MUST be 10.

4. **INTERSECTS WITH** — The elements partially overlap. Some requirements of
   the focal element are addressed by the reference element and vice versa,
   but each also covers areas the other does not.

5. **NOT RELATED TO** — There is no meaningful conceptual overlap between the
   elements. Strength MUST be 0.

## Rationale Qualifiers

Choose the rationale that best describes WHY the relationship holds:

- **Syntactic** — The relationship is evident from the text/tokens themselves
  (similar wording, shared terminology).
- **Semantic** — The relationship is based on meaning equivalence even if the
  wording differs (concepts map to the same underlying idea).
- **Functional** — The relationship is based on practical outcome equivalence
  (different approaches that achieve the same operational result).

## Strength Scale (0-10)

- 10 = Perfect alignment (mandatory for EQUAL)
- 7-9 = Strong alignment with minor gaps
- 4-6 = Moderate alignment with notable differences
- 1-3 = Weak alignment, tangential connection only
- 0 = No relationship (mandatory for NOT RELATED TO)

## Analysis Requirements

Your analysis MUST:
1. Quote or reference specific text from both elements
2. Identify what overlaps and what diverges
3. Justify the chosen relationship type with concrete evidence
4. Explain the rationale qualifier selection
5. Be defensible in a peer-review context (IR 8477 recommends peer review)

Be conservative. When uncertain, prefer INTERSECTS WITH over SUBSET/SUPERSET,
and use a lower confidence score. Do not inflate relationships.
"""


# ---------------------------------------------------------------------------
# Progress / batch result types
# ---------------------------------------------------------------------------


class MappingAnalysis(BaseModel):
    """Result of a single AI-driven element pair analysis."""

    mapping: MappingRecord
    raw_analysis: dict[str, Any]
    tokens_used: int = 0
    skipped: bool = False
    skip_reason: str | None = None


class MappingBatchResult(BaseModel):
    """Aggregate result from a full framework-to-framework mapping run."""

    focal_document_id: str
    reference_document_id: str
    total_pairs: int
    analyzed_pairs: int
    skipped_pairs: int
    mappings: list[MappingRecord] = Field(default_factory=list)
    total_tokens: int = 0
    started_at: datetime
    completed_at: datetime | None = None
    model_name: str = ""
    errors: list[str] = Field(default_factory=list)


# ---------------------------------------------------------------------------
# Filtering / pre-screening
# ---------------------------------------------------------------------------


class ElementFilter:
    """Filter element pairs before sending to AI to reduce cost/noise."""

    def __init__(
        self,
        *,
        element_types: set[str] | None = None,
        min_text_length: int = 10,
        exclude_parents_with_children: bool = False,
    ) -> None:
        self.element_types = element_types
        self.min_text_length = min_text_length
        self.exclude_parents_with_children = exclude_parents_with_children

    def should_include(
        self,
        element: FrameworkElement,
        child_ids: set[str],
    ) -> bool:
        if self.element_types and element.element_type not in self.element_types:
            return False
        if len(element.text.strip()) < self.min_text_length:
            return False
        if self.exclude_parents_with_children and element.id in child_ids:
            return False
        return True


# ---------------------------------------------------------------------------
# AIMapper — the core AI mapping engine
# ---------------------------------------------------------------------------


class AIMapper:
    """AI-powered STRM mapping engine using the Anthropic Claude API.

    Iterates through element pairs between two frameworks, sends their
    content to Claude for set-theory relationship analysis, and produces
    fully-provenance MappingRecords that integrate with STRMEngine.

    Usage::

        from nist_strm import STRMEngine
        from nist_strm.ai_mapper import AIMapper

        engine = STRMEngine()
        # ... register documents and elements ...

        mapper = AIMapper(engine, model="claude-sonnet-4-6")
        result = mapper.map_frameworks("dcam", "dmbok")

        for m in result.mappings:
            engine.add_mapping(m)
    """

    def __init__(
        self,
        engine: STRMEngine,
        *,
        model: str = "claude-sonnet-4-6",
        api_key: str | None = None,
        max_tokens: int = 4096,
        temperature: float = 0.0,
        audit_trail: AuditTrail | None = None,
        on_progress: Callable[[int, int, MappingAnalysis | None], None] | None = None,
    ) -> None:
        """Initialize the AI mapper.

        Args:
            engine: STRMEngine with documents and elements registered.
            model: Anthropic model ID to use for analysis.
            api_key: Anthropic API key. If None, uses ANTHROPIC_API_KEY env var.
            max_tokens: Max tokens per Claude response.
            temperature: Sampling temperature (0.0 = deterministic).
            audit_trail: Optional AuditTrail for logging all AI operations.
            on_progress: Callback(current_index, total_pairs, analysis) for progress.
        """
        if _anthropic is None:
            raise ImportError(
                "The 'anthropic' package is required for AI-powered mapping. "
                "Install it with: pip install nist-strm[ai]"
            )

        self._engine = engine
        self._model = model
        self._max_tokens = max_tokens
        self._temperature = temperature
        self._audit_trail = audit_trail
        self._on_progress = on_progress
        self._system_prompt = _SYSTEM_PROMPT
        self._system_prompt_hash = AIProvenance.hash_prompt(_SYSTEM_PROMPT)

        self._client = _anthropic.Anthropic(api_key=api_key)

    @property
    def system_prompt(self) -> str:
        return self._system_prompt

    @system_prompt.setter
    def system_prompt(self, value: str) -> None:
        self._system_prompt = value
        self._system_prompt_hash = AIProvenance.hash_prompt(value)

    # ------------------------------------------------------------------
    # Element gathering and filtering
    # ------------------------------------------------------------------

    def _get_document_elements(
        self,
        doc_id: str,
        element_filter: ElementFilter | None = None,
    ) -> list[FrameworkElement]:
        """Get all elements for a document, optionally filtered."""
        all_elements = self._engine.elements
        doc_elements = [e for e in all_elements.values() if e.document_id == doc_id]

        if not doc_elements:
            raise ValueError(
                f"No elements found for document '{doc_id}'. "
                "Register elements before mapping."
            )

        if element_filter is None:
            return doc_elements

        # Build set of parent IDs to detect parents with children
        child_parent_ids: set[str] = set()
        for e in doc_elements:
            if e.parent_id:
                child_parent_ids.add(e.parent_id)

        return [
            e
            for e in doc_elements
            if element_filter.should_include(e, child_parent_ids)
        ]

    # ------------------------------------------------------------------
    # Single pair analysis
    # ------------------------------------------------------------------

    def _build_user_prompt(
        self,
        focal: FrameworkElement,
        reference: FrameworkElement,
    ) -> str:
        """Build the user prompt for a single element pair analysis."""
        focal_doc = self._engine.documents.get(focal.document_id)
        ref_doc = self._engine.documents.get(reference.document_id)

        focal_doc_name = focal_doc.title if focal_doc else focal.document_id
        ref_doc_name = ref_doc.title if ref_doc else reference.document_id

        return (
            f"Analyze the STRM relationship between these two framework elements.\n\n"
            f"## Focal Element\n"
            f"**Framework:** {focal_doc_name}\n"
            f"**Identifier:** {focal.identifier}\n"
            f"**Type:** {focal.element_type}\n"
            f"**Text:** {focal.text}\n\n"
            f"## Reference Element\n"
            f"**Framework:** {ref_doc_name}\n"
            f"**Identifier:** {reference.identifier}\n"
            f"**Type:** {reference.element_type}\n"
            f"**Text:** {reference.text}\n\n"
            f"Use the record_strm_mapping tool to record your analysis."
        )

    def analyze_pair(
        self,
        focal: FrameworkElement,
        reference: FrameworkElement,
    ) -> MappingAnalysis:
        """Analyze a single focal/reference element pair using Claude.

        Returns a MappingAnalysis with the full MappingRecord and raw output.
        """
        user_prompt = self._build_user_prompt(focal, reference)
        activity_id = str(uuid.uuid4())
        started_at = datetime.now(timezone.utc)

        response = self._client.messages.create(
            model=self._model,
            max_tokens=self._max_tokens,
            temperature=self._temperature,
            system=self._system_prompt,
            tools=[_STRM_ANALYSIS_TOOL],
            tool_choice={"type": "tool", "name": "record_strm_mapping"},
            messages=[{"role": "user", "content": user_prompt}],
        )

        ended_at = datetime.now(timezone.utc)
        tokens_used = response.usage.input_tokens + response.usage.output_tokens

        # Extract the tool call result
        tool_result: dict[str, Any] = {}
        for block in response.content:
            if block.type == "tool_use" and block.name == "record_strm_mapping":
                tool_result = block.input
                break

        if not tool_result:
            raise ValueError(
                f"Claude did not produce a tool call for pair "
                f"{focal.identifier} -> {reference.identifier}"
            )

        # Build the MappingRecord with full provenance
        relationship = SetTheoryRelationship(tool_result["relationship"])
        rationale = Rationale(tool_result["rationale"])
        strength = tool_result["strength"]
        confidence_score = tool_result["confidence"]

        mapping_id = str(uuid.uuid4())

        concept_pair = ConceptPair(
            focal_element_id=focal.id,
            focal_element_description=focal.text,
            reference_element_id=reference.id,
            reference_element_description=reference.text,
        )

        ai_prov = AIProvenance(
            ai_model_name=self._model,
            ai_model_version=None,
            ai_provider="Anthropic",
            system_prompt_hash=self._system_prompt_hash,
            user_prompt_text=user_prompt,
            ai_raw_output=json.dumps(tool_result, indent=2),
            ai_confidence_score=confidence_score,
            confidence_method="self-assessed",
            temperature_setting=self._temperature,
            tokens_consumed=tokens_used,
            timestamp=ended_at,
        )

        provenance = ProvenanceRecord(
            activity_id=activity_id,
            activity_type="AIAssistedMapping",
            started_at=started_at,
            ended_at=ended_at,
            agent_id=f"anthropic:{self._model}",
            agent_type="SoftwareAgent",
            plan_id="NIST-IR-8477-STRM",
            input_entity_ids=[focal.id, reference.id],
        )

        confidence_vector = ConfidenceVector(
            relationship=relationship,
            rationale=rationale,
            strength=strength,
            source_text_specificity="H",
            analyst_expertise="M",
            peer_reviewed=False,
        )

        # Build the comments from the structured analysis
        comments_parts = [tool_result.get("analysis", "")]
        if tool_result.get("focal_coverage"):
            comments_parts.append(
                f"Focal coverage: {tool_result['focal_coverage']}"
            )
        if tool_result.get("reference_coverage"):
            comments_parts.append(
                f"Reference coverage: {tool_result['reference_coverage']}"
            )
        comments = "\n\n".join(comments_parts)

        mapping = MappingRecord(
            id=mapping_id,
            concept_pair=concept_pair,
            relationship=relationship,
            rationale=rationale,
            strength=strength,
            comments=comments,
            confidence=confidence_vector,
            provenance=provenance,
            ai_provenance=ai_prov,
            human_validation=HumanValidation(
                reviewer_id="PENDING",
                review_timestamp=ended_at,
                status=ValidationStatus.PENDING,
            ),
            source_type=AnalysisSourceType.AI_GENERATED,
        )

        # Audit trail
        if self._audit_trail is not None:
            self._audit_trail.append(
                AuditEvent(
                    event_id=str(uuid.uuid4()),
                    event_type="ai_mapping_created",
                    actor_id=f"anthropic:{self._model}",
                    actor_type="SoftwareAgent",
                    target_id=mapping_id,
                    details={
                        "focal_element": focal.identifier,
                        "reference_element": reference.identifier,
                        "relationship": relationship.value,
                        "rationale": rationale.value,
                        "strength": strength,
                        "confidence": confidence_score,
                        "tokens_used": tokens_used,
                        "activity_id": activity_id,
                    },
                )
            )

        return MappingAnalysis(
            mapping=mapping,
            raw_analysis=tool_result,
            tokens_used=tokens_used,
        )

    # ------------------------------------------------------------------
    # Full framework-to-framework mapping
    # ------------------------------------------------------------------

    def map_frameworks(
        self,
        focal_doc_id: str,
        reference_doc_id: str,
        *,
        focal_filter: ElementFilter | None = None,
        reference_filter: ElementFilter | None = None,
        skip_not_related: bool = False,
        min_confidence: float = 0.0,
        auto_add_to_engine: bool = False,
    ) -> MappingBatchResult:
        """Map all element pairs between two frameworks using AI analysis.

        Iterates through each focal element, comparing it against each
        reference element. Produces MappingRecords with full provenance.

        Args:
            focal_doc_id: ID of the focal (source) document.
            reference_doc_id: ID of the reference (target) document.
            focal_filter: Optional filter for focal elements.
            reference_filter: Optional filter for reference elements.
            skip_not_related: If True, exclude NOT_RELATED_TO from results.
            min_confidence: Minimum AI confidence to include in results.
            auto_add_to_engine: If True, automatically add mappings to engine.

        Returns:
            MappingBatchResult with all analyses and aggregate statistics.
        """
        # Validate documents exist
        if focal_doc_id not in self._engine.documents:
            raise ValueError(f"Focal document '{focal_doc_id}' not registered")
        if reference_doc_id not in self._engine.documents:
            raise ValueError(f"Reference document '{reference_doc_id}' not registered")

        focal_elements = self._get_document_elements(focal_doc_id, focal_filter)
        ref_elements = self._get_document_elements(reference_doc_id, reference_filter)

        total_pairs = len(focal_elements) * len(ref_elements)
        started_at = datetime.now(timezone.utc)

        result = MappingBatchResult(
            focal_document_id=focal_doc_id,
            reference_document_id=reference_doc_id,
            total_pairs=total_pairs,
            analyzed_pairs=0,
            skipped_pairs=0,
            started_at=started_at,
            model_name=self._model,
        )

        logger.info(
            "Starting STRM mapping: %s (%d elements) -> %s (%d elements) = %d pairs",
            focal_doc_id,
            len(focal_elements),
            reference_doc_id,
            len(ref_elements),
            total_pairs,
        )

        # Audit trail: log the batch start
        if self._audit_trail is not None:
            self._audit_trail.append(
                AuditEvent(
                    event_id=str(uuid.uuid4()),
                    event_type="ai_batch_mapping_started",
                    actor_id=f"anthropic:{self._model}",
                    actor_type="SoftwareAgent",
                    details={
                        "focal_doc": focal_doc_id,
                        "reference_doc": reference_doc_id,
                        "focal_elements": len(focal_elements),
                        "reference_elements": len(ref_elements),
                        "total_pairs": total_pairs,
                    },
                )
            )

        current_pair = 0
        for focal in focal_elements:
            for ref in ref_elements:
                current_pair += 1

                try:
                    analysis = self.analyze_pair(focal, ref)
                except Exception as e:
                    error_msg = (
                        f"Error analyzing {focal.identifier} -> "
                        f"{ref.identifier}: {e}"
                    )
                    logger.error(error_msg)
                    result.errors.append(error_msg)
                    result.skipped_pairs += 1
                    if self._on_progress:
                        self._on_progress(current_pair, total_pairs, None)
                    continue

                result.analyzed_pairs += 1
                result.total_tokens += analysis.tokens_used

                # Apply post-filters
                rel = analysis.mapping.relationship
                conf = analysis.mapping.ai_provenance.ai_confidence_score if analysis.mapping.ai_provenance else 0.0

                if skip_not_related and rel == SetTheoryRelationship.NOT_RELATED_TO:
                    result.skipped_pairs += 1
                    logger.debug(
                        "Skipping NOT_RELATED_TO: %s -> %s",
                        focal.identifier,
                        ref.identifier,
                    )
                elif conf is not None and conf < min_confidence:
                    result.skipped_pairs += 1
                    logger.debug(
                        "Skipping low confidence (%.2f): %s -> %s",
                        conf,
                        focal.identifier,
                        ref.identifier,
                    )
                else:
                    result.mappings.append(analysis.mapping)
                    if auto_add_to_engine:
                        self._engine.add_mapping(analysis.mapping)

                if self._on_progress:
                    self._on_progress(current_pair, total_pairs, analysis)

                logger.info(
                    "[%d/%d] %s -> %s: %s (%s, strength=%d, confidence=%.2f)",
                    current_pair,
                    total_pairs,
                    focal.identifier,
                    ref.identifier,
                    rel.value,
                    analysis.mapping.rationale.value,
                    analysis.mapping.strength or 0,
                    conf or 0.0,
                )

        result.completed_at = datetime.now(timezone.utc)

        # Audit trail: log the batch completion
        if self._audit_trail is not None:
            self._audit_trail.append(
                AuditEvent(
                    event_id=str(uuid.uuid4()),
                    event_type="ai_batch_mapping_completed",
                    actor_id=f"anthropic:{self._model}",
                    actor_type="SoftwareAgent",
                    details={
                        "focal_doc": focal_doc_id,
                        "reference_doc": reference_doc_id,
                        "analyzed_pairs": result.analyzed_pairs,
                        "skipped_pairs": result.skipped_pairs,
                        "mappings_produced": len(result.mappings),
                        "total_tokens": result.total_tokens,
                        "errors": len(result.errors),
                    },
                )
            )

        logger.info(
            "Completed STRM mapping: %d analyzed, %d mappings produced, "
            "%d skipped, %d errors, %d tokens",
            result.analyzed_pairs,
            len(result.mappings),
            result.skipped_pairs,
            len(result.errors),
            result.total_tokens,
        )

        return result

    # ------------------------------------------------------------------
    # Targeted mapping (smart pre-screening)
    # ------------------------------------------------------------------

    def map_element(
        self,
        focal_element_id: str,
        reference_doc_id: str,
        *,
        reference_filter: ElementFilter | None = None,
        skip_not_related: bool = True,
    ) -> list[MappingAnalysis]:
        """Map a single focal element against all elements in a reference document.

        Useful for incremental mapping or exploring one element's relationships.
        """
        focal = self._engine.elements.get(focal_element_id)
        if focal is None:
            raise ValueError(f"Focal element '{focal_element_id}' not registered")

        ref_elements = self._get_document_elements(reference_doc_id, reference_filter)
        results: list[MappingAnalysis] = []

        for i, ref in enumerate(ref_elements):
            try:
                analysis = self.analyze_pair(focal, ref)
            except Exception as e:
                logger.error(
                    "Error analyzing %s -> %s: %s",
                    focal.identifier,
                    ref.identifier,
                    e,
                )
                continue

            if skip_not_related and analysis.mapping.relationship == SetTheoryRelationship.NOT_RELATED_TO:
                continue

            results.append(analysis)

            if self._on_progress:
                self._on_progress(i + 1, len(ref_elements), analysis)

        return results
