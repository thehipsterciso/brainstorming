"""Custom file ingestion provider — CSV, JSON, JSONL, and log files.

This provider handles user-supplied data files. It normalizes records into
a common format and lets the extraction agent determine entity types from content.
"""

from __future__ import annotations

import csv
import io
import json
import logging
from pathlib import Path
from typing import Any

from kg_enrichment.core.graph import KnowledgeGraph
from kg_enrichment.core.models import Entity, ProviderResult
from kg_enrichment.providers.base import BaseProvider

logger = logging.getLogger(__name__)


class CustomFileProvider(BaseProvider):
    name = "custom_file"
    description = "Ingest CSV, JSON, JSONL, and log files from user-provided data sources"
    supported_entity_types = ["*"]
    requires_api_key = False
    rate_limit = 100.0  # Local files, no rate limit

    async def can_enrich(self, entity: Entity) -> bool:
        return entity.entity_type in ("file", "data_source")

    async def enrich(self, entity: Entity, graph: KnowledgeGraph) -> ProviderResult:
        file_path = entity.attributes.get("path") or entity.name
        return await self.ingest_file(file_path)

    async def ingest_file(self, file_path: str, file_type: str = "auto") -> ProviderResult:
        """Ingest a file and return normalized records."""
        result = ProviderResult(provider_name=self.name)
        path = Path(file_path)

        if not path.exists():
            result.errors.append(f"File not found: {file_path}")
            return result

        if file_type == "auto":
            file_type = self._detect_type(path)

        try:
            if file_type == "csv":
                records = self._read_csv(path)
            elif file_type == "json":
                records = self._read_json(path)
            elif file_type == "jsonl":
                records = self._read_jsonl(path)
            elif file_type == "log":
                records = self._read_log(path)
            elif file_type == "txt":
                records = self._read_text(path)
            elif file_type == "pdf":
                records = self._read_pdf(path)
            else:
                records = self._read_text(path)

            result.raw_data = records
            result.metadata = {
                "file": str(path),
                "file_type": file_type,
                "records": len(records),
            }

        except Exception as e:
            logger.error(f"Failed to ingest {file_path}: {e}")
            result.errors.append(f"Ingestion error: {e}")

        return result

    async def search(self, query: str) -> list[Entity]:
        """Create a file entity for a given path."""
        path = Path(query)
        if path.exists():
            return [Entity(
                entity_type="file",
                name=str(path),
                attributes={"path": str(path), "size": path.stat().st_size},
                sources=["custom_file"],
            )]
        return []

    def _detect_type(self, path: Path) -> str:
        suffix = path.suffix.lower()
        type_map = {
            ".csv": "csv",
            ".tsv": "csv",
            ".json": "json",
            ".jsonl": "jsonl",
            ".ndjson": "jsonl",
            ".log": "log",
            ".txt": "txt",
            ".pdf": "pdf",
        }
        return type_map.get(suffix, "txt")

    def _read_csv(self, path: Path) -> list[dict[str, Any]]:
        text = path.read_text(encoding="utf-8", errors="replace")
        dialect = csv.Sniffer().sniff(text[:4096])
        reader = csv.DictReader(io.StringIO(text), dialect=dialect)
        return [dict(row) for row in reader]

    def _read_json(self, path: Path) -> list[dict[str, Any]]:
        data = json.loads(path.read_text(encoding="utf-8"))
        if isinstance(data, list):
            return [item if isinstance(item, dict) else {"value": item} for item in data]
        if isinstance(data, dict):
            return [data]
        return [{"value": data}]

    def _read_jsonl(self, path: Path) -> list[dict[str, Any]]:
        records = []
        for line in path.read_text(encoding="utf-8", errors="replace").splitlines():
            line = line.strip()
            if line:
                try:
                    obj = json.loads(line)
                    records.append(obj if isinstance(obj, dict) else {"value": obj})
                except json.JSONDecodeError:
                    records.append({"raw_line": line})
        return records

    def _read_log(self, path: Path) -> list[dict[str, Any]]:
        """Parse log files — tries JSON first, then raw lines."""
        records = []
        for line in path.read_text(encoding="utf-8", errors="replace").splitlines():
            line = line.strip()
            if not line:
                continue
            try:
                records.append(json.loads(line))
            except json.JSONDecodeError:
                records.append({"raw_line": line, "type": "log_entry"})
        return records

    def _read_text(self, path: Path) -> list[dict[str, Any]]:
        text = path.read_text(encoding="utf-8", errors="replace")
        # Return as single record with full text for agent extraction
        return [{"text": text, "source": str(path)}]

    def _read_pdf(self, path: Path) -> list[dict[str, Any]]:
        try:
            import pdfplumber
        except ImportError:
            return [{"error": "pdfplumber not installed", "source": str(path)}]

        records = []
        with pdfplumber.open(path) as pdf:
            for i, page in enumerate(pdf.pages):
                text = page.extract_text() or ""
                tables = page.extract_tables() or []
                record: dict[str, Any] = {
                    "page": i + 1,
                    "text": text,
                    "source": str(path),
                }
                if tables:
                    record["tables"] = tables
                records.append(record)
        return records
