"""Load and extract entities from documents into database."""

import json
import sqlite3
from pathlib import Path

from rich.console import Console
from rich.progress import track

from ..entities.extractor import HybridEntityExtractor
from ..parsers.email_parser import EmailParser

console = Console()


def normalize_entity_text(text: str, entity_type: str) -> str:
    """Normalize entity text for deduplication.

    Args:
        text: Raw entity text
        entity_type: Type of entity (person, organization, location, date)

    Returns:
        Normalized text for deduplication
    """
    # Remove extra whitespace
    normalized = " ".join(text.split())

    # Lowercase for case-insensitive matching
    normalized = normalized.lower()

    # Remove punctuation for names
    if entity_type in ("person", "organization"):
        # Remove common punctuation but keep apostrophes in names
        normalized = normalized.replace(".", "").replace(",", "")

    return normalized


def extract_and_store_entities(
    conn: sqlite3.Connection,
    doc_id: str,
    filepath: Path,
    enable_llm: bool = False,
) -> dict:
    """Extract entities from a document and store in database.

    Args:
        conn: Database connection
        doc_id: Document ID
        filepath: Path to document file
        enable_llm: Whether to use LLM validation (slower but more accurate)

    Returns:
        Dict with extraction statistics
    """
    stats = {
        "entities_found": 0,
        "entities_new": 0,
        "entities_existing": 0,
        "email_metadata": False,
        "thread_messages": 0,
        "parsing_issues": 0,
    }

    try:
        # Read document
        with open(filepath, encoding="utf-8-sig", errors="replace") as f:
            text = f.read()

        # Extract entities
        extractor = HybridEntityExtractor(enable_llm=enable_llm)
        entities_by_type = extractor.extract(text)

        # Map extractor type names to database type names
        type_mapping = {
            "people": "person",
            "organizations": "organization",
            "locations": "location",
            "dates": "date",
        }
        entities_by_type = {type_mapping.get(k, k): v for k, v in entities_by_type.items()}

        # Parse email metadata if document is classified as email
        email_metadata = None
        doc_type = conn.execute(
            "SELECT doc_type FROM documents WHERE doc_id = ?", (doc_id,)
        ).fetchone()

        if doc_type and doc_type[0] == "email":
            try:
                parser = EmailParser()
                email_metadata = parser.parse(filepath)
                stats["email_metadata"] = True
                stats["thread_messages"] = len(email_metadata.thread_messages)
                stats["parsing_issues"] = len(email_metadata.parsing_issues)
            except Exception as e:
                console.print(f"[yellow]Warning: Email parsing failed for {doc_id}: {e}[/yellow]")

        # Store entities
        for entity_type, entity_list in entities_by_type.items():
            for entity in entity_list:
                # Normalize for deduplication
                normalized = normalize_entity_text(entity.text, entity_type)

                # Check if entity exists
                existing = conn.execute(
                    """
                    SELECT entity_id, occurrence_count FROM entities
                    WHERE normalized_text = ? AND type = ?
                    """,
                    (normalized, entity_type),
                ).fetchone()

                if existing:
                    entity_id = existing[0]
                    # Update occurrence count
                    conn.execute(
                        """
                        UPDATE entities
                        SET occurrence_count = occurrence_count + 1
                        WHERE entity_id = ?
                        """,
                        (entity_id,),
                    )
                    stats["entities_existing"] += 1
                else:
                    # Insert new entity
                    cursor = conn.execute(
                        """
                        INSERT INTO entities
                        (text, type, normalized_text, first_seen_doc_id, occurrence_count)
                        VALUES (?, ?, ?, ?, 1)
                        """,
                        (entity.text, entity_type, normalized, doc_id),
                    )
                    entity_id = cursor.lastrowid
                    stats["entities_new"] += 1

                stats["entities_found"] += 1

                # Link entity to document with metadata
                # Note: No PRIMARY KEY on (doc_id, entity_id) to allow multiple mentions
                conn.execute(
                    """
                    INSERT INTO document_entities
                    (doc_id, entity_id, context, confidence, method)
                    VALUES (?, ?, ?, ?, ?)
                    """,
                    (doc_id, entity_id, entity.context, entity.confidence, entity.method),
                )

        # Store email metadata if available
        if email_metadata:
            _store_email_metadata(conn, doc_id, email_metadata)

        conn.commit()

    except Exception as e:
        console.print(f"[red]Error extracting entities from {doc_id}: {e}[/red]")
        raise

    return stats


