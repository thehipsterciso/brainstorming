"""Tests for the extraction agent (unit tests with mocked Claude API)."""

import json
from unittest.mock import MagicMock, AsyncMock, patch

import pytest

from kg_enrichment.agents.extraction import ExtractionAgent
from kg_enrichment.core.graph import KnowledgeGraph


class TestExtractionAgent:
    def test_init(self):
        client = MagicMock()
        graph = KnowledgeGraph()
        agent = ExtractionAgent(client=client, graph=graph)
        assert agent.system_prompt  # Has a system prompt
        assert "exhaustive" in agent.system_prompt.lower()

    def test_tools_include_graph_operations(self):
        client = MagicMock()
        graph = KnowledgeGraph()
        agent = ExtractionAgent(client=client, graph=graph)

        tool_names = [t["name"] for t in agent.tools]
        assert "add_entity" in tool_names
        assert "add_relationship" in tool_names
        assert "search_graph" in tool_names

    def test_additional_instructions(self):
        client = MagicMock()
        graph = KnowledgeGraph()
        agent = ExtractionAgent(
            client=client, graph=graph,
            additional_instructions="Focus on financial data",
        )
        assert "financial data" in agent.system_prompt


class TestAgentToolExecution:
    """Test tool execution logic directly (without Claude API)."""

    def test_add_entity_tool(self):
        client = MagicMock()
        graph = KnowledgeGraph()
        agent = ExtractionAgent(client=client, graph=graph)

        from kg_enrichment.core.models import AgentResult
        result = AgentResult()
        output = agent._tool_add_entity(
            {"entity_type": "organization", "name": "Test Corp", "attributes": {"sector": "Tech"}},
            result,
        )
        parsed = json.loads(output)
        assert parsed["name"] == "Test Corp"
        assert len(result.entities_added) == 1
        assert len(graph) == 1

    def test_search_graph_tool(self):
        client = MagicMock()
        graph = KnowledgeGraph()
        from kg_enrichment.core.models import Entity
        graph.add_entity(Entity(entity_type="org", name="Apple Inc."))

        agent = ExtractionAgent(client=client, graph=graph)
        output = agent._tool_search_graph({"query": "Apple"})
        parsed = json.loads(output)
        assert len(parsed) == 1
        assert parsed[0]["name"] == "Apple Inc."

    def test_get_graph_schema_tool(self):
        client = MagicMock()
        graph = KnowledgeGraph()
        from kg_enrichment.core.models import Entity
        graph.add_entity(Entity(entity_type="org", name="A"))
        graph.add_entity(Entity(entity_type="person", name="B"))

        agent = ExtractionAgent(client=client, graph=graph)
        output = agent._tool_get_graph_schema()
        parsed = json.loads(output)
        assert parsed["total_entities"] == 2
        assert "org" in parsed["entity_types"]
        assert "person" in parsed["entity_types"]
