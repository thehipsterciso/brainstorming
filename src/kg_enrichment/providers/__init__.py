"""Data source provider plugins — auto-discovered, extensible, greedy."""

from kg_enrichment.providers.base import BaseProvider
from kg_enrichment.providers.registry import ProviderRegistry

__all__ = ["BaseProvider", "ProviderRegistry"]
