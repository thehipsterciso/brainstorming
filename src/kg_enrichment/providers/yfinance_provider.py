"""yfinance provider — company profile, financials, holders, recommendations.

Greedy: fetches full company profile, all financial statements, institutional
holders, major holders, analyst recommendations, ESG scores, and more.
"""

from __future__ import annotations

import asyncio
import logging
from typing import Any

from kg_enrichment.core.graph import KnowledgeGraph
from kg_enrichment.core.models import Entity, EnrichmentTask, ProviderResult, Relationship
from kg_enrichment.providers.base import BaseProvider

logger = logging.getLogger(__name__)


class YFinanceProvider(BaseProvider):
    name = "yfinance"
    description = "Company profile, financials, holders, analyst recommendations"
    supported_entity_types = ["organization", "ticker", "financial_instrument"]
    requires_api_key = False
    rate_limit = 2.0

    async def can_enrich(self, entity: Entity) -> bool:
        return self._get_ticker(entity) is not None

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
            logger.error(f"yfinance enrichment failed for {ticker}: {e}")
            result.errors.append(f"yfinance error: {str(e)}")

        return result

    def _fetch_all(self, ticker: str, source_entity: Entity) -> dict[str, Any]:
        try:
            import yfinance as yf
        except ImportError:
            return {"raw": [], "metadata": {"error": "yfinance not installed"}}

        entities: list[Entity] = []
        relationships: list[Relationship] = []
        tasks: list[EnrichmentTask] = []
        raw: list[dict[str, Any]] = []

        stock = yf.Ticker(ticker)

        # Company info — everything available
        try:
            info = stock.info or {}
            if info:
                source_entity.attributes.update({
                    k: v for k, v in info.items()
                    if v is not None and k not in ("logo_url", "companyOfficers")
                })
                source_entity.add_source("yfinance")
                raw.append({"type": "company_info", "data": info})

                # Extract sector/industry as entities
                for field in ("sector", "industry"):
                    val = info.get(field)
                    if val:
                        sector_entity = Entity(
                            entity_type=field,
                            name=val,
                            sources=["yfinance"],
                        )
                        entities.append(sector_entity)
                        relationships.append(Relationship(
                            rel_type=f"in_{field}",
                            source_entity_id=source_entity.id,
                            target_entity_id=sector_entity.id,
                            sources=["yfinance"],
                        ))

                # Company officers from info
                officers = info.get("companyOfficers", [])
                for officer in officers:
                    name = officer.get("name", "")
                    if not name:
                        continue
                    officer_attrs = {
                        k: v for k, v in officer.items()
                        if v is not None and k != "name"
                    }
                    person = Entity(
                        entity_type="person",
                        name=name,
                        attributes=officer_attrs,
                        sources=["yfinance"],
                    )
                    entities.append(person)
                    relationships.append(Relationship(
                        rel_type="officer_of",
                        source_entity_id=person.id,
                        target_entity_id=source_entity.id,
                        attributes={"title": officer.get("title", "")},
                        sources=["yfinance"],
                    ))
                    tasks.append(EnrichmentTask(
                        entity_id=person.id,
                        priority=0.5,
                        context={"role": officer.get("title", ""), "company": ticker},
                    ))
                    raw.append({"type": "officer", "data": officer})

                # Website → domain entity
                website = info.get("website")
                if website:
                    from urllib.parse import urlparse
                    domain = urlparse(website).netloc or website
                    domain_entity = Entity(
                        entity_type="domain",
                        name=domain,
                        attributes={"url": website},
                        sources=["yfinance"],
                    )
                    entities.append(domain_entity)
                    relationships.append(Relationship(
                        rel_type="owns_domain",
                        source_entity_id=source_entity.id,
                        target_entity_id=domain_entity.id,
                        sources=["yfinance"],
                    ))
                    tasks.append(EnrichmentTask(
                        entity_id=domain_entity.id,
                        provider_hints=["dns_whois"],
                        priority=0.6,
                    ))
        except Exception as e:
            logger.warning(f"Failed to fetch info for {ticker}: {e}")

        # Institutional holders
        try:
            holders = stock.institutional_holders
            if holders is not None and not holders.empty:
                for _, row in holders.iterrows():
                    holder_name = str(row.get("Holder", ""))
                    if not holder_name:
                        continue
                    holder_attrs = {
                        k: str(v) for k, v in row.to_dict().items()
                        if k != "Holder" and v is not None
                    }
                    holder_entity = Entity(
                        entity_type="organization",
                        name=holder_name,
                        attributes=holder_attrs,
                        sources=["yfinance"],
                    )
                    entities.append(holder_entity)
                    relationships.append(Relationship(
                        rel_type="holds_shares_in",
                        source_entity_id=holder_entity.id,
                        target_entity_id=source_entity.id,
                        attributes=holder_attrs,
                        sources=["yfinance"],
                    ))
                    tasks.append(EnrichmentTask(
                        entity_id=holder_entity.id,
                        priority=0.4,
                        context={"role": "institutional_holder", "target": ticker},
                    ))
                raw.append({"type": "institutional_holders", "count": len(holders)})
        except Exception as e:
            logger.warning(f"Failed to fetch holders for {ticker}: {e}")

        # Recommendations
        try:
            recs = stock.recommendations
            if recs is not None and not recs.empty:
                raw.append({
                    "type": "recommendations",
                    "data": recs.tail(20).to_dict(orient="records"),
                })
        except Exception:
            pass

        # Sustainability / ESG
        try:
            sustainability = stock.sustainability
            if sustainability is not None and not sustainability.empty:
                esg_data = sustainability.to_dict()
                source_entity.attributes["esg"] = {
                    str(k): str(v) for k, v in esg_data.items() if v is not None
                }
                raw.append({"type": "sustainability", "data": esg_data})
        except Exception:
            pass

        return {
            "raw": raw,
            "entities": entities,
            "relationships": relationships,
            "tasks": tasks,
            "metadata": {"ticker": ticker, "entities_found": len(entities)},
        }

    @staticmethod
    def _get_ticker(entity: Entity) -> str | None:
        if entity.entity_type == "ticker":
            return entity.name.upper()
        ticker = entity.attributes.get("ticker") or entity.attributes.get("symbol")
        if ticker:
            return str(ticker).upper()
        return None
