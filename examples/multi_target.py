#!/usr/bin/env python3
"""Enrich multiple targets and find connections between them.

Usage:
    python examples/multi_target.py AAPL MSFT GOOGL
    python examples/multi_target.py AAPL MSFT --track financial --iterations 3
"""

import argparse
import asyncio
import json
import logging

from kg_enrichment.agents.orchestrator import Orchestrator

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(name)s %(levelname)s: %(message)s")


async def main():
    parser = argparse.ArgumentParser(description="Enrich multiple targets")
    parser.add_argument("tickers", nargs="+", help="Stock ticker symbols")
    parser.add_argument("--track", default=None)
    parser.add_argument("--iterations", type=int, default=3)
    parser.add_argument("--output", default=None)
    args = parser.parse_args()

    track = None
    if args.track:
        from kg_enrichment.cli import _get_track
        track = _get_track(args.track)

    orchestrator = Orchestrator(track=track)

    # Seed all tickers
    for ticker in args.tickers:
        await orchestrator.seed_from_ticker(ticker)
        print(f"Seeded: {ticker}")

    # Run enrichment loop (all tickers enriched together)
    report = await orchestrator.run_enrichment_loop(
        max_iterations=args.iterations,
        snapshot_name="multi_" + "_".join(t.lower() for t in args.tickers),
    )

    print(f"\n{'='*60}")
    print(f"Multi-Target Enrichment Report")
    print(f"{'='*60}")
    print(f"Targets:        {', '.join(args.tickers)}")
    print(f"Entities:       {report.entities_total}")
    print(f"Relationships:  {report.relationships_total}")
    print(f"Types:          {list(report.entity_types.keys())}")

    # Find connections between seed entities
    graph = orchestrator.graph
    seed_entities = []
    for ticker in args.tickers:
        matches = graph.find_entities(name=ticker)
        if matches:
            seed_entities.append(matches[0])

    if len(seed_entities) >= 2:
        print(f"\nConnections between targets:")
        for i, e1 in enumerate(seed_entities):
            for e2 in seed_entities[i + 1:]:
                path = graph.shortest_path(e1.id, e2.id)
                if path:
                    path_names = [graph.get_entity(eid).name for eid in path if graph.get_entity(eid)]
                    print(f"  {e1.name} → {e2.name}: {' → '.join(path_names)}")
                else:
                    # Check shared neighbors
                    n1 = set(n.id for n in graph.get_neighbors(e1.id, depth=2))
                    n2 = set(n.id for n in graph.get_neighbors(e2.id, depth=2))
                    shared = n1 & n2
                    if shared:
                        shared_names = [
                            graph.get_entity(eid).name
                            for eid in list(shared)[:5]
                            if graph.get_entity(eid)
                        ]
                        print(f"  {e1.name} & {e2.name} share: {', '.join(shared_names)}")
                    else:
                        print(f"  {e1.name} & {e2.name}: no direct connection found")

    if args.output:
        with open(args.output, "w") as f:
            f.write(orchestrator.graph.to_json())
        print(f"\nGraph exported to {args.output}")


if __name__ == "__main__":
    asyncio.run(main())
