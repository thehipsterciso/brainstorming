"""Base track interface — role-specific enrichment prioritization.

Tracks shape PRIORITY, not LIMITS. All tracks can discover anything.
A track tells agents what to focus on first, not what they're allowed to find.
"""

from __future__ import annotations

from abc import ABC, abstractmethod

from kg_enrichment.core.models import Entity


class BaseTrack(ABC):
    """Base class for enrichment track profiles.

    A track customizes how agents prioritize enrichment without
    constraining what they can discover. Tracks influence:
    - Which entity types are enriched first (score_entity)
    - Which providers are tried first (preferred_providers)
    - How the agents interpret data (system prompt additions)
    """

    name: str = ""
    description: str = ""

    @abstractmethod
    def get_system_prompt_addition(self) -> str:
        """Additional instructions appended to agent system prompts.

        Should describe the analyst's perspective and what to prioritize.
        This shapes how agents interpret and pursue data.
        """
        ...

    @abstractmethod
    def score_entity(self, entity: Entity) -> float:
        """Score an entity's enrichment priority for this track.

        Higher scores = enrich sooner. Default entities score 1.0.
        Track-relevant entities should score higher (2.0-5.0).
        """
        ...

    @abstractmethod
    def preferred_providers(self) -> list[str]:
        """Providers to try first (all are still available).

        Returns provider names in priority order. Agents will
        query these first but can use any provider.
        """
        ...

    def max_depth_for(self, entity_type: str) -> int | None:
        """Suggested max enrichment depth for an entity type.

        None = unlimited. This is a suggestion, not a hard limit.
        Agents may exceed this if they find critical data.
        """
        return None

    def __repr__(self) -> str:
        return f"{self.__class__.__name__}(name={self.name!r})"
