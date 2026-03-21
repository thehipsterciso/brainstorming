"""CLI entry point for kg-enrich command."""

from __future__ import annotations

import asyncio
import json
import os
import sys

import click
from rich.console import Console
from rich.table import Table

console = Console()


def _get_track(track_name: str | None):
    """Load a track by name."""
    if not track_name:
        return None
    tracks = {
        "financial": "kg_enrichment.tracks.financial:FinancialAnalystTrack",
        "security": "kg_enrichment.tracks.security:SecurityAnalystTrack",
        "compliance": "kg_enrichment.tracks.compliance:ComplianceOfficerTrack",
        "threat_intel": "kg_enrichment.tracks.threat_intel:ThreatIntelTrack",
        "executive": "kg_enrichment.tracks.executive:ExecutiveTrack",
    }
    if track_name not in tracks:
        console.print(f"[red]Unknown track: {track_name}[/red]")
        console.print(f"Available tracks: {', '.join(tracks.keys())}")
        sys.exit(1)

    module_path, class_name = tracks[track_name].rsplit(":", 1)
    import importlib
    module = importlib.import_module(module_path)
    return getattr(module, class_name)()


def _create_orchestrator(track_name: str | None = None, store_dir: str = "./kg_data"):
    """Create an Orchestrator with all dependencies."""
    from kg_enrichment.agents.orchestrator import Orchestrator

    track = _get_track(track_name)
    model = os.environ.get("KG_MODEL", "claude-sonnet-4-6")
    return Orchestrator(track=track, model=model, store_dir=store_dir)


@click.group()
@click.version_option(version="0.1.0")
def main():
    """KG Enrichment — AI-driven autonomous knowledge graph enrichment."""
    pass


@main.command()
@click.argument("ticker")
@click.option("--track", "-t", default=None, help="Enrichment track (financial, security, compliance, threat_intel, executive)")
@click.option("--iterations", "-i", default=5, help="Max enrichment iterations")
@click.option("--store-dir", "-s", default="./kg_data", help="Directory for graph snapshots")
def ticker(ticker: str, track: str | None, iterations: int, store_dir: str):
    """Enrich knowledge graph from a stock ticker symbol."""
    console.print(f"[bold]Enriching from ticker: {ticker}[/bold]")
    if track:
        console.print(f"Track: [cyan]{track}[/cyan]")

    orchestrator = _create_orchestrator(track_name=track, store_dir=store_dir)
    report = asyncio.run(orchestrator.enrich_ticker(ticker, max_iterations=iterations))

    _print_report(report)


@main.command()
@click.argument("file_path", type=click.Path(exists=True))
@click.option("--track", "-t", default=None, help="Enrichment track")
@click.option("--iterations", "-i", default=3, help="Max enrichment iterations")
@click.option("--store-dir", "-s", default="./kg_data", help="Directory for graph snapshots")
def ingest(file_path: str, track: str | None, iterations: int, store_dir: str):
    """Ingest a data file and enrich the knowledge graph."""
    console.print(f"[bold]Ingesting: {file_path}[/bold]")

    orchestrator = _create_orchestrator(track_name=track, store_dir=store_dir)
    report = asyncio.run(orchestrator.enrich_file(file_path, max_iterations=iterations))

    _print_report(report)


@main.command()
@click.option("--track", "-t", default=None, help="Enrichment track")
@click.option("--store-dir", "-s", default="./kg_data", help="Directory for graph snapshots")
@click.option("--load", "-l", default=None, help="Load existing graph snapshot by name")
def chat(track: str | None, store_dir: str, load: str | None):
    """Interactive chat-based enrichment."""
    console.print("[bold]Interactive KG Enrichment Chat[/bold]")
    console.print("Type your questions or commands. Use 'quit' to exit.\n")

    orchestrator = _create_orchestrator(track_name=track, store_dir=store_dir)

    if load:
        try:
            orchestrator.graph = orchestrator.store.load(load)
            console.print(f"[green]Loaded graph: {load}[/green]")
            stats = orchestrator.graph.stats()
            console.print(
                f"  Entities: {stats['entities']}, "
                f"Relationships: {stats['relationships']}"
            )
        except FileNotFoundError:
            console.print(f"[yellow]No snapshot found for '{load}', starting fresh.[/yellow]")

    async def _chat_loop():
        while True:
            try:
                user_input = console.input("[bold cyan]You>[/bold cyan] ")
            except (EOFError, KeyboardInterrupt):
                break

            if user_input.strip().lower() in ("quit", "exit", "q"):
                break
            if user_input.strip().lower() == "stats":
                _print_stats(orchestrator.graph.stats())
                continue
            if user_input.strip().lower() == "schema":
                console.print_json(json.dumps(orchestrator.graph.schema_summary()))
                continue
            if user_input.strip().lower().startswith("export"):
                _handle_export(orchestrator, user_input)
                continue

            with console.status("[bold green]Thinking..."):
                response = await orchestrator.chat(user_input)

            console.print(f"\n[bold green]Agent>[/bold green] {response}\n")

    asyncio.run(_chat_loop())
    console.print("\n[dim]Session ended.[/dim]")


