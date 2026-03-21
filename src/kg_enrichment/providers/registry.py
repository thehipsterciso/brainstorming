"""Provider registry — auto-discovers and manages provider plugins."""

from __future__ import annotations

import importlib
import inspect
import pkgutil
from pathlib import Path

from kg_enrichment.core.models import Entity
from kg_enrichment.providers.base import BaseProvider


class ProviderRegistry:
    """Auto-discovers BaseProvider subclasses from the providers/ package.

    Drop a .py file with a BaseProvider subclass into providers/ and it
    will be discovered automatically. No registration code needed.
    """

    def __init__(self, auto_discover: bool = True) -> None:
        self._providers: dict[str, BaseProvider] = {}
        if auto_discover:
            self.discover()

    def discover(self) -> None:
        """Scan the providers package for BaseProvider subclasses."""
        package_path = Path(__file__).parent
        package_name = "kg_enrichment.providers"

        for _, module_name, _ in pkgutil.iter_modules([str(package_path)]):
            if module_name in ("base", "registry", "__init__"):
                continue
            try:
                module = importlib.import_module(f"{package_name}.{module_name}")
                for _, obj in inspect.getmembers(module, inspect.isclass):
                    if (
                        issubclass(obj, BaseProvider)
                        and obj is not BaseProvider
                        and obj.name  # Must have a name set
                    ):
                        self.register(obj())
            except Exception as e:
                # Don't crash on broken providers — log and skip
                print(f"Warning: Failed to load provider {module_name}: {e}")

    def register(self, provider: BaseProvider) -> None:
        """Manually register a provider instance."""
        self._providers[provider.name] = provider

    def get_providers_for(self, entity: Entity) -> list[BaseProvider]:
        """Get all providers that can potentially enrich this entity type."""
        results = []
        for provider in self._providers.values():
            if "*" in provider.supported_entity_types:
                results.append(provider)
            elif entity.entity_type in provider.supported_entity_types:
                results.append(provider)
        return results

    def get_all(self) -> list[BaseProvider]:
        """Get all registered providers."""
        return list(self._providers.values())

    def get_by_name(self, name: str) -> BaseProvider | None:
        """Get a provider by its name."""
        return self._providers.get(name)

    def names(self) -> list[str]:
        """List all registered provider names."""
        return list(self._providers.keys())

    def __len__(self) -> int:
        return len(self._providers)

    def __repr__(self) -> str:
        return f"ProviderRegistry(providers={self.names()})"
