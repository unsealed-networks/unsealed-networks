#!/usr/bin/env python3
"""Command-line interface for unsealed-networks."""

import hashlib
import json
import tarfile
from datetime import datetime
from pathlib import Path

import requests
import typer
from rich.console import Console
from rich.progress import Progress
from rich.table import Table

from .database.entity_loader import batch_extract_entities
from .database.loader import load_documents
from .database.queries import find_email_threads, find_entity_mentions, get_dlq_documents
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


@app.command()
def download_data(
    target_dir: Path = typer.Option(
        ".", "--target-dir", "-t", help="Target directory for downloads"
    ),
    skip_source: bool = typer.Option(False, "--skip-source", help="Skip source data download"),
    skip_database: bool = typer.Option(False, "--skip-database", help="Skip database download"),
):
    """Download source data and database from S3."""
    # S3 URLs and checksums
    S3_BASE = "https://unsealed-networks-public.s3.us-east-2.amazonaws.com"
    FILES = {
        "source": {
            "url": f"{S3_BASE}/source/house-oversight/7th-production/Epstein-Seventh-Production-Text-Only.tgz",  # noqa: E501
            "checksum": "03d688f39e6740a43590742a636b82a4f9e8ef673675dceb65d8301846bc704a",
            "output": "source_text/7th_production/Epstein-Seventh-Production-Text-Only.tgz",
            "extract_to": "source_text/7th_production",
        },
        "database": {
            "url": f"{S3_BASE}/database/unsealed-v0.0.1.db",
            "checksum": "bce1efef6dc0d309359b4a5c74ac9c0b5f8040c54f39c1beb7c8bb2b14cc4208",
            "output": "data/unsealed.db",
        },
    }

    def download_file(url: str, output_path: Path) -> None:
        """Download file with progress bar."""
        output_path.parent.mkdir(parents=True, exist_ok=True)

        response = requests.get(url, stream=True, timeout=30)
        response.raise_for_status()

        total_size = int(response.headers.get("content-length", 0))

        with Progress() as progress:
            task = progress.add_task(f"Downloading {output_path.name}...", total=total_size)

            with open(output_path, "wb") as f:
                for chunk in response.iter_content(chunk_size=8192):
                    f.write(chunk)
                    progress.update(task, advance=len(chunk))

    def verify_checksum(filepath: Path, expected: str) -> bool:
        """Verify SHA256 checksum."""
        sha256 = hashlib.sha256()

        with open(filepath, "rb") as f:
            for chunk in iter(lambda: f.read(8192), b""):
                sha256.update(chunk)

        return sha256.hexdigest() == expected

    target_path = Path(target_dir).resolve()

    # Download source data
    if not skip_source:
        source_info = FILES["source"]
        output_file = target_path / source_info["output"]

        if output_file.exists():
            console.print(f"[yellow]Source file already exists:[/yellow] {output_file}")
            console.print("[yellow]Verifying checksum...[/yellow]")

            if verify_checksum(output_file, source_info["checksum"]):
                console.print("[green]✓ Checksum verified[/green]")
            else:
                console.print("[red]✗ Checksum mismatch! Re-downloading...[/red]")
                output_file.unlink()
                download_file(source_info["url"], output_file)
        else:
            console.print("[bold]Downloading source data...[/bold]")
            download_file(source_info["url"], output_file)

        # Verify checksum
        console.print("[yellow]Verifying checksum...[/yellow]")
        if not verify_checksum(output_file, source_info["checksum"]):
            console.print("[red]✗ Checksum verification failed![/red]")
            raise typer.Exit(1)

        console.print("[green]✓ Checksum verified[/green]")

        # Extract if needed
        extract_dir = target_path / source_info["extract_to"]
        if not (extract_dir / "TEXT").exists():
            console.print(f"[bold]Extracting to {extract_dir}...[/bold]")
            with tarfile.open(output_file, "r:gz") as tar:
                tar.extractall(extract_dir)
            console.print("[green]✓ Extraction complete[/green]")
        else:
            console.print("[dim]TEXT directory already exists, skipping extraction[/dim]")

    # Download database
    if not skip_database:
        db_info = FILES["database"]
        output_file = target_path / db_info["output"]

        if output_file.exists():
            console.print(f"[yellow]Database already exists:[/yellow] {output_file}")
            console.print("[yellow]Verifying checksum...[/yellow]")

            if verify_checksum(output_file, db_info["checksum"]):
                console.print("[green]✓ Checksum verified[/green]")
            else:
                console.print("[red]✗ Checksum mismatch! Re-downloading...[/red]")
                output_file.unlink()
                download_file(db_info["url"], output_file)
        else:
            console.print("[bold]Downloading database...[/bold]")
            download_file(db_info["url"], output_file)

        # Verify checksum
        console.print("[yellow]Verifying checksum...[/yellow]")
        if not verify_checksum(output_file, db_info["checksum"]):
            console.print("[red]✗ Checksum verification failed![/red]")
            raise typer.Exit(1)

        console.print("[green]✓ Checksum verified[/green]")

    console.print("\n[bold green]✓ Download complete![/bold green]")
    console.print(f"\n[bold]Files downloaded to:[/bold] {target_path}")

    if not skip_source:
        console.print(f"  Source: {target_path / FILES['source']['output']}")
        console.print(f"  Extracted to: {target_path / FILES['source']['extract_to']}/TEXT")

    if not skip_database:
        console.print(f"  Database: {target_path / FILES['database']['output']}")


