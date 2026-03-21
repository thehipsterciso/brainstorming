"""News feeds provider — RSS/Atom aggregation and news entity extraction.

Fetches news from multiple RSS feeds, extracts articles as event entities,
and links them to organizations/people mentioned.
"""

from __future__ import annotations

import logging
from typing import Any
from xml.etree import ElementTree

import httpx

from kg_enrichment.core.graph import KnowledgeGraph
from kg_enrichment.core.models import Entity, ProviderResult, Relationship
from kg_enrichment.providers.base import BaseProvider

logger = logging.getLogger(__name__)

# Free RSS feeds by topic
COMPANY_NEWS_FEEDS = [
    "https://feeds.finance.yahoo.com/rss/2.0/headline?s={ticker}&region=US&lang=en-US",
]

GENERAL_FEEDS = [
    "https://news.google.com/rss/search?q={query}&hl=en-US&gl=US&ceid=US:en",
]


class NewsFeedsProvider(BaseProvider):
    name = "news_feeds"
    description = "RSS/Atom news aggregation with entity extraction"
    supported_entity_types = ["organization", "person", "ticker", "domain"]
    requires_api_key = False
    rate_limit = 1.0

    async def can_enrich(self, entity: Entity) -> bool:
        return entity.entity_type in self.supported_entity_types

    async def enrich(self, entity: Entity, graph: KnowledgeGraph) -> ProviderResult:
        result = ProviderResult(provider_name=self.name)
        entities: list[Entity] = []
        relationships: list[Relationship] = []
        raw: list[dict[str, Any]] = []

        query = entity.name
        ticker = entity.attributes.get("ticker") or (
            entity.name if entity.entity_type == "ticker" else None
        )

        feeds_to_check: list[str] = []
        if ticker:
            feeds_to_check.extend(f.format(ticker=ticker) for f in COMPANY_NEWS_FEEDS)
        feeds_to_check.extend(f.format(query=query) for f in GENERAL_FEEDS)

        async with httpx.AsyncClient(
            follow_redirects=True,
            timeout=15.0,
            headers={"User-Agent": "KGEnrichment/0.1 (research)"},
        ) as client:
            for feed_url in feeds_to_check:
                try:
                    response = await client.get(feed_url)
                    response.raise_for_status()
                    articles = self._parse_feed(response.text)

                    for article in articles[:25]:  # Up to 25 articles per feed
                        event_entity = Entity(
                            entity_type="news_article",
                            name=article.get("title", "Untitled"),
                            attributes={
                                "url": article.get("link", ""),
                                "published": article.get("published", ""),
                                "description": article.get("description", "")[:500],
                                "source_feed": feed_url,
                            },
                            sources=["news_feeds"],
                        )
                        entities.append(event_entity)
                        relationships.append(Relationship(
                            rel_type="mentioned_in",
                            source_entity_id=entity.id,
                            target_entity_id=event_entity.id,
                            sources=["news_feeds"],
                        ))
                        raw.append(article)

                except Exception as e:
                    logger.warning(f"Failed to fetch feed {feed_url}: {e}")
                    result.errors.append(f"Feed error ({feed_url}): {e}")

        result.raw_data = raw
        result.suggested_entities = entities
        result.suggested_relationships = relationships
        result.metadata = {"query": query, "articles_found": len(entities)}
        return result

    def _parse_feed(self, xml_text: str) -> list[dict[str, str]]:
        """Parse RSS or Atom feed XML into article dicts."""
        articles: list[dict[str, str]] = []
        try:
            root = ElementTree.fromstring(xml_text)
        except ElementTree.ParseError:
            return articles

        # RSS 2.0
        for item in root.iter("item"):
            article: dict[str, str] = {}
            for field in ("title", "link", "description", "pubDate"):
                elem = item.find(field)
                if elem is not None and elem.text:
                    key = "published" if field == "pubDate" else field
                    article[key] = elem.text.strip()
            if article:
                articles.append(article)

        # Atom
        if not articles:
            ns = {"atom": "http://www.w3.org/2005/Atom"}
            for entry in root.findall(".//atom:entry", ns):
                article = {}
                title = entry.find("atom:title", ns)
                if title is not None and title.text:
                    article["title"] = title.text.strip()
                link = entry.find("atom:link", ns)
                if link is not None:
                    article["link"] = link.get("href", "")
                published = entry.find("atom:published", ns) or entry.find("atom:updated", ns)
                if published is not None and published.text:
                    article["published"] = published.text.strip()
                summary = entry.find("atom:summary", ns) or entry.find("atom:content", ns)
                if summary is not None and summary.text:
                    article["description"] = summary.text.strip()[:500]
                if article:
                    articles.append(article)

        return articles
