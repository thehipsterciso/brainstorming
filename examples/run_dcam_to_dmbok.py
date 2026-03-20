#!/usr/bin/env python3
"""DCAM-to-DMBOK STRM Mapping — end-to-end demonstration.

This script:
  1. Loads DCAM and DMBOK framework elements from JSON data files
  2. Registers them in an STRMEngine instance
  3. Performs AI-assisted STRM analysis for every element pair
     using the AIMapper (Claude API)
  4. Records each mapping with full provenance:
     - W3C PROV-JSON provenance records
     - AI provenance per NIST AI 600-1
     - CVSS-inspired confidence vectors
     - Hash-chained audit trail (AU-9/AU-10)
     - Human validation queue (PENDING status)
  5. Exports results to OLIR JSON and CPRT JSON
  6. Prints a full summary with statistics

Usage:
    export ANTHROPIC_API_KEY=sk-ant-...
    python examples/run_dcam_to_dmbok.py

    # Or with a different model:
    python examples/run_dcam_to_dmbok.py --model claude-opus-4-6

    # Skip NOT_RELATED_TO pairs and filter by confidence:
    python examples/run_dcam_to_dmbok.py --skip-unrelated --min-confidence 0.3
"""

from __future__ import annotations

import argparse
import json
import sys
from datetime import date, datetime, timezone
from pathlib import Path

# ── Module imports — this is the nist_strm library ──────────────────────
from nist_strm import (
    FrameworkDocument,
    FrameworkElement,
    OLIRGeneralInfo,
    STRMEngine,
)
from nist_strm.audit import AuditTrail
from nist_strm.ai_mapper import AIMapper, ElementFilter, MappingBatchResult


# ========================================================================
# Step 1: Load framework element data from JSON
# ========================================================================

def load_framework(engine: STRMEngine, json_path: str) -> list[FrameworkElement]:
    """Load a framework document and its elements into the engine."""
    with open(json_path) as f:
        data = json.load(f)

    doc_data = data["document"]
    doc = FrameworkDocument(
        id=doc_data["id"],
        title=doc_data["title"],
        short_name=doc_data["short_name"],
        version=doc_data["version"],
        author=doc_data["author"],
        url=doc_data["url"],
        date=date.fromisoformat(doc_data["date"]),
    )
    engine.register_document(doc)
    print(f"  Registered document: {doc.title} ({doc.short_name} v{doc.version})")

    elements = []
    for el_data in data["elements"]:
        element = FrameworkElement(
            id=el_data["id"],
            document_id=doc_data["id"],
            element_type=el_data["element_type"],
            identifier=el_data["identifier"],
            text=el_data["text"],
            parent_id=el_data.get("parent_id"),
            metadata=el_data.get("metadata", {}),
        )
        engine.register_element(element)
        elements.append(element)

    print(f"  Registered {len(elements)} elements")
    return elements


# ========================================================================
# Step 2: Progress callback
# ========================================================================

def on_progress(current: int, total: int, analysis) -> None:
    """Print progress for each analyzed pair."""
    if analysis is None:
        print(f"  [{current}/{total}] ERROR - skipped")
        return

    m = analysis.mapping
    prov = m.ai_provenance
    conf = prov.ai_confidence_score if prov else 0.0
    print(
        f"  [{current}/{total}] "
        f"{m.concept_pair.focal_element_id} -> {m.concept_pair.reference_element_id}: "
        f"{m.relationship.value} | {m.rationale.value} | "
        f"strength={m.strength} | confidence={conf:.2f} | "
        f"tokens={analysis.tokens_used}"
    )


# ========================================================================
# Step 3: Print results
# ========================================================================

