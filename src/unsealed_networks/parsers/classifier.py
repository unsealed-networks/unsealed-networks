"""Improved document classifier for all document types."""

import re
from dataclasses import dataclass
from pathlib import Path


@dataclass
class DocumentType:
    """Classification result with confidence."""

    doc_type: str  # email, legal, news, narrative, other
    confidence: float  # 0.0 - 1.0
    subtype: str | None = None  # More specific type (e.g., "court_filing", "deposition")


class DocumentClassifier:
    """Classify documents into types for appropriate parsing."""

    # Configuration constants - extracted for maintainability
    MAX_READ_SIZE = 51200  # Read first 50KB for classification (avoids loading huge files)
    CLASSIFICATION_HEADER_SIZE = 2000  # Use first 2000 chars for pattern matching

    # Email detection patterns
    EMAIL_HEADER_PATTERN = re.compile(
        r"From:\s+.+\nTo:\s+.+\nSubject:\s+.+\nSent:\s+\d+/\d+/\d+",
        re.MULTILINE,
    )

    # Legal document patterns
    CASE_NUMBER_PATTERN = re.compile(r"Case\s+\d+:\d+-[a-z]+-\d+", re.IGNORECASE)
    COURT_HEADER_PATTERN = re.compile(
        r"UNITED\s+STATES\s+DISTRICT\s+COURT|UNITED\s+STATES\s+COURT\s+OF\s+APPEALS",
        re.IGNORECASE,
    )
    DOCUMENT_FILED_PATTERN = re.compile(r"Document\s+\d+\s+Filed\s+\d+/\d+/\d+", re.IGNORECASE)

    # News article patterns
    BYLINE_PATTERN = re.compile(r"^By\s+[A-Z][a-z]+\s+[A-Z][a-z]+", re.MULTILINE)
    PUBLICATION_PATTERN = re.compile(
        r"(?:Palm\s+Beach\s+Post|New\s+York\s+Times|Washington\s+Post|Wall\s+Street\s+Journal)",
        re.IGNORECASE,
    )

    # Congressional record
    CONGRESSIONAL_PATTERN = re.compile(r"CONGRESSIONAL\s+RECORD", re.IGNORECASE)

    def classify(self, filepath: Path) -> DocumentType:
        """Classify a document by analyzing its structure.

        Args:
            filepath: Path to document file

        Returns:
            DocumentType with classification and confidence
        """
        with open(filepath, encoding="utf-8-sig", errors="replace") as f:
            content = f.read(self.MAX_READ_SIZE)

        # Get first characters for fast classification
        header = content[: self.CLASSIFICATION_HEADER_SIZE]

        # Check for email (highest priority - clearest markers)
        if self._is_email(header):
            return DocumentType(doc_type="email", confidence=0.95)

        # Check for legal documents
        legal_result = self._check_legal(header, content)
        if legal_result:
            return legal_result

        # Check for news articles
        if self._is_news(header):
            return DocumentType(doc_type="news", confidence=0.85, subtype="article")

        # Check for congressional record
        if self.CONGRESSIONAL_PATTERN.search(header):
            return DocumentType(doc_type="legal", confidence=0.90, subtype="congressional")

        # Check for narrative (long-form prose)
        if self._is_narrative(content):
            return DocumentType(doc_type="narrative", confidence=0.70)

        # Default to other
        return DocumentType(doc_type="other", confidence=0.50)

    def _is_email(self, header: str) -> bool:
        """Check if document is an email."""
        return bool(self.EMAIL_HEADER_PATTERN.search(header))

    def _check_legal(self, header: str, content: str) -> DocumentType | None:
        """Check if document is a legal filing."""
        confidence = 0.0
        subtype = None

        # Case number is strong indicator
        if self.CASE_NUMBER_PATTERN.search(header):
            confidence += 0.4
            subtype = "court_filing"

        # Court header
        if self.COURT_HEADER_PATTERN.search(header):
            confidence += 0.3

        # Document filed marker
        if self.DOCUMENT_FILED_PATTERN.search(header):
            confidence += 0.2

        # Deposition markers
        if re.search(r"DEPOSITION|EXAMINATION\s+OF", content[:3000], re.IGNORECASE):
            confidence += 0.3
            subtype = "deposition"

        # Motion markers
        if re.search(r"MOTION\s+(?:TO|FOR)|MEMORANDUM\s+OF\s+LAW", header, re.IGNORECASE):
            confidence += 0.2
            subtype = "motion"

        if confidence >= 0.5:
            return DocumentType(doc_type="legal", confidence=min(confidence, 0.95), subtype=subtype)

        return None

    def _is_news(self, header: str) -> bool:
        """Check if document is a news article."""
        has_byline = bool(self.BYLINE_PATTERN.search(header))
        has_publication = bool(self.PUBLICATION_PATTERN.search(header))

        return has_byline or has_publication

    def _is_narrative(self, content: str) -> bool:
        """Check if document is narrative prose."""
        # Count sentences and check for first-person
        lines = content.split("\n")
        text_lines = [line.strip() for line in lines if len(line.strip()) > 20]

        if len(text_lines) < 10:
            return False

        # Look for narrative markers - expanded verb list for better detection
        has_first_person = bool(
            re.search(
                r"\bI\s+(?:have|was|am|had|did|said|went|saw|thought|felt|believe|remember|knew)\b",
                content,
                re.IGNORECASE,
            )
        )
        has_long_paragraphs = any(len(line) > 200 for line in text_lines)

        return has_first_person and has_long_paragraphs
