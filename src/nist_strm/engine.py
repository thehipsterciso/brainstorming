"""STRM Engine — core mapping operations and validation.

Provides the main interface for creating, validating, querying,
and exporting STRM mappings.
"""

from __future__ import annotations

import json
import uuid
from typing import Any

from nist_strm.enums import (
    Rationale,
    SetTheoryRelationship,
)
from nist_strm.models import (
    ConceptPair,
    ConfidenceVector,
    FrameworkDocument,
    FrameworkElement,
    MappingRecord,
    OLIRGeneralInfo,
    OLIRSubmission,
)


class STRMEngine:
    """Core engine for managing STRM mappings between framework elements.

    Enforces NIST IR 8477 constraints:
    - Rationale is required for every mapping
    - Relationship is required for every mapping
    - Both must be used together
    - Equal relationships must score 10 when strength is provided
    - Multiple mappings per concept pair are permitted with different rationales
    """

    def __init__(self) -> None:
        self._documents: dict[str, FrameworkDocument] = {}
        self._elements: dict[str, FrameworkElement] = {}
        self._mappings: dict[str, MappingRecord] = {}
        self._elements_by_document: dict[str, list[str]] = {}

    # ------------------------------------------------------------------
    # Document and element registration
    # ------------------------------------------------------------------

    def register_document(self, document: FrameworkDocument) -> None:
        """Register a framework document."""
        self._documents[document.id] = document
        if document.id not in self._elements_by_document:
            self._elements_by_document[document.id] = []

    def register_element(self, element: FrameworkElement) -> None:
        """Register a framework element, validating it belongs to a known document."""
        if element.document_id not in self._documents:
            raise ValueError(
                f"Document '{element.document_id}' not registered. "
                "Register the document before adding elements."
            )
        doc = self._documents[element.document_id]
        if doc.identifier_pattern:
            import re

            if not re.match(doc.identifier_pattern, element.identifier):
                raise ValueError(
                    f"Element identifier '{element.identifier}' does not match "
                    f"document pattern '{doc.identifier_pattern}'"
                )
        self._elements[element.id] = element
        self._elements_by_document.setdefault(element.document_id, []).append(element.id)

    def register_elements(self, elements: list[FrameworkElement]) -> None:
        """Register multiple framework elements."""
        for element in elements:
            self.register_element(element)

    # ------------------------------------------------------------------
    # Mapping operations
    # ------------------------------------------------------------------

    def create_mapping(
        self,
        focal_element_id: str,
        reference_element_id: str,
        relationship: SetTheoryRelationship,
        rationale: Rationale,
        strength: int | None = None,
        comments: str | None = None,
        mapping_id: str | None = None,
        **kwargs: Any,
    ) -> MappingRecord:
        """Create a new STRM mapping between two framework elements.

        Enforces all NIST IR 8477 and IR 8278Ar1 validation constraints.
        """
        focal = self._elements.get(focal_element_id)
        reference = self._elements.get(reference_element_id)

        pair = ConceptPair(
            focal_element_id=focal_element_id,
            focal_element_description=focal.text if focal else None,
            reference_element_id=reference_element_id,
            reference_element_description=reference.text if reference else None,
        )

        record = MappingRecord(
            id=mapping_id or str(uuid.uuid4()),
            concept_pair=pair,
            relationship=relationship,
            rationale=rationale,
            strength=strength,
            comments=comments,
            **kwargs,
        )

        self._mappings[record.id] = record
        return record

    def add_mapping(self, mapping: MappingRecord) -> None:
        """Add a pre-constructed MappingRecord to the engine."""
        self._mappings[mapping.id] = mapping

    def get_mapping(self, mapping_id: str) -> MappingRecord | None:
        """Retrieve a mapping by ID."""
        return self._mappings.get(mapping_id)

    def remove_mapping(self, mapping_id: str) -> bool:
        """Remove a mapping by ID. Returns True if found and removed."""
        return self._mappings.pop(mapping_id, None) is not None

    # ------------------------------------------------------------------
    # Querying
    # ------------------------------------------------------------------

    def get_mappings_for_element(
        self,
        element_id: str,
        as_focal: bool = True,
    ) -> list[MappingRecord]:
        """Get all mappings where the element appears as focal or reference."""
        results = []
        for m in self._mappings.values():
            if as_focal and m.concept_pair.focal_element_id == element_id:
                results.append(m)
            elif not as_focal and m.concept_pair.reference_element_id == element_id:
                results.append(m)
        return results

    def get_mappings_between_documents(
        self,
        focal_doc_id: str,
        reference_doc_id: str,
    ) -> list[MappingRecord]:
        """Get all mappings between elements of two documents."""
        focal_elements = set(self._elements_by_document.get(focal_doc_id, []))
        ref_elements = set(self._elements_by_document.get(reference_doc_id, []))
        return [
            m
            for m in self._mappings.values()
            if m.concept_pair.focal_element_id in focal_elements
            and m.concept_pair.reference_element_id in ref_elements
        ]

    def find_mappings(
        self,
        relationship: SetTheoryRelationship | None = None,
        rationale: Rationale | None = None,
        min_strength: int | None = None,
        max_strength: int | None = None,
    ) -> list[MappingRecord]:
        """Query mappings by relationship type, rationale, and/or strength range."""
        results = []
        for m in self._mappings.values():
            if relationship is not None and m.relationship != relationship:
                continue
            if rationale is not None and m.rationale != rationale:
                continue
            if min_strength is not None and (m.strength is None or m.strength < min_strength):
                continue
            if max_strength is not None and (m.strength is None or m.strength > max_strength):
                continue
            results.append(m)
        return results

    def get_concept_pair_mappings(
        self,
        focal_element_id: str,
        reference_element_id: str,
    ) -> list[MappingRecord]:
        """Get all mappings for a specific concept pair (may have multiple rationales)."""
        return [
            m
            for m in self._mappings.values()
            if m.concept_pair.focal_element_id == focal_element_id
            and m.concept_pair.reference_element_id == reference_element_id
        ]

    # ------------------------------------------------------------------
    # Inverse mapping
    # ------------------------------------------------------------------

    def create_inverse_mapping(self, mapping_id: str) -> MappingRecord:
        """Create the inverse of an existing mapping (swap focal/reference).

        Uses SetTheoryRelationship.inverse to determine the correct relationship.
        """
        original = self._mappings.get(mapping_id)
        if original is None:
            raise ValueError(f"Mapping '{mapping_id}' not found")

        inverse_pair = ConceptPair(
            focal_element_id=original.concept_pair.reference_element_id,
            focal_element_description=original.concept_pair.reference_element_description,
            reference_element_id=original.concept_pair.focal_element_id,
            reference_element_description=original.concept_pair.focal_element_description,
        )

        inverse = MappingRecord(
            id=str(uuid.uuid4()),
            concept_pair=inverse_pair,
            relationship=original.relationship.inverse,
            rationale=original.rationale,
            strength=original.strength,
            comments=f"Inverse of mapping {mapping_id}",
        )
        self._mappings[inverse.id] = inverse
        return inverse

    # ------------------------------------------------------------------
    # Relationship style conversion (IR 8477 Table 7)
    # ------------------------------------------------------------------

    def convert_to_supportive(self, mapping_id: str) -> dict[str, str | None]:
        """Convert a STRM mapping to supportive relationship per IR 8477 Table 7.

        Returns a dict with the supportive relationship type, or raises
        ValueError for INTERSECTS_WITH (requires manual re-evaluation).
        """
        mapping = self._mappings.get(mapping_id)
        if mapping is None:
            raise ValueError(f"Mapping '{mapping_id}' not found")

        supportive = mapping.relationship.to_supportive()
        if supportive is None:
            raise ValueError(
                f"INTERSECTS_WITH cannot be automatically converted to a supportive "
                f"relationship (IR 8477 Table 7). Manual re-evaluation required."
            )

        return {
            "mapping_id": mapping_id,
            "strm_relationship": mapping.relationship.value,
            "supportive_relationship": supportive.value,
        }

    # ------------------------------------------------------------------
    # Statistics
    # ------------------------------------------------------------------

    def statistics(self) -> dict[str, Any]:
        """Compute summary statistics for all mappings."""
        rel_counts: dict[str, int] = {}
        rat_counts: dict[str, int] = {}
        strengths: list[int] = []

        for m in self._mappings.values():
            rel_counts[m.relationship.value] = rel_counts.get(m.relationship.value, 0) + 1
            rat_counts[m.rationale.value] = rat_counts.get(m.rationale.value, 0) + 1
            if m.strength is not None:
                strengths.append(m.strength)

        return {
            "total_mappings": len(self._mappings),
            "total_documents": len(self._documents),
            "total_elements": len(self._elements),
            "relationship_counts": rel_counts,
            "rationale_counts": rat_counts,
            "strength_stats": {
                "count": len(strengths),
                "mean": sum(strengths) / len(strengths) if strengths else None,
                "min": min(strengths) if strengths else None,
                "max": max(strengths) if strengths else None,
            },
        }

    # ------------------------------------------------------------------
    # Accessors
    # ------------------------------------------------------------------

    @property
    def documents(self) -> dict[str, FrameworkDocument]:
        return dict(self._documents)

    @property
    def elements(self) -> dict[str, FrameworkElement]:
        return dict(self._elements)

    @property
    def mappings(self) -> dict[str, MappingRecord]:
        return dict(self._mappings)

    # ------------------------------------------------------------------
    # OLIR export
    # ------------------------------------------------------------------

    def create_olir_submission(
        self,
        general_info: OLIRGeneralInfo,
        focal_doc_id: str | None = None,
        reference_doc_id: str | None = None,
    ) -> OLIRSubmission:
        """Create an OLIR submission from current mappings.

        Optionally filter to mappings between specific documents.
        """
        if focal_doc_id and reference_doc_id:
            mappings = self.get_mappings_between_documents(focal_doc_id, reference_doc_id)
        else:
            mappings = list(self._mappings.values())

        return OLIRSubmission(
            general_info=general_info,
            mappings=mappings,
        )

    # ------------------------------------------------------------------
    # Serialization
    # ------------------------------------------------------------------

    def to_cprt_json(self) -> dict[str, Any]:
        """Export to NIST CPRT JSON schema format."""
        documents = [
            {
                "id": d.id,
                "title": d.title,
                "version": d.version,
                "url": d.url,
            }
            for d in self._documents.values()
        ]
        elements = [
            {
                "id": e.id,
                "document_id": e.document_id,
                "element_type": e.element_type,
                "identifier": e.identifier,
                "text": e.text,
                "parent_id": e.parent_id,
            }
            for e in self._elements.values()
        ]
        relationships = [
            {
                "id": m.id,
                "source_element_id": m.concept_pair.focal_element_id,
                "target_element_id": m.concept_pair.reference_element_id,
                "relationship_type": m.relationship.value,
                "rationale": m.rationale.value,
                "strength": m.strength,
            }
            for m in self._mappings.values()
        ]
        relationship_types = [
            {"id": r.value, "name": r.value}
            for r in SetTheoryRelationship
        ]
        return {
            "documents": documents,
            "elements": elements,
            "relationships": relationships,
            "relationship_types": relationship_types,
        }

    def export_json(self, path: str) -> None:
        """Export all data to a JSON file."""
        data = self.to_cprt_json()
        with open(path, "w") as f:
            json.dump(data, f, indent=2, default=str)

    def export_olir_json(self, submission: OLIRSubmission, path: str) -> None:
        """Export an OLIR submission to JSON."""
        data = {
            "general_info": submission.general_info.model_dump(),
            "mappings": [m.to_olir_row() for m in submission.mappings],
            "status": submission.status.value,
        }
        with open(path, "w") as f:
            json.dump(data, f, indent=2, default=str)
