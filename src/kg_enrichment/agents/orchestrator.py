"""Orchestrator — runs the autonomous enrichment loop.

Coordinates extraction, resolution, and discovery agents in a recursive loop:
1. Seed the graph (from ticker, file, or text)
2. Extract entities and relationships
3. Resolve duplicates
4. Discover what to enrich next
5. Repeat until exhausted or max iterations reached
"""

from __future__ import annotations

import logging
import time
from typing import Any

import anthropic

from kg_enrichment.agents.analyst import AnalystAgent
from kg_enrichment.agents.discovery import DiscoveryAgent
from kg_enrichment.agents.extraction import ExtractionAgent
from kg_enrichment.agents.resolution import ResolutionAgent
from kg_enrichment.core.graph import KnowledgeGraph
from kg_enrichment.core.models import Entity, EnrichmentReport, EnrichmentTask
from kg_enrichment.core.store import GraphStore
from kg_enrichment.providers.custom_file import CustomFileProvider
from kg_enrichment.providers.registry import ProviderRegistry
from kg_enrichment.tracks.base import BaseTrack

logger = logging.getLogger(__name__)


class Orchestrator:
    """Runs the autonomous enrichment loop.

    Coordinates agents and providers to recursively enrich a knowledge graph
    starting from a seed (ticker, file, or text).
    """

    def __init__(
        self,
        client: anthropic.Anthropic | None = None,
        graph: KnowledgeGraph | None = None,
        providers: ProviderRegistry | None = None,
        track: BaseTrack | None = None,
        model: str = "claude-sonnet-4-6",
        store_dir: str = "./kg_data",
    ) -> None:
        self.client = client or anthropic.Anthropic()
        self.graph = graph or KnowledgeGraph()
        self.providers = providers or ProviderRegistry()
        self.track = track
        self.model = model
        self.store = GraphStore(store_dir)
        self._task_queue: list[EnrichmentTask] = []

        track_prompt = track.get_system_prompt_addition() if track else ""

        self.extraction_agent = ExtractionAgent(
            client=self.client,
            graph=self.graph,
            providers=self.providers,
            model=model,
            additional_instructions=track_prompt,
        )
        self.resolution_agent = ResolutionAgent(
            client=self.client,
            graph=self.graph,
            providers=self.providers,
            model=model,
        )
        self.discovery_agent = DiscoveryAgent(
            client=self.client,
            graph=self.graph,
            providers=self.providers,
            model=model,
            track_prompt=track_prompt,
        )
        self.analyst_agent = AnalystAgent(
            client=self.client,
            graph=self.graph,
            providers=self.providers,
            model=model,
            track_prompt=track_prompt,
        )

    # ── Seeding ────────────────────────────────────────────────────────

    async def seed_from_ticker(self, ticker: str) -> Entity:
        """Create initial entities from a stock ticker symbol."""
        ticker = ticker.upper().strip()
        entity = Entity(
            entity_type="organization",
            name=ticker,
            aliases=[ticker],
            attributes={"ticker": ticker, "symbol": ticker},
            sources=["user_input"],
            enrichment_depth=0,
        )
        self.graph.add_entity(entity)
        logger.info(f"Seeded graph with ticker entity: {ticker} ({entity.id})")
        return entity

    async def seed_from_file(self, file_path: str) -> list[dict[str, Any]]:
        """Ingest a file and extract entities from it."""
        file_provider = CustomFileProvider()
        result = await file_provider.ingest_file(file_path)

        if result.errors:
            logger.error(f"File ingestion errors: {result.errors}")
            return result.raw_data

        # Use extraction agent to find entities in the data
        if result.raw_data:
            extract_result = await self.extraction_agent.extract_from_records(
                result.raw_data, source=file_path
            )
            logger.info(
                f"Extracted {len(extract_result.entities_added)} entities from {file_path}"
            )

        return result.raw_data

    async def seed_from_text(self, text: str, source: str = "user_input") -> None:
        """Extract entities from free text."""
        result = await self.extraction_agent.extract_from_text(text, source=source)
        logger.info(f"Extracted {len(result.entities_added)} entities from text")

    # ── Enrichment loop ────────────────────────────────────────────────

    async def run_enrichment_loop(
        self,
        max_iterations: int | None = 5,
        save_interval: int = 1,
        snapshot_name: str = "enrichment",
    ) -> EnrichmentReport:
        """Run the autonomous enrichment loop.

        Each iteration:
        1. Discovery agent identifies what to enrich
        2. Providers fetch data
        3. Extraction agent processes raw data
        4. Resolution agent deduplicates
        5. New entities enter the queue for next iteration
        """
        start_time = time.time()
        report = EnrichmentReport(
            seed=snapshot_name,
            track=self.track.name if self.track else None,
        )
        iteration = 0

        while True:
            if max_iterations is not None and iteration >= max_iterations:
                logger.info(f"Reached max iterations ({max_iterations})")
                break

            unenriched = self.graph.unenriched_entities()
            if not unenriched:
                logger.info("No more unenriched entities. Enrichment complete.")
                break

            iteration += 1
            logger.info(
                f"=== Enrichment iteration {iteration} "
                f"({len(unenriched)} unenriched entities) ==="
            )

            # Discovery + enrichment
            discovery_result = await self.discovery_agent.discover_and_enrich()

            # Collect new entity IDs for resolution
            new_entity_ids = discovery_result.entities_added
            if new_entity_ids:
                logger.info(f"Discovery added {len(new_entity_ids)} new entities")

            # Resolution — deduplicate new entities
            if new_entity_ids and len(new_entity_ids) > 1:
                resolution_result = await self.resolution_agent.resolve_candidates(
                    new_entity_ids
                )
                if resolution_result.entities_merged:
                    logger.info(
                        f"Resolution merged {len(resolution_result.entities_merged)} "
                        f"duplicate pairs"
                    )

            # Process any follow-up tasks from providers
            for task in discovery_result.tasks_generated:
                self._task_queue.append(task)

            # Save periodically
            if save_interval and iteration % save_interval == 0:
                self.store.save(self.graph, name=snapshot_name)
                logger.info(f"Saved snapshot at iteration {iteration}")

            report.iterations = iteration

        # Final report
        stats = self.graph.stats()
        report.entities_total = stats["entities"]
        report.relationships_total = stats["relationships"]
        report.entity_types = stats["entity_types"]
        report.relationship_types = stats["relationship_types"]
        report.providers_used = self.providers.names()
        report.duration_seconds = time.time() - start_time

        # Final save
        self.store.save(self.graph, name=snapshot_name)

        return report

    # ── Interactive chat ───────────────────────────────────────────────

    async def chat(self, user_message: str) -> str:
        """Interactive mode — user asks questions, agent enriches as needed."""
        result = await self.analyst_agent.ask(user_message)
        return "\n".join(result.messages) if result.messages else result.raw_response

    # ── Full pipeline ──────────────────────────────────────────────────

    async def enrich_ticker(
        self, ticker: str, max_iterations: int = 5
    ) -> EnrichmentReport:
        """Full pipeline: seed from ticker → enrichment loop → report."""
        await self.seed_from_ticker(ticker)
        return await self.run_enrichment_loop(
            max_iterations=max_iterations,
            snapshot_name=ticker.lower(),
        )

    async def enrich_file(
        self, file_path: str, max_iterations: int = 3
    ) -> EnrichmentReport:
        """Full pipeline: ingest file → enrichment loop → report."""
        await self.seed_from_file(file_path)
        return await self.run_enrichment_loop(
            max_iterations=max_iterations,
            snapshot_name="file_enrichment",
        )
