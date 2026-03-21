"""Tests for core data models."""

from kg_enrichment.core.models import Entity, Relationship, EnrichmentTask, ProviderResult


class TestEntity:
    def test_create_entity(self):
        entity = Entity(entity_type="organization", name="Test Corp")
        assert entity.entity_type == "organization"
        assert entity.name == "Test Corp"
        assert entity.id  # Auto-generated UUID
        assert entity.confidence == 1.0
        assert entity.enriched is False

    def test_dynamic_entity_type(self):
        """Entity types are free-form strings, not enums."""
        entity = Entity(entity_type="custom_thing_we_just_invented", name="Whatever")
        assert entity.entity_type == "custom_thing_we_just_invented"

    def test_merge_from(self):
        e1 = Entity(
            entity_type="organization",
            name="Apple Inc.",
            aliases=["Apple"],
            attributes={"sector": "Technology"},
            sources=["source1"],
            confidence=0.8,
        )
        e2 = Entity(
            entity_type="organization",
            name="AAPL",
            aliases=["Apple Inc"],
            attributes={"ticker": "AAPL", "industry": "Consumer Electronics"},
            sources=["source2"],
            confidence=0.9,
        )

        e1.merge_from(e2)

        assert "AAPL" in e1.aliases
        assert "Apple Inc" in e1.aliases
        assert e1.attributes["sector"] == "Technology"  # Original kept
        assert e1.attributes["ticker"] == "AAPL"  # New added
        assert "source2" in e1.sources
        assert e1.confidence == 0.9  # Max of both

    def test_add_source(self):
        entity = Entity(entity_type="person", name="Test", sources=["a"])
        entity.add_source("b")
        entity.add_source("a")  # Duplicate
        assert entity.sources == ["a", "b"]

    def test_entity_hash_and_eq(self):
        e1 = Entity(id="same-id", entity_type="x", name="A")
        e2 = Entity(id="same-id", entity_type="y", name="B")
        e3 = Entity(id="different-id", entity_type="x", name="A")

        assert e1 == e2  # Same ID
        assert e1 != e3  # Different ID
        assert hash(e1) == hash(e2)


class TestRelationship:
    def test_create_relationship(self):
        rel = Relationship(
            rel_type="employs",
            source_entity_id="org-1",
            target_entity_id="person-1",
        )
        assert rel.rel_type == "employs"
        assert rel.id  # Auto-generated

    def test_dynamic_relationship_type(self):
        rel = Relationship(
            rel_type="some_weird_relationship_we_discovered",
            source_entity_id="a",
            target_entity_id="b",
        )
        assert rel.rel_type == "some_weird_relationship_we_discovered"


class TestProviderResult:
    def test_empty_result(self):
        result = ProviderResult(provider_name="test")
        assert result.raw_data == []
        assert result.suggested_entities == []
        assert result.errors == []

    def test_result_with_data(self):
        entity = Entity(entity_type="org", name="Test")
        result = ProviderResult(
            provider_name="test",
            raw_data=[{"key": "value"}],
            suggested_entities=[entity],
        )
        assert len(result.raw_data) == 1
        assert len(result.suggested_entities) == 1
