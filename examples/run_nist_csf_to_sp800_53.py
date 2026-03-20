#!/usr/bin/env python3
"""NIST CSF 2.0 -> SP 800-53r5 STRM Mapping — LIVE end-to-end.

Uses CANONICAL NIST source data from OSCAL GitHub repository.
Calls the Claude API via AIMapper for real STRM analysis.

Usage:
    # First, download canonical sources (one-time):
    curl -sL https://raw.githubusercontent.com/usnistgov/oscal-content/main/nist.gov/CSF/v2.0/json/NIST_CSF_v2.0_catalog.json -o /tmp/csf2_raw.json
    curl -sL https://raw.githubusercontent.com/usnistgov/oscal-content/main/nist.gov/SP800-53/rev5/json/NIST_SP-800-53_rev5_catalog.json -o /tmp/sp800_53_raw.json

    # Convert to nist_strm format:
    python examples/convert_oscal.py --sp53-families ac at au sc si pm

    # Run STRM mapping:
    export ANTHROPIC_API_KEY=sk-ant-...
    python examples/run_nist_csf_to_sp800_53.py

    # Options:
    python examples/run_nist_csf_to_sp800_53.py \\
      --model claude-sonnet-4-6 \\
      --skip-unrelated \\
      --min-confidence 0.3
"""
from __future__ import annotations

import argparse
import json
import sys
from datetime import date, datetime, timezone
from pathlib import Path

from nist_strm import FrameworkDocument, FrameworkElement, OLIRGeneralInfo, STRMEngine
from nist_strm.audit import AuditTrail
from nist_strm.ai_mapper import AIMapper, ElementFilter, MappingBatchResult


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
    print(f"  Registered: {doc.title} ({doc.short_name} v{doc.version})")

    elements = []
    for el in data["elements"]:
        element = FrameworkElement(
            id=el["id"],
            document_id=doc_data["id"],
            element_type=el["element_type"],
            identifier=el["identifier"],
            text=el["text"],
            parent_id=el.get("parent_id"),
            metadata=el.get("metadata", {}),
        )
        engine.register_element(element)
        elements.append(element)

    print(f"  Elements: {len(elements)}")
    return elements


def on_progress(current: int, total: int, analysis) -> None:
    if analysis is None:
        print(f"  [{current}/{total}] ERROR")
        return
    m = analysis.mapping
    prov = m.ai_provenance
    conf = prov.ai_confidence_score if prov else 0.0
    print(
        f"  [{current}/{total}] "
        f"{m.concept_pair.focal_element_id} -> {m.concept_pair.reference_element_id}: "
        f"{m.relationship.value} | {m.rationale.value} | "
        f"str={m.strength} conf={conf:.2f} tok={analysis.tokens_used}"
    )


