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

    # Create enhanced entities table with type, confidence, etc.
    conn.execute("""
        CREATE TABLE IF NOT EXISTS entities (
            entity_id INTEGER PRIMARY KEY AUTOINCREMENT,
            text TEXT NOT NULL,
            type TEXT NOT NULL CHECK(type IN ('person', 'organization', 'location', 'date')),
            normalized_text TEXT NOT NULL,
            first_seen_doc_id TEXT NOT NULL,
            occurrence_count INTEGER DEFAULT 1,
            UNIQUE(normalized_text, type),
            FOREIGN KEY (first_seen_doc_id) REFERENCES documents(doc_id)
        )
    """)

    # Create index on normalized_text for deduplication
    conn.execute("""
        CREATE INDEX IF NOT EXISTS idx_entity_normalized
        ON entities(normalized_text, type)
    """)

    # Create document_entities junction table with rich metadata
    conn.execute("""
        CREATE TABLE IF NOT EXISTS document_entities (
            mention_id INTEGER PRIMARY KEY AUTOINCREMENT,
            doc_id TEXT NOT NULL,
            entity_id INTEGER NOT NULL,
            context TEXT,
            confidence REAL NOT NULL,
            method TEXT NOT NULL CHECK(method IN ('regex', 'llm')),
            position_start INTEGER,
            position_end INTEGER,
            FOREIGN KEY (doc_id) REFERENCES documents(doc_id),
            FOREIGN KEY (entity_id) REFERENCES entities(entity_id)
        )
    """)

    # Create index for finding all entities in a document
    conn.execute("""
        CREATE INDEX IF NOT EXISTS idx_doc_entities_doc
        ON document_entities(doc_id)
    """)

    # Create index for finding all documents mentioning an entity
    conn.execute("""
        CREATE INDEX IF NOT EXISTS idx_doc_entities_entity
        ON document_entities(entity_id)
    """)

    # Create email metadata table
    conn.execute("""
        CREATE TABLE IF NOT EXISTS email_metadata (
            doc_id TEXT PRIMARY KEY,
            from_addr TEXT,
            to_addrs TEXT,
            cc_addrs TEXT,
            subject TEXT,
            date TEXT,
            message_id TEXT,
            in_reply_to TEXT,
            is_reply INTEGER,
            is_forward INTEGER,
            all_participants TEXT,
            parsing_issues TEXT,
            FOREIGN KEY (doc_id) REFERENCES documents(doc_id)
        )
    """)

    # Create thread messages table
    conn.execute("""
        CREATE TABLE IF NOT EXISTS thread_messages (
            doc_id TEXT NOT NULL,
            author TEXT NOT NULL,
            date TEXT,
            date_str TEXT,
            content_preview TEXT,
            message_index INTEGER NOT NULL,
            PRIMARY KEY (doc_id, message_index),
            FOREIGN KEY (doc_id) REFERENCES documents(doc_id)
        )
    """)

    # Create index for finding threads by participant
    conn.execute("""
        CREATE INDEX IF NOT EXISTS idx_thread_author
        ON thread_messages(author)
    """)

    conn.commit()
    return conn


def rebuild_fts_index(conn: sqlite3.Connection):
    """Rebuild the FTS5 index from documents table."""
    conn.execute("INSERT INTO documents_fts(documents_fts) VALUES('rebuild')")
    conn.commit()
