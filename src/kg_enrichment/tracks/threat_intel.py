"""Threat intelligence track — IOCs, threat actor infrastructure, campaigns."""

from __future__ import annotations

from kg_enrichment.core.models import Entity
from kg_enrichment.tracks.base import BaseTrack

THREAT_INTEL_PROMPT = """You are operating as a THREAT INTELLIGENCE ANALYST. Prioritize:

- **Indicators of Compromise (IOCs)** — IP addresses, domains, URLs, file hashes,
  email addresses associated with malicious activity.
- **Infrastructure analysis** — Hosting providers, registrars, ASN information,
  passive DNS history, certificate transparency data.
- **Vulnerability exploitation** — CVEs being actively exploited, zero-days,
  proof-of-concept availability, exploitation timelines.
- **Threat actor attribution** — Naming conventions, known campaigns, TTPs
  (Tactics, Techniques, and Procedures), MITRE ATT&CK mapping.
- **Supply chain risks** — Third-party software dependencies, compromised libraries,
  dependency confusion risks, typosquatting domains.
- **Exposed credentials** — Code repositories with leaked secrets, public paste sites,
  breach databases (via legitimate threat intel feeds only).
- **Network infrastructure** — DNS chains, shared infrastructure with known bad actors,
  bulletproof hosting indicators, fast-flux networks.
- **Malware analysis artifacts** — Command and control domains, payload delivery URLs,
  exfiltration endpoints.

Follow every thread. A single domain or IP can unravel an entire campaign.
Cross-reference infrastructure, correlate timestamps, map the full threat landscape.
"""


class ThreatIntelTrack(BaseTrack):
    name = "threat_intel"
    description = "Threat intelligence — IOCs, threat actor infrastructure, campaigns"

    def get_system_prompt_addition(self) -> str:
        return THREAT_INTEL_PROMPT

    def score_entity(self, entity: Entity) -> float:
        high_priority = {
            "ip_address": 5.0,
            "domain": 5.0,
            "vulnerability": 5.0,
            "software": 4.0,
            "hash": 5.0,
            "url": 4.0,
            "email": 3.5,
            "nameserver": 3.0,
            "certificate": 3.0,
            "mail_server": 3.0,
            "repository": 3.0,
        }
        base = high_priority.get(entity.entity_type, 1.0)

        # Boost for threat-relevant indicators
        if entity.attributes.get("cvss_score"):
            score = entity.attributes["cvss_score"]
            if isinstance(score, (int, float)) and score >= 9.0:
                base *= 2.0
            elif isinstance(score, (int, float)) and score >= 7.0:
                base *= 1.5
        if entity.attributes.get("malicious"):
            base *= 2.0

        return base

    def preferred_providers(self) -> list[str]:
        return ["dns_whois", "cve_provider", "github", "web_scraper", "news_feeds"]