def print_results(result: MappingBatchResult, engine: STRMEngine, trail: AuditTrail) -> None:
    """Print comprehensive results summary."""
    print("\n" + "=" * 80)
    print("STRM MAPPING RESULTS: DCAM -> DMBOK")
    print("=" * 80)

    print(f"\nModel:            {result.model_name}")
    print(f"Started:          {result.started_at.isoformat()}")
    print(f"Completed:        {result.completed_at.isoformat() if result.completed_at else 'N/A'}")
    print(f"Total pairs:      {result.total_pairs}")
    print(f"Analyzed:         {result.analyzed_pairs}")
    print(f"Mappings kept:    {len(result.mappings)}")
    print(f"Skipped:          {result.skipped_pairs}")
    print(f"Errors:           {len(result.errors)}")
    print(f"Total tokens:     {result.total_tokens:,}")

    # ── Statistics from engine ──
    stats = engine.statistics()
    print(f"\n--- Engine Statistics ---")
    print(f"Documents:        {stats['total_documents']}")
    print(f"Elements:         {stats['total_elements']}")
    print(f"Mappings:         {stats['total_mappings']}")
    print(f"Relationship distribution:")
    for rel, count in sorted(stats["relationship_counts"].items()):
        print(f"  {rel}: {count}")
    print(f"Rationale distribution:")
    for rat, count in sorted(stats["rationale_counts"].items()):
        print(f"  {rat}: {count}")
    if stats["strength_stats"]["count"] > 0:
        ss = stats["strength_stats"]
        print(f"Strength: mean={ss['mean']:.1f}, min={ss['min']}, max={ss['max']}")

    # ── Individual mappings ──
    print(f"\n--- All Mappings ---")
    print(f"{'Focal':<12} {'Ref':<12} {'Relationship':<18} {'Rationale':<12} {'Str':>3} {'Conf':>5} {'Source':>10}")
    print("-" * 80)
    for m in result.mappings:
        conf = m.ai_provenance.ai_confidence_score if m.ai_provenance else 0.0
        print(
            f"{m.concept_pair.focal_element_id:<12} "
            f"{m.concept_pair.reference_element_id:<12} "
            f"{m.relationship.value:<18} "
            f"{m.rationale.value:<12} "
            f"{m.strength or 0:>3} "
            f"{conf:>5.2f} "
            f"{m.source_type.value:>10}"
        )

    # ── Provenance detail for first mapping ──
    if result.mappings:
        m0 = result.mappings[0]
        print(f"\n--- Sample Provenance Detail (first mapping) ---")

        print(f"\n[W3C PROV-JSON]")
        if m0.provenance:
            prov_json = m0.provenance.to_prov_json()
            print(json.dumps(prov_json, indent=2, default=str))

        print(f"\n[AI Provenance (NIST AI 600-1)]")
        if m0.ai_provenance:
            print(f"  Model:        {m0.ai_provenance.ai_model_name}")
            print(f"  Provider:     {m0.ai_provenance.ai_provider}")
            print(f"  Confidence:   {m0.ai_provenance.ai_confidence_score}")
            print(f"  Method:       {m0.ai_provenance.confidence_method}")
            print(f"  Temperature:  {m0.ai_provenance.temperature_setting}")
            print(f"  Tokens:       {m0.ai_provenance.tokens_consumed}")
            print(f"  Prompt hash:  {m0.ai_provenance.system_prompt_hash[:16]}...")
            print(f"  Timestamp:    {m0.ai_provenance.timestamp}")

        print(f"\n[Confidence Vector]")
        if m0.confidence:
            print(f"  Nomenclature: {m0.confidence.nomenclature}")
            print(f"  Vector:       {m0.confidence.to_vector_string()}")

        print(f"\n[Human Validation]")
        if m0.human_validation:
            print(f"  Status:       {m0.human_validation.status.value}")
            print(f"  Reviewer:     {m0.human_validation.reviewer_id}")

        print(f"\n[OLIR Row Export]")
        print(json.dumps(m0.to_olir_row(), indent=2, default=str))

    # ── Audit trail ──
    print(f"\n--- Audit Trail ---")
    print(f"Total events: {len(trail)}")
    print(f"Chain valid:  {trail.verify_chain()}")
    for event in trail.events[:5]:
        print(f"  [{event.event_type}] actor={event.actor_id} target={event.target_id or 'N/A'}")
    if len(trail) > 5:
        print(f"  ... and {len(trail) - 5} more events")


# ========================================================================
# Step 4: Export
# ========================================================================

