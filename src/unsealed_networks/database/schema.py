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

    # Create canonical entities table for entity merging/normalization
    conn.execute("""
        CREATE TABLE IF NOT EXISTS canonical_entities (
            canonical_id INTEGER PRIMARY KEY AUTOINCREMENT,
            entity_type TEXT NOT NULL
                CHECK(entity_type IN ('person', 'organization', 'location', 'date')),
            canonical_text TEXT NOT NULL,
            canonical_normalized TEXT NOT NULL,
            total_mentions INTEGER DEFAULT 0,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            UNIQUE(canonical_normalized, entity_type)
        )
    """)

    # Create index on canonical entities for fast lookups
    conn.execute("""
        CREATE INDEX IF NOT EXISTS idx_canonical_normalized
        ON canonical_entities(entity_type, canonical_normalized)
    """)

    # Create entity aliases table to map entities to canonical forms
    conn.execute("""
        CREATE TABLE IF NOT EXISTS entity_aliases (
            entity_id INTEGER PRIMARY KEY,
            canonical_id INTEGER NOT NULL,
            is_canonical BOOLEAN DEFAULT 0,
            merge_method TEXT,
            merge_confidence REAL,
            merged_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            merged_by TEXT,
            FOREIGN KEY (entity_id) REFERENCES entities(entity_id),
            FOREIGN KEY (canonical_id) REFERENCES canonical_entities(canonical_id)
        )
    """)

    # Create index for fast canonical lookups
    conn.execute("""
        CREATE INDEX IF NOT EXISTS idx_entity_aliases_canonical
        ON entity_aliases(canonical_id)
    """)

    # Create FTS5 virtual table for canonical entity search
    conn.execute("""
        CREATE VIRTUAL TABLE IF NOT EXISTS canonical_entities_fts USING fts5(
            canonical_text,
            canonical_normalized,
            content='canonical_entities',
            content_rowid='canonical_id'
        )
    """)

    # Triggers to keep canonical_entities_fts in sync
    conn.execute("""
        CREATE TRIGGER IF NOT EXISTS canonical_entities_ai AFTER INSERT ON canonical_entities BEGIN
            INSERT INTO canonical_entities_fts(rowid, canonical_text, canonical_normalized)
            VALUES (new.canonical_id, new.canonical_text, new.canonical_normalized);
        END
    """)

    conn.execute("""
        CREATE TRIGGER IF NOT EXISTS canonical_entities_ad
        AFTER DELETE ON canonical_entities BEGIN
            INSERT INTO canonical_entities_fts(
                canonical_entities_fts, rowid, canonical_text, canonical_normalized
            )
            VALUES('delete', old.canonical_id, old.canonical_text, old.canonical_normalized);
        END
    """)

    conn.execute("""
        CREATE TRIGGER IF NOT EXISTS canonical_entities_au
        AFTER UPDATE ON canonical_entities BEGIN
            INSERT INTO canonical_entities_fts(
                canonical_entities_fts, rowid, canonical_text, canonical_normalized
            )
            VALUES('delete', old.canonical_id, old.canonical_text, old.canonical_normalized);
            INSERT INTO canonical_entities_fts(rowid, canonical_text, canonical_normalized)
            VALUES (new.canonical_id, new.canonical_text, new.canonical_normalized);
        END
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

    # Create FTS5 virtual table for entity search
    conn.execute("""
        CREATE VIRTUAL TABLE IF NOT EXISTS entities_fts USING fts5(
            text,
            normalized_text,
            content='entities',
            content_rowid='entity_id'
        )
    """)

    # Triggers to keep entities_fts in sync with entities table
    conn.execute("""
        CREATE TRIGGER IF NOT EXISTS entities_ai AFTER INSERT ON entities BEGIN
            INSERT INTO entities_fts(rowid, text, normalized_text)
            VALUES (new.entity_id, new.text, new.normalized_text);
        END
    """)

    conn.execute("""
        CREATE TRIGGER IF NOT EXISTS entities_ad AFTER DELETE ON entities BEGIN
            INSERT INTO entities_fts(entities_fts, rowid, text, normalized_text)
            VALUES('delete', old.entity_id, old.text, old.normalized_text);
        END
    """)

    conn.execute("""
        CREATE TRIGGER IF NOT EXISTS entities_au AFTER UPDATE ON entities BEGIN
            INSERT INTO entities_fts(entities_fts, rowid, text, normalized_text)
            VALUES('delete', old.entity_id, old.text, old.normalized_text);
            INSERT INTO entities_fts(rowid, text, normalized_text)
            VALUES (new.entity_id, new.text, new.normalized_text);
        END
    """)

    # Create FTS5 virtual table for thread author search
    conn.execute("""
        CREATE VIRTUAL TABLE IF NOT EXISTS thread_messages_fts USING fts5(
            author,
            content='thread_messages',
            content_rowid='rowid'
        )
    """)

    # Triggers to keep thread_messages_fts in sync
    conn.execute("""
        CREATE TRIGGER IF NOT EXISTS thread_messages_ai AFTER INSERT ON thread_messages BEGIN
            INSERT INTO thread_messages_fts(rowid, author)
            VALUES (new.rowid, new.author);
        END
    """)

    conn.execute("""
        CREATE TRIGGER IF NOT EXISTS thread_messages_ad AFTER DELETE ON thread_messages BEGIN
            INSERT INTO thread_messages_fts(thread_messages_fts, rowid, author)
            VALUES('delete', old.rowid, old.author);
        END
    """)

    conn.execute("""
        CREATE TRIGGER IF NOT EXISTS thread_messages_au AFTER UPDATE ON thread_messages BEGIN
            INSERT INTO thread_messages_fts(thread_messages_fts, rowid, author)
            VALUES('delete', old.rowid, old.author);
            INSERT INTO thread_messages_fts(rowid, author)
            VALUES (new.rowid, new.author);
        END
    """)

    conn.commit()
    return conn


def rebuild_fts_index(conn: sqlite3.Connection):
    """Rebuild all FTS5 indexes from their source tables."""
    conn.execute("INSERT INTO documents_fts(documents_fts) VALUES('rebuild')")
    conn.execute("INSERT INTO entities_fts(entities_fts) VALUES('rebuild')")
    conn.execute("INSERT INTO canonical_entities_fts(canonical_entities_fts) VALUES('rebuild')")
    conn.execute("INSERT INTO thread_messages_fts(thread_messages_fts) VALUES('rebuild')")
    conn.commit()
