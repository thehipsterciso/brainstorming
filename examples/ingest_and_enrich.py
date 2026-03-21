#!/usr/bin/env python3
"""Ingest a data file and enrich the resulting knowledge graph.

Usage:
    python examples/ingest_and_enrich.py data.csv
    python examples/ingest_and_enrich.py report.json --track compliance
    python examples/ingest_and_enrich.py access.log --iterations 2
"""

import argparse
import asyncio
import logging

from kg_enrichment.agents.orchestrator import Orchestrator

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(name)s %(levelname)s: %(message)s")


async def main():
    parser = argparse.ArgumentParser(description="Ingest file and enrich KG")
    parser.add_argument("file", help="Path to data file (CSV, JSON, JSONL, log, txt, pdf)")
    parser.add_argument("--track", default=None)
    parser.add_argument("--iterations", type=int, default=3)
    parser.add_argument("--output", default=None)
    args = parser.parse_args()

    track = None
    if args.track:
        from kg_enrichment.cli import _get_track
        track = _get_track(args.track)

    orchestrator = Orchestrator(track=track)
    report = await orchestrator.enrich_file(args.file, max_iterations=args.iterations)

    print(f"\nIngested: {args.file}")
    print(f"Entities: {report.entities_total}")
    print(f"Relationships: {report.relationships_total}")
    print(f"Types discovered: {list(report.entity_types.keys())}")

    if args.output:
        with open(args.output, "w") as f:
            f.write(orchestrator.graph.to_json())
        print(f"Graph exported to {args.output}")


if __name__ == "__main__":
    asyncio.run(main())
