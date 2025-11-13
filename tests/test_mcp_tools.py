"""Test MCP server tools with actual database."""

import sqlite3

import pytest


@pytest.fixture
def test_db(tmp_path):
    """Create a minimal test database."""
    from unsealed_networks.database.schema import init_database

    db_path = tmp_path / "test.db"
    conn = init_database(db_path)

    # Insert test documents
    test_docs = [
        (
            "HOUSE_OVERSIGHT_001",
            "/path/to/doc1.txt",
            "email",
            0.95,
            50,
            (
                "From: Peter Thiel\nTo: Jeffrey Epstein\nSubject: Meeting\n"
                "Let's discuss the Gates Foundation project."
            ),
        ),
        (
            "HOUSE_OVERSIGHT_002",
            "/path/to/doc2.txt",
            "email",
            0.90,
            30,
            (
                "From: Bill Gates\nTo: Jeffrey Epstein\nSubject: Donation\n"
                "Regarding the donor advised fund."
            ),
        ),
    ]

    conn.executemany(
        """
        INSERT INTO documents (doc_id, filepath, doc_type, confidence, line_count, full_text)
        VALUES (?, ?, ?, ?, ?, ?)
        """,
        test_docs,
    )

    # Insert into FTS
    conn.executemany(
        """
        INSERT INTO documents_fts (doc_id, full_text)
        VALUES (?, ?)
        """,
        [(doc[0], doc[5]) for doc in test_docs],
    )

    # Insert entity mentions
    entity_mentions = [
        ("HOUSE_OVERSIGHT_001", "Peter Thiel"),
        ("HOUSE_OVERSIGHT_001", "Jeffrey Epstein"),
        ("HOUSE_OVERSIGHT_002", "Bill Gates"),
        ("HOUSE_OVERSIGHT_002", "Jeffrey Epstein"),
    ]

    conn.executemany(
        """
        INSERT INTO entity_mentions (doc_id, entity_name)
        VALUES (?, ?)
        """,
        entity_mentions,
    )

    conn.commit()
    conn.close()

    return db_path


def test_search_documents(test_db):
    """Test full-text search."""
    conn = sqlite3.connect(test_db)
    conn.row_factory = sqlite3.Row

    # Search for "donor" which only appears in doc 002
    cursor = conn.execute(
        """
        SELECT d.doc_id, d.doc_type
        FROM documents_fts
        JOIN documents d ON documents_fts.doc_id = d.doc_id
        WHERE documents_fts MATCH ?
        """,
        ("donor",),
    )

    results = cursor.fetchall()
    assert len(results) == 1
    assert results[0]["doc_id"] == "HOUSE_OVERSIGHT_002"

    conn.close()


def test_find_by_entity(test_db):
    """Test entity lookup."""
    conn = sqlite3.connect(test_db)
    conn.row_factory = sqlite3.Row

    cursor = conn.execute(
        """
        SELECT d.doc_id
        FROM documents d
        JOIN entity_mentions e ON d.doc_id = e.doc_id
        WHERE e.entity_name = ?
        """,
        ("Jeffrey Epstein",),
    )

    results = cursor.fetchall()
    assert len(results) == 2  # Both documents mention Epstein

    conn.close()


def test_get_document(test_db):
    """Test document retrieval."""
    conn = sqlite3.connect(test_db)
    conn.row_factory = sqlite3.Row

    cursor = conn.execute(
        """
        SELECT doc_id, full_text
        FROM documents
        WHERE doc_id = ?
        """,
        ("HOUSE_OVERSIGHT_001",),
    )

    result = cursor.fetchone()
    assert result is not None
    assert "Peter Thiel" in result["full_text"]

    conn.close()
