"""Tool definitions for Claude agents.

These are the tools Claude can call during enrichment. They map to
operations on the KnowledgeGraph, ProviderRegistry, and web resources.
"""

from __future__ import annotations

# Tool definitions in Anthropic tool_use format
GRAPH_TOOLS = [
    {
        "name": "add_entity",
        "description": (
            "Add a new entity to the knowledge graph. Entity types are free-form strings "
            "(e.g., 'organization', 'person', 'domain', 'vulnerability', 'filing', etc.). "
            "Use whatever type best describes the entity — types are not constrained."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "entity_type": {
                    "type": "string",
                    "description": "The type of entity (free-form, e.g., 'organization', 'person', 'ip_address')",
                },
                "name": {
                    "type": "string",
                    "description": "Primary name of the entity",
                },
                "aliases": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "Alternative names or identifiers",
                    "default": [],
                },
                "attributes": {
                    "type": "object",
                    "description": "Key-value attributes for the entity (unbounded)",
                    "default": {},
                },
                "confidence": {
                    "type": "number",
                    "description": "Confidence score 0.0-1.0",
                    "default": 1.0,
                },
            },
            "required": ["entity_type", "name"],
        },
    },
    {
        "name": "add_relationship",
        "description": (
            "Add a directed relationship between two entities in the graph. "
            "Relationship types are free-form strings."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "rel_type": {
                    "type": "string",
                    "description": "Type of relationship (e.g., 'subsidiary_of', 'employs', 'resolves_to')",
                },
                "source_entity_id": {
                    "type": "string",
                    "description": "ID of the source entity",
                },
                "target_entity_id": {
                    "type": "string",
                    "description": "ID of the target entity",
                },
                "attributes": {
                    "type": "object",
                    "description": "Additional attributes on the relationship",
                    "default": {},
                },
                "confidence": {
                    "type": "number",
                    "description": "Confidence score 0.0-1.0",
                    "default": 1.0,
                },
            },
            "required": ["rel_type", "source_entity_id", "target_entity_id"],
        },
    },
    {
        "name": "search_graph",
        "description": (
            "Search the knowledge graph for entities matching a query. "
            "Searches across names, aliases, and attributes."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "query": {
                    "type": "string",
                    "description": "Search query (name, alias, or attribute value)",
                },
                "entity_type": {
                    "type": "string",
                    "description": "Optional: filter by entity type",
                },
            },
            "required": ["query"],
        },
    },
    {
        "name": "get_entity_details",
        "description": (
            "Get full details of an entity including all attributes and relationships."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "entity_id": {
                    "type": "string",
                    "description": "The entity ID to look up",
                },
            },
            "required": ["entity_id"],
        },
    },
    {
        "name": "merge_entities",
        "description": (
            "Merge two entities that represent the same real-world thing. "
            "Keeps the first entity and absorbs the second."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "keep_id": {
                    "type": "string",
                    "description": "ID of the entity to keep",
                },
                "remove_id": {
                    "type": "string",
                    "description": "ID of the entity to merge into the kept one",
                },
            },
            "required": ["keep_id", "remove_id"],
        },
    },
    {
        "name": "get_graph_schema",
        "description": (
            "Get the current schema of the knowledge graph — all entity types, "
            "relationship types, counts, and attribute keys discovered so far."
        ),
        "input_schema": {
            "type": "object",
            "properties": {},
        },
    },
]

ENRICHMENT_TOOLS = [
    {
        "name": "query_provider",
        "description": (
            "Query a specific data provider to enrich an entity. "
            "Providers include: sec_edgar, yfinance, dns_whois, web_scraper, "
            "news_feeds, cve_provider, github, custom_file."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "provider_name": {
                    "type": "string",
                    "description": "Name of the provider to query",
                },
                "entity_id": {
                    "type": "string",
                    "description": "ID of the entity to enrich",
                },
            },
            "required": ["provider_name", "entity_id"],
        },
    },
    {
        "name": "list_providers",
        "description": "List all available data providers and their capabilities.",
        "input_schema": {
            "type": "object",
            "properties": {},
        },
    },
    {
        "name": "queue_enrichment",
        "description": (
            "Queue an entity for further enrichment in a future iteration. "
            "Use this when you discover an entity that should be enriched "
            "but you don't want to do it right now."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "entity_id": {
                    "type": "string",
                    "description": "ID of the entity to queue",
                },
                "provider_hints": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "Suggested providers to use",
                    "default": [],
                },
                "priority": {
                    "type": "number",
                    "description": "Priority (higher = sooner). Default 1.0",
                    "default": 1.0,
                },
            },
            "required": ["entity_id"],
        },
    },
    {
        "name": "mark_enriched",
        "description": "Mark an entity as fully enriched (no more data to find).",
        "input_schema": {
            "type": "object",
            "properties": {
                "entity_id": {
                    "type": "string",
                    "description": "ID of the entity to mark as enriched",
                },
            },
            "required": ["entity_id"],
        },
    },
    {
        "name": "get_enrichment_queue",
        "description": "See entities that are pending enrichment.",
        "input_schema": {
            "type": "object",
            "properties": {
                "limit": {
                    "type": "integer",
                    "description": "Max number of entries to return",
                    "default": 20,
                },
            },
        },
    },
]

WEB_TOOLS = [
    {
        "name": "fetch_url",
        "description": (
            "Fetch content from any URL. Returns extracted text content. "
            "Use this to gather data from web pages, APIs, or documents."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "url": {
                    "type": "string",
                    "description": "The URL to fetch",
                },
            },
            "required": ["url"],
        },
    },
]

ALL_TOOLS = GRAPH_TOOLS + ENRICHMENT_TOOLS + WEB_TOOLS
