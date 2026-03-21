"""Resolution agent — deduplicates, merges, and links entities.

Compares newly added entities against existing graph to find duplicates,
resolve aliases, and merge related records into clean entities.
"""

from __future__ import annotations

import json

import anthropic

from kg_enrichment.agents.base import BaseAgent
from kg_enrichment.agents.tools import GRAPH_TOOLS
from kg_enrichment.core.graph import KnowledgeGraph
from kg_enrichment.providers.registry import ProviderRegistry

RESOLUTION_SYSTEM_PROMPT = """You are an entity resolution agent for a knowledge graph.

Your job is to find and merge duplicate entities in the graph. Two entities are duplicates
if they refer to the same real-world thing, even if they have different names or slightly
different attributes.

## Rules

1. **Search thoroughly** — For each candidate entity, search the graph by name, aliases,
   and key attributes to find potential duplicates.

2. **Be smart about matching** — "Apple Inc.", "Apple", "AAPL", and "Apple Inc" are all
   the same organization. "Tim Cook" and "Timothy D. Cook" are the same person.
   "apple.com" registered to "Apple Inc." confirms a connection.

3. **Merge carefully** — When merging, keep the entity with more data/confidence.
   The merge operation absorbs aliases and attributes from the removed entity.

4. **Don't over-merge** — "Apple Inc." (tech company) and "Apple Records" (record label)
   are NOT the same entity. Use attributes, relationships, and context to distinguish.

5. **Fix relationships** — After merging, verify that relationships still make sense.
   The merge operation automatically redirects relationships.

6. **Report what you did** — Provide a summary of merges performed and why.

Search the graph schema first to understand what types of entities exist, then
systematically check for duplicates within each type.
"""


class ResolutionAgent(BaseAgent):
    """Finds and merges duplicate entities in the knowledge graph."""

    def __init__(
        self,
        client: anthropic.Anthropic,
        graph: KnowledgeGraph,
        providers: ProviderRegistry | None = None,
        model: str = "claude-sonnet-4-6",
    ) -> None:
        super().__init__(
            client=client,
            graph=graph,
            providers=providers,
            model=model,
            system_prompt=RESOLUTION_SYSTEM_PROMPT,
            tools=GRAPH_TOOLS,
        )

    async def resolve_all(self):
        """Scan the entire graph for duplicates and merge them."""
        schema = self.graph.schema_summary()
        prompt = (
            f"The knowledge graph currently has {schema['total_entities']} entities "
            f"across these types: {json.dumps(schema['entity_types'])}.\n\n"
            f"Systematically check for duplicate entities within each type. "
            f"Search for entities with similar names, check aliases, and merge "
            f"any confirmed duplicates. Start with the types that have the most entities."
        )
        return await self.run(prompt)

    async def resolve_candidates(self, entity_ids: list[str]):
        """Check specific entities for duplicates against the existing graph."""
        entities_info = []
        for eid in entity_ids:
            entity = self.graph.get_entity(eid)
            if entity:
                entities_info.append({
                    "id": entity.id,
                    "type": entity.entity_type,
                    "name": entity.name,
                    "aliases": entity.aliases[:5],
                })

        prompt = (
            f"These {len(entities_info)} entities were recently added to the graph. "
            f"Check each one against existing entities to find duplicates:\n\n"
            f"{json.dumps(entities_info, indent=2)}\n\n"
            f"For each entity, search the graph for potential matches and merge "
            f"any confirmed duplicates."
        )
        return await self.run(prompt)
