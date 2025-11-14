"""Canonical entity management for entity merging and normalization."""

import sqlite3
from pathlib import Path

from rich.console import Console
from rich.progress import track

console = Console()


def initialize_canonical_entities(db_path: Path) -> dict:
    """Initialize canonical entities from existing entities table.

    Creates a 1:1 mapping where each entity is its own canonical entity.
    This is the starting point before any merging occurs.

    Args:
        db_path: Path to SQLite database

    Returns:
        Dict with initialization statistics
    """
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row

    # Check if already initialized
    existing = conn.execute("SELECT COUNT(*) as count FROM canonical_entities").fetchone()
    if existing["count"] > 0:
        console.print(
            f"[yellow]Canonical entities already initialized "
            f"({existing['count']} entities)[/yellow]"
        )
        console.print("[yellow]Skipping initialization. Use --force to reinitialize.[/yellow]")
        conn.close()
        return {"status": "already_initialized", "count": existing["count"]}

    # Get all entities
    entities = conn.execute(
        "SELECT entity_id, text, type, normalized_text, occurrence_count FROM entities"
    ).fetchall()

    console.print(f"[bold]Initializing canonical entities from {len(entities)} entities...[/bold]")

    stats = {
        "total_entities": len(entities),
        "canonical_created": 0,
        "aliases_created": 0,
    }

    # Create canonical entity for each entity
    for entity in track(entities, description="Creating canonical entities"):
        # Insert canonical entity
        cursor = conn.execute(
            """
            INSERT INTO canonical_entities
            (entity_type, canonical_text, canonical_normalized, total_mentions)
            VALUES (?, ?, ?, ?)
            """,
            (entity["type"], entity["text"], entity["normalized_text"], entity["occurrence_count"]),
        )
        canonical_id = cursor.lastrowid
        stats["canonical_created"] += 1

        # Create alias mapping (entity is its own canonical form initially)
        conn.execute(
            """
            INSERT INTO entity_aliases
            (entity_id, canonical_id, is_canonical, merge_method, merge_confidence, merged_by)
            VALUES (?, ?, 1, 'initial', 1.0, 'system')
            """,
            (entity["entity_id"], canonical_id),
        )
        stats["aliases_created"] += 1

        # Commit every 1000 entities for performance
        if stats["canonical_created"] % 1000 == 0:
            conn.commit()

    # Final commit
    conn.commit()
    conn.close()

    console.print("[bold green]✓ Canonical entities initialized![/bold green]")
    console.print(f"  Canonical entities created: {stats['canonical_created']}")
    console.print(f"  Alias mappings created: {stats['aliases_created']}")

    return stats


def get_canonical_entity(conn: sqlite3.Connection, entity_id: int) -> dict | None:
    """Get canonical entity for a given entity ID.

    Args:
        conn: Database connection
        entity_id: Entity ID to look up

    Returns:
        Dict with canonical entity info or None if not found
    """
    result = conn.execute(
        """
        SELECT ce.canonical_id, ce.canonical_text, ce.canonical_normalized,
               ce.entity_type, ce.total_mentions
        FROM entity_aliases ea
        JOIN canonical_entities ce ON ea.canonical_id = ce.canonical_id
        WHERE ea.entity_id = ?
        """,
        (entity_id,),
    ).fetchone()

    if result:
        return dict(result)
    return None


def get_all_aliases(conn: sqlite3.Connection, canonical_id: int) -> list[dict]:
    """Get all entity aliases for a canonical entity.

    Args:
        conn: Database connection
        canonical_id: Canonical entity ID

    Returns:
        List of entity dicts that map to this canonical entity
    """
    results = conn.execute(
        """
        SELECT e.entity_id, e.text, e.type, e.normalized_text, e.occurrence_count,
               ea.is_canonical, ea.merge_method, ea.merge_confidence, ea.merged_at
        FROM entity_aliases ea
        JOIN entities e ON ea.entity_id = e.entity_id
        WHERE ea.canonical_id = ?
        ORDER BY e.occurrence_count DESC
        """,
        (canonical_id,),
    ).fetchall()

    return [dict(row) for row in results]


def find_canonical_by_text(conn: sqlite3.Connection, search_text: str) -> list[dict]:
    """Find canonical entities by text search (FTS5).

    Args:
        conn: Database connection
        search_text: Text to search for

    Returns:
        List of canonical entity dicts matching the search
    """
    # FTS5 prefix search
    search_query = f'"{search_text}"*'

    results = conn.execute(
        """
        SELECT ce.canonical_id, ce.canonical_text, ce.canonical_normalized,
               ce.entity_type, ce.total_mentions
        FROM canonical_entities ce
        WHERE ce.canonical_id IN (
            SELECT rowid FROM canonical_entities_fts
            WHERE canonical_entities_fts MATCH ?
        )
        ORDER BY ce.total_mentions DESC
        """,
        (search_query,),
    ).fetchall()

    return [dict(row) for row in results]