def export_results(engine: STRMEngine, result: MappingBatchResult, trail: AuditTrail, output_dir: Path) -> None:
    """Export all artifacts."""
    output_dir.mkdir(parents=True, exist_ok=True)

    # CPRT JSON
    cprt_path = output_dir / "dcam_to_dmbok_cprt.json"
    engine.export_json(str(cprt_path))
    print(f"\n  Exported CPRT JSON:  {cprt_path}")

    # OLIR JSON
    general_info = OLIRGeneralInfo(
        reference_document="DAMA Data Management Body of Knowledge",
        reference_document_short_name="DMBOK2",
        reference_document_version="2.0",
        reference_document_author="DAMA International",
        reference_document_url="https://dama.org/dmbok",
        reference_document_date="07/01/2017",
        informative_reference_name="DCAM-to-DMBOK2 (2.2)",
        informative_reference_short_name="DCAM-DMBOK2-STRM",
        informative_reference_version="1.0.0",
        point_of_contact="strm-mapping@example.com",
        informative_reference_developer="NIST STRM Library (AI-Assisted)",
        comprehensive="No",
        summary="AI-assisted STRM mapping of EDM Council DCAM v2.2 to DAMA DMBOK2, "
                "with full provenance per NIST IR 8477 and NIST AI 600-1.",
    )
    submission = engine.create_olir_submission(
        general_info=general_info,
        focal_doc_id="dcam",
        reference_doc_id="dmbok",
    )
    olir_path = output_dir / "dcam_to_dmbok_olir.json"
    engine.export_olir_json(submission, str(olir_path))
    print(f"  Exported OLIR JSON:  {olir_path}")

    # Audit trail JSONL
    audit_path = output_dir / "dcam_to_dmbok_audit.jsonl"
    audit_path.write_text(trail.to_jsonl())
    print(f"  Exported Audit JSONL: {audit_path}")

    # Raw mappings with full provenance
    full_path = output_dir / "dcam_to_dmbok_full.json"
    full_data = {
        "metadata": {
            "focal_document": "dcam",
            "reference_document": "dmbok",
            "model": result.model_name,
            "started_at": result.started_at.isoformat(),
            "completed_at": result.completed_at.isoformat() if result.completed_at else None,
            "total_pairs": result.total_pairs,
            "analyzed_pairs": result.analyzed_pairs,
            "mappings_produced": len(result.mappings),
            "total_tokens": result.total_tokens,
        },
        "mappings": [m.model_dump(mode="json") for m in result.mappings],
    }
    with open(full_path, "w") as f:
        json.dump(full_data, f, indent=2, default=str)
    print(f"  Exported Full JSON:  {full_path}")


# ========================================================================
# Main
# ========================================================================

def main() -> None:
    parser = argparse.ArgumentParser(description="DCAM-to-DMBOK STRM Mapping")
    parser.add_argument("--model", default="claude-sonnet-4-6", help="Anthropic model ID")
    parser.add_argument("--skip-unrelated", action="store_true", help="Skip NOT_RELATED_TO pairs")
    parser.add_argument("--min-confidence", type=float, default=0.0, help="Minimum AI confidence")
    parser.add_argument("--output-dir", default="examples/output", help="Output directory")
    parser.add_argument("--api-key", default=None, help="Anthropic API key (or set ANTHROPIC_API_KEY)")
    args = parser.parse_args()

    print("=" * 80)
    print("NIST STRM Library — AI-Powered Framework Mapping")
    print("DCAM v2.2 -> DMBOK2")
    print("=" * 80)

    # ── Initialize engine ──
    engine = STRMEngine()
    trail = AuditTrail()

    # ── Load frameworks ──
    print("\n[1/4] Loading framework elements...")
    examples_dir = Path(__file__).parent
    load_framework(engine, str(examples_dir / "dcam_elements.json"))
    load_framework(engine, str(examples_dir / "dmbok_elements.json"))

    print(f"\n  Engine state: {len(engine.documents)} documents, {len(engine.elements)} elements")

    # ── Initialize AI mapper ──
    print(f"\n[2/4] Initializing AIMapper (model={args.model})...")
    mapper = AIMapper(
        engine,
        model=args.model,
        api_key=args.api_key,
        temperature=0.0,
        audit_trail=trail,
        on_progress=on_progress,
    )
    print(f"  System prompt hash: {mapper._system_prompt_hash[:16]}...")

    # ── Run mapping ──
    print(f"\n[3/4] Running STRM mapping (DCAM -> DMBOK)...")
    print(f"  skip_not_related={args.skip_unrelated}, min_confidence={args.min_confidence}")
    print()

    result = mapper.map_frameworks(
        focal_doc_id="dcam",
        reference_doc_id="dmbok",
        skip_not_related=args.skip_unrelated,
        min_confidence=args.min_confidence,
        auto_add_to_engine=True,
    )

    # ── Results ──
    print_results(result, engine, trail)

    # ── Export ──
    print(f"\n[4/4] Exporting artifacts...")
    export_results(engine, result, trail, Path(args.output_dir))

    print("\n" + "=" * 80)
    print("DONE. All artifacts exported.")
    print("=" * 80)


if __name__ == "__main__":
    main()
