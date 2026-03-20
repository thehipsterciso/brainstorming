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
    NICEAdapter,
    DMBOKAdapter,
    DCAMAdapter,
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


class TestNICEAdapter:
    def test_parse_task(self):
        p = NICEAdapter.parse("T0001")
        assert p.components == ["T", "0001"]
        assert p.metadata["type_name"] == "Task"

    def test_parse_knowledge(self):
        p = NICEAdapter.parse("K0233")
        assert p.components == ["K", "0233"]
        assert p.metadata["type_name"] == "Knowledge"

    def test_parse_skill(self):
        p = NICEAdapter.parse("S0015")
        assert p.metadata["type_name"] == "Skill"

    def test_parse_ability(self):
        p = NICEAdapter.parse("A0001")
        assert p.metadata["type_name"] == "Ability"

    def test_validate(self):
        assert NICEAdapter.validate("T0001")
        assert NICEAdapter.validate("K0233")
        assert not NICEAdapter.validate("X0001")  # invalid type
        assert not NICEAdapter.validate("T001")   # too few digits

    def test_parse_invalid_raises(self):
        with pytest.raises(ValueError):
            NICEAdapter.parse("Z9999")


class TestDMBOKAdapter:
    def test_parse_topic(self):
        p = DMBOKAdapter.parse("1.3")
        assert p.components == ["1", "3"]
        assert p.hierarchy_level == 1

    def test_parse_subtopic(self):
        p = DMBOKAdapter.parse("14.1.1")
        assert p.components == ["14", "1", "1"]
        assert p.hierarchy_level == 2

    def test_validate(self):
        assert DMBOKAdapter.validate("1.3")
        assert DMBOKAdapter.validate("14.1.1")
        assert not DMBOKAdapter.validate("DMBOK-1")

    def test_parse_invalid_raises(self):
        with pytest.raises(ValueError):
            DMBOKAdapter.parse("bad")


class TestDCAMAdapter:
    def test_parse_capability(self):
        p = DCAMAdapter.parse("1.1")
        assert p.components == ["1", "1"]
        assert p.hierarchy_level == 1

    def test_parse_sub_capability(self):
        p = DCAMAdapter.parse("7.3.2")
        assert p.components == ["7", "3", "2"]
        assert p.hierarchy_level == 2

    def test_validate(self):
        assert DCAMAdapter.validate("1.1")
        assert DCAMAdapter.validate("7.3.2")
        assert not DCAMAdapter.validate("DCAM-1")

    def test_parse_invalid_raises(self):
        with pytest.raises(ValueError):
            DCAMAdapter.parse("bad")


class TestRegistryFunctions:
    def test_all_adapters_registered(self):
        expected = {"CSF2", "SP800-53", "AI-RMF", "ISO27001", "CISv8", "COBIT2019", "NICE", "DMBOK", "DCAM"}
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
