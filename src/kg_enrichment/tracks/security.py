"""Security analyst track — attack surface, infrastructure, vulnerabilities."""

from __future__ import annotations

from kg_enrichment.core.models import Entity
from kg_enrichment.tracks.base import BaseTrack

SECURITY_PROMPT = """You are operating as a SECURITY ANALYST. Prioritize:

- **Attack surface mapping** — Domains, subdomains, IP ranges, exposed services,
  cloud infrastructure, CDN providers, hosting providers.
- **Technology stack** — What software, frameworks, and platforms does the target use?
  Check DNS TXT records for SPF/DKIM/DMARC, look for technology indicators.
- **Vulnerabilities** — CVEs affecting the target's technology stack. Cross-reference
  software versions with NVD data. CVSS scores, exploit availability.
- **Infrastructure relationships** — Shared hosting, shared DNS, shared certificates.
  ASN and IP range analysis. Cloud provider identification.
- **Email security** — MX records, SPF/DKIM/DMARC configuration, email providers.
- **Code exposure** — GitHub repositories, public code, leaked credentials,
  dependency supply chain risks.
- **Third-party risk** — Service providers, SaaS dependencies, supply chain vendors
  with access to the target's systems.

Map everything. Every domain, every IP, every piece of exposed infrastructure matters.
Follow DNS chains, certificate transparency, and infrastructure connections relentlessly.
"""


class SecurityAnalystTrack(BaseTrack):
    name = "security"
    description = "Security analysis — attack surface, infrastructure, vulnerabilities"

    def get_system_prompt_addition(self) -> str:
        return SECURITY_PROMPT

    def score_entity(self, entity: Entity) -> float:
        high_priority = {
            "domain": 5.0,
            "ip_address": 5.0,
            "software": 4.0,
            "vulnerability": 4.0,
            "nameserver": 3.5,
            "mail_server": 3.5,
            "certificate": 3.5,
            "repository": 3.0,
            "organization": 2.0,
        }
        base = high_priority.get(entity.entity_type, 1.0)

        # Boost for infrastructure-related attributes
        if entity.attributes.get("cve_id"):
            base *= 1.5
        if entity.attributes.get("cvss_score"):
            score = entity.attributes["cvss_score"]
            if isinstance(score, (int, float)) and score >= 7.0:
                base *= 1.5

        return base

    def preferred_providers(self) -> list[str]:
        return ["dns_whois", "cve_provider", "github", "web_scraper", "news_feeds"]
