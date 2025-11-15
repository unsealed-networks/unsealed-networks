"""Tests for URL extraction pipeline step."""

import pytest

from unsealed_networks.pipeline.manifest import Manifest
from unsealed_networks.pipeline.steps.extract_urls import ExtractURLsStep


@pytest.fixture
def temp_doc(tmp_path):
    """Create a temporary test document."""
    doc_path = tmp_path / "test_doc.txt"
    return doc_path


@pytest.fixture
def empty_manifest():
    """Create a fresh manifest for testing."""
    return Manifest.create_new("TEST_DOC_001", "test.txt")


class TestExtractURLsStep:
    """Test suite for URL extraction step."""

    def test_extracts_single_url(self, temp_doc, empty_manifest):
        """Should extract a single URL from document."""
        temp_doc.write_text("Visit https://example.com for details")

        step = ExtractURLsStep()
        outcome = step.execute(temp_doc, empty_manifest)

        assert outcome["urls_found"] == 1
        assert outcome["urls"][0]["url"] == "https://example.com"
        assert outcome["urls"][0]["domain"] == "example.com"
        assert outcome["urls"][0]["type"] == "other"

    def test_extracts_multiple_urls(self, temp_doc, empty_manifest):
        """Should extract multiple URLs from document."""
        content = """
        Check out https://youtube.com/watch?v=abc123
        and also https://news.bbc.com/article.html
        """
        temp_doc.write_text(content)

        step = ExtractURLsStep()
        outcome = step.execute(temp_doc, empty_manifest)

        assert outcome["urls_found"] == 2
        # Check YouTube classification
        youtube_url = next(u for u in outcome["urls"] if "youtube" in u["url"])
        assert youtube_url["type"] == "youtube"
        # Check news classification
        news_url = next(u for u in outcome["urls"] if "bbc" in u["url"])
        assert news_url["type"] == "news"

    def test_deduplicates_urls(self, temp_doc, empty_manifest):
        """Should not return duplicate URLs."""
        content = """
        Visit https://example.com
        Visit https://example.com again
        """
        temp_doc.write_text(content)

        step = ExtractURLsStep()
        outcome = step.execute(temp_doc, empty_manifest)

        assert outcome["urls_found"] == 1

    def test_handles_no_urls(self, temp_doc, empty_manifest):
        """Should handle documents with no URLs."""
        temp_doc.write_text("This document has no URLs at all.")

        step = ExtractURLsStep()
        outcome = step.execute(temp_doc, empty_manifest)

        assert outcome["urls_found"] == 0
        assert outcome["urls"] == []

    def test_stores_data_in_outcome(self, temp_doc, empty_manifest):
        """Should store extracted URLs in step outcome, not global metadata."""
        temp_doc.write_text("Visit https://example.com")

        step = ExtractURLsStep()
        outcome = step.execute(temp_doc, empty_manifest)

        # Check data is in outcome
        assert "urls" in outcome
        assert outcome["urls"][0]["url"] == "https://example.com"

        # Verify global metadata is NOT updated by this step
        assert "urls" not in empty_manifest.metadata

    def test_classifies_youtube_urls(self, temp_doc, empty_manifest):
        """Should classify YouTube URLs correctly."""
        content = "Watch https://youtube.com/watch?v=abc and https://youtu.be/def"
        temp_doc.write_text(content)

        step = ExtractURLsStep()
        outcome = step.execute(temp_doc, empty_manifest)

        assert outcome["urls_found"] == 2
        assert all(u["type"] == "youtube" for u in outcome["urls"])

    def test_classifies_pdf_urls(self, temp_doc, empty_manifest):
        """Should classify PDF URLs correctly."""
        temp_doc.write_text("Download https://example.com/document.pdf")

        step = ExtractURLsStep()
        outcome = step.execute(temp_doc, empty_manifest)

        assert outcome["urls"][0]["type"] == "pdf"

    def test_classifies_social_media_urls(self, temp_doc, empty_manifest):
        """Should classify social media URLs correctly."""
        content = """
        Twitter: https://twitter.com/user/status/123
        Short: https://t.co/abc123
        """
        temp_doc.write_text(content)

        step = ExtractURLsStep()
        outcome = step.execute(temp_doc, empty_manifest)

        assert all(u["type"] == "social" for u in outcome["urls"])

    def test_records_url_position(self, temp_doc, empty_manifest):
        """Should record the position of URLs in document."""
        temp_doc.write_text("Start https://example.com end")

        step = ExtractURLsStep()
        outcome = step.execute(temp_doc, empty_manifest)

        assert "position" in outcome["urls"][0]
        assert outcome["urls"][0]["position"] == 6  # Position of 'https'

    def test_handles_http_and_https(self, temp_doc, empty_manifest):
        """Should handle both HTTP and HTTPS URLs."""
        content = "HTTP: http://example.com HTTPS: https://example.org"
        temp_doc.write_text(content)

        step = ExtractURLsStep()
        outcome = step.execute(temp_doc, empty_manifest)

        assert outcome["urls_found"] == 2

    def test_step_properties(self):
        """Should have correct step metadata."""
        step = ExtractURLsStep()

        assert step.name == "extract_urls"
        assert step.version == 1
        assert step.depends_on == []  # No dependencies

    def test_handles_unicode_documents(self, temp_doc, empty_manifest):
        """Should handle documents with Unicode characters."""
        content = "Check this: https://example.com/path 日本語 text"
        temp_doc.write_text(content, encoding="utf-8")

        step = ExtractURLsStep()
        outcome = step.execute(temp_doc, empty_manifest)

        assert outcome["urls_found"] == 1

    def test_ignores_urls_without_protocol(self, temp_doc, empty_manifest):
        """Should not extract URLs without http/https protocol."""
        temp_doc.write_text("Visit www.example.com or example.org")

        step = ExtractURLsStep()
        outcome = step.execute(temp_doc, empty_manifest)

        # Should not find any URLs (no http/https)
        assert outcome["urls_found"] == 0
