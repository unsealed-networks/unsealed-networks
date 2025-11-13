"""Tests for document scanner."""

from pathlib import Path

import pytest

from unsealed_networks.survey.scanner import DocumentScanner


@pytest.fixture
def sample_email_text():
    """Sample email text."""
    return """From: John Doe
Sent: 1/15/2017 10:30:00 AM
To: jeevacation@gmail.com
Subject: Meeting notes
Importance: High

Peter Thiel and I discussed the proposal.

please note
The information contained in this communication is
confidential...
HOUSE OVERSIGHT 012345
"""


@pytest.fixture
def sample_narrative_text():
    """Sample narrative text."""
    return """    It's an absurdly vast house, among the largest in Manhattan,
but the dining room is windowless, creating a hermetic or stop-time sense.

    In sweatshirt, draw-string pants, palm beach slippers, and half glasses,
Jeffrey Epstein sits at the head of the table.

    A week in late September begins, over Sunday lunch, with a colloquial for
billionaires: Bill Gates, Peter Thiel, and others discussing philanthropy.
"""


def test_email_classification(tmp_path, sample_email_text):
    """Test that emails are correctly classified."""
    # Create temp file
    test_file = tmp_path / "HOUSE_OVERSIGHT_012345.txt"
    test_file.write_text(sample_email_text)

    scanner = DocumentScanner(tmp_path)
    result = scanner.classify_document(test_file)

    assert result.document_type == "email"
    assert result.confidence > 0.7
    assert result.doc_id == "HOUSE_OVERSIGHT_012345"
    assert "Peter Thiel" in result.entity_mentions


def test_narrative_classification(tmp_path, sample_narrative_text):
    """Test that narratives are correctly classified."""
    # Create temp file
    test_file = tmp_path / "HOUSE_OVERSIGHT_022894.txt"
    test_file.write_text(sample_narrative_text)

    scanner = DocumentScanner(tmp_path)
    result = scanner.classify_document(test_file)

    assert result.document_type == "narrative"
    assert "Jeffrey Epstein" in result.entity_mentions
    assert "Peter Thiel" in result.entity_mentions
    assert "Bill Gates" in result.entity_mentions


def test_entity_extraction(tmp_path, sample_email_text):
    """Test entity extraction."""
    test_file = tmp_path / "test.txt"
    test_file.write_text(sample_email_text)

    scanner = DocumentScanner(tmp_path)
    result = scanner.classify_document(test_file)

    assert "Peter Thiel" in result.entity_mentions


def test_scan_all(tmp_path, sample_email_text):
    """Test scanning multiple files."""
    # Create multiple test files
    for i in range(5):
        test_file = tmp_path / f"HOUSE_OVERSIGHT_0{i}.txt"
        test_file.write_text(sample_email_text)

    scanner = DocumentScanner(tmp_path)
    report = scanner.scan_all(progress=False)

    assert report["total_documents"] == 5
    assert report["document_types"]["email"]["count"] == 5
    assert "Peter Thiel" in report["entity_mentions"]


def test_get_emails(tmp_path, sample_email_text, sample_narrative_text):
    """Test getting only email documents."""
    # Create mix of files
    email_file = tmp_path / "HOUSE_OVERSIGHT_01.txt"
    email_file.write_text(sample_email_text)

    narrative_file = tmp_path / "HOUSE_OVERSIGHT_02.txt"
    narrative_file.write_text(sample_narrative_text)

    scanner = DocumentScanner(tmp_path)
    scanner.scan_all(progress=False)

    emails = scanner.get_emails(min_confidence=0.7)

    assert len(emails) == 1
    assert emails[0].document_type == "email"


def test_doc_id_extraction():
    """Test document ID extraction."""
    scanner = DocumentScanner(Path("."))

    assert scanner.extract_doc_id("HOUSE_OVERSIGHT_012345") == "HOUSE_OVERSIGHT_012345"
    assert (
        scanner.extract_doc_id("prefix_HOUSE_OVERSIGHT_067890_suffix") == "HOUSE_OVERSIGHT_067890"
    )
