"""KnowledgeGraph — Dynamic-schema graph engine built on NetworkX.

Entity and relationship types are free-form strings that emerge from agent discovery.
The graph tracks schema statistics dynamically as data is added.
"""

from __future__ import annotations

import json
from collections import Counter
from typing import Any

import networkx as nx

from kg_enrichment.core.models import Entity, Relationship, _now


class KnowledgeGraph:
    """In-memory knowledge graph with dynamic schema, backed by NetworkX MultiDiGraph."""

    def __init__(self) -> None:
        self._graph = nx.MultiDiGraph()
        self._entities: dict[str, Entity] = {}
        self._relationships: dict[str, Relationship] = {}

    # ── Entity operations ──────────────────────────────────────────────

    def add_entity(self, entity: Entity) -> str:
        """Add an entity to the graph. Returns the entity ID."""
        self._entities[entity.id] = entity
        self._graph.add_node(entity.id, **self._entity_node_attrs(entity))
        return entity.id

    def update_entity(self, entity_id: str, updates: dict[str, Any]) -> Entity:
        """Update entity attributes. Returns the updated entity."""
        entity = self._entities[entity_id]
        for key, value in updates.items():
            if key == "attributes":
                entity.attributes.update(value)
            elif key == "aliases":
                for alias in value:
                    if alias not in entity.aliases:
                        entity.aliases.append(alias)
            elif hasattr(entity, key):
                setattr(entity, key, value)
        entity.updated_at = _now()
        self._graph.nodes[entity_id].update(self._entity_node_attrs(entity))
        return entity

    def get_entity(self, entity_id: str) -> Entity | None:
        """Get an entity by ID."""
        return self._entities.get(entity_id)

    def find_entities(
        self,
        entity_type: str | None = None,
        name: str | None = None,
        attribute_filter: dict[str, Any] | None = None,
    ) -> list[Entity]:
        """Find entities matching criteria. All filters are AND-combined."""
        results = list(self._entities.values())
        if entity_type:
            results = [e for e in results if e.entity_type == entity_type]
        if name:
            name_lower = name.lower()
            results = [
                e
                for e in results
                if name_lower in e.name.lower()
                or any(name_lower in a.lower() for a in e.aliases)
            ]
        if attribute_filter:
            results = [
                e
                for e in results
                if all(e.attributes.get(k) == v for k, v in attribute_filter.items())
            ]
        return results

    def search(self, query: str) -> list[Entity]:
        """Fuzzy name search across all entities."""
        query_lower = query.lower()
        scored: list[tuple[float, Entity]] = []
        for entity in self._entities.values():
            score = 0.0
            if query_lower == entity.name.lower():
                score = 1.0
            elif query_lower in entity.name.lower():
                score = 0.8
            elif any(query_lower == a.lower() for a in entity.aliases):
                score = 0.9
            elif any(query_lower in a.lower() for a in entity.aliases):
                score = 0.6
            # Check attribute values too
            elif any(
                query_lower in str(v).lower() for v in entity.attributes.values()
            ):
                score = 0.3
            if score > 0:
                scored.append((score, entity))
        scored.sort(key=lambda x: x[0], reverse=True)
        return [entity for _, entity in scored]

    def merge_entities(self, keep_id: str, remove_id: str) -> Entity:
        """Merge remove_id into keep_id. Redirects all relationships."""
        keep = self._entities[keep_id]
        remove = self._entities[remove_id]
        keep.merge_from(remove)

        # Redirect relationships
        for rel in list(self._relationships.values()):
            if rel.source_entity_id == remove_id:
                rel.source_entity_id = keep_id
            if rel.target_entity_id == remove_id:
                rel.target_entity_id = keep_id

        # Rebuild graph edges
        for _, _, key in list(self._graph.edges(remove_id, keys=True)):
            self._graph.remove_edge(remove_id, _, key=key)
        for _, _, key in list(self._graph.in_edges(remove_id, keys=True)):
            self._graph.remove_edge(_, remove_id, key=key)

        self._graph.remove_node(remove_id)
        del self._entities[remove_id]

        # Re-add redirected edges
        for rel in self._relationships.values():
            if rel.source_entity_id == keep_id or rel.target_entity_id == keep_id:
                if not self._graph.has_node(rel.source_entity_id):
                    continue
                if not self._graph.has_node(rel.target_entity_id):
                    continue
                # Edge may already exist from initial add; skip if so
                existing_keys = [
                    k
                    for _, _, k in self._graph.edges(
                        rel.source_entity_id, keys=True
                    )
                    if _ == rel.target_entity_id
                ]
                if rel.id not in existing_keys:
                    self._graph.add_edge(
                        rel.source_entity_id,
                        rel.target_entity_id,
                        key=rel.id,
                        **self._rel_edge_attrs(rel),
                    )

        self._graph.nodes[keep_id].update(self._entity_node_attrs(keep))
        return keep

    # ── Relationship operations ────────────────────────────────────────

    def add_relationship(self, rel: Relationship) -> str:
        """Add a relationship (edge) to the graph. Returns the relationship ID."""
        if rel.source_entity_id not in self._entities:
            raise ValueError(f"Source entity {rel.source_entity_id} not in graph")
        if rel.target_entity_id not in self._entities:
            raise ValueError(f"Target entity {rel.target_entity_id} not in graph")

        self._relationships[rel.id] = rel
        self._graph.add_edge(
            rel.source_entity_id,
            rel.target_entity_id,
            key=rel.id,
            **self._rel_edge_attrs(rel),
        )
        return rel.id

    def get_relationships(
        self,
        entity_id: str,
        direction: str = "both",
        rel_type: str | None = None,
    ) -> list[Relationship]:
        """Get relationships for an entity. Direction: 'out', 'in', or 'both'."""
        results: list[Relationship] = []
        for rel in self._relationships.values():
            match = False
            if direction in ("out", "both") and rel.source_entity_id == entity_id:
                match = True
            if direction in ("in", "both") and rel.target_entity_id == entity_id:
                match = True
            if match and (rel_type is None or rel.rel_type == rel_type):
                results.append(rel)
        return results

    def get_neighbors(
        self,
        entity_id: str,
        rel_type: str | None = None,
        depth: int = 1,
    ) -> list[Entity]:
        """Get neighboring entities up to N hops away."""
        visited: set[str] = {entity_id}
        frontier: set[str] = {entity_id}

        for _ in range(depth):
            next_frontier: set[str] = set()
            for node_id in frontier:
                rels = self.get_relationships(node_id, direction="both", rel_type=rel_type)
                for rel in rels:
                    neighbor_id = (
                        rel.target_entity_id
                        if rel.source_entity_id == node_id
                        else rel.source_entity_id
                    )
                    if neighbor_id not in visited:
                        visited.add(neighbor_id)
                        next_frontier.add(neighbor_id)
            frontier = next_frontier
            if not frontier:
                break

        visited.discard(entity_id)
        return [self._entities[eid] for eid in visited if eid in self._entities]

    # ── Schema introspection ───────────────────────────────────────────

    def entity_types(self) -> dict[str, int]:
        """Count of entities by type. Types are discovered, not predefined."""
        return dict(Counter(e.entity_type for e in self._entities.values()))

    def relationship_types(self) -> dict[str, int]:
        """Count of relationships by type."""
        return dict(Counter(r.rel_type for r in self._relationships.values()))

    def schema_summary(self) -> dict[str, Any]:
        """Full schema breakdown: types, counts, sample attributes per type."""
        entity_attrs: dict[str, set[str]] = {}
        for e in self._entities.values():
            entity_attrs.setdefault(e.entity_type, set()).update(e.attributes.keys())
        return {
            "entity_types": self.entity_types(),
            "relationship_types": self.relationship_types(),
            "entity_attributes": {k: sorted(v) for k, v in entity_attrs.items()},
            "total_entities": len(self._entities),
            "total_relationships": len(self._relationships),
        }

    # ── Enrichment tracking ────────────────────────────────────────────

    def unenriched_entities(self) -> list[Entity]:
        """Entities not yet marked as enriched."""
        return [e for e in self._entities.values() if not e.enriched]

    def entities_at_depth(self, depth: int) -> list[Entity]:
        """Entities at a specific enrichment depth from seed."""
        return [e for e in self._entities.values() if e.enrichment_depth == depth]

    def mark_enriched(self, entity_id: str) -> None:
        """Mark an entity as fully enriched."""
        if entity_id in self._entities:
            self._entities[entity_id].enriched = True
            self._entities[entity_id].updated_at = _now()

    # ── Traversal & analysis ───────────────────────────────────────────

    def subgraph(self, entity_ids: list[str]) -> KnowledgeGraph:
        """Extract a subgraph containing only the specified entities."""
        sub = KnowledgeGraph()
        for eid in entity_ids:
            if eid in self._entities:
                sub.add_entity(self._entities[eid].model_copy())
        for rel in self._relationships.values():
            if rel.source_entity_id in entity_ids and rel.target_entity_id in entity_ids:
                sub.add_relationship(rel.model_copy())
        return sub

    def connected_components(self) -> list[list[str]]:
        """Find connected components (treating graph as undirected)."""
        undirected = self._graph.to_undirected()
        return [list(c) for c in nx.connected_components(undirected)]

    def shortest_path(self, source_id: str, target_id: str) -> list[str] | None:
        """Find shortest path between two entities."""
        try:
            return nx.shortest_path(self._graph, source_id, target_id)
        except (nx.NetworkXNoPath, nx.NodeNotFound):
            return None

    def stats(self) -> dict[str, Any]:
        """Graph statistics."""
        return {
            "entities": len(self._entities),
            "relationships": len(self._relationships),
            "entity_types": self.entity_types(),
            "relationship_types": self.relationship_types(),
            "connected_components": len(self.connected_components()),
            "enriched": sum(1 for e in self._entities.values() if e.enriched),
            "unenriched": sum(1 for e in self._entities.values() if not e.enriched),
        }

    # ── Serialization ──────────────────────────────────────────────────

    def to_dict(self) -> dict[str, Any]:
        """Serialize the entire graph to a dictionary."""
        return {
            "entities": [e.model_dump(mode="json") for e in self._entities.values()],
            "relationships": [r.model_dump(mode="json") for r in self._relationships.values()],
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> KnowledgeGraph:
        """Restore a graph from a serialized dictionary."""
        graph = cls()
        for entity_data in data.get("entities", []):
            graph.add_entity(Entity.model_validate(entity_data))
        for rel_data in data.get("relationships", []):
            graph.add_relationship(Relationship.model_validate(rel_data))
        return graph

    def to_json(self) -> str:
        """Serialize to JSON string."""
        return json.dumps(self.to_dict(), indent=2, default=str)

    @classmethod
    def from_json(cls, json_str: str) -> KnowledgeGraph:
        """Restore from JSON string."""
        return cls.from_dict(json.loads(json_str))

    # ── Internal helpers ───────────────────────────────────────────────

    @staticmethod
    def _entity_node_attrs(entity: Entity) -> dict[str, Any]:
        return {
            "entity_type": entity.entity_type,
            "name": entity.name,
            "enriched": entity.enriched,
        }

    @staticmethod
    def _rel_edge_attrs(rel: Relationship) -> dict[str, Any]:
        return {
            "rel_type": rel.rel_type,
            "confidence": rel.confidence,
        }

    def __len__(self) -> int:
        return len(self._entities)

    def __contains__(self, entity_id: str) -> bool:
        return entity_id in self._entities

    def __repr__(self) -> str:
        return (
            f"KnowledgeGraph(entities={len(self._entities)}, "
            f"relationships={len(self._relationships)}, "
            f"types={list(self.entity_types().keys())})"
        )