def main() -> None:
    parser = argparse.ArgumentParser(description="NIST CSF 2.0 -> SP 800-53r5 STRM Mapping")
    parser.add_argument("--model", default="claude-sonnet-4-6")
    parser.add_argument("--skip-unrelated", action="store_true")
    parser.add_argument("--min-confidence", type=float, default=0.0)
    parser.add_argument("--output-dir", default="examples/output")
    parser.add_argument("--api-key", default=None)
    parser.add_argument("--focal-types", nargs="*", default=["category"],
                        help="CSF element types to map (function, category, subcategory)")
    parser.add_argument("--ref-types", nargs="*", default=["control"],
                        help="SP 800-53 element types to map (family, control)")
    args = parser.parse_args()

    print("=" * 80)
    print("NIST STRM Library — Canonical NIST Framework Mapping")
    print("CSF 2.0 -> SP 800-53 rev5")
    print("=" * 80)

    engine = STRMEngine()
    trail = AuditTrail()

    print("\n[1/4] Loading canonical NIST elements...")
    examples_dir = Path(__file__).parent
    csf_path = examples_dir / "nist_csf2_elements.json"
    sp53_path = examples_dir / "nist_sp800_53_elements.json"

    if not csf_path.exists() or not sp53_path.exists():
        print("\n  Element files not found. Run convert_oscal.py first:")
        print("    python examples/convert_oscal.py --sp53-families ac at au sc si pm")
        sys.exit(1)

    load_framework(engine, str(csf_path))
    load_framework(engine, str(sp53_path))
    print(f"  Engine: {len(engine.documents)} docs, {len(engine.elements)} elements")

    print(f"\n[2/4] Initializing AIMapper (model={args.model})...")
    focal_filter = ElementFilter(element_types=set(args.focal_types))
    ref_filter = ElementFilter(element_types=set(args.ref_types))

    # Count how many pairs
    focal_count = sum(
        1 for e in engine.elements.values()
        if e.document_id == "nist-csf-2.0" and e.element_type in args.focal_types
    )
    ref_count = sum(
        1 for e in engine.elements.values()
        if e.document_id == "nist-sp800-53r5" and e.element_type in args.ref_types
    )
    print(f"  Focal elements: {focal_count} ({', '.join(args.focal_types)})")
    print(f"  Ref elements:   {ref_count} ({', '.join(args.ref_types)})")
    print(f"  Total pairs:    {focal_count * ref_count}")

    mapper = AIMapper(
        engine,
        model=args.model,
        api_key=args.api_key,
        temperature=0.0,
        audit_trail=trail,
        on_progress=on_progress,
    )

    print(f"\n[3/4] Running STRM mapping...")
    result = mapper.map_frameworks(
        focal_doc_id="nist-csf-2.0",
        reference_doc_id="nist-sp800-53r5",
        focal_filter=focal_filter,
        reference_filter=ref_filter,
        skip_not_related=args.skip_unrelated,
        min_confidence=args.min_confidence,
        auto_add_to_engine=True,
    )

    # Print results
    print("\n" + "=" * 80)
    print("RESULTS")
    print("=" * 80)
    print(f"Model:       {result.model_name}")
    print(f"Pairs:       {result.total_pairs}")
    print(f"Analyzed:    {result.analyzed_pairs}")
    print(f"Mappings:    {len(result.mappings)}")
    print(f"Errors:      {len(result.errors)}")
    print(f"Tokens:      {result.total_tokens:,}")

    stats = engine.statistics()
    print(f"\nRelationship distribution:")
    for rel, count in sorted(stats["relationship_counts"].items()):
        print(f"  {rel}: {count}")

    print(f"\n{'Focal':<16} {'Ref':<12} {'Relationship':<18} {'Rat':<10} {'Str':>3} {'Conf':>5}")
    print("-" * 70)
    for m in result.mappings:
        conf = m.ai_provenance.ai_confidence_score if m.ai_provenance else 0.0
        print(
            f"{m.concept_pair.focal_element_id:<16} "
            f"{m.concept_pair.reference_element_id:<12} "
            f"{m.relationship.value:<18} "
            f"{m.rationale.value:<10} "
            f"{m.strength or 0:>3} "
            f"{conf:>5.2f}"
        )

    # Export
    print(f"\n[4/4] Exporting...")
    out = Path(args.output_dir)
    out.mkdir(parents=True, exist_ok=True)

    engine.export_json(str(out / "csf_to_sp53_cprt.json"))
    print(f"  CPRT JSON:  {out / 'csf_to_sp53_cprt.json'}")

    general_info = OLIRGeneralInfo(
        reference_document="NIST SP 800-53 Revision 5",
        reference_document_short_name="SP 800-53r5",
        reference_document_version="5.1.1",
        reference_document_author="NIST",
        reference_document_url="https://csrc.nist.gov/publications/detail/sp/800-53/rev-5/final",
        reference_document_date="09/23/2020",
        informative_reference_name="CSF 2.0 to SP 800-53r5",
        informative_reference_short_name="CSF2-SP53-STRM",
        informative_reference_version="1.0.0",
        point_of_contact="strm@example.com",
        informative_reference_developer="NIST STRM Library (AI-Assisted)",
        comprehensive="No",
        summary="AI-assisted STRM mapping of NIST CSF 2.0 to SP 800-53r5 using canonical OSCAL sources.",
    )
    submission = engine.create_olir_submission(
        general_info=general_info,
        focal_doc_id="nist-csf-2.0",
        reference_doc_id="nist-sp800-53r5",
    )
    engine.export_olir_json(submission, str(out / "csf_to_sp53_olir.json"))
    print(f"  OLIR JSON:  {out / 'csf_to_sp53_olir.json'}")

    (out / "csf_to_sp53_audit.jsonl").write_text(trail.to_jsonl())
    print(f"  Audit JSONL: {out / 'csf_to_sp53_audit.jsonl'}")

    full = {
        "metadata": {
            "focal": "nist-csf-2.0",
            "reference": "nist-sp800-53r5",
            "model": result.model_name,
            "started_at": result.started_at.isoformat(),
            "completed_at": result.completed_at.isoformat() if result.completed_at else None,
            "total_pairs": result.total_pairs,
            "mappings": len(result.mappings),
            "tokens": result.total_tokens,
        },
        "mappings": [m.model_dump(mode="json") for m in result.mappings],
    }
    with open(out / "csf_to_sp53_full.json", "w") as f:
        json.dump(full, f, indent=2, default=str)
    print(f"  Full JSON:  {out / 'csf_to_sp53_full.json'}")

    print(f"\nAudit trail: {len(trail)} events, chain valid: {trail.verify_chain()}")
    print("\nDONE.")


if __name__ == "__main__":
    main()
