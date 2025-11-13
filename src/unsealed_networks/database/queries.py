"""Data access layer for database queries."""

import json
import sqlite3
from pathlib import Path


def find_entity_mentions(
    db_path: Path,
    entity_name: str,
    entity_type: str = None,
    limit: int = 20,
) -> dict:
    """Find all documents mentioning an entity.

    Args:
        db_path: Path to database
        entity_name: Entity name to search for (partial match)
        entity_type: Optional entity type filter (person, organization, location, date)
        limit: Maximum results per entity

    Returns:
        Dictionary with 'entities' list containing matching entities and their documents
    """
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row

    # Find matching entities
    query = "SELECT * FROM entities WHERE text LIKE ? OR normalized_text LIKE ?"
    params = [f"%{entity_name}%", f"%{entity_name.lower()}%"]

    if entity_type:
        query += " AND type = ?"
        params.append(entity_type)

    entities = conn.execute(query, params).fetchall()

    results = {"entities": []}

    for entity in entities:
        # Find documents for this entity
        docs = conn.execute(
            """
            SELECT d.doc_id, d.doc_type, de.confidence, de.context
            FROM document_entities de
            JOIN documents d ON de.doc_id = d.doc_id
            WHERE de.entity_id = ?
            ORDER BY de.confidence DESC
            LIMIT ?
            """,
            (entity["entity_id"], limit),
        ).fetchall()

        results["entities"].append(
            {
                "text": entity["text"],
                "type": entity["type"],
                "normalized_text": entity["normalized_text"],
                "occurrence_count": entity["occurrence_count"],
                "first_seen_doc_id": entity["first_seen_doc_id"],
                "documents": [
                    {
                        "doc_id": doc["doc_id"],
                        "doc_type": doc["doc_type"],
                        "confidence": doc["confidence"],
                        "context": doc["context"],
                    }
                    for doc in docs
                ],
            }
        )

    conn.close()
    return results


def find_email_threads(
    db_path: Path,
    participant: str,
    limit: int = 20,
) -> list[dict]:
    """Find email threads involving a participant.

    Args:
        db_path: Path to database
        participant: Participant name to search for (partial match)
        limit: Maximum results to return

    Returns:
        List of thread message dictionaries
    """
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row

    threads = conn.execute(
        """
        SELECT tm.doc_id, tm.author, tm.date, tm.date_str, tm.content_preview,
               d.doc_type, em.subject, em.from_addr, em.to_addrs
        FROM thread_messages tm
        JOIN documents d ON tm.doc_id = d.doc_id
        LEFT JOIN email_metadata em ON tm.doc_id = em.doc_id
        WHERE tm.author LIKE ?
        ORDER BY tm.date DESC
        LIMIT ?
        """,
        (f"%{participant}%", limit),
    ).fetchall()

    conn.close()

    return [
        {
            "doc_id": thread["doc_id"],
            "doc_type": thread["doc_type"],
            "subject": thread["subject"],
            "from_addr": thread["from_addr"],
            "to_addrs": thread["to_addrs"],
            "author": thread["author"],
            "date": thread["date"],
            "date_str": thread["date_str"],
            "content_preview": thread["content_preview"],
        }
        for thread in threads
    ]


def get_dlq_documents(
    db_path: Path,
    limit: int = 20,
) -> list[dict]:
    """Get documents with parsing issues (Dead Letter Queue).

    Args:
        db_path: Path to database
        limit: Maximum results to return

    Returns:
        List of document dictionaries with parsing issues
    """
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row

    dlq = conn.execute(
        """
        SELECT em.doc_id, em.subject, em.from_addr, em.parsing_issues, d.filepath
        FROM email_metadata em
        JOIN documents d ON em.doc_id = d.doc_id
        WHERE em.parsing_issues IS NOT NULL AND em.parsing_issues != '[]'
        LIMIT ?
        """,
        (limit,),
    ).fetchall()

    conn.close()

    return [
        {
            "doc_id": item["doc_id"],
            "subject": item["subject"],
            "from_addr": item["from_addr"],
            "filepath": item["filepath"],
            "parsing_issues": json.loads(item["parsing_issues"]),
        }
        for item in dlq
    ]
