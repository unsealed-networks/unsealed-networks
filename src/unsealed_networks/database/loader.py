"""Load documents from classification results into SQLite."""

import json
import sqlite3
from pathlib import Path

from rich.console import Console
from rich.progress import track

console = Console()


def load_documents(
    db_path: Path,
    classifications_json: Path,
    text_dir: Path,
    batch_size: int = 100,
) -> dict:
    """Load documents from classification results into database.

    Args:
        db_path: Path to SQLite database
        classifications_json: Path to classification_results.json
        text_dir: Root directory containing TEXT/ subdirs with .txt files
        batch_size: Number of documents to insert per transaction

    Returns:
        Dict with loading statistics
    """
    from .schema import init_database

    # Initialize database
    conn = init_database(db_path)

    # Load classifications
    with open(classifications_json, encoding="utf-8") as f:
        classifications = json.load(f)

    console.print(f"[bold]Loading {len(classifications)} documents into database...[/bold]")

    stats = {
        "total": len(classifications),
        "loaded": 0,
        "skipped": 0,
        "errors": 0,
    }

    # Prepare batch insert
    docs_batch = []
    entities_batch = []

    for _i, doc in enumerate(track(classifications, description="Loading documents")):
        try:
            # Read full text from file
            filepath = Path(doc["filepath"])
            if not filepath.exists():
                console.print(f"[yellow]Warning: File not found: {filepath}[/yellow]")
                stats["skipped"] += 1
                continue

            with open(filepath, encoding="utf-8", errors="replace") as f:
                full_text = f.read()

            # Add to batch
            docs_batch.append(
                (
                    doc["doc_id"],
                    str(filepath),
                    doc["document_type"],
                    doc["confidence"],
                    doc["line_count"],
                    full_text,
                )
            )

            # Add entity mentions to batch
            for entity in doc["entity_mentions"]:
                entities_batch.append((doc["doc_id"], entity))

            # Insert batch if at batch_size
            if len(docs_batch) >= batch_size:
                _insert_batch(conn, docs_batch, entities_batch)
                stats["loaded"] += len(docs_batch)
                docs_batch = []
                entities_batch = []

        except Exception as e:
            console.print(f"[red]Error loading {doc.get('doc_id', 'unknown')}: {e}[/red]")
            stats["errors"] += 1

    # Insert remaining documents
    if docs_batch:
        _insert_batch(conn, docs_batch, entities_batch)
        stats["loaded"] += len(docs_batch)

    # Rebuild FTS index
    console.print("[bold]Rebuilding full-text search index...[/bold]")
    from .schema import rebuild_fts_index

    rebuild_fts_index(conn)

    conn.close()

    console.print(f"[bold green]✓ Loaded {stats['loaded']} documents[/bold green]")
    if stats["skipped"]:
        console.print(f"[yellow]  Skipped {stats['skipped']} (files not found)[/yellow]")
    if stats["errors"]:
        console.print(f"[red]  Errors: {stats['errors']}[/red]")

    return stats


def _insert_batch(conn: sqlite3.Connection, docs_batch: list, entities_batch: list):
    """Insert a batch of documents and entity mentions."""
    # Insert documents
    conn.executemany(
        """
        INSERT OR REPLACE INTO documents
        (doc_id, filepath, doc_type, confidence, line_count, full_text)
        VALUES (?, ?, ?, ?, ?, ?)
        """,
        docs_batch,
    )

    # Insert into FTS table
    conn.executemany(
        """
        INSERT OR REPLACE INTO documents_fts (doc_id, full_text)
        VALUES (?, ?)
        """,
        [(doc[0], doc[5]) for doc in docs_batch],  # doc_id, full_text
    )

    # Insert entity mentions
    if entities_batch:
        conn.executemany(
            """
            INSERT OR IGNORE INTO entity_mentions (doc_id, entity_name)
            VALUES (?, ?)
            """,
            entities_batch,
        )

    conn.commit()
