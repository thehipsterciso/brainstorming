"""Compliance officer track — regulatory exposure, officer relationships, governance."""

from __future__ import annotations

from kg_enrichment.core.models import Entity
from kg_enrichment.tracks.base import BaseTrack

COMPLIANCE_PROMPT = """You are operating as a COMPLIANCE OFFICER. Prioritize:

- **Regulatory filings** — All SEC filings, especially 8-K (material events),
  proxy statements (DEF 14A), annual reports (10-K), and registration statements.
- **Officer and director relationships** — Board composition, executive compensation,
  related-party transactions, conflicts of interest, interlocking directorates.
- **Beneficial ownership** — Schedule 13D/13G filings, Form 4 insider trades,
  Form 3 initial beneficial ownership.
- **Regulatory actions** — SEC enforcement actions, consent orders, Wells notices,
  FINRA actions, state regulatory actions.
- **Corporate governance** — Governance policies, audit committee composition,
  whistleblower mechanisms, code of ethics.
- **Sanctions and restrictions** — OFAC sanctions lists, denied parties lists,
  export control classifications.
- **ESG and sustainability** — Environmental violations, labor practices,
  sustainability reporting, controversies.
- **Subsidiary and entity structure** — Legal entity hierarchy, jurisdictions of
  incorporation, offshore structures.

Leave no filing unturned. Every officer relationship, every regulatory interaction,
every ownership change is relevant. Compliance requires completeness.
"""


class ComplianceOfficerTrack(BaseTrack):
    name = "compliance"
    description = "Compliance analysis — regulatory exposure, governance, officer relationships"

    def get_system_prompt_addition(self) -> str:
        return COMPLIANCE_PROMPT

    def score_entity(self, entity: Entity) -> float:
        high_priority = {
            "organization": 4.0,
            "person": 5.0,  # Officers are critical for compliance
            "filing": 5.0,
            "regulation": 5.0,
            "event": 3.0,  # Regulatory events
        }
        base = high_priority.get(entity.entity_type, 1.0)

        # Boost for compliance-relevant attributes
        if entity.attributes.get("title") and any(
            role in str(entity.attributes.get("title", "")).lower()
            for role in ("ceo", "cfo", "coo", "director", "officer", "counsel", "secretary")
        ):
            base *= 1.5
        if entity.attributes.get("form") in ("8-K", "DEF 14A", "SC 13D", "SC 13G"):
            base *= 1.5

        return base

    def preferred_providers(self) -> list[str]:
        return ["sec_edgar", "yfinance", "news_feeds", "web_scraper"]
