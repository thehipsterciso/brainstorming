"""Tests for graph persistence."""

import tempfile
from pathlib import Path

import pytest

from kg_enrichment.core.graph import KnowledgeGraph
from kg_enrichment.core.models import Entity
from kg_enrichment.core.store import GraphStore


class TestGraphStore:
    def test_save_and_load(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            store = GraphStore(tmpdir)
            graph = KnowledgeGraph()
            graph.add_entity(Entity(entity_type="org", name="Test"))

            path = store.save(graph, name="test")
            assert path.exists()

            loaded = store.load("test")
            assert len(loaded) == 1
            entities = loaded.find_entities(name="Test")
            assert len(entities) == 1

    def test_load_or_create_new(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            store = GraphStore(tmpdir)
            graph = store.load_or_create("nonexistent")
            assert len(graph) == 0

    def test_load_or_create_existing(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            store = GraphStore(tmpdir)
            graph = KnowledgeGraph()
            graph.add_entity(Entity(entity_type="org", name="Saved"))
            store.save(graph, name="existing")

            loaded = store.load_or_create("existing")
            assert len(loaded) == 1

    def test_list_snapshots(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            store = GraphStore(tmpdir)
            graph = KnowledgeGraph()
            store.save(graph, name="snap1")
            store.save(graph, name="snap2")

            snaps = store.list_snapshots()
            assert len(snaps) >= 2

    def test_load_nonexistent_raises(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            store = GraphStore(tmpdir)
            with pytest.raises(FileNotFoundError):
                store.load("nonexistent")
