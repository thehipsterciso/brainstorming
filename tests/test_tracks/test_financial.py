"""Tests for track profiles."""

from kg_enrichment.core.models import Entity
from kg_enrichment.tracks.financial import FinancialAnalystTrack
from kg_enrichment.tracks.security import SecurityAnalystTrack
from kg_enrichment.tracks.executive import ExecutiveTrack


class TestFinancialTrack:
    def test_name(self):
        track = FinancialAnalystTrack()
        assert track.name == "financial"

    def test_score_organization_high(self):
        track = FinancialAnalystTrack()
        org = Entity(entity_type="organization", name="Test")
        assert track.score_entity(org) >= 4.0

    def test_score_domain_low(self):
        track = FinancialAnalystTrack()
        domain = Entity(entity_type="domain", name="test.com")
        assert track.score_entity(domain) < 3.0

    def test_ticker_boost(self):
        track = FinancialAnalystTrack()
        org_no_ticker = Entity(entity_type="organization", name="Test")
        org_with_ticker = Entity(
            entity_type="organization", name="Test",
            attributes={"ticker": "TST"},
        )
        assert track.score_entity(org_with_ticker) > track.score_entity(org_no_ticker)

    def test_preferred_providers(self):
        track = FinancialAnalystTrack()
        providers = track.preferred_providers()
        assert "sec_edgar" in providers
        assert "yfinance" in providers

    def test_system_prompt(self):
        track = FinancialAnalystTrack()
        prompt = track.get_system_prompt_addition()
        assert "FINANCIAL ANALYST" in prompt
        assert "ownership" in prompt.lower()


class TestSecurityTrack:
    def test_score_domain_high(self):
        track = SecurityAnalystTrack()
        domain = Entity(entity_type="domain", name="test.com")
        assert track.score_entity(domain) >= 4.0

    def test_score_organization_lower(self):
        track = SecurityAnalystTrack()
        org = Entity(entity_type="organization", name="Test")
        assert track.score_entity(org) < track.score_entity(
            Entity(entity_type="domain", name="test.com")
        )

    def test_cvss_boost(self):
        track = SecurityAnalystTrack()
        vuln_low = Entity(
            entity_type="vulnerability", name="CVE-2024-0001",
            attributes={"cvss_score": 3.0},
        )
        vuln_high = Entity(
            entity_type="vulnerability", name="CVE-2024-0002",
            attributes={"cvss_score": 9.5},
        )
        assert track.score_entity(vuln_high) > track.score_entity(vuln_low)


class TestExecutiveTrack:
    def test_balanced_scoring(self):
        track = ExecutiveTrack()
        org = Entity(entity_type="organization", name="Test")
        person = Entity(entity_type="person", name="CEO Test")

        # Executive track scores things more evenly than specialized tracks
        org_score = track.score_entity(org)
        person_score = track.score_entity(person)
        assert org_score > 0
        assert person_score > 0

    def test_ceo_boost(self):
        track = ExecutiveTrack()
        ceo = Entity(entity_type="person", name="Test", attributes={"title": "CEO"})
        regular = Entity(entity_type="person", name="Test", attributes={"title": "Analyst"})
        assert track.score_entity(ceo) > track.score_entity(regular)
