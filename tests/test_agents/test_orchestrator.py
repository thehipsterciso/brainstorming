"""Tests for the orchestrator (unit tests without live API calls)."""

from unittest.mock import MagicMock

import pytest

from kg_enrichment.agents.orchestrator import Orchestrator
from kg_enrichment.core.graph import KnowledgeGraph
from kg_enrichment.providers.registry import ProviderRegistry


class TestOrchestratorInit:
    def test_default_init(self):
        client = MagicMock()
        orchestrator = Orchestrator(client=client)
        assert orchestrator.graph is not None
        assert orchestrator.providers is not None

    def test_init_with_track(self):
        from kg_enrichment.tracks.financial import FinancialAnalystTrack

        client = MagicMock()
        track = FinancialAnalystTrack()
        orchestrator = Orchestrator(client=client, track=track)
        assert orchestrator.track.name == "financial"


class TestSeeding:
    @pytest.mark.asyncio
    async def test_seed_from_ticker(self):
        client = MagicMock()
        orchestrator = Orchestrator(client=client)
        entity = await orchestrator.seed_from_ticker("AAPL")

        assert entity.name == "AAPL"
        assert entity.entity_type == "organization"
        assert entity.attributes["ticker"] == "AAPL"
        assert len(orchestrator.graph) == 1

    @pytest.mark.asyncio
    async def test_seed_multiple_tickers(self):
        client = MagicMock()
        orchestrator = Orchestrator(client=client)
        await orchestrator.seed_from_ticker("AAPL")
        await orchestrator.seed_from_ticker("MSFT")

        assert len(orchestrator.graph) == 2
