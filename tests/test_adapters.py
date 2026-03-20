"""Tests for framework identifier adapters."""

import pytest

from nist_strm.adapters import (
    ADAPTER_REGISTRY,
    CSF2Adapter,
    SP80053Adapter,
    AIRMFAdapter,
    ISO27001Adapter,
    CISControlsAdapter,
    COBIT2019Adapter,
    parse_identifier,
    validate_identifier,
)


class TestCSF2Adapter:
    def test_parse_valid(self):
        p = CSF2Adapter.parse("GV.OC-01")
        assert p.framework == "CSF2"
        assert p.components == ["GV", "OC", "01"]
        assert p.hierarchy_level == 2

    def test_validate_valid(self):
        assert CSF2Adapter.validate("GV.OC-01")
        assert CSF2Adapter.validate("PR.AC-03")

    def test_validate_invalid(self):
        assert not CSF2Adapter.validate("INVALID")
        assert not CSF2Adapter.validate("GV.OC-1")  # needs two digits

    def test_parse_invalid_raises(self):
        with pytest.raises(ValueError):
            CSF2Adapter.parse("BAD")


class TestSP80053Adapter:
    def test_parse_control(self):
        p = SP80053Adapter.parse("AC-2")
        assert p.components == ["AC", "2"]
        assert p.hierarchy_level == 1

    def test_parse_enhancement(self):
        p = SP80053Adapter.parse("AC-2(1)")
        assert p.components == ["AC", "2", "1"]
        assert p.hierarchy_level == 2

    def test_validate(self):
        assert SP80053Adapter.validate("AC-2")
        assert SP80053Adapter.validate("AC-2(1)")
        assert not SP80053Adapter.validate("AC2")


class TestAIRMFAdapter:
    def test_parse(self):
        p = AIRMFAdapter.parse("GOVERN 1.1")
        assert p.components == ["GOVERN", "1", "1"]

    def test_validate(self):
        assert AIRMFAdapter.validate("GOVERN 1.1")
        assert AIRMFAdapter.validate("MAP 2.3")
        assert not AIRMFAdapter.validate("govern 1.1")


class TestISO27001Adapter:
    def test_parse(self):
        p = ISO27001Adapter.parse("A.5.1")
        assert p.components == ["A", "5", "1"]

    def test_validate(self):
        assert ISO27001Adapter.validate("A.5.1")
        assert not ISO27001Adapter.validate("5.1")


class TestCISControlsAdapter:
    def test_parse(self):
        p = CISControlsAdapter.parse("4.6")
        assert p.components == ["4", "6"]

    def test_validate(self):
        assert CISControlsAdapter.validate("4.6")
        assert not CISControlsAdapter.validate("CIS-4.6")


class TestCOBIT2019Adapter:
    def test_parse(self):
        p = COBIT2019Adapter.parse("APO01")
        assert p.components == ["APO", "01"]

    def test_validate(self):
        assert COBIT2019Adapter.validate("APO01")
        assert COBIT2019Adapter.validate("DSS05")
        assert not COBIT2019Adapter.validate("APO-01")


class TestRegistryFunctions:
    def test_all_adapters_registered(self):
        expected = {"CSF2", "SP800-53", "AI-RMF", "ISO27001", "CISv8", "COBIT2019"}
        assert set(ADAPTER_REGISTRY.keys()) == expected

    def test_parse_identifier_function(self):
        p = parse_identifier("CSF2", "GV.OC-01")
        assert p.normalized == "CSF2:GV.OC-01"

    def test_validate_identifier_function(self):
        assert validate_identifier("SP800-53", "AC-2(1)")
        assert not validate_identifier("SP800-53", "INVALID")

    def test_unknown_framework_raises(self):
        with pytest.raises(ValueError, match="No adapter"):
            parse_identifier("UNKNOWN", "X-1")
