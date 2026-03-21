"""Export KnowledgeGraph to various formats for production use."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import networkx as nx

from kg_enrichment.core.graph import KnowledgeGraph


def to_cypher(graph: KnowledgeGraph) -> str:
    """Export graph as Neo4j Cypher CREATE statements.

    Produces valid Cypher that can be run against a Neo4j instance to
    recreate the entire graph. Entity types become node labels,
    relationship types become edge types.
    """
    lines: list[str] = []

    # Create nodes
    for entity in graph._entities.values():
        label = _cypher_label(entity.entity_type)
        props = {
            "id": entity.id,
            "name": entity.name,
            "aliases": entity.aliases,
            "confidence": entity.confidence,
            "sources": entity.sources,
            "enriched": entity.enriched,
            "enrichment_depth": entity.enrichment_depth,
            **entity.attributes,
        }
        props_str = _cypher_props(props)
        lines.append(f"CREATE (n{_short_id(entity.id)}:{label} {props_str});")

    # Create relationships
    for rel in graph._relationships.values():
        rel_label = rel.rel_type.upper().replace(" ", "_")
        props = {
            "id": rel.id,
            "confidence": rel.confidence,
            "sources": rel.sources,
            **rel.attributes,
        }
        props_str = _cypher_props(props)
        src = _short_id(rel.source_entity_id)
        tgt = _short_id(rel.target_entity_id)
        lines.append(
            f"MATCH (a {{id: '{rel.source_entity_id}'}}), "
            f"(b {{id: '{rel.target_entity_id}'}}) "
            f"CREATE (a)-[:{rel_label} {props_str}]->(b);"
        )

    return "\n".join(lines)


def to_jsonld(graph: KnowledgeGraph) -> dict[str, Any]:
    """Export graph as JSON-LD document."""
    nodes = []
    for entity in graph._entities.values():
        node: dict[str, Any] = {
            "@id": f"urn:kg:{entity.id}",
            "@type": entity.entity_type,
            "name": entity.name,
            "aliases": entity.aliases,
            "confidence": entity.confidence,
            "sources": entity.sources,
        }
        node.update(entity.attributes)
        nodes.append(node)

    edges = []
    for rel in graph._relationships.values():
        edge: dict[str, Any] = {
            "@type": rel.rel_type,
            "source": f"urn:kg:{rel.source_entity_id}",
            "target": f"urn:kg:{rel.target_entity_id}",
            "confidence": rel.confidence,
        }
        edge.update(rel.attributes)
        edges.append(edge)

    return {
        "@context": {
            "@vocab": "https://schema.org/",
            "kg": "urn:kg:",
        },
        "@graph": nodes,
        "relationships": edges,
    }


def to_graphml(graph: KnowledgeGraph, path: str | Path) -> None:
    """Export graph as GraphML file (compatible with Gephi, yEd, etc.)."""
    g = nx.MultiDiGraph()

    for entity in graph._entities.values():
        g.add_node(
            entity.id,
            label=entity.name,
            entity_type=entity.entity_type,
            confidence=str(entity.confidence),
        )

    for rel in graph._relationships.values():
        g.add_edge(
            rel.source_entity_id,
            rel.target_entity_id,
            key=rel.id,
            label=rel.rel_type,
            rel_type=rel.rel_type,
            confidence=str(rel.confidence),
        )

    nx.write_graphml(g, str(path))


def to_gexf(graph: KnowledgeGraph, path: str | Path) -> None:
    """Export graph as GEXF file (compatible with Gephi)."""
    g = nx.MultiDiGraph()

    for entity in graph._entities.values():
        g.add_node(
            entity.id,
            label=entity.name,
            entity_type=entity.entity_type,
        )

    for rel in graph._relationships.values():
        g.add_edge(
            rel.source_entity_id,
            rel.target_entity_id,
            key=rel.id,
            label=rel.rel_type,
        )

    nx.write_gexf(g, str(path))


# ── Internal helpers ─────────────────────────────────────────────────


def _cypher_label(entity_type: str) -> str:
    """Convert entity type to a valid Cypher label."""
    return "".join(word.capitalize() for word in entity_type.replace("-", "_").split("_"))


def _short_id(entity_id: str) -> str:
    """Short variable name for Cypher."""
    return entity_id.replace("-", "")[:8]


def _cypher_props(props: dict[str, Any]) -> str:
    """Format a dict as Cypher properties."""
    parts = []
    for key, value in props.items():
        if value is None:
            continue
        key = key.replace(" ", "_").replace("-", "_")
        if isinstance(value, str):
            escaped = value.replace("'", "\\'")
            parts.append(f"{key}: '{escaped}'")
        elif isinstance(value, bool):
            parts.append(f"{key}: {'true' if value else 'false'}")
        elif isinstance(value, (int, float)):
            parts.append(f"{key}: {value}")
        elif isinstance(value, list):
            items = ", ".join(
                f"'{str(v).replace(chr(39), chr(92)+chr(39))}'" for v in value
            )
            parts.append(f"{key}: [{items}]")
    return "{" + ", ".join(parts) + "}"
