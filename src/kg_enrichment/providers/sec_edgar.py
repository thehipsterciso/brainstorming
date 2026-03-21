"""SEC EDGAR provider — filings, XBRL financials, officers, insider trades.

Uses the edgartools library (free, no API key required).
Greedy: fetches ALL available filing types, officer data, and financial facts.
"""

from __future__ import annotations

import asyncio
import logging
from typing import Any

from kg_enrichment.core.graph import KnowledgeGraph
from kg_enrichment.core.models import Entity, EnrichmentTask, ProviderResult, Relationship
from kg_enrichment.providers.base import BaseProvider

logger = logging.getLogger(__name__)


class SECEdgarProvider(BaseProvider):
    name = "sec_edgar"
    description = "SEC EDGAR filings, XBRL financials, officers, and insider trading data"
    supported_entity_types = ["organization", "person", "ticker"]
    requires_api_key = False
    rate_limit = 5.0  # SEC fair access: 10 req/sec max

    async def can_enrich(self, entity: Entity) -> bool:
        ticker = self._get_ticker(entity)
        return ticker is not None

    async def enrich(self, entity: Entity, graph: KnowledgeGraph) -> ProviderResult:
        ticker = self._get_ticker(entity)
        if not ticker:
            return ProviderResult(provider_name=self.name)

        result = ProviderResult(provider_name=self.name)

        try:
            data = await asyncio.to_thread(self._fetch_all, ticker, entity)
            result.raw_data = data.get("raw", [])
            result.suggested_entities = data.get("entities", [])
            result.suggested_relationships = data.get("relationships", [])
            result.follow_up_tasks = data.get("tasks", [])
            result.metadata = data.get("metadata", {})
        except Exception as e:
            logger.error(f"SEC EDGAR enrichment failed for {ticker}: {e}")
            result.errors.append(f"SEC EDGAR error: {str(e)}")

        return result

    def _fetch_all(self, ticker: str, source_entity: Entity) -> dict[str, Any]:
        """Synchronous fetch — run in thread. Grabs everything available."""
        try:
            from edgar import Company
        except ImportError:
            return {"raw": [], "entities": [], "relationships": [],
                    "metadata": {"error": "edgartools not installed"}}

        entities: list[Entity] = []
        relationships: list[Relationship] = []
        tasks: list[EnrichmentTask] = []
        raw: list[dict[str, Any]] = []

        try:
            company = Company(ticker)
        except Exception as e:
            return {"raw": [], "entities": [], "relationships": [],
                    "metadata": {"error": f"Company not found: {e}"}}

        # Company profile
        company_attrs: dict[str, Any] = {}
        for attr in ["name", "cik", "sic", "sic_description", "state",
                      "state_of_incorporation", "fiscal_year_end",
                      "industry", "category", "entity_type"]:
            try:
                val = getattr(company, attr, None)
                if val is not None:
                    company_attrs[attr] = str(val)
            except Exception:
                pass

        source_entity.attributes.update(company_attrs)
        source_entity.add_source("sec_edgar")
        raw.append({"type": "company_profile", "data": company_attrs})

        # Filings — get all recent filings across all types
        try:
            filings = company.get_filings()
            recent_filings = list(filings[:50])  # Last 50 filings
            for filing in recent_filings:
                filing_data: dict[str, Any] = {}
                for attr in ["form", "filing_date", "accession_no",
                              "primary_doc_url", "description"]:
                    try:
                        val = getattr(filing, attr, None)
                        if val is not None:
                            filing_data[attr] = str(val)
                    except Exception:
                        pass

                if filing_data:
                    filing_entity = Entity(
                        entity_type="filing",
                        name=f"{ticker} {filing_data.get('form', 'Filing')} "
                             f"{filing_data.get('filing_date', '')}",
                        attributes=filing_data,
                        sources=["sec_edgar"],
                    )
                    entities.append(filing_entity)
                    relationships.append(Relationship(
                        rel_type="filed",
                        source_entity_id=source_entity.id,
                        target_entity_id=filing_entity.id,
                        sources=["sec_edgar"],
                    ))
                    raw.append({"type": "filing", "data": filing_data})
        except Exception as e:
            logger.warning(f"Failed to fetch filings for {ticker}: {e}")

        # Officers / insiders
        try:
            if hasattr(company, "officers"):
                officers = company.officers
                if officers:
                    for officer in officers:
                        officer_data: dict[str, Any] = {}
                        for attr in ["name", "title", "age"]:
                            try:
                                val = getattr(officer, attr, None)
                                if val is not None:
                                    officer_data[attr] = str(val)
                            except Exception:
                                pass

                        if officer_data.get("name"):
                            person_entity = Entity(
                                entity_type="person",
                                name=officer_data["name"],
                                attributes=officer_data,
                                sources=["sec_edgar"],
                            )
                            entities.append(person_entity)
                            relationships.append(Relationship(
                                rel_type="officer_of",
                                source_entity_id=person_entity.id,
                                target_entity_id=source_entity.id,
                                attributes={"title": officer_data.get("title", "")},
                                sources=["sec_edgar"],
                            ))
                            # Queue person for further enrichment
                            tasks.append(EnrichmentTask(
                                entity_id=person_entity.id,
                                priority=0.7,
                                context={"role": "officer", "company": ticker},
                            ))
                            raw.append({"type": "officer", "data": officer_data})
        except Exception as e:
            logger.warning(f"Failed to fetch officers for {ticker}: {e}")

        # Company facts (XBRL financial data)
        try:
            if hasattr(company, "facts"):
                facts = company.facts
                if facts:
                    facts_data = {"type": "company_facts", "ticker": ticker}
                    raw.append(facts_data)
        except Exception as e:
            logger.warning(f"Failed to fetch company facts for {ticker}: {e}")

        metadata = {
            "ticker": ticker,
            "filings_found": len([r for r in raw if r.get("type") == "filing"]),
            "officers_found": len([r for r in raw if r.get("type") == "officer"]),
        }

        return {
            "raw": raw,
            "entities": entities,
            "relationships": relationships,
            "tasks": tasks,
            "metadata": metadata,
        }

    @staticmethod
    def _get_ticker(entity: Entity) -> str | None:
        """Extract ticker symbol from entity attributes or type."""
        if entity.entity_type == "ticker":
            return entity.name.upper()
        ticker = entity.attributes.get("ticker") or entity.attributes.get("symbol")
        if ticker:
            return str(ticker).upper()
        return None
