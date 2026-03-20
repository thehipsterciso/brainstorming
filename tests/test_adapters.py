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
    CDMCAdapter,
    ISO42001Adapter,
    OECDAIPrinciplesAdapter,
    CDAMMAdapter,
    CSAAICMAdapter,
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


class TestCDMCAdapter:
    def test_parse_capability(self):
        p = CDMCAdapter.parse("1.2")
        assert p.components == ["1", "2"]
        assert p.hierarchy_level == 1

    def test_parse_sub_capability(self):
        p = CDMCAdapter.parse("3.1.4")
        assert p.components == ["3", "1", "4"]
        assert p.hierarchy_level == 2

    def test_validate(self):
        assert CDMCAdapter.validate("1.2")
        assert CDMCAdapter.validate("6.14.37")
        assert not CDMCAdapter.validate("CDMC-1")

    def test_parse_invalid_raises(self):
        with pytest.raises(ValueError):
            CDMCAdapter.parse("bad")


class TestISO42001Adapter:
    def test_parse(self):
        p = ISO42001Adapter.parse("A.2.1")
        assert p.components == ["A", "2", "1"]
        assert p.hierarchy_level == 2

    def test_parse_higher_domain(self):
        p = ISO42001Adapter.parse("A.9.4")
        assert p.components == ["A", "9", "4"]

    def test_validate(self):
        assert ISO42001Adapter.validate("A.2.1")
        assert ISO42001Adapter.validate("A.9.4")
        assert not ISO42001Adapter.validate("2.1")    # missing A prefix
        assert not ISO42001Adapter.validate("A.2")     # needs control number

    def test_parse_invalid_raises(self):
        with pytest.raises(ValueError):
            ISO42001Adapter.parse("B.1.1")


class TestOECDAIPrinciplesAdapter:
    def test_parse_values(self):
        p = OECDAIPrinciplesAdapter.parse("1.1")
        assert p.components == ["1", "1"]
        assert p.metadata["section_type"] == "Values"

    def test_parse_policy(self):
        p = OECDAIPrinciplesAdapter.parse("2.5")
        assert p.components == ["2", "5"]
        assert p.metadata["section_type"] == "Policy"

    def test_validate(self):
        assert OECDAIPrinciplesAdapter.validate("1.1")
        assert OECDAIPrinciplesAdapter.validate("2.5")
        assert not OECDAIPrinciplesAdapter.validate("3.1")  # only sections 1-2
        assert not OECDAIPrinciplesAdapter.validate("1.6")  # only 1-5

    def test_parse_invalid_raises(self):
        with pytest.raises(ValueError):
            OECDAIPrinciplesAdapter.parse("3.1")


class TestCDAMMAdapter:
    def test_parse_indicator(self):
        p = CDAMMAdapter.parse("DS.03")
        assert p.components == ["DS", "03"]
        assert p.hierarchy_level == 1
        assert p.metadata["dimension_name"] == "Data Strategy"

    def test_parse_sub_indicator(self):
        p = CDAMMAdapter.parse("DG.12.2")
        assert p.components == ["DG", "12", "2"]
        assert p.hierarchy_level == 2
        assert p.metadata["dimension_name"] == "Data Governance"

    def test_parse_analytics(self):
        p = CDAMMAdapter.parse("AN.45")
        assert p.components == ["AN", "45"]
        assert p.metadata["dimension_name"] == "Analytics"

    def test_parse_technology(self):
        p = CDAMMAdapter.parse("TI.08.1")
        assert p.components == ["TI", "08", "1"]
        assert p.metadata["dimension_name"] == "Technology & Infrastructure"

    def test_validate(self):
        assert CDAMMAdapter.validate("DS.03")
        assert CDAMMAdapter.validate("DG.12.2")
        assert CDAMMAdapter.validate("AN.100")  # 200+ indicators
        assert not CDAMMAdapter.validate("CDAMM-1")
        assert not CDAMMAdapter.validate("DS")  # missing indicator

    def test_parse_invalid_raises(self):
        with pytest.raises(ValueError):
            CDAMMAdapter.parse("bad")


class TestCSAAICMAdapter:
    def test_parse(self):
        p = CSAAICMAdapter.parse("AIS-01")
        assert p.components == ["AIS", "01"]
        assert p.hierarchy_level == 1

    def test_parse_model_security(self):
        p = CSAAICMAdapter.parse("MDS-03")
        assert p.components == ["MDS", "03"]

    def test_validate(self):
        assert CSAAICMAdapter.validate("AIS-01")
        assert CSAAICMAdapter.validate("MDS-03")
        assert CSAAICMAdapter.validate("DSP-12")
        assert CSAAICMAdapter.validate("GRC-05")
        assert not CSAAICMAdapter.validate("AIS01")    # missing hyphen
        assert not CSAAICMAdapter.validate("AIS-1")    # needs two digits

    def test_parse_invalid_raises(self):
        with pytest.raises(ValueError):
            CSAAICMAdapter.parse("bad-id")


class TestRegistryFunctions:
    def test_all_adapters_registered(self):
        expected = {
            "CSF2", "SP800-53", "AI-RMF", "ISO27001", "CISv8", "COBIT2019",
            "NICE", "DMBOK", "DCAM", "CDMC", "CDAMM", "ISO42001", "OECD-AI", "CSA-AICM",
        }
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
