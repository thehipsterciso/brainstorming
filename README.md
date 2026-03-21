# KG Enrichment AI Agents

AI-driven autonomous knowledge graph enrichment. Seed with a stock ticker, point at
data files, or chat interactively — agents recursively discover and enrich entities
across an unconstrained, dynamic schema.

## Architecture

- **Dynamic schema** — Entity and relationship types emerge from data, not predefined enums
- **Plugin providers** — Drop a `.py` file in `providers/`, it auto-registers
- **Recursive enrichment** — Every new entity becomes a candidate for further enrichment
- **Track prioritization** — Analyst roles shape what agents pursue first, never what they can find
- **Agent autonomy** — Claude agents decide what to chase, when to stop, and how to resolve conflicts

## Quick Start

```bash
# Install
pip install -e ".[dev]"

# Set your API key
export ANTHROPIC_API_KEY=sk-ant-...

# Enrich from a stock ticker
kg-enrich ticker AAPL

# Enrich from a file
kg-enrich ingest data.csv

# Interactive chat enrichment
kg-enrich chat

# Use a specific track
kg-enrich ticker AAPL --track security
```

## Providers

| Provider | Source | API Key? |
|----------|--------|----------|
| SEC EDGAR | Filings, XBRL, officers | No |
| yfinance | Company profile, financials | No |
| DNS/WHOIS | DNS records, domain registration | No |
| Web Scraper | Any URL content extraction | No |
| News Feeds | RSS/Atom aggregation | No |
| CVE/NVD | Vulnerability database | No |
| GitHub | Org/repo intelligence | Optional |
| Custom File | CSV, JSON, JSONL, logs | No |

## Tracks

| Track | Focus |
|-------|-------|
| Financial | Ownership, filings, revenue, risk |
| Security | Attack surface, infrastructure, vulns |
| Compliance | Regulatory exposure, officer relationships |
| Threat Intel | IOCs, threat actor infrastructure |
| Executive | Strategic overview, competitive landscape |

## Exports

```python
from kg_enrichment.core.exporters import to_cypher, to_jsonld, to_graphml

cypher = to_cypher(graph)        # Neo4j import
jsonld = to_jsonld(graph)        # JSON-LD
to_graphml(graph, "output.graphml")
```
