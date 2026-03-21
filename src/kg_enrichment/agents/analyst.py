"""Analyst agent — answers questions, synthesizes findings, and generates reports.

Also handles interactive chat mode where users ask questions and the agent
enriches the graph on the fly to answer them.
"""

from __future__ import annotations

import json

import anthropic

from kg_enrichment.agents.base import BaseAgent
from kg_enrichment.agents.tools import ALL_TOOLS
from kg_enrichment.core.graph import KnowledgeGraph
from kg_enrichment.providers.registry import ProviderRegistry

ANALYST_SYSTEM_PROMPT = """You are an analyst agent for a knowledge graph enrichment system.

You help users understand the knowledge graph, answer questions, and generate insights.
You can also enrich the graph on the fly if you need more data to answer a question.

## Capabilities

1. **Answer questions** — Query the graph to answer user questions about entities,
   relationships, patterns, and risks.

2. **Enrich on demand** — If the graph doesn't have enough data to answer a question,
   use providers to fetch more data, add it to the graph, and then answer.

3. **Generate insights** — Look for patterns, connections, anomalies, and risks in
   the graph data. Cross-reference entities, trace relationship chains, identify
   clusters.

4. **Synthesize reports** — When asked for a report, pull together relevant entities
   and relationships into a coherent narrative.

## Interaction Style

- Be direct and data-driven. Cite specific entities and relationships from the graph.
- When you enrich the graph to answer a question, mention what new data you found.
- If you can't find something, say so and suggest what data sources might help.
- Always search the graph before enriching — the data might already be there.
"""


class AnalystAgent(BaseAgent):
    """Answers questions and generates insights from the knowledge graph."""

    def __init__(
        self,
        client: anthropic.Anthropic,
        graph: KnowledgeGraph,
        providers: ProviderRegistry | None = None,
        model: str = "claude-sonnet-4-6",
        track_prompt: str = "",
    ) -> None:
        system = ANALYST_SYSTEM_PROMPT
        if track_prompt:
            system += f"\n\n## Analyst Focus\n{track_prompt}"

        super().__init__(
            client=client,
            graph=graph,
            providers=providers,
            model=model,
            system_prompt=system,
            tools=ALL_TOOLS,
        )

    async def ask(self, question: str):
        """Answer a question about the knowledge graph."""
        schema = self.graph.schema_summary()
        prompt = (
            f"Graph state: {schema['total_entities']} entities, "
            f"{schema['total_relationships']} relationships, "
            f"types: {json.dumps(schema['entity_types'])}\n\n"
            f"User question: {question}\n\n"
            f"Search the graph to answer this question. If the graph doesn't have "
            f"enough data, use providers to enrich it, then answer."
        )
        return await self.run(prompt, max_turns=30)

    async def generate_report(self, topic: str):
        """Generate an analytical report on a topic."""
        schema = self.graph.schema_summary()
        prompt = (
            f"Generate a comprehensive analytical report on: {topic}\n\n"
            f"Graph state: {schema['total_entities']} entities, "
            f"{schema['total_relationships']} relationships.\n\n"
            f"Search the graph for all relevant entities and relationships. "
            f"Synthesize the data into a structured report covering:\n"
            f"- Key entities and their attributes\n"
            f"- Important relationships and patterns\n"
            f"- Risk indicators or anomalies\n"
            f"- Data gaps and recommendations for further enrichment\n\n"
            f"If you need more data, enrich the graph first."
        )
        return await self.run(prompt, max_turns=30)
