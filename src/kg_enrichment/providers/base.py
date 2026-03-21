"""Base provider interface — all data source plugins implement this."""

from __future__ import annotations

from abc import ABC, abstractmethod

from kg_enrichment.core.graph import KnowledgeGraph
from kg_enrichment.core.models import Entity, ProviderResult


class BaseProvider(ABC):
    """Interface for data source providers.

    Providers are greedy — they fetch ALL available data for an entity,
    not a predefined subset. New providers are auto-discovered by the
    registry; just subclass BaseProvider in a file under providers/.
    """

    name: str = ""
    description: str = ""
    supported_entity_types: list[str] = ["*"]  # "*" means any type
    requires_api_key: bool = False
    rate_limit: float = 1.0  # Max requests per second

    @abstractmethod
    async def can_enrich(self, entity: Entity) -> bool:
        """Return True if this provider can supply data for this entity."""
        ...

    @abstractmethod
    async def enrich(self, entity: Entity, graph: KnowledgeGraph) -> ProviderResult:
        """Fetch all available data for this entity. Be greedy.

        Returns a ProviderResult with raw data, suggested entities/relationships,
        and follow-up tasks for recursive enrichment.
        """
        ...

    async def search(self, query: str) -> list[Entity]:
        """Optional: search this provider by free-text query."""
        return []

    def __repr__(self) -> str:
        return f"{self.__class__.__name__}(name={self.name!r})"
