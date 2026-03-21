"""Persistence layer for knowledge graph snapshots."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from kg_enrichment.core.graph import KnowledgeGraph


class GraphStore:
    """Persists KnowledgeGraph snapshots to disk as JSON files."""

    def __init__(self, store_dir: str | Path = "./kg_data") -> None:
        self.store_dir = Path(store_dir)
        self.store_dir.mkdir(parents=True, exist_ok=True)

    def save(self, graph: KnowledgeGraph, name: str = "default") -> Path:
        """Save a graph snapshot. Returns the file path."""
        timestamp = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
        filename = f"{name}_{timestamp}.json"
        filepath = self.store_dir / filename
        filepath.write_text(graph.to_json(), encoding="utf-8")

        # Also update the "latest" symlink
        latest = self.store_dir / f"{name}_latest.json"
        latest.write_text(graph.to_json(), encoding="utf-8")

        return filepath

    def load(self, name: str = "default", version: str = "latest") -> KnowledgeGraph:
        """Load a graph snapshot. Use version='latest' or a specific timestamp."""
        if version == "latest":
            filepath = self.store_dir / f"{name}_latest.json"
        else:
            filepath = self.store_dir / f"{name}_{version}.json"

        if not filepath.exists():
            raise FileNotFoundError(f"No snapshot found at {filepath}")

        return KnowledgeGraph.from_json(filepath.read_text(encoding="utf-8"))

    def list_snapshots(self, name: str | None = None) -> list[dict[str, Any]]:
        """List available snapshots."""
        snapshots = []
        for path in sorted(self.store_dir.glob("*.json")):
            if path.name.endswith("_latest.json"):
                continue
            parts = path.stem.rsplit("_", 2)
            if len(parts) >= 3:
                snap_name = parts[0]
                timestamp = f"{parts[1]}_{parts[2]}"
            else:
                snap_name = path.stem
                timestamp = "unknown"

            if name and snap_name != name:
                continue

            snapshots.append({
                "name": snap_name,
                "timestamp": timestamp,
                "path": str(path),
                "size_bytes": path.stat().st_size,
            })
        return snapshots

    def load_or_create(self, name: str = "default") -> KnowledgeGraph:
        """Load existing snapshot or create a fresh graph."""
        try:
            return self.load(name)
        except FileNotFoundError:
            return KnowledgeGraph()
