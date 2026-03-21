"""Base agent — Claude SDK wrapper with tool_use for knowledge graph operations."""

from __future__ import annotations

import json
import logging
from typing import Any

import anthropic

from kg_enrichment.agents.tools import ALL_TOOLS
from kg_enrichment.core.graph import KnowledgeGraph
from kg_enrichment.core.models import (
    AgentResult,
    Entity,
    EnrichmentTask,
    Relationship,
    _now,
)
from kg_enrichment.providers.registry import ProviderRegistry

logger = logging.getLogger(__name__)


class BaseAgent:
    """Claude-powered agent with tool_use for knowledge graph operations.

    Subclasses specialize the system prompt and tool set for specific tasks
    (extraction, resolution, discovery, analysis).
    """

    def __init__(
        self,
        client: anthropic.Anthropic,
        graph: KnowledgeGraph,
        providers: ProviderRegistry | None = None,
        model: str = "claude-sonnet-4-6",
        system_prompt: str = "",
        tools: list[dict] | None = None,
    ) -> None:
        self.client = client
        self.graph = graph
        self.providers = providers or ProviderRegistry(auto_discover=False)
        self.model = model
        self.system_prompt = system_prompt
        self.tools = tools or ALL_TOOLS
        self._enrichment_queue: list[EnrichmentTask] = []

    async def run(self, prompt: str, max_turns: int = 25) -> AgentResult:
        """Run the agent with a prompt. Handles tool_use loop automatically."""
        result = AgentResult()
        messages: list[dict[str, Any]] = [{"role": "user", "content": prompt}]

        for turn in range(max_turns):
            try:
                response = self.client.messages.create(
                    model=self.model,
                    max_tokens=4096,
                    system=self.system_prompt,
                    tools=self.tools,
                    messages=messages,
                )
            except Exception as e:
                logger.error(f"Claude API error: {e}")
                result.messages.append(f"API error: {e}")
                break

            # Process response content blocks
            assistant_content: list[dict[str, Any]] = []
            tool_results: list[dict[str, Any]] = []

            for block in response.content:
                if block.type == "text":
                    result.raw_response += block.text
                    result.messages.append(block.text)
                    assistant_content.append({"type": "text", "text": block.text})

                elif block.type == "tool_use":
                    assistant_content.append({
                        "type": "tool_use",
                        "id": block.id,
                        "name": block.name,
                        "input": block.input,
                    })

                    # Execute the tool
                    tool_output = await self._handle_tool_call(
                        block.name, block.input, result
                    )
                    tool_results.append({
                        "type": "tool_result",
                        "tool_use_id": block.id,
                        "content": tool_output,
                    })

            messages.append({"role": "assistant", "content": assistant_content})

            if tool_results:
                messages.append({"role": "user", "content": tool_results})

            # Stop if no tool calls (agent is done)
            if response.stop_reason == "end_turn":
                break

        result.tasks_generated = self._enrichment_queue
        return result

    async def _handle_tool_call(
        self, tool_name: str, tool_input: dict[str, Any], result: AgentResult
    ) -> str:
        """Execute a tool call and return the result as a string."""
        try:
            if tool_name == "add_entity":
                return self._tool_add_entity(tool_input, result)
            elif tool_name == "add_relationship":
                return self._tool_add_relationship(tool_input, result)
            elif tool_name == "search_graph":
                return self._tool_search_graph(tool_input)
            elif tool_name == "get_entity_details":
                return self._tool_get_entity_details(tool_input)
            elif tool_name == "merge_entities":
                return self._tool_merge_entities(tool_input, result)
            elif tool_name == "get_graph_schema":
                return self._tool_get_graph_schema()
            elif tool_name == "query_provider":
                return await self._tool_query_provider(tool_input, result)
            elif tool_name == "list_providers":
                return self._tool_list_providers()
            elif tool_name == "queue_enrichment":
                return self._tool_queue_enrichment(tool_input)
            elif tool_name == "mark_enriched":
                return self._tool_mark_enriched(tool_input)
            elif tool_name == "get_enrichment_queue":
                return self._tool_get_enrichment_queue(tool_input)
            elif tool_name == "fetch_url":
                return await self._tool_fetch_url(tool_input)
            else:
                return json.dumps({"error": f"Unknown tool: {tool_name}"})
        except Exception as e:
            logger.error(f"Tool execution error ({tool_name}): {e}")
            return json.dumps({"error": str(e)})

    # ── Tool implementations ────────────────────────────────────────

    def _tool_add_entity(self, inp: dict, result: AgentResult) -> str:
        entity = Entity(
            entity_type=inp["entity_type"],
            name=inp["name"],
            aliases=inp.get("aliases", []),
            attributes=inp.get("attributes", {}),
            confidence=inp.get("confidence", 1.0),
            sources=["agent"],
        )
        entity_id = self.graph.add_entity(entity)
        result.entities_added.append(entity_id)
        return json.dumps({"entity_id": entity_id, "name": entity.name})

    def _tool_add_relationship(self, inp: dict, result: AgentResult) -> str:
        rel = Relationship(
            rel_type=inp["rel_type"],
            source_entity_id=inp["source_entity_id"],
            target_entity_id=inp["target_entity_id"],
            attributes=inp.get("attributes", {}),
            confidence=inp.get("confidence", 1.0),
            sources=["agent"],
        )
        rel_id = self.graph.add_relationship(rel)
        result.relationships_added.append(rel_id)
        return json.dumps({"relationship_id": rel_id})

    def _tool_search_graph(self, inp: dict) -> str:
        query = inp["query"]
        entity_type = inp.get("entity_type")
        entities = self.graph.find_entities(entity_type=entity_type, name=query)
        if not entities:
            entities = self.graph.search(query)
        return json.dumps([
            {
                "id": e.id,
                "entity_type": e.entity_type,
                "name": e.name,
                "aliases": e.aliases[:5],
                "enriched": e.enriched,
                "attributes_summary": {
                    k: str(v)[:100] for k, v in list(e.attributes.items())[:10]
                },
            }
            for e in entities[:20]
        ])

    def _tool_get_entity_details(self, inp: dict) -> str:
        entity = self.graph.get_entity(inp["entity_id"])
        if not entity:
            return json.dumps({"error": "Entity not found"})
        rels = self.graph.get_relationships(entity.id)
        neighbors = self.graph.get_neighbors(entity.id)
        return json.dumps({
            "entity": {
                "id": entity.id,
                "entity_type": entity.entity_type,
                "name": entity.name,
                "aliases": entity.aliases,
                "attributes": {k: str(v)[:200] for k, v in entity.attributes.items()},
                "confidence": entity.confidence,
                "sources": entity.sources,
                "enriched": entity.enriched,
                "enrichment_depth": entity.enrichment_depth,
            },
            "relationships": [
                {
                    "id": r.id,
                    "rel_type": r.rel_type,
                    "source": r.source_entity_id,
                    "target": r.target_entity_id,
                }
                for r in rels[:30]
            ],
            "neighbors": [
                {"id": n.id, "type": n.entity_type, "name": n.name}
                for n in neighbors[:20]
            ],
        })

    def _tool_merge_entities(self, inp: dict, result: AgentResult) -> str:
        merged = self.graph.merge_entities(inp["keep_id"], inp["remove_id"])
        result.entities_merged.append((inp["keep_id"], inp["remove_id"]))
        return json.dumps({
            "merged_id": merged.id,
            "name": merged.name,
            "aliases": merged.aliases,
        })

    def _tool_get_graph_schema(self) -> str:
        return json.dumps(self.graph.schema_summary())

    async def _tool_query_provider(self, inp: dict, result: AgentResult) -> str:
        provider_name = inp["provider_name"]
        entity_id = inp["entity_id"]

        provider = self.providers.get_by_name(provider_name)
        if not provider:
            return json.dumps({"error": f"Provider '{provider_name}' not found"})

        entity = self.graph.get_entity(entity_id)
        if not entity:
            return json.dumps({"error": f"Entity '{entity_id}' not found"})

        provider_result = await provider.enrich(entity, self.graph)

        # Add suggested entities and relationships to graph
        entity_id_map: dict[str, str] = {}
        for suggested in provider_result.suggested_entities:
            # Check for existing duplicates
            existing = self.graph.find_entities(
                entity_type=suggested.entity_type, name=suggested.name
            )
            if existing:
                entity_id_map[suggested.id] = existing[0].id
                existing[0].merge_from(suggested)
            else:
                new_id = self.graph.add_entity(suggested)
                entity_id_map[suggested.id] = new_id
                result.entities_added.append(new_id)

        for rel in provider_result.suggested_relationships:
            # Remap entity IDs
            rel.source_entity_id = entity_id_map.get(
                rel.source_entity_id, rel.source_entity_id
            )
            rel.target_entity_id = entity_id_map.get(
                rel.target_entity_id, rel.target_entity_id
            )
            if (
                rel.source_entity_id in self.graph
                and rel.target_entity_id in self.graph
            ):
                try:
                    rel_id = self.graph.add_relationship(rel)
                    result.relationships_added.append(rel_id)
                except ValueError:
                    pass

        for task in provider_result.follow_up_tasks:
            task.entity_id = entity_id_map.get(task.entity_id, task.entity_id)
            self._enrichment_queue.append(task)

        return json.dumps({
            "provider": provider_name,
            "entities_added": len(provider_result.suggested_entities),
            "relationships_added": len(provider_result.suggested_relationships),
            "follow_up_tasks": len(provider_result.follow_up_tasks),
            "raw_records": len(provider_result.raw_data),
            "errors": provider_result.errors,
        })

    def _tool_list_providers(self) -> str:
        return json.dumps([
            {
                "name": p.name,
                "description": p.description,
                "entity_types": p.supported_entity_types,
                "requires_api_key": p.requires_api_key,
            }
            for p in self.providers.get_all()
        ])

    def _tool_queue_enrichment(self, inp: dict) -> str:
        task = EnrichmentTask(
            entity_id=inp["entity_id"],
            provider_hints=inp.get("provider_hints", []),
            priority=inp.get("priority", 1.0),
        )
        self._enrichment_queue.append(task)
        return json.dumps({"queued": True, "task_id": task.id})

    def _tool_mark_enriched(self, inp: dict) -> str:
        self.graph.mark_enriched(inp["entity_id"])
        return json.dumps({"marked": True})

    def _tool_get_enrichment_queue(self, inp: dict) -> str:
        limit = inp.get("limit", 20)
        unenriched = self.graph.unenriched_entities()
        return json.dumps([
            {
                "id": e.id,
                "entity_type": e.entity_type,
                "name": e.name,
                "enrichment_depth": e.enrichment_depth,
            }
            for e in unenriched[:limit]
        ])

    async def _tool_fetch_url(self, inp: dict) -> str:
        url = inp["url"]
        try:
            from kg_enrichment.providers.web_scraper import WebScraperProvider
            scraper = WebScraperProvider()
            data = await scraper.fetch_url(url)
            return json.dumps(data)
        except Exception as e:
            return json.dumps({"error": str(e)})
