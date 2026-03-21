"""Tests for the provider registry."""

from kg_enrichment.core.models import Entity
from kg_enrichment.providers.base import BaseProvider
from kg_enrichment.providers.registry import ProviderRegistry


class TestProviderRegistry:
    def test_auto_discover(self):
        registry = ProviderRegistry(auto_discover=True)
        assert len(registry) > 0
        assert "sec_edgar" in registry.names()
        assert "yfinance" in registry.names()
        assert "dns_whois" in registry.names()

    def test_manual_register(self):
        registry = ProviderRegistry(auto_discover=False)
        assert len(registry) == 0

        class FakeProvider(BaseProvider):
            name = "fake"
            description = "Test"

            async def can_enrich(self, entity):
                return True

            async def enrich(self, entity, graph):
                from kg_enrichment.core.models import ProviderResult
                return ProviderResult(provider_name=self.name)

        registry.register(FakeProvider())
        assert len(registry) == 1
        assert registry.get_by_name("fake") is not None

    def test_get_providers_for_entity(self):
        registry = ProviderRegistry(auto_discover=True)
        org_entity = Entity(entity_type="organization", name="Test Corp")
        providers = registry.get_providers_for(org_entity)
        provider_names = [p.name for p in providers]
        assert "sec_edgar" in provider_names or "yfinance" in provider_names

    def test_get_by_name(self):
        registry = ProviderRegistry(auto_discover=True)
        provider = registry.get_by_name("sec_edgar")
        assert provider is not None
        assert provider.name == "sec_edgar"

    def test_get_nonexistent_provider(self):
        registry = ProviderRegistry(auto_discover=True)
        assert registry.get_by_name("nonexistent") is None
