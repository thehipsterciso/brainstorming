# nist-strm

A Python library implementing NIST Set Theory Relationship Mapping (STRM) per IR 8477 and IR 8278Ar1.

## Features

- **STRM Core**: Five set-theoretic relationship types with three rationale qualifiers
- **OLIR Data Model**: Full IR 8278Ar1 submission model with 17+ metadata fields
- **Confidence Scoring**: CVSS-inspired vector strings with layered enrichment (STRM-B/BE/BET)
- **Framework Adapters**: Identifier parsing for CSF 2.0, SP 800-53, AI RMF, ISO 27001, CIS Controls, COBIT 2019
- **Provenance**: W3C PROV-JSON compatible provenance records mapped to AU-3 requirements
- **AI Tracking**: Model provenance and human validation per NIST AI 600-1 and EU AI Act Annex IV
- **Audit Trail**: Hash-chained, append-only audit logging (AU-9/AU-10 compliance)

## Installation

```bash
pip install nist-strm
```

With optional dependencies:

```bash
pip install nist-strm[all]   # prov + openpyxl
pip install nist-strm[dev]   # development dependencies
```

## Quick Start

```python
from datetime import date
from nist_strm import (
    STRMEngine,
    FrameworkDocument,
    FrameworkElement,
    SetTheoryRelationship,
    Rationale,
)

engine = STRMEngine()

# Register frameworks
csf = FrameworkDocument(
    id="csf2", title="NIST CSF 2.0", short_name="CSF 2.0",
    version="2.0", author="NIST",
    url="https://www.nist.gov/cyberframework", date=date(2024, 2, 26),
)
engine.register_document(csf)

# Register elements
engine.register_element(FrameworkElement(
    id="csf2-gvoc01", document_id="csf2",
    element_type="subcategory", identifier="GV.OC-01",
    text="The organizational context is understood",
))

# Create STRM mappings
mapping = engine.create_mapping(
    focal_element_id="csf2-gvoc01",
    reference_element_id="sp-ac1",
    relationship=SetTheoryRelationship.SUBSET_OF,
    rationale=Rationale.SEMANTIC,
    strength=8,
)

# Query and export
stats = engine.statistics()
cprt_data = engine.to_cprt_json()
```
