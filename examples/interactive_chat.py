#!/usr/bin/env python3
"""Interactive chat-based knowledge graph enrichment.

Start a session, ask questions, and the agent will enrich the graph on the fly.

Usage:
    python examples/interactive_chat.py
    python examples/interactive_chat.py --track security
    python examples/interactive_chat.py --load aapl  # Load existing snapshot
"""

import argparse
import asyncio
import json
import logging

from kg_enrichment.agents.orchestrator import Orchestrator
from kg_enrichment.core.store import GraphStore

logging.basicConfig(level=logging.WARNING)


async def main():
    parser = argparse.ArgumentParser(description="Interactive KG enrichment chat")
    parser.add_argument("--track", default=None)
    parser.add_argument("--load", default=None, help="Load existing graph snapshot")
    args = parser.parse_args()

    track = None
    if args.track:
        from kg_enrichment.cli import _get_track
        track = _get_track(args.track)

    orchestrator = Orchestrator(track=track)

    if args.load:
        try:
            orchestrator.graph = orchestrator.store.load(args.load)
            stats = orchestrator.graph.stats()
            print(f"Loaded graph '{args.load}': {stats['entities']} entities, "
                  f"{stats['relationships']} relationships")
        except FileNotFoundError:
            print(f"No snapshot '{args.load}' found, starting fresh.")

    print("KG Enrichment Chat — Type 'quit' to exit")
    print("Commands: 'stats', 'schema', 'export <format> <path>', 'enrich <ticker>'")
    print()

    while True:
        try:
            user_input = input("You> ").strip()
        except (EOFError, KeyboardInterrupt):
            break

        if not user_input:
            continue
        if user_input.lower() in ("quit", "exit", "q"):
            break
        if user_input.lower() == "stats":
            print(json.dumps(orchestrator.graph.stats(), indent=2))
            continue
        if user_input.lower() == "schema":
            print(json.dumps(orchestrator.graph.schema_summary(), indent=2))
            continue
        if user_input.lower().startswith("enrich "):
            ticker = user_input.split(maxsplit=1)[1].strip().upper()
            print(f"Starting enrichment for {ticker}...")
            report = await orchestrator.enrich_ticker(ticker, max_iterations=3)
            print(f"Done: {report.entities_total} entities, "
                  f"{report.relationships_total} relationships")
            continue

        response = await orchestrator.chat(user_input)
        print(f"\nAgent> {response}\n")

    print("\nSession ended.")


if __name__ == "__main__":
    asyncio.run(main())
