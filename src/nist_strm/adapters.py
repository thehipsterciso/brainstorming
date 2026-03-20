"""Framework identifier adapters.

Normalizes identifier schemes from various cybersecurity frameworks
into a common internal representation while preserving originals
for OLIR submission compatibility.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import ClassVar

from nist_strm.models import FrameworkDocument, FrameworkElement


@dataclass
class ParsedIdentifier:
    """A normalized, parsed framework element identifier."""

    framework: str
    raw: str
    components: list[str]
    hierarchy_level: int
    metadata: dict[str, str] | None = None

    @property
    def normalized(self) -> str:
        """Stable normalized form for internal use."""
        return f"{self.framework}:{self.raw}"


class IdentifierAdapter:
    """Base class for framework identifier adapters."""

    framework_name: ClassVar[str] = ""
    identifier_pattern: ClassVar[str] = ""

    @classmethod
    def parse(cls, identifier: str) -> ParsedIdentifier:
        raise NotImplementedError

    @classmethod
    def validate(cls, identifier: str) -> bool:
        return bool(re.match(cls.identifier_pattern, identifier))


class CSF2Adapter(IdentifierAdapter):
    """NIST CSF 2.0: {FN}.{CAT}-{##} (e.g., GV.OC-01)"""

    framework_name: ClassVar[str] = "CSF2"
    identifier_pattern: ClassVar[str] = r"^[A-Z]{2}\.[A-Z]{2}-\d{2}$"

    @classmethod
    def parse(cls, identifier: str) -> ParsedIdentifier:
        match = re.match(r"^([A-Z]{2})\.([A-Z]{2})-(\d{2})$", identifier)
        if not match:
            raise ValueError(f"Invalid CSF 2.0 identifier: {identifier}")
        function, category, number = match.groups()
        return ParsedIdentifier(
            framework="CSF2",
            raw=identifier,
            components=[function, category, number],
            hierarchy_level=2,  # subcategory
        )


class SP80053Adapter(IdentifierAdapter):
    """NIST SP 800-53: {FAM}-{#}({enh}) (e.g., AC-2, AC-2(1))"""

    framework_name: ClassVar[str] = "SP800-53"
    identifier_pattern: ClassVar[str] = r"^[A-Z]{2}-\d+(\(\d+\))?$"

    @classmethod
    def parse(cls, identifier: str) -> ParsedIdentifier:
        match = re.match(r"^([A-Z]{2})-(\d+)(?:\((\d+)\))?$", identifier)
        if not match:
            raise ValueError(f"Invalid SP 800-53 identifier: {identifier}")
        family, control, enhancement = match.groups()
        components = [family, control]
        level = 1  # control
        if enhancement:
            components.append(enhancement)
            level = 2  # enhancement
        return ParsedIdentifier(
            framework="SP800-53",
            raw=identifier,
            components=components,
            hierarchy_level=level,
        )


class AIRMFAdapter(IdentifierAdapter):
    """NIST AI RMF: {FUNCTION} {#}.{#} (e.g., GOVERN 1.1)"""

    framework_name: ClassVar[str] = "AI-RMF"
    identifier_pattern: ClassVar[str] = r"^[A-Z]+ \d+\.\d+$"

    @classmethod
    def parse(cls, identifier: str) -> ParsedIdentifier:
        match = re.match(r"^([A-Z]+) (\d+)\.(\d+)$", identifier)
        if not match:
            raise ValueError(f"Invalid AI RMF identifier: {identifier}")
        function, category, subcategory = match.groups()
        return ParsedIdentifier(
            framework="AI-RMF",
            raw=identifier,
            components=[function, category, subcategory],
            hierarchy_level=2,
        )


class ISO27001Adapter(IdentifierAdapter):
    """ISO 27001:2022: A.{theme}.{#} (e.g., A.5.1)"""

    framework_name: ClassVar[str] = "ISO27001"
    identifier_pattern: ClassVar[str] = r"^A\.\d+\.\d+$"

    @classmethod
    def parse(cls, identifier: str) -> ParsedIdentifier:
        match = re.match(r"^A\.(\d+)\.(\d+)$", identifier)
        if not match:
            raise ValueError(f"Invalid ISO 27001 identifier: {identifier}")
        theme, control = match.groups()
        return ParsedIdentifier(
            framework="ISO27001",
            raw=identifier,
            components=["A", theme, control],
            hierarchy_level=2,
        )


class CISControlsAdapter(IdentifierAdapter):
    """CIS Controls v8: {control}.{safeguard} (e.g., 4.6)"""

    framework_name: ClassVar[str] = "CISv8"
    identifier_pattern: ClassVar[str] = r"^\d+\.\d+$"

    @classmethod
    def parse(cls, identifier: str) -> ParsedIdentifier:
        match = re.match(r"^(\d+)\.(\d+)$", identifier)
        if not match:
            raise ValueError(f"Invalid CIS Controls identifier: {identifier}")
        control, safeguard = match.groups()
        return ParsedIdentifier(
            framework="CISv8",
            raw=identifier,
            components=[control, safeguard],
            hierarchy_level=1,
        )


class COBIT2019Adapter(IdentifierAdapter):
    """COBIT 2019: {domain}{##} (e.g., APO01)"""

    framework_name: ClassVar[str] = "COBIT2019"
    identifier_pattern: ClassVar[str] = r"^[A-Z]{2,4}\d{2}$"

    @classmethod
    def parse(cls, identifier: str) -> ParsedIdentifier:
        match = re.match(r"^([A-Z]{2,4})(\d{2})$", identifier)
        if not match:
            raise ValueError(f"Invalid COBIT 2019 identifier: {identifier}")
        domain, process = match.groups()
        return ParsedIdentifier(
            framework="COBIT2019",
            raw=identifier,
            components=[domain, process],
            hierarchy_level=1,
        )


class NICEAdapter(IdentifierAdapter):
    """NICE Workforce Framework: {Type}{####} (e.g., T0001, K0233, S0015, A0001)

    Type codes: T=Task, K=Knowledge, S=Skill, A=Ability
    """

    framework_name: ClassVar[str] = "NICE"
    identifier_pattern: ClassVar[str] = r"^[TKSA]\d{4}$"

    @classmethod
    def parse(cls, identifier: str) -> ParsedIdentifier:
        match = re.match(r"^([TKSA])(\d{4})$", identifier)
        if not match:
            raise ValueError(f"Invalid NICE identifier: {identifier}")
        type_code, number = match.groups()
        type_names = {"T": "Task", "K": "Knowledge", "S": "Skill", "A": "Ability"}
        return ParsedIdentifier(
            framework="NICE",
            raw=identifier,
            components=[type_code, number],
            hierarchy_level=1,
            metadata={"type_name": type_names.get(type_code, type_code)},
        )


class DMBOKAdapter(IdentifierAdapter):
    """DAMA DMBOK2: {KA}.{topic}.{subtopic} (e.g., 1.3.2, 14.1.1)

    Knowledge Areas 1-14 (Data Governance, Data Architecture, etc.)
    """

    framework_name: ClassVar[str] = "DMBOK"
    identifier_pattern: ClassVar[str] = r"^\d{1,2}\.\d+(\.\d+)?$"

    @classmethod
    def parse(cls, identifier: str) -> ParsedIdentifier:
        match = re.match(r"^(\d{1,2})\.(\d+)(?:\.(\d+))?$", identifier)
        if not match:
            raise ValueError(f"Invalid DMBOK identifier: {identifier}")
        ka, topic, subtopic = match.groups()
        components = [ka, topic]
        level = 1
        if subtopic:
            components.append(subtopic)
            level = 2
        return ParsedIdentifier(
            framework="DMBOK",
            raw=identifier,
            components=components,
            hierarchy_level=level,
        )


class DCAMAdapter(IdentifierAdapter):
    """EDM Council DCAM: {Component}.{Capability}.{Sub} (e.g., 1.1, 1.1.1, 7.3.2)

    Components 1-8 (Strategy, Program, Governance, Architecture, Technology, etc.)
    """

    framework_name: ClassVar[str] = "DCAM"
    identifier_pattern: ClassVar[str] = r"^\d+\.\d+(\.\d+)?$"

    @classmethod
    def parse(cls, identifier: str) -> ParsedIdentifier:
        match = re.match(r"^(\d+)\.(\d+)(?:\.(\d+))?$", identifier)
        if not match:
            raise ValueError(f"Invalid DCAM identifier: {identifier}")
        component, capability, sub = match.groups()
        components = [component, capability]
        level = 1  # capability level
        if sub:
            components.append(sub)
            level = 2  # sub-capability
        return ParsedIdentifier(
            framework="DCAM",
            raw=identifier,
            components=components,
            hierarchy_level=level,
        )


class CDMCAdapter(IdentifierAdapter):
    """EDM Council CDMC: {Component}.{Capability}.{Sub} (e.g., 1.2, 3.1.4)

    6 components, 14 capabilities, 37 sub-capabilities for cloud data management.
    Components: 1=Governance & Accountability, 2=Cataloguing & Classification,
    3=Accessibility & Usage, 4=Protection & Privacy, 5=Lifecycle, 6=Technical Architecture
    """

    framework_name: ClassVar[str] = "CDMC"
    identifier_pattern: ClassVar[str] = r"^\d\.\d{1,2}(\.\d{1,2})?$"

    @classmethod
    def parse(cls, identifier: str) -> ParsedIdentifier:
        match = re.match(r"^(\d)\.(\d{1,2})(?:\.(\d{1,2}))?$", identifier)
        if not match:
            raise ValueError(f"Invalid CDMC identifier: {identifier}")
        component, capability, sub = match.groups()
        components = [component, capability]
        level = 1  # capability
        if sub:
            components.append(sub)
            level = 2  # sub-capability
        return ParsedIdentifier(
            framework="CDMC",
            raw=identifier,
            components=components,
            hierarchy_level=level,
        )


class ISO42001Adapter(IdentifierAdapter):
    """ISO/IEC 42001:2023 AI Management System: A.{domain}.{control} (e.g., A.2.1, A.9.4)

    9 Annex A domains with 38 total controls for AI governance.
    """

    framework_name: ClassVar[str] = "ISO42001"
    identifier_pattern: ClassVar[str] = r"^A\.\d{1,2}\.\d{1,2}$"

    @classmethod
    def parse(cls, identifier: str) -> ParsedIdentifier:
        match = re.match(r"^A\.(\d{1,2})\.(\d{1,2})$", identifier)
        if not match:
            raise ValueError(f"Invalid ISO 42001 identifier: {identifier}")
        domain, control = match.groups()
        return ParsedIdentifier(
            framework="ISO42001",
            raw=identifier,
            components=["A", domain, control],
            hierarchy_level=2,
        )


class OECDAIPrinciplesAdapter(IdentifierAdapter):
    """OECD AI Principles: {section}.{principle} (e.g., 1.1, 2.5)

    Section 1 = Values-based principles (1.1-1.5)
    Section 2 = Policy recommendations (2.1-2.5)
    """

    framework_name: ClassVar[str] = "OECD-AI"
    identifier_pattern: ClassVar[str] = r"^[12]\.[1-5]$"

    @classmethod
    def parse(cls, identifier: str) -> ParsedIdentifier:
        match = re.match(r"^([12])\.([1-5])$", identifier)
        if not match:
            raise ValueError(f"Invalid OECD AI Principles identifier: {identifier}")
        section, principle = match.groups()
        section_names = {"1": "Values", "2": "Policy"}
        return ParsedIdentifier(
            framework="OECD-AI",
            raw=identifier,
            components=[section, principle],
            hierarchy_level=1,
            metadata={"section_type": section_names[section]},
        )


class CSAAICMAdapter(IdentifierAdapter):
    """CSA AI Controls Matrix (AICM): {DOMAIN}-{##} (e.g., AIS-01, MDS-03, DSP-12)

    18 security domains, 243 control objectives. Extends CSA CCM naming convention.
    """

    framework_name: ClassVar[str] = "CSA-AICM"
    identifier_pattern: ClassVar[str] = r"^[A-Z]{2,4}-\d{2}$"

    @classmethod
    def parse(cls, identifier: str) -> ParsedIdentifier:
        match = re.match(r"^([A-Z]{2,4})-(\d{2})$", identifier)
        if not match:
            raise ValueError(f"Invalid CSA AICM identifier: {identifier}")
        domain, control_num = match.groups()
        return ParsedIdentifier(
            framework="CSA-AICM",
            raw=identifier,
            components=[domain, control_num],
            hierarchy_level=1,
        )


# Registry of available adapters
ADAPTER_REGISTRY: dict[str, type[IdentifierAdapter]] = {
    "CSF2": CSF2Adapter,
    "SP800-53": SP80053Adapter,
    "AI-RMF": AIRMFAdapter,
    "ISO27001": ISO27001Adapter,
    "CISv8": CISControlsAdapter,
    "COBIT2019": COBIT2019Adapter,
    "NICE": NICEAdapter,
    "DMBOK": DMBOKAdapter,
    "DCAM": DCAMAdapter,
    "CDMC": CDMCAdapter,
    "ISO42001": ISO42001Adapter,
    "OECD-AI": OECDAIPrinciplesAdapter,
    "CSA-AICM": CSAAICMAdapter,
}


def get_adapter(framework: str) -> type[IdentifierAdapter]:
    """Get the identifier adapter for a framework."""
    adapter = ADAPTER_REGISTRY.get(framework)
    if adapter is None:
        raise ValueError(
            f"No adapter registered for framework '{framework}'. "
            f"Available: {list(ADAPTER_REGISTRY.keys())}"
        )
    return adapter


def parse_identifier(framework: str, identifier: str) -> ParsedIdentifier:
    """Parse an identifier using the appropriate framework adapter."""
    return get_adapter(framework).parse(identifier)


def validate_identifier(framework: str, identifier: str) -> bool:
    """Validate an identifier against the appropriate framework pattern."""
    return get_adapter(framework).validate(identifier)