def _store_email_metadata(conn: sqlite3.Connection, doc_id: str, metadata):
    """Store email metadata and thread messages."""
    # Store main email metadata
    conn.execute(
        """
        INSERT OR REPLACE INTO email_metadata
        (doc_id, from_addr, to_addrs, cc_addrs, subject, date, message_id,
         in_reply_to, is_reply, is_forward, all_participants, parsing_issues)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            doc_id,
            str(metadata.from_addr) if metadata.from_addr else None,
            json.dumps([str(addr) for addr in metadata.to_addrs]),
            json.dumps([str(addr) for addr in metadata.cc_addrs]),
            metadata.subject,
            metadata.date.isoformat() if metadata.date else None,
            metadata.message_id,
            metadata.in_reply_to,
            int(metadata.is_reply),
            int(metadata.is_forward),
            json.dumps(sorted(metadata.all_participants)),
            json.dumps(metadata.parsing_issues) if metadata.parsing_issues else None,
        ),
    )

    # Store thread messages
    for i, thread_msg in enumerate(metadata.thread_messages):
        conn.execute(
            """
            INSERT OR REPLACE INTO thread_messages
            (doc_id, author, date, date_str, content_preview, message_index)
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            (
                doc_id,
                thread_msg.author,
                thread_msg.date.isoformat() if thread_msg.date else None,
                thread_msg.date_str,
                thread_msg.content_preview,
                i,
            ),
        )


def batch_extract_entities(
    db_path: Path,
    doc_ids: list[str] = None,
    enable_llm: bool = False,
    batch_size: int = 50,
) -> dict:
    """Extract entities from all documents (or subset) in database.

    Args:
        db_path: Path to SQLite database
        doc_ids: Optional list of doc_ids to process (if None, processes all)
        enable_llm: Whether to use LLM validation
        batch_size: Commit every N documents

    Returns:
        Dict with overall statistics
    """
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row

    # Get documents to process
    if doc_ids:
        placeholders = ",".join("?" * len(doc_ids))
        query = f"SELECT doc_id, filepath FROM documents WHERE doc_id IN ({placeholders})"
        docs = conn.execute(query, doc_ids).fetchall()
    else:
        docs = conn.execute("SELECT doc_id, filepath FROM documents").fetchall()

    console.print(f"[bold]Extracting entities from {len(docs)} documents...[/bold]")
    if enable_llm:
        console.print("[yellow]LLM validation enabled - this will be slower[/yellow]")

    overall_stats = {
        "total_docs": len(docs),
        "processed": 0,
        "entities_found": 0,
        "entities_new": 0,
        "emails_parsed": 0,
        "thread_messages": 0,
        "parsing_issues": 0,
        "errors": 0,
    }

    for doc in track(docs, description="Extracting entities"):
        try:
            doc_stats = extract_and_store_entities(
                conn, doc["doc_id"], Path(doc["filepath"]), enable_llm
            )

            overall_stats["processed"] += 1
            overall_stats["entities_found"] += doc_stats["entities_found"]
            overall_stats["entities_new"] += doc_stats["entities_new"]
            if doc_stats["email_metadata"]:
                overall_stats["emails_parsed"] += 1
            overall_stats["thread_messages"] += doc_stats["thread_messages"]
            overall_stats["parsing_issues"] += doc_stats["parsing_issues"]

            # Commit every batch_size documents
            if overall_stats["processed"] % batch_size == 0:
                conn.commit()

        except Exception as e:
            console.print(f"[red]Error processing {doc['doc_id']}: {e}[/red]")
            overall_stats["errors"] += 1

    # Final commit
    conn.commit()
    conn.close()

    # Print summary
    console.print("\n[bold green]✓ Entity extraction complete![/bold green]")
    console.print(
        f"  Processed: {overall_stats['processed']}/{overall_stats['total_docs']} documents"
    )
    console.print(f"  Entities found: {overall_stats['entities_found']}")
    console.print(f"  New unique entities: {overall_stats['entities_new']}")
    console.print(f"  Emails parsed: {overall_stats['emails_parsed']}")
    console.print(f"  Thread messages: {overall_stats['thread_messages']}")
    if overall_stats["parsing_issues"]:
        console.print(f"  [yellow]Parsing issues (DLQ): {overall_stats['parsing_issues']}[/yellow]")
    if overall_stats["errors"]:
        console.print(f"  [red]Errors: {overall_stats['errors']}[/red]")

    return overall_stats
