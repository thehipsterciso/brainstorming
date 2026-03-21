"""Shared test fixtures."""

import pytest

from kg_enrichment.core.graph import KnowledgeGraph
from kg_enrichment.core.models import Entity, Relationship


@pytest.fixture
def empty_graph():
    """Empty knowledge graph."""
    return KnowledgeGraph()


@pytest.fixture
def sample_graph():
    """Graph with sample entities and relationships."""
    graph = KnowledgeGraph()

    # Organizations
    apple = Entity(
        id="org-apple",
        entity_type="organization",
        name="Apple Inc.",
        aliases=["AAPL", "Apple"],
        attributes={"ticker": "AAPL", "sector": "Technology"},
        sources=["yfinance"],
    )
    graph.add_entity(apple)

    microsoft = Entity(
        id="org-microsoft",
        entity_type="organization",
        name="Microsoft Corporation",
        aliases=["MSFT", "Microsoft"],
        attributes={"ticker": "MSFT", "sector": "Technology"},
        sources=["yfinance"],
    )
    graph.add_entity(microsoft)

    # Person
    tim_cook = Entity(
        id="person-cook",
        entity_type="person",
        name="Tim Cook",
        aliases=["Timothy D. Cook"],
        attributes={"title": "CEO"},
        sources=["sec_edgar"],
    )
    graph.add_entity(tim_cook)

    # Domain
    apple_domain = Entity(
        id="domain-apple",
        entity_type="domain",
        name="apple.com",
        sources=["dns_whois"],
    )
    graph.add_entity(apple_domain)

    # Filing
    filing = Entity(
        id="filing-10k",
        entity_type="filing",
        name="AAPL 10-K 2024",
        attributes={"form": "10-K", "filing_date": "2024-11-01"},
        sources=["sec_edgar"],
    )
    graph.add_entity(filing)

    # Relationships
    graph.add_relationship(Relationship(
        id="rel-cook-apple",
        rel_type="officer_of",
        source_entity_id="person-cook",
        target_entity_id="org-apple",
        attributes={"title": "CEO"},
        sources=["sec_edgar"],
    ))
    graph.add_relationship(Relationship(
        id="rel-apple-domain",
        rel_type="owns_domain",
        source_entity_id="org-apple",
        target_entity_id="domain-apple",
        sources=["dns_whois"],
    ))
    graph.add_relationship(Relationship(
        id="rel-apple-filing",
        rel_type="filed",
        source_entity_id="org-apple",
        target_entity_id="filing-10k",
        sources=["sec_edgar"],
    ))
    graph.add_relationship(Relationship(
        id="rel-competes",
        rel_type="competes_with",
        source_entity_id="org-apple",
        target_entity_id="org-microsoft",
        sources=["agent"],
    ))

    return graph
