"""Financial analyst track — ownership chains, revenue, filings, risk."""

from __future__ import annotations

from kg_enrichment.core.models import Entity
from kg_enrichment.tracks.base import BaseTrack

FINANCIAL_PROMPT = """You are operating as a FINANCIAL ANALYST. Prioritize:

- **Ownership and control** — Who owns what? Subsidiary chains, holding companies,
  beneficial ownership, institutional holders, activist investors.
- **Financial health** — Revenue, profit margins, debt levels, cash flow, working capital.
  Pull from SEC filings (10-K, 10-Q) and financial data providers.
- **Material risks** — Risk factors from filings, litigation, regulatory actions,
  concentration risks, supply chain dependencies.
- **Corporate actions** — M&A activity, spin-offs, IPOs, secondary offerings,
  share buybacks, dividend changes.
- **Officer and director activity** — Insider trading patterns, executive compensation,
  board composition, golden parachutes.
- **Industry positioning** — Competitors, market share, sector trends, peer comparisons.

Chase financial data aggressively. Every subsidiary, every holder, every material
contract is relevant. Follow the money.
"""


class FinancialAnalystTrack(BaseTrack):
    name = "financial"
    description = "Financial analysis — ownership, filings, risk, corporate actions"

    def get_system_prompt_addition(self) -> str:
        return FINANCIAL_PROMPT

    def score_entity(self, entity: Entity) -> float:
        high_priority = {
            "organization": 5.0,
            "filing": 4.0,
            "financial_instrument": 4.0,
            "person": 3.0,  # Officers, directors
            "sector": 3.0,
            "industry": 3.0,
        }
        base = high_priority.get(entity.entity_type, 1.0)

        # Boost for financial attributes
        if entity.attributes.get("ticker"):
            base *= 1.5
        if entity.attributes.get("role") in ("institutional_holder", "officer"):
            base *= 1.3

        return base

    def preferred_providers(self) -> list[str]:
        return ["sec_edgar", "yfinance", "news_feeds", "web_scraper"]
