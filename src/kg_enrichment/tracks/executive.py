"""Executive track — strategic overview, competitive landscape, market position."""

from __future__ import annotations

from kg_enrichment.core.models import Entity
from kg_enrichment.tracks.base import BaseTrack

EXECUTIVE_PROMPT = """You are operating as an EXECUTIVE INTELLIGENCE ANALYST providing
strategic-level insights. Prioritize:

- **Competitive landscape** — Who are the competitors? Market positioning, differentiation,
  competitive advantages and weaknesses. Technology moats.
- **Key personnel** — C-suite executives, board members, key hires, departures.
  Their backgrounds, previous companies, board interlocks.
- **Market dynamics** — Industry trends, regulatory changes, emerging technologies,
  disruptive threats, market consolidation patterns.
- **Financial trajectory** — Revenue growth, profitability trends, R&D investment,
  capital allocation strategy, shareholder returns.
- **Strategic initiatives** — M&A activity, partnerships, joint ventures, new market
  entries, product launches, geographic expansion.
- **Stakeholder ecosystem** — Major customers, suppliers, partners, regulators,
  investors, analysts. Who influences the company and who does the company influence?
- **Risk landscape** — Geopolitical risks, supply chain dependencies, key person risks,
  technology risks, regulatory risks, reputational risks.
- **Innovation indicators** — Patent activity, R&D facilities, technology acquisitions,
  open source contributions, talent acquisition patterns.

Build the full picture. An executive needs to see the forest AND the trees.
Connect the dots between financial data, competitive positioning, and strategic risks.
"""


class ExecutiveTrack(BaseTrack):
    name = "executive"
    description = "Executive intelligence — strategic overview, competitive landscape, market position"

    def get_system_prompt_addition(self) -> str:
        return EXECUTIVE_PROMPT

    def score_entity(self, entity: Entity) -> float:
        # Balanced scoring — everything matters at the executive level
        priority = {
            "organization": 4.0,  # Competitors, partners, customers
            "person": 3.5,  # Key executives
            "sector": 3.0,
            "industry": 3.0,
            "filing": 2.5,
            "event": 3.0,
            "news_article": 2.5,
            "financial_instrument": 2.0,
            "domain": 1.5,
            "repository": 1.5,
        }
        base = priority.get(entity.entity_type, 1.0)

        # Boost for strategic attributes
        if entity.attributes.get("title") and any(
            role in str(entity.attributes.get("title", "")).lower()
            for role in ("ceo", "cfo", "cto", "coo", "president", "chairman")
        ):
            base *= 1.5
        if entity.attributes.get("competitor"):
            base *= 1.5

        return base

    def preferred_providers(self) -> list[str]:
        return ["yfinance", "sec_edgar", "news_feeds", "github", "web_scraper"]