def merge_entities(
    conn: sqlite3.Connection,
    source_entity_id: int,
    target_canonical_id: int,
    method: str = "manual",
    confidence: float = 1.0,
    merged_by: str = "user",
) -> dict:
    """Merge an entity into a canonical entity.

    Args:
        conn: Database connection
        source_entity_id: Entity to merge (will become alias)
        target_canonical_id: Canonical entity to merge into
        method: Merge method ('auto', 'llm', 'manual')
        confidence: Confidence score for merge (0.0-1.0)
        merged_by: Who/what performed the merge

    Returns:
        Dict with merge statistics
    """
    # Get source entity's current canonical mapping
    current = conn.execute(
        "SELECT canonical_id FROM entity_aliases WHERE entity_id = ?", (source_entity_id,)
    ).fetchone()

    if not current:
        raise ValueError(f"Entity {source_entity_id} not found in aliases table")

    source_canonical_id = current["canonical_id"]

    if source_canonical_id == target_canonical_id:
        return {"status": "already_merged", "message": "Entity already mapped to target canonical"}

    # Get source entity occurrence count
    source_entity = conn.execute(
        "SELECT occurrence_count FROM entities WHERE entity_id = ?", (source_entity_id,)
    ).fetchone()

    # Update alias mapping
    conn.execute(
        """
        UPDATE entity_aliases
        SET canonical_id = ?,
            is_canonical = 0,
            merge_method = ?,
            merge_confidence = ?,
            merged_at = CURRENT_TIMESTAMP,
            merged_by = ?
        WHERE entity_id = ?
        """,
        (target_canonical_id, method, confidence, merged_by, source_entity_id),
    )

    # Update total mentions for target canonical entity
    conn.execute(
        """
        UPDATE canonical_entities
        SET total_mentions = total_mentions + ?,
            updated_at = CURRENT_TIMESTAMP
        WHERE canonical_id = ?
        """,
        (source_entity["occurrence_count"], target_canonical_id),
    )

    # Update total mentions for source canonical entity (now has fewer)
    conn.execute(
        """
        UPDATE canonical_entities
        SET total_mentions = total_mentions - ?,
            updated_at = CURRENT_TIMESTAMP
        WHERE canonical_id = ?
        """,
        (source_entity["occurrence_count"], source_canonical_id),
    )

    # Check if source canonical has any remaining aliases
    remaining = conn.execute(
        "SELECT COUNT(*) as count FROM entity_aliases WHERE canonical_id = ?",
        (source_canonical_id,),
    ).fetchone()

    # If no remaining aliases, delete the orphaned canonical entity
    if remaining["count"] == 0:
        conn.execute(
            "DELETE FROM canonical_entities WHERE canonical_id = ?", (source_canonical_id,)
        )

    conn.commit()

    return {
        "status": "merged",
        "source_canonical_id": source_canonical_id,
        "target_canonical_id": target_canonical_id,
        "orphaned_canonical_deleted": remaining["count"] == 0,
    }


def get_canonical_stats(db_path: Path) -> dict:
    """Get statistics about canonical entities.

    Args:
        db_path: Path to SQLite database

    Returns:
        Dict with statistics
    """
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row

    stats = {}

    # Total canonical entities
    result = conn.execute("SELECT COUNT(*) as count FROM canonical_entities").fetchone()
    stats["total_canonical"] = result["count"]

    # Total entity aliases
    result = conn.execute("SELECT COUNT(*) as count FROM entity_aliases").fetchone()
    stats["total_aliases"] = result["count"]

    # Average aliases per canonical
    if stats["total_canonical"] > 0:
        stats["avg_aliases_per_canonical"] = stats["total_aliases"] / stats["total_canonical"]
    else:
        stats["avg_aliases_per_canonical"] = 0

    # Canonical entities by type
    results = conn.execute(
        """
        SELECT entity_type, COUNT(*) as count
        FROM canonical_entities
        GROUP BY entity_type
        ORDER BY count DESC
        """
    ).fetchall()
    stats["by_type"] = {row["entity_type"]: row["count"] for row in results}

    # Top merged entities (canonical entities with >1 alias)
    results = conn.execute(
        """
        SELECT ce.canonical_text, ce.entity_type, COUNT(ea.entity_id) as alias_count
        FROM canonical_entities ce
        JOIN entity_aliases ea ON ce.canonical_id = ea.canonical_id
        GROUP BY ce.canonical_id
        HAVING alias_count > 1
        ORDER BY alias_count DESC
        LIMIT 10
        """
    ).fetchall()
    stats["top_merged"] = [
        {"text": row["canonical_text"], "type": row["entity_type"], "aliases": row["alias_count"]}
        for row in results
    ]

    conn.close()
    return stats