@app.command()
def extract_entities(
    db_path: Path = typer.Option("data/unsealed.db", "--db", "-d", help="Database path"),
    enable_llm: bool = typer.Option(
        False, "--enable-llm", help="Enable LLM validation (slower but more accurate)"
    ),
    batch_size: int = typer.Option(50, "--batch-size", "-b", help="Commit every N documents"),
    doc_ids: str = typer.Option(None, "--doc-ids", help="Comma-separated doc IDs to process"),
):
    """Extract entities from documents in database."""
    if not db_path.exists():
        console.print(f"[red]Database not found:[/red] {db_path}")
        console.print("\nRun 'unsealed-networks load-db' first to create the database")
        raise typer.Exit(1)

    # Parse doc_ids if provided
    doc_id_list = None
    if doc_ids:
        doc_id_list = [d.strip() for d in doc_ids.split(",")]
        console.print(f"[bold]Processing {len(doc_id_list)} specific documents[/bold]")

    # Run extraction (stats are printed by batch_extract_entities)
    _stats = batch_extract_entities(
        db_path=db_path,
        doc_ids=doc_id_list,
        enable_llm=enable_llm,
        batch_size=batch_size,
    )

    console.print(f"\n[bold]Database updated:[/bold] {db_path}")
    console.print(f"  Size: {db_path.stat().st_size / (1024 * 1024):.1f} MB")


@app.command()
def query_entity(
    entity_name: str = typer.Argument(..., help="Entity name to search for"),
    db_path: Path = typer.Option("data/unsealed.db", "--db", "-d", help="Database path"),
    entity_type: str = typer.Option(
        None, "--type", "-t", help="Filter by entity type (person, organization, location, date)"
    ),
    limit: int = typer.Option(20, "--limit", "-l", help="Maximum results to show"),
):
    """Find all documents mentioning an entity."""
    if not db_path.exists():
        console.print(f"[red]Database not found:[/red] {db_path}")
        raise typer.Exit(1)

    results = find_entity_mentions(db_path, entity_name, entity_type, limit)

    if not results["entities"]:
        console.print(f"[yellow]No entities found matching:[/yellow] {entity_name}")
        return

    console.print(f"\n[bold]Found {len(results['entities'])} matching entities:[/bold]")

    for entity in results["entities"]:
        console.print(f"\n[cyan]{entity['text']}[/cyan] ({entity['type']})")
        console.print(f"  Occurrences: {entity['occurrence_count']}")
        console.print(f"  First seen: {entity['first_seen_doc_id']}")

        if entity["documents"]:
            table = Table(title=f"Documents mentioning '{entity['text']}'")
            table.add_column("Doc ID", style="cyan")
            table.add_column("Type", style="magenta")
            table.add_column("Confidence", justify="right", style="green")
            table.add_column("Context", style="dim")

            for doc in entity["documents"]:
                context = doc["context"][:60] + "..." if doc["context"] else "N/A"
                table.add_row(
                    doc["doc_id"],
                    doc["doc_type"],
                    f"{doc['confidence']:.2f}",
                    context,
                )

            console.print(table)


@app.command()
def find_threads(
    participant: str = typer.Argument(..., help="Email participant to search for"),
    db_path: Path = typer.Option("data/unsealed.db", "--db", "-d", help="Database path"),
    limit: int = typer.Option(20, "--limit", "-l", help="Maximum results to show"),
):
    """Find email threads involving a participant."""
    if not db_path.exists():
        console.print(f"[red]Database not found:[/red] {db_path}")
        raise typer.Exit(1)

    threads = find_email_threads(db_path, participant, limit)

    if not threads:
        console.print(f"[yellow]No threads found for:[/yellow] {participant}")
        return

    console.print(f"\n[bold]Found {len(threads)} thread messages for:[/bold] {participant}\n")

    for thread in threads:
        console.print(f"[bold cyan]{thread['doc_id']}[/bold cyan]")
        console.print(f"  Subject: {thread['subject']}")
        console.print(f"  From: {thread['from_addr']}")
        console.print(f"  Author: {thread['author']}")
        console.print(f"  Date: {thread['date'] or thread['date_str']}")
        if thread["content_preview"]:
            preview = thread["content_preview"][:100].replace("\n", " ")
            console.print(f"  Preview: {preview}...")
        console.print()


@app.command()
def show_dlq(
    db_path: Path = typer.Option("data/unsealed.db", "--db", "-d", help="Database path"),
    limit: int = typer.Option(20, "--limit", "-l", help="Maximum results to show"),
):
    """Show documents with parsing issues (Dead Letter Queue)."""
    if not db_path.exists():
        console.print(f"[red]Database not found:[/red] {db_path}")
        raise typer.Exit(1)

    dlq = get_dlq_documents(db_path, limit)

    if not dlq:
        console.print("[green]✓ No documents with parsing issues![/green]")
        return

    console.print(f"\n[bold yellow]Found {len(dlq)} documents with parsing issues:[/bold yellow]\n")

    for item in dlq:
        console.print(f"[bold cyan]{item['doc_id']}[/bold cyan]")
        console.print(f"  Subject: {item['subject']}")
        console.print(f"  From: {item['from_addr']}")
        console.print(f"  File: {item['filepath']}")

        console.print(f"  Issues ({len(item['parsing_issues'])}):")
        for issue in item["parsing_issues"]:
            console.print(f"    - {issue}")
        console.print()


def main():
    """Entry point for CLI."""
    app()


if __name__ == "__main__":
    main()