@main.command()
@click.option("--store-dir", "-s", default="./kg_data", help="Directory for graph snapshots")
def snapshots(store_dir: str):
    """List available graph snapshots."""
    from kg_enrichment.core.store import GraphStore

    store = GraphStore(store_dir)
    snaps = store.list_snapshots()

    if not snaps:
        console.print("[dim]No snapshots found.[/dim]")
        return

    table = Table(title="Graph Snapshots")
    table.add_column("Name")
    table.add_column("Timestamp")
    table.add_column("Size")
    table.add_column("Path")

    for snap in snaps:
        size_kb = snap["size_bytes"] / 1024
        table.add_row(snap["name"], snap["timestamp"], f"{size_kb:.1f} KB", snap["path"])

    console.print(table)


@main.command()
def providers():
    """List available data providers."""
    from kg_enrichment.providers.registry import ProviderRegistry

    registry = ProviderRegistry()

    table = Table(title="Available Providers")
    table.add_column("Name")
    table.add_column("Description")
    table.add_column("Entity Types")
    table.add_column("API Key?")

    for provider in registry.get_all():
        types = ", ".join(provider.supported_entity_types[:5])
        key = "Yes" if provider.requires_api_key else "No"
        table.add_row(provider.name, provider.description, types, key)

    console.print(table)


@main.command()
def tracks():
    """List available enrichment tracks."""
    track_info = [
        ("financial", "Financial analysis — ownership, filings, risk, corporate actions"),
        ("security", "Security analysis — attack surface, infrastructure, vulnerabilities"),
        ("compliance", "Compliance — regulatory exposure, governance, officer relationships"),
        ("threat_intel", "Threat intelligence — IOCs, threat actor infrastructure, campaigns"),
        ("executive", "Executive intelligence — strategic overview, competitive landscape"),
    ]

    table = Table(title="Available Tracks")
    table.add_column("Name")
    table.add_column("Description")

    for name, desc in track_info:
        table.add_row(name, desc)

    console.print(table)


def _print_report(report):
    """Print an enrichment report."""
    console.print("\n[bold]═══ Enrichment Report ═══[/bold]")
    console.print(f"  Seed: {report.seed}")
    if report.track:
        console.print(f"  Track: {report.track}")
    console.print(f"  Iterations: {report.iterations}")
    console.print(f"  Duration: {report.duration_seconds:.1f}s")
    console.print(f"  Entities: {report.entities_total}")
    console.print(f"  Relationships: {report.relationships_total}")

    if report.entity_types:
        console.print("\n  [bold]Entity Types:[/bold]")
        for etype, count in sorted(report.entity_types.items(), key=lambda x: -x[1]):
            console.print(f"    {etype}: {count}")

    if report.relationship_types:
        console.print("\n  [bold]Relationship Types:[/bold]")
        for rtype, count in sorted(report.relationship_types.items(), key=lambda x: -x[1]):
            console.print(f"    {rtype}: {count}")

    if report.errors:
        console.print(f"\n  [yellow]Errors: {len(report.errors)}[/yellow]")

    console.print()


def _print_stats(stats: dict):
    """Print graph statistics."""
    console.print(f"\n  Entities: {stats['entities']}")
    console.print(f"  Relationships: {stats['relationships']}")
    console.print(f"  Components: {stats['connected_components']}")
    console.print(f"  Enriched: {stats['enriched']}")
    console.print(f"  Unenriched: {stats['unenriched']}")
    if stats['entity_types']:
        console.print("  Entity types: " + json.dumps(stats['entity_types']))
    console.print()


def _handle_export(orchestrator, command: str):
    """Handle export commands."""
    parts = command.strip().split()
    fmt = parts[1] if len(parts) > 1 else "json"
    path = parts[2] if len(parts) > 2 else f"kg_export.{fmt}"

    from kg_enrichment.core.exporters import to_cypher, to_graphml, to_jsonld

    if fmt == "cypher":
        output = to_cypher(orchestrator.graph)
        with open(path, "w") as f:
            f.write(output)
    elif fmt == "jsonld":
        output = to_jsonld(orchestrator.graph)
        with open(path, "w") as f:
            json.dump(output, f, indent=2)
    elif fmt == "graphml":
        to_graphml(orchestrator.graph, path)
    elif fmt == "json":
        with open(path, "w") as f:
            f.write(orchestrator.graph.to_json())
    else:
        console.print(f"[red]Unknown format: {fmt}. Use: json, cypher, jsonld, graphml[/red]")
        return

    console.print(f"[green]Exported to {path}[/green]")


if __name__ == "__main__":
    main()
