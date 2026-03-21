"""Web scraper provider — extract content from any URL.

Uses httpx for fetching and trafilatura for content extraction. Extracts
main text, metadata, and linked URLs for follow-up enrichment.
"""

from __future__ import annotations

import logging
from typing import Any
from urllib.parse import urljoin, urlparse

from kg_enrichment.core.graph import KnowledgeGraph
from kg_enrichment.core.models import Entity, EnrichmentTask, ProviderResult
from kg_enrichment.providers.base import BaseProvider

logger = logging.getLogger(__name__)


class WebScraperProvider(BaseProvider):
    name = "web_scraper"
    description = "Extract content and metadata from any URL"
    supported_entity_types = ["domain", "webpage", "url"]
    requires_api_key = False
    rate_limit = 1.0

    async def can_enrich(self, entity: Entity) -> bool:
        return self._get_url(entity) is not None

    async def enrich(self, entity: Entity, graph: KnowledgeGraph) -> ProviderResult:
        url = self._get_url(entity)
        if not url:
            return ProviderResult(provider_name=self.name)

        result = ProviderResult(provider_name=self.name)

        try:
            import httpx

            async with httpx.AsyncClient(
                follow_redirects=True,
                timeout=30.0,
                headers={"User-Agent": "KGEnrichment/0.1 (research)"},
            ) as client:
                response = await client.get(url)
                response.raise_for_status()
                html = response.text

            # Extract main content
            try:
                import trafilatura

                extracted = trafilatura.extract(
                    html,
                    include_links=True,
                    include_tables=True,
                    include_comments=False,
                    output_format="json",
                )
                if extracted:
                    import json
                    content_data = json.loads(extracted)
                else:
                    content_data = {"text": trafilatura.extract(html) or ""}
            except ImportError:
                content_data = {"text": html[:10000], "warning": "trafilatura not installed"}

            result.raw_data = [{"type": "web_content", "url": url, "data": content_data}]

            # Store extracted content on the entity
            entity.attributes["content"] = content_data.get("text", "")[:5000]
            entity.attributes["title"] = content_data.get("title", "")
            entity.attributes["url"] = url
            entity.add_source("web_scraper")

            # Extract linked domains for follow-up
            links = content_data.get("links", [])
            if isinstance(links, list):
                seen_domains: set[str] = set()
                for link in links[:20]:
                    if isinstance(link, str):
                        parsed = urlparse(link if "://" in link else urljoin(url, link))
                        domain = parsed.netloc
                        if domain and domain not in seen_domains:
                            seen_domains.add(domain)
                            domain_entity = Entity(
                                entity_type="domain",
                                name=domain,
                                attributes={"discovered_from": url},
                                sources=["web_scraper"],
                            )
                            result.suggested_entities.append(domain_entity)

            result.metadata = {
                "url": url,
                "title": content_data.get("title", ""),
                "content_length": len(content_data.get("text", "")),
            }

        except Exception as e:
            logger.error(f"Web scraping failed for {url}: {e}")
            result.errors.append(f"Scraping error: {e}")

        return result

    async def fetch_url(self, url: str) -> dict[str, Any]:
        """Standalone URL fetch — used as an agent tool."""
        try:
            import httpx

            async with httpx.AsyncClient(
                follow_redirects=True,
                timeout=30.0,
                headers={"User-Agent": "KGEnrichment/0.1 (research)"},
            ) as client:
                response = await client.get(url)
                response.raise_for_status()

            try:
                import trafilatura
                text = trafilatura.extract(response.text) or response.text[:5000]
            except ImportError:
                text = response.text[:5000]

            return {"url": url, "status": response.status_code, "text": text}
        except Exception as e:
            return {"url": url, "error": str(e)}

    @staticmethod
    def _get_url(entity: Entity) -> str | None:
        if entity.entity_type in ("webpage", "url"):
            url = entity.attributes.get("url") or entity.name
            if "://" in url:
                return url
            return f"https://{url}"
        if entity.entity_type == "domain":
            return f"https://{entity.name}"
        return entity.attributes.get("url")
