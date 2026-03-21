"""Dynamic data models for knowledge graph entities, relationships, and enrichment tasks.

Types are strings, not enums — they emerge from the data as agents discover them.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any
from uuid import uuid4

from pydantic import BaseModel, Field


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _uuid() -> str:
    return str(uuid4())


class Entity(BaseModel):
    """A node in the knowledge graph. Type is a free-form string."""

    id: str = Field(default_factory=_uuid)
    entity_type: str  # "organization", "person", "domain", "vulnerability", anything
    name: str
    aliases: list[str] = Field(default_factory=list)
    attributes: dict[str, Any] = Field(default_factory=dict)
    sources: list[str] = Field(default_factory=list)
    confidence: float = 1.0
    created_at: datetime = Field(default_factory=_now)
    updated_at: datetime = Field(default_factory=_now)
    enrichment_depth: int = 0  # Hops from the seed entity
    enriched: bool = False  # Has this entity been fully enriched?

    def merge_from(self, other: Entity) -> None:
        """Absorb attributes and aliases from another entity (dedup merge)."""
        for alias in other.aliases:
            if alias not in self.aliases and alias != self.name:
                self.aliases.append(alias)
        if other.name != self.name and other.name not in self.aliases:
            self.aliases.append(other.name)
        for key, value in other.attributes.items():
            if key not in self.attributes:
                self.attributes[key] = value
        for src in other.sources:
            if src not in self.sources:
                self.sources.append(src)
        self.confidence = max(self.confidence, other.confidence)
        self.updated_at = _now()

    def add_source(self, source: str) -> None:
        if source not in self.sources:
            self.sources.append(source)

    def __hash__(self) -> int:
        return hash(self.id)

    def __eq__(self, other: object) -> bool:
        if isinstance(other, Entity):
            return self.id == other.id
        return NotImplemented


class Relationship(BaseModel):
    """A directed edge in the knowledge graph. Type is a free-form string."""

    id: str = Field(default_factory=_uuid)
    rel_type: str  # "subsidiary_of", "employs", "resolves_to", anything
    source_entity_id: str
    target_entity_id: str
    attributes: dict[str, Any] = Field(default_factory=dict)
    sources: list[str] = Field(default_factory=list)
    confidence: float = 1.0
    created_at: datetime = Field(default_factory=_now)

    def __hash__(self) -> int:
        return hash(self.id)

    def __eq__(self, other: object) -> bool:
        if isinstance(other, Relationship):
            return self.id == other.id
        return NotImplemented


class EnrichmentTask(BaseModel):
    """A unit of work for the enrichment loop."""

    id: str = Field(default_factory=_uuid)
    entity_id: str
    provider_hints: list[str] = Field(default_factory=list)  # Suggested providers
    priority: float = 1.0  # Higher = process sooner
    max_depth: int | None = None  # None = unlimited
    context: dict[str, Any] = Field(default_factory=dict)
    created_at: datetime = Field(default_factory=_now)
    completed: bool = False


class ProviderResult(BaseModel):
    """What a provider returns after fetching data."""

    provider_name: str
    raw_data: list[dict[str, Any]] = Field(default_factory=list)
    suggested_entities: list[Entity] = Field(default_factory=list)
    suggested_relationships: list[Relationship] = Field(default_factory=list)
    metadata: dict[str, Any] = Field(default_factory=dict)
    follow_up_tasks: list[EnrichmentTask] = Field(default_factory=list)
    errors: list[str] = Field(default_factory=list)


class AgentResult(BaseModel):
    """Result from an agent's run."""

    entities_added: list[str] = Field(default_factory=list)
    entities_merged: list[tuple[str, str]] = Field(default_factory=list)
    relationships_added: list[str] = Field(default_factory=list)
    tasks_generated: list[EnrichmentTask] = Field(default_factory=list)
    messages: list[str] = Field(default_factory=list)
    raw_response: str = ""


class EnrichmentReport(BaseModel):
    """Summary of a full enrichment run."""

    seed: str
    track: str | None = None
    iterations: int = 0
    entities_total: int = 0
    relationships_total: int = 0
    entity_types: dict[str, int] = Field(default_factory=dict)
    relationship_types: dict[str, int] = Field(default_factory=dict)
    providers_used: list[str] = Field(default_factory=list)
    duration_seconds: float = 0.0
    errors: list[str] = Field(default_factory=list)
