"""Extraction agent — identifies entities and relationships from raw data.

No type constraints. The agent discovers whatever entity and relationship types
are present in the data. Uses Claude's understanding to extract structured
knowledge from unstructured or semi-structured input.
"""

from __future__ import annotations

import anthropic

from kg_enrichment.agents.base import BaseAgent
from kg_enrichment.agents.tools import ENRICHMENT_TOOLS, GRAPH_TOOLS
from kg_enrichment.core.graph import KnowledgeGraph
from kg_enrichment.providers.registry import ProviderRegistry

EXTRACTION_SYSTEM_PROMPT = """You are an entity and relationship extraction agent for a knowledge graph.

Your job is to extract ALL entities and relationships from the provided data and add them
to the knowledge graph using the available tools.

## Rules

1. **Be exhaustive** — Extract every entity you can identify. Organizations, people, locations,
   domains, IP addresses, products, software, regulations, events, financial instruments,
   vulnerabilities, dates, amounts — anything that is a distinct named thing.

2. **Types are free-form** — Use whatever entity type best describes the thing. Common types
   include: organization, person, location, domain, ip_address, software, vulnerability,
   filing, financial_instrument, regulation, event, sector, industry, product, service,
   country, state, city, email, phone, certificate, hash, url. But you can create new types
   as needed.

3. **Extract relationships** — For every pair of related entities, create a relationship.
   Relationship types are also free-form. Common ones: subsidiary_of, employs, officer_of,
   located_in, owns_domain, resolves_to, filed, regulates, affects, competes_with,
   supplies_to, acquired, invested_in, partner_of. Create new types as needed.

4. **Check existing graph first** — Before adding an entity, search the graph to see if it
   already exists. If it does, use the existing entity ID for relationships.

5. **Set confidence scores** — Use lower confidence (0.5-0.8) for inferred or uncertain
   entities, higher (0.9-1.0) for explicitly stated ones.

6. **Include attributes** — Add all available attributes to entities (titles, amounts, dates,
   descriptions, identifiers, etc.). More data is always better.

7. **Mark important entities for follow-up** — If you identify entities that seem important
   and could benefit from further enrichment, queue them using queue_enrichment.

When you're done extracting, provide a brief summary of what you found.
"""


class ExtractionAgent(BaseAgent):
    """Extracts entities and relationships from raw data using Claude."""

    def __init__(
        self,
        client: anthropic.Anthropic,
        graph: KnowledgeGraph,
        providers: ProviderRegistry | None = None,
        model: str = "claude-sonnet-4-6",
        additional_instructions: str = "",
    ) -> None:
        system = EXTRACTION_SYSTEM_PROMPT
        if additional_instructions:
            system += f"\n\n## Additional Instructions\n{additional_instructions}"

        enrichment_subset = [
            t for t in ENRICHMENT_TOOLS
            if t["name"] in ("queue_enrichment", "mark_enriched")
        ]
        super().__init__(
            client=client,
            graph=graph,
            providers=providers,
            model=model,
            system_prompt=system,
            tools=GRAPH_TOOLS + enrichment_subset,
        )

    async def extract_from_text(self, text: str, source: str = "user_input"):
        """Extract entities and relationships from free text."""
        prompt = (
            f"Extract all entities and relationships from the following data. "
            f"Source: {source}\n\n---\n\n{text[:15000]}"
        )
        return await self.run(prompt)

    async def extract_from_records(
        self, records: list[dict], source: str = "data_source"
    ):
        """Extract entities and relationships from structured records."""
        import json
        data_str = json.dumps(records[:100], indent=2, default=str)
        prompt = (
            f"Extract all entities and relationships from these {len(records)} records "
            f"(showing first 100). Source: {source}\n\n---\n\n{data_str}"
        )
        return await self.run(prompt)
