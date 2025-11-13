#!/usr/bin/env python3
"""Command-line interface for unsealed-networks."""

import json
from datetime import datetime
from pathlib import Path

import typer
from rich.console import Console
from rich.table import Table

from .database.loader import load_documents
from .survey.scanner import DocumentScanner

app = typer.Typer(help="Unsealed Networks - Document analysis toolkit")
console = Console()


@app.command()
def survey(
    text_dir: Path = typer.Argument(
        ..., help="Directory containing text files to scan", exists=True, file_okay=False
    ),
    output: Path = typer.Option(
        "survey_report.json", "--output", "-o", help="Output JSON report file"
    ),
    classifications: Path = typer.Option(
        "classification_results.json",
        "--classifications",
        "-c",
        help="Output detailed classifications file",
    ),
    quiet: bool = typer.Option(False, "--quiet", "-q", help="Suppress progress output"),
):
    """Scan and classify all documents in a directory."""
    console.print(f"[bold]Scanning documents in:[/bold] {text_dir}")

    scanner = DocumentScanner(text_dir)
    report = scanner.scan_all(progress=not quiet)

    # Add timestamp
    report["scan_date"] = datetime.now().isoformat()

    # Save report
    with open(output, "w", encoding="utf-8") as f:
        json.dump(report, f, indent=2)

    # Save detailed results
    with open(classifications, "w", encoding="utf-8") as f:
        json.dump(scanner.get_results(), f, indent=2)

    # Print summary
    console.print("\n[bold green]✓ Scan complete[/bold green]")
    console.print(f"Total documents: {report['total_documents']}")
    console.print(f"Total size: {report['total_size_mb']:.1f} MB")

    # Document types table
    if report["document_types"]:
        table = Table(title="Document Types")
        table.add_column("Type", style="cyan")
        table.add_column("Count", justify="right", style="magenta")
        table.add_column("Percentage", justify="right", style="green")

        for dtype, stats in sorted(
            report["document_types"].items(), key=lambda x: x[1]["count"], reverse=True
        ):
            table.add_row(dtype, str(stats["count"]), f"{stats['percentage']:.1f}%")

        console.print(table)

    # Entity mentions
    if report["entity_mentions"]:
        console.print("\n[bold]Top entity mentions:[/bold]")
        for entity, count in list(report["entity_mentions"].items())[:10]:
            console.print(f"  {entity:20s}: {count:5d}")

    console.print("\n[bold]Reports saved:[/bold]")
    console.print(f"  {output}")
    console.print(f"  {classifications}")


@app.command()
def list_emails(
    classifications: Path = typer.Argument(
        ..., help="Classification results JSON file", exists=True
    ),
    min_confidence: float = typer.Option(
        0.7, "--min-confidence", "-c", help="Minimum confidence threshold"
    ),
    entity: str = typer.Option(None, "--entity", "-e", help="Filter by entity mention"),
    output: Path = typer.Option(None, "--output", "-o", help="Save results to JSON file"),
):
    """List all documents classified as emails."""
    with open(classifications, encoding="utf-8") as f:
        results = json.load(f)

    # Filter emails
    emails = [
        r for r in results if r["document_type"] == "email" and r["confidence"] >= min_confidence
    ]

    # Filter by entity if specified
    if entity:
        emails = [r for r in emails if entity in r["entity_mentions"]]

    console.print(f"[bold]Found {len(emails)} emails[/bold] (confidence >= {min_confidence})")

    if entity:
        console.print(f"[bold]Mentioning:[/bold] {entity}")

    # Create table
    table = Table()
    table.add_column("Doc ID", style="cyan")
    table.add_column("Confidence", justify="right", style="magenta")
    table.add_column("Entities", style="green")
    table.add_column("Lines", justify="right")

    for email in emails[:50]:  # Limit display to 50
        table.add_row(
            email["doc_id"],
            f"{email['confidence']:.2f}",
            ", ".join(email["entity_mentions"][:3]),  # First 3 entities
            str(email["line_count"]),
        )

    console.print(table)

    if len(emails) > 50:
        console.print(f"\n[dim]Showing first 50 of {len(emails)} results[/dim]")

    # Save to file if requested
    if output:
        with open(output, "w", encoding="utf-8") as f:
            json.dump(emails, f, indent=2)
        console.print(f"\n[bold green]✓ Saved {len(emails)} emails to:[/bold green] {output}")


@app.command()
def stats(
    report: Path = typer.Argument(..., help="Survey report JSON file", exists=True),
):
    """Display detailed statistics from a survey report."""
    with open(report, encoding="utf-8") as f:
        data = json.load(f)

    console.print("[bold]Survey Report[/bold]")
    console.print(f"Scan date: {data.get('scan_date', 'Unknown')}")
    console.print(f"Total documents: {data['total_documents']}")
    console.print(f"Total size: {data['total_size_mb']:.1f} MB")
    high_conf_pct = data["classification_quality"]["high_confidence_pct"]
    console.print(f"High confidence classifications: {high_conf_pct:.1f}%")
    console.print(f"Total issues: {data['total_issues']}")

    # All entity mentions
    if data["entity_mentions"]:
        console.print("\n[bold]All entity mentions:[/bold]")
        for entity, count in data["entity_mentions"].items():
            console.print(f"  {entity:30s}: {count:5d}")


@app.command()
def load_db(
    classifications: Path = typer.Argument(
        ..., help="Classification results JSON file", exists=True
    ),
    text_dir: Path = typer.Argument(
        ..., help="Root directory containing TEXT/ subdirs", exists=True, file_okay=False
    ),
    db_path: Path = typer.Option("data/unsealed.db", "--db", "-d", help="Output database path"),
):
    """Load documents from classification results into SQLite database."""
    # Create data directory if needed
    db_path.parent.mkdir(parents=True, exist_ok=True)

    load_documents(
        db_path=db_path,
        classifications_json=classifications,
        text_dir=text_dir,
    )

    console.print(f"\n[bold green]✓ Database created:[/bold green] {db_path}")
    console.print(f"  Size: {db_path.stat().st_size / (1024 * 1024):.1f} MB")


def main():
    """Entry point for CLI."""
    app()


if __name__ == "__main__":
    main()
