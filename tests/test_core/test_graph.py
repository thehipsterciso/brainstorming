"""Tests for the KnowledgeGraph engine."""

import json

import pytest

from kg_enrichment.core.graph import KnowledgeGraph
from kg_enrichment.core.models import Entity, Relationship


class TestKnowledgeGraphBasic:
    def test_empty_graph(self, empty_graph):
        assert len(empty_graph) == 0
        assert empty_graph.stats()["entities"] == 0

    def test_add_entity(self, empty_graph):
        entity = Entity(entity_type="organization", name="Test Corp")
        eid = empty_graph.add_entity(entity)
        assert eid == entity.id
        assert len(empty_graph) == 1
        assert entity.id in empty_graph

    def test_get_entity(self, sample_graph):
        entity = sample_graph.get_entity("org-apple")
        assert entity is not None
        assert entity.name == "Apple Inc."
        assert entity.entity_type == "organization"

    def test_get_nonexistent_entity(self, empty_graph):
        assert empty_graph.get_entity("nonexistent") is None

    def test_update_entity(self, sample_graph):
        updated = sample_graph.update_entity("org-apple", {
            "attributes": {"employees": 160000},
            "aliases": ["Apple Computer"],
        })
        assert updated.attributes["employees"] == 160000
        assert "Apple Computer" in updated.aliases

    def test_add_relationship(self, empty_graph):
        e1 = Entity(id="a", entity_type="org", name="A")
        e2 = Entity(id="b", entity_type="org", name="B")
        empty_graph.add_entity(e1)
        empty_graph.add_entity(e2)

        rel = Relationship(
            rel_type="partner_of",
            source_entity_id="a",
            target_entity_id="b",
        )
        rid = empty_graph.add_relationship(rel)
        assert rid == rel.id

    def test_relationship_validation(self, empty_graph):
        """Can't add relationship with missing entities."""
        rel = Relationship(
            rel_type="test",
            source_entity_id="nonexistent",
            target_entity_id="also-nonexistent",
        )
        with pytest.raises(ValueError):
            empty_graph.add_relationship(rel)


class TestSearch:
    def test_find_by_type(self, sample_graph):
        orgs = sample_graph.find_entities(entity_type="organization")
        assert len(orgs) == 2

    def test_find_by_name(self, sample_graph):
        results = sample_graph.find_entities(name="Apple")
        assert any(e.name == "Apple Inc." for e in results)

    def test_find_by_alias(self, sample_graph):
        results = sample_graph.find_entities(name="AAPL")
        assert any(e.name == "Apple Inc." for e in results)

    def test_find_by_attribute(self, sample_graph):
        results = sample_graph.find_entities(
            attribute_filter={"ticker": "AAPL"}
        )
        assert len(results) == 1

    def test_fuzzy_search(self, sample_graph):
        results = sample_graph.search("Apple")
        assert len(results) > 0
        assert results[0].name == "Apple Inc."  # Exact match first

    def test_search_attribute_values(self, sample_graph):
        results = sample_graph.search("Technology")
        assert len(results) > 0  # Finds via sector attribute


class TestRelationships:
    def test_get_relationships(self, sample_graph):
        rels = sample_graph.get_relationships("org-apple", direction="out")
        assert len(rels) >= 2  # owns_domain, filed, competes_with

    def test_get_relationships_in(self, sample_graph):
        rels = sample_graph.get_relationships("person-cook", direction="in")
        assert len(rels) == 0  # Cook has no incoming

    def test_get_relationships_by_type(self, sample_graph):
        rels = sample_graph.get_relationships("org-apple", rel_type="filed")
        assert len(rels) == 1
        assert rels[0].target_entity_id == "filing-10k"

    def test_get_neighbors(self, sample_graph):
        neighbors = sample_graph.get_neighbors("org-apple")
        names = [n.name for n in neighbors]
        assert "Tim Cook" in names
        assert "apple.com" in names

    def test_get_neighbors_depth_2(self, sample_graph):
        neighbors = sample_graph.get_neighbors("person-cook", depth=2)
        # Cook → Apple → (domain, filing, Microsoft)
        names = [n.name for n in neighbors]
        assert "Apple Inc." in names


class TestDynamicSchema:
    def test_entity_types_tracked(self, sample_graph):
        types = sample_graph.entity_types()
        assert "organization" in types
        assert "person" in types
        assert "domain" in types
        assert "filing" in types

    def test_relationship_types_tracked(self, sample_graph):
        types = sample_graph.relationship_types()
        assert "officer_of" in types
        assert "owns_domain" in types

    def test_schema_summary(self, sample_graph):
        schema = sample_graph.schema_summary()
        assert schema["total_entities"] == 5
        assert schema["total_relationships"] == 4

    def test_new_types_emerge(self, empty_graph):
        """Dynamic types that were never predefined."""
        empty_graph.add_entity(Entity(
            entity_type="quantum_computer",
            name="IBM Q System One",
        ))
        types = empty_graph.entity_types()
        assert "quantum_computer" in types


class TestMerge:
    def test_merge_entities(self, sample_graph):
        # Add a duplicate
        apple_dup = Entity(
            id="org-apple-dup",
            entity_type="organization",
            name="AAPL",
            attributes={"market_cap": "3T"},
            sources=["yfinance"],
        )
        sample_graph.add_entity(apple_dup)

        # Merge
        merged = sample_graph.merge_entities("org-apple", "org-apple-dup")
        assert merged.name == "Apple Inc."
        assert "AAPL" in merged.aliases
        assert merged.attributes["market_cap"] == "3T"
        assert "org-apple-dup" not in sample_graph


class TestEnrichmentTracking:
    def test_unenriched_entities(self, sample_graph):
        unenriched = sample_graph.unenriched_entities()
        assert len(unenriched) == 5  # None are enriched

    def test_mark_enriched(self, sample_graph):
        sample_graph.mark_enriched("org-apple")
        entity = sample_graph.get_entity("org-apple")
        assert entity.enriched is True
        assert len(sample_graph.unenriched_entities()) == 4


class TestSerialization:
    def test_to_dict_and_back(self, sample_graph):
        data = sample_graph.to_dict()
        restored = KnowledgeGraph.from_dict(data)
        assert len(restored) == len(sample_graph)
        assert restored.get_entity("org-apple").name == "Apple Inc."

    def test_to_json_and_back(self, sample_graph):
        json_str = sample_graph.to_json()
        assert isinstance(json_str, str)
        restored = KnowledgeGraph.from_json(json_str)
        assert len(restored) == len(sample_graph)

    def test_json_roundtrip_preserves_attributes(self, sample_graph):
        json_str = sample_graph.to_json()
        restored = KnowledgeGraph.from_json(json_str)
        apple = restored.get_entity("org-apple")
        assert apple.attributes["ticker"] == "AAPL"
        assert "AAPL" in apple.aliases


class TestTraversal:
    def test_subgraph(self, sample_graph):
        sub = sample_graph.subgraph(["org-apple", "person-cook"])
        assert len(sub) == 2

    def test_connected_components(self, sample_graph):
        components = sample_graph.connected_components()
        assert len(components) == 1  # All connected

    def test_shortest_path(self, sample_graph):
        path = sample_graph.shortest_path("person-cook", "domain-apple")
        assert path is not None
        assert len(path) >= 2

    def test_no_path(self, empty_graph):
        e1 = Entity(id="a", entity_type="x", name="A")
        e2 = Entity(id="b", entity_type="x", name="B")
        empty_graph.add_entity(e1)
        empty_graph.add_entity(e2)
        assert empty_graph.shortest_path("a", "b") is None
