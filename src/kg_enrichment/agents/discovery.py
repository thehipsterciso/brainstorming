"""Discovery agent — decides what to enrich next.

The brain of autonomous enrichment. Given the current graph state and track
priorities, decides which unenriched entities to pursue and which providers
to query. Generates enrichment tasks for the orchestrator.
"""

from __future__ import annotations

import json

import anthropic

from kg_enrichment.agents.base import BaseAgent
from kg_enrichment.agents.tools import ALL_TOOLS
from kg_enrichment.core.graph import KnowledgeGraph
from kg_enrichment.providers.registry import ProviderRegistry

DISCOVERY_SYSTEM_PROMPT = """You are a discovery agent for a knowledge graph enrichment system.

Your job is to analyze the current state of the knowledge graph and decide what should
be enriched next. You have access to the full graph and all available data providers.

## Your Process

1. **Assess the graph** — Look at the schema, unenriched entities, and overall coverage.
2. **Identify gaps** — Which entities have sparse attributes? Which areas of the graph
   are thin? What connections are missing?
3. **Prioritize** — Decide which entities to enrich next based on:
   - Importance (central entities, hubs with many connections)
   - Data availability (which providers can help?)
   - Depth (how far from the seed entity? Closer = higher priority)
   - Type (based on the active track's priorities, if any)
4. **Query providers** — For high-priority entities, directly query the appropriate
   providers to enrich them.
5. **Queue follow-ups** — For lower-priority entities, queue them for future iterations.

## Key Principles

- **Be greedy** — If data is available, get it. Don't skip entities because they seem
  unimportant. Everything connects.
- **Follow the threads** — When enrichment reveals new entities (subsidiaries, officers,
  domains, etc.), those become candidates for the next round.
- **Use the right provider** — Match entities to providers that can help:
  - Organizations → sec_edgar, yfinance, github, news_feeds
  - Domains → dns_whois, web_scraper
  - Software → cve_provider, github
  - People → sec_edgar, github, news_feeds
  - Any entity → web_scraper, news_feeds (for general web intelligence)
- **Know when to stop** — Mark entities as enriched when you've queried all relevant
  providers and there's nothing more to find.

When you're done, summarize what you enriched and what's queued for next time.
"""


class DiscoveryAgent(BaseAgent):
    """Decides what to enrich next and drives the enrichment forward."""

    def __init__(
        self,
        client: anthropic.Anthropic,
        graph: KnowledgeGraph,
        providers: ProviderRegistry | None = None,
        model: str = "claude-sonnet-4-6",
        track_prompt: str = "",
    ) -> None:
        system = DISCOVERY_SYSTEM_PROMPT
        if track_prompt:
            system += f"\n\n## Active Track Priorities\n{track_prompt}"

        super().__init__(
            client=client,
            graph=graph,
            providers=providers,
            model=model,
            system_prompt=system,
            tools=ALL_TOOLS,
        )

    async def discover_and_enrich(self, focus: str | None = None):
        """Run a discovery cycle — find gaps and enrich."""
        schema = self.graph.schema_summary()
        unenriched = self.graph.unenriched_entities()

        prompt_parts = [
            f"The knowledge graph has {schema['total_entities']} entities and "
            f"{schema['total_relationships']} relationships.",
            f"Entity types: {json.dumps(schema['entity_types'])}",
            f"Relationship types: {json.dumps(schema['relationship_types'])}",
            f"Unenriched entities: {len(unenriched)}",
        ]

        if unenriched:
            sample = [
                {
                    "id": e.id,
                    "type": e.entity_type,
                    "name": e.name,
                    "depth": e.enrichment_depth,
                    "attributes_count": len(e.attributes),
                }
                for e in sorted(unenriched, key=lambda x: x.enrichment_depth)[:30]
            ]
            prompt_parts.append(
                f"\nUnenriched entities (sorted by depth from seed):\n"
                f"{json.dumps(sample, indent=2)}"
            )

        if focus:
            prompt_parts.append(f"\nFocus area: {focus}")

        prompt_parts.append(
            "\nAnalyze the graph state, then query providers to enrich the highest-priority "
            "unenriched entities. Use list_providers to see what's available, then "
            "query_provider for each entity/provider combination that makes sense."
        )

        return await self.run("\n".join(prompt_parts), max_turns=40)
