"""Database schema for document storage."""

import sqlite3
from pathlib import Path


def init_database(db_path: Path) -> sqlite3.Connection:
    """Initialize SQLite database with schema."""
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row  # Return rows as dicts

    # Create main documents table
    conn.execute("""
        CREATE TABLE IF NOT EXISTS documents (
            doc_id TEXT PRIMARY KEY,
            filepath TEXT NOT NULL,
            doc_type TEXT NOT NULL,
            confidence REAL NOT NULL,
            line_count INTEGER NOT NULL,
            full_text TEXT NOT NULL
        )
    """)

    # Create FTS5 virtual table for full-text search
    conn.execute("""
        CREATE VIRTUAL TABLE IF NOT EXISTS documents_fts USING fts5(
            doc_id UNINDEXED,
            full_text,
            content='documents',
            content_rowid='rowid'
        )
    """)

    # Create entity mentions table
    conn.execute("""
        CREATE TABLE IF NOT EXISTS entity_mentions (
            doc_id TEXT NOT NULL,
            entity_name TEXT NOT NULL,
            PRIMARY KEY (doc_id, entity_name),
            FOREIGN KEY (doc_id) REFERENCES documents(doc_id)
        )
    """)

    # Create index on entity_name for fast lookups
    conn.execute("""
        CREATE INDEX IF NOT EXISTS idx_entity_name
        ON entity_mentions(entity_name)
    """)

    conn.commit()
    return conn


def rebuild_fts_index(conn: sqlite3.Connection):
    """Rebuild the FTS5 index from documents table."""
    conn.execute("INSERT INTO documents_fts(documents_fts) VALUES('rebuild')")
    conn.commit()
