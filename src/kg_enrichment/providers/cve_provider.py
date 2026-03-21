"""CVE/NVD provider — vulnerability data from NIST National Vulnerability Database.

Fetches CVE records, CVSS scores, affected products (CPE), and references.
Uses the free NVD API (no key required, but rate-limited).
"""

from __future__ import annotations

import logging
from typing import Any

import httpx

from kg_enrichment.core.graph import KnowledgeGraph
from kg_enrichment.core.models import Entity, EnrichmentTask, ProviderResult, Relationship
from kg_enrichment.providers.base import BaseProvider

logger = logging.getLogger(__name__)

NVD_API_BASE = "https://services.nvd.nist.gov/rest/json/cves/2.0"


class CVEProvider(BaseProvider):
    name = "cve_provider"
    description = "CVE vulnerability data, CVSS scores, affected products from NVD"
    supported_entity_types = ["software", "vendor", "organization", "vulnerability", "domain"]
    requires_api_key = False
    rate_limit = 0.5  # NVD rate limit: ~5 req/30 seconds without API key

    async def can_enrich(self, entity: Entity) -> bool:
        if entity.entity_type == "vulnerability":
            return True
        if entity.entity_type in ("software", "vendor", "organization"):
            return True
        return False

    async def enrich(self, entity: Entity, graph: KnowledgeGraph) -> ProviderResult:
        result = ProviderResult(provider_name=self.name)

        if entity.entity_type == "vulnerability":
            cve_id = entity.attributes.get("cve_id") or entity.name
            if cve_id.startswith("CVE-"):
                return await self._fetch_cve(cve_id, entity, result)

        # Search for vulnerabilities affecting this software/vendor
        keyword = entity.name
        return await self._search_cves(keyword, entity, result)

    async def _fetch_cve(
        self, cve_id: str, entity: Entity, result: ProviderResult
    ) -> ProviderResult:
        """Fetch a specific CVE by ID."""
        try:
            async with httpx.AsyncClient(timeout=30.0) as client:
                response = await client.get(
                    NVD_API_BASE, params={"cveId": cve_id}
                )
                response.raise_for_status()
                data = response.json()

            vulns = data.get("vulnerabilities", [])
            if vulns:
                cve_data = vulns[0].get("cve", {})
                self._process_cve(cve_data, entity, result)

        except Exception as e:
            logger.error(f"NVD fetch failed for {cve_id}: {e}")
            result.errors.append(f"NVD error: {e}")

        return result

    async def _search_cves(
        self, keyword: str, entity: Entity, result: ProviderResult
    ) -> ProviderResult:
        """Search NVD for CVEs matching a keyword."""
        try:
            async with httpx.AsyncClient(timeout=30.0) as client:
                response = await client.get(
                    NVD_API_BASE,
                    params={"keywordSearch": keyword, "resultsPerPage": 20},
                )
                response.raise_for_status()
                data = response.json()

            for vuln_entry in data.get("vulnerabilities", []):
                cve_data = vuln_entry.get("cve", {})
                cve_id = cve_data.get("id", "")
                if not cve_id:
                    continue

                descriptions = cve_data.get("descriptions", [])
                desc = next(
                    (d["value"] for d in descriptions if d.get("lang") == "en"),
                    "",
                )

                # CVSS scores
                metrics = cve_data.get("metrics", {})
                cvss_score = None
                cvss_severity = None
                for metric_key in ("cvssMetricV31", "cvssMetricV30", "cvssMetricV2"):
                    metric_list = metrics.get(metric_key, [])
                    if metric_list:
                        cvss_data = metric_list[0].get("cvssData", {})
                        cvss_score = cvss_data.get("baseScore")
                        cvss_severity = cvss_data.get("baseSeverity")
                        break

                vuln_entity = Entity(
                    entity_type="vulnerability",
                    name=cve_id,
                    attributes={
                        "cve_id": cve_id,
                        "description": desc[:1000],
                        "cvss_score": cvss_score,
                        "cvss_severity": cvss_severity,
                        "published": cve_data.get("published", ""),
                        "last_modified": cve_data.get("lastModified", ""),
                    },
                    sources=["cve_provider"],
                )
                result.suggested_entities.append(vuln_entity)
                result.suggested_relationships.append(Relationship(
                    rel_type="affected_by",
                    source_entity_id=entity.id,
                    target_entity_id=vuln_entity.id,
                    sources=["cve_provider"],
                ))

                # Extract affected products from CPE configurations
                configurations = cve_data.get("configurations", [])
                for config in configurations:
                    for node in config.get("nodes", []):
                        for cpe_match in node.get("cpeMatch", []):
                            criteria = cpe_match.get("criteria", "")
                            parts = criteria.split(":")
                            if len(parts) >= 5:
                                vendor = parts[3]
                                product = parts[4]
                                if vendor != "*" and product != "*":
                                    sw_entity = Entity(
                                        entity_type="software",
                                        name=f"{vendor} {product}",
                                        attributes={
                                            "vendor": vendor,
                                            "product": product,
                                            "cpe": criteria,
                                        },
                                        sources=["cve_provider"],
                                    )
                                    result.suggested_entities.append(sw_entity)
                                    result.suggested_relationships.append(Relationship(
                                        rel_type="affects",
                                        source_entity_id=vuln_entity.id,
                                        target_entity_id=sw_entity.id,
                                        sources=["cve_provider"],
                                    ))

                result.raw_data.append({"type": "cve", "data": cve_data})

        except Exception as e:
            logger.error(f"NVD search failed for {keyword}: {e}")
            result.errors.append(f"NVD search error: {e}")

        result.metadata = {
            "keyword": keyword,
            "cves_found": len(result.suggested_entities),
        }
        return result

    def _process_cve(
        self, cve_data: dict[str, Any], entity: Entity, result: ProviderResult
    ) -> None:
        """Process a single CVE record and update the entity."""
        descriptions = cve_data.get("descriptions", [])
        desc = next(
            (d["value"] for d in descriptions if d.get("lang") == "en"), ""
        )
        entity.attributes.update({
            "cve_id": cve_data.get("id", ""),
            "description": desc[:1000],
            "published": cve_data.get("published", ""),
            "last_modified": cve_data.get("lastModified", ""),
        })

        # CVSS
        metrics = cve_data.get("metrics", {})
        for metric_key in ("cvssMetricV31", "cvssMetricV30", "cvssMetricV2"):
            metric_list = metrics.get(metric_key, [])
            if metric_list:
                cvss_data = metric_list[0].get("cvssData", {})
                entity.attributes["cvss_score"] = cvss_data.get("baseScore")
                entity.attributes["cvss_severity"] = cvss_data.get("baseSeverity")
                entity.attributes["cvss_vector"] = cvss_data.get("vectorString")
                break

        # References
        references = cve_data.get("references", [])
        entity.attributes["references"] = [
            {"url": ref.get("url", ""), "source": ref.get("source", "")}
            for ref in references[:20]
        ]

        entity.add_source("cve_provider")
        result.raw_data.append({"type": "cve_detail", "data": cve_data})
