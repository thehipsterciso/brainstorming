#!/usr/bin/env python3
"""Enrich a knowledge graph from a stock ticker symbol.

Usage:
    python examples/enrich_ticker.py AAPL
    python examples/enrich_ticker.py AAPL --track security
    python examples/enrich_ticker.py MSFT --iterations 10
"""

import argparse
import asyncio
import json
import logging

from kg_enrichment.agents.orchestrator import Orchestrator
from kg_enrichment.tracks.financial import FinancialAnalystTrack
from kg_enrichment.tracks.security import SecurityAnalystTrack
from kg_enrichment.tracks.compliance import ComplianceOfficerTrack
from kg_enrichment.tracks.threat_intel import ThreatIntelTrack
from kg_enrichment.tracks.executive import ExecutiveTrack

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(name)s %(levelname)s: %(message)s")

TRACKS = {
    "financial": FinancialAnalystTrack,
    "security": SecurityAnalystTrack,
    "compliance": ComplianceOfficerTrack,
    "threat_intel": ThreatIntelTrack,
    "executive": ExecutiveTrack,
}


async def main():
    parser = argparse.ArgumentParser(description="Enrich KG from stock ticker")
    parser.add_argument("ticker", help="Stock ticker symbol (e.g., AAPL, MSFT)")
    parser.add_argument("--track", choices=list(TRACKS.keys()), default=None)
    parser.add_argument("--iterations", type=int, default=5)
    parser.add_argument("--output", default=None, help="Export graph to JSON file")
    args = parser.parse_args()

    track = TRACKS[args.track]() if args.track else None

    orchestrator = Orchestrator(track=track)
    report = await orchestrator.enrich_ticker(args.ticker, max_iterations=args.iterations)

    print(f"\n{'='*60}")
    print(f"Enrichment Report: {args.ticker}")
    print(f"{'='*60}")
    print(f"Track:          {report.track or 'none'}")
    print(f"Iterations:     {report.iterations}")
    print(f"Duration:       {report.duration_seconds:.1f}s")
    print(f"Entities:       {report.entities_total}")
    print(f"Relationships:  {report.relationships_total}")
    print(f"\nEntity types:")
    for etype, count in sorted(report.entity_types.items(), key=lambda x: -x[1]):
        print(f"  {etype}: {count}")
    print(f"\nRelationship types:")
    for rtype, count in sorted(report.relationship_types.items(), key=lambda x: -x[1]):
        print(f"  {rtype}: {count}")

    if args.output:
        with open(args.output, "w") as f:
            f.write(orchestrator.graph.to_json())
        print(f"\nGraph exported to {args.output}")


if __name__ == "__main__":
    asyncio.run(main())
