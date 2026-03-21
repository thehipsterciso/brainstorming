"""DNS and WHOIS provider — domain intelligence, DNS records, registration data.

Greedy: fetches ALL DNS record types, full WHOIS data, and linked infrastructure.
"""

from __future__ import annotations

import asyncio
import logging
from typing import Any

from kg_enrichment.core.graph import KnowledgeGraph
from kg_enrichment.core.models import Entity, EnrichmentTask, ProviderResult, Relationship
from kg_enrichment.providers.base import BaseProvider

logger = logging.getLogger(__name__)

DNS_RECORD_TYPES = ["A", "AAAA", "MX", "NS", "TXT", "CNAME", "SOA", "SRV", "CAA"]


class DNSWhoisProvider(BaseProvider):
    name = "dns_whois"
    description = "DNS records, WHOIS registration, domain and infrastructure intelligence"
    supported_entity_types = ["domain", "ip_address", "organization"]
    requires_api_key = False
    rate_limit = 2.0

    async def can_enrich(self, entity: Entity) -> bool:
        return self._get_domain(entity) is not None

    async def enrich(self, entity: Entity, graph: KnowledgeGraph) -> ProviderResult:
        domain = self._get_domain(entity)
        if not domain:
            return ProviderResult(provider_name=self.name)

        result = ProviderResult(provider_name=self.name)
        entities: list[Entity] = []
        relationships: list[Relationship] = []
        tasks: list[EnrichmentTask] = []
        raw: list[dict[str, Any]] = []

        # DNS resolution
        try:
            dns_data = await self._fetch_dns(domain)
            raw.append({"type": "dns_records", "domain": domain, "data": dns_data})

            for record_type, records in dns_data.items():
                for record in records:
                    if record_type in ("A", "AAAA"):
                        ip_entity = Entity(
                            entity_type="ip_address",
                            name=record,
                            attributes={"record_type": record_type, "domain": domain},
                            sources=["dns_whois"],
                        )
                        entities.append(ip_entity)
                        relationships.append(Relationship(
                            rel_type="resolves_to",
                            source_entity_id=entity.id,
                            target_entity_id=ip_entity.id,
                            sources=["dns_whois"],
                        ))
                    elif record_type == "MX":
                        mx_entity = Entity(
                            entity_type="mail_server",
                            name=record,
                            attributes={"domain": domain},
                            sources=["dns_whois"],
                        )
                        entities.append(mx_entity)
                        relationships.append(Relationship(
                            rel_type="mail_handled_by",
                            source_entity_id=entity.id,
                            target_entity_id=mx_entity.id,
                            sources=["dns_whois"],
                        ))
                    elif record_type == "NS":
                        ns_entity = Entity(
                            entity_type="nameserver",
                            name=record,
                            attributes={"domain": domain},
                            sources=["dns_whois"],
                        )
                        entities.append(ns_entity)
                        relationships.append(Relationship(
                            rel_type="nameserver_of",
                            source_entity_id=ns_entity.id,
                            target_entity_id=entity.id,
                            sources=["dns_whois"],
                        ))
                    elif record_type == "TXT":
                        entity.attributes.setdefault("txt_records", [])
                        entity.attributes["txt_records"].append(record)
                    elif record_type == "CNAME":
                        cname_entity = Entity(
                            entity_type="domain",
                            name=record,
                            sources=["dns_whois"],
                        )
                        entities.append(cname_entity)
                        relationships.append(Relationship(
                            rel_type="cname_of",
                            source_entity_id=entity.id,
                            target_entity_id=cname_entity.id,
                            sources=["dns_whois"],
                        ))
                        tasks.append(EnrichmentTask(
                            entity_id=cname_entity.id,
                            provider_hints=["dns_whois"],
                            priority=0.5,
                        ))
        except Exception as e:
            logger.warning(f"DNS lookup failed for {domain}: {e}")
            result.errors.append(f"DNS error: {e}")

        # WHOIS lookup
        try:
            whois_data = await asyncio.to_thread(self._fetch_whois, domain)
            if whois_data:
                raw.append({"type": "whois", "domain": domain, "data": whois_data})
                entity.attributes["whois"] = whois_data
                entity.add_source("dns_whois")

                # Registrar entity
                registrar = whois_data.get("registrar")
                if registrar:
                    registrar_entity = Entity(
                        entity_type="registrar",
                        name=registrar,
                        sources=["dns_whois"],
                    )
                    entities.append(registrar_entity)
                    relationships.append(Relationship(
                        rel_type="registered_with",
                        source_entity_id=entity.id,
                        target_entity_id=registrar_entity.id,
                        sources=["dns_whois"],
                    ))

                # Registrant org
                registrant = whois_data.get("org") or whois_data.get("registrant_org")
                if registrant:
                    reg_org = Entity(
                        entity_type="organization",
                        name=registrant,
                        attributes={"role": "domain_registrant"},
                        sources=["dns_whois"],
                    )
                    entities.append(reg_org)
                    relationships.append(Relationship(
                        rel_type="registered_by",
                        source_entity_id=entity.id,
                        target_entity_id=reg_org.id,
                        sources=["dns_whois"],
                    ))
        except Exception as e:
            logger.warning(f"WHOIS lookup failed for {domain}: {e}")
            result.errors.append(f"WHOIS error: {e}")

        result.raw_data = raw
        result.suggested_entities = entities
        result.suggested_relationships = relationships
        result.follow_up_tasks = tasks
        result.metadata = {"domain": domain, "dns_records": len(raw)}
        return result

    async def _fetch_dns(self, domain: str) -> dict[str, list[str]]:
        """Fetch all DNS record types for a domain."""
        try:
            import dns.resolver
        except ImportError:
            return {}

        records: dict[str, list[str]] = {}
        for rtype in DNS_RECORD_TYPES:
            try:
                answers = await asyncio.to_thread(
                    lambda rt=rtype: dns.resolver.resolve(domain, rt)
                )
                records[rtype] = [str(r) for r in answers]
            except Exception:
                pass
        return records

    def _fetch_whois(self, domain: str) -> dict[str, Any]:
        """Fetch WHOIS data for a domain."""
        try:
            import whois
        except ImportError:
            return {}

        try:
            w = whois.whois(domain)
            if w:
                return {
                    k: (str(v) if not isinstance(v, (list, dict)) else v)
                    for k, v in w.items()
                    if v is not None
                }
        except Exception:
            pass
        return {}

    @staticmethod
    def _get_domain(entity: Entity) -> str | None:
        if entity.entity_type == "domain":
            return entity.name
        domain = entity.attributes.get("domain") or entity.attributes.get("website")
        if domain:
            from urllib.parse import urlparse
            parsed = urlparse(domain if "://" in domain else f"https://{domain}")
            return parsed.netloc or domain
        return None
