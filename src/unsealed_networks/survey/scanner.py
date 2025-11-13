#!/usr/bin/env python3
"""Document scanner - fast classification of document types."""

import re
from collections import defaultdict
from dataclasses import asdict, dataclass
from pathlib import Path


@dataclass
class DocumentClassification:
    """Classification result for a single document."""

    doc_id: str
    filepath: str
    file_size: int
    line_count: int
    document_type: str
    confidence: float
    entity_mentions: list[str]
    sample_lines: list[str]
    issues: list[str]


class DocumentScanner:
    """Fast scanner to classify document types."""

    # Email patterns
    EMAIL_PATTERNS = [
        (r"^From:\s+.+", "from_header"),
        (r"^To:\s+.+", "to_header"),
        (r"^Subject:\s+.+", "subject_header"),
        (r"^Sent:\s+\d{1,2}/\d{1,2}/\d{4}", "sent_header"),
        (r"jeevacation@gmail\.com", "epstein_email"),
    ]

    # Seed entities to track
    SEED_ENTITIES = {
        "Peter Thiel": r"\bPeter\s+Thiel\b",
        "Elon Musk": r"\bElon\s+Musk\b",
        "Bill Gates": r"\bBill\s+Gates\b",
        "Donald Trump": r"\b(?:Donald\s+)?Trump\b",
        "Bill Clinton": r"\bBill\s+Clinton\b",
        "Jeffrey Epstein": r"\b(?:Jeffrey\s+)?Epstein\b",
        "Ghislaine Maxwell": r"\bGhislaine\s+Maxwell\b|\bMaxwell\b",
        "Michael Wolff": r"\bMichael\s+Wolff?\b",
        "Landon Thomas": r"\bLandon\s+Thomas\b",
    }

    def __init__(self, text_dir: Path):
        self.text_dir = Path(text_dir)
        self.results: list[DocumentClassification] = []

    def scan_all(self, progress: bool = True) -> dict:
        """Scan all documents in the directory."""
        files = sorted(self.text_dir.rglob("*.txt"))
        total = len(files)

        if progress:
            print(f"Found {total} documents to scan...")

        for i, filepath in enumerate(files, 1):
            if progress and i % 100 == 0:
                print(f"  Scanned {i}/{total}...")

            classification = self.classify_document(filepath)
            self.results.append(classification)

        return self.generate_report()

    def classify_document(self, filepath: Path) -> DocumentClassification:
        """Classify a single document."""
        try:
            with open(filepath, encoding="utf-8", errors="replace") as f:
                lines = f.readlines()

            text = "".join(lines)
            doc_id = self.extract_doc_id(filepath.stem)
            file_size = filepath.stat().st_size
            line_count = len(lines)

            # Classify type
            doc_type, confidence = self.determine_type(text, lines)

            # Find entity mentions
            entities = self.find_entities(text)

            # Get sample lines (first 10, last 10, or all if <20)
            sample_lines = self._get_sample_lines(lines)

            # Check for issues
            issues = self._check_issues(text, lines)

            return DocumentClassification(
                doc_id=doc_id,
                filepath=str(filepath),
                file_size=file_size,
                line_count=line_count,
                document_type=doc_type,
                confidence=confidence,
                entity_mentions=entities,
                sample_lines=sample_lines,
                issues=issues,
            )

        except Exception as e:
            # Handle errors gracefully
            return DocumentClassification(
                doc_id=self.extract_doc_id(filepath.stem),
                filepath=str(filepath),
                file_size=0,
                line_count=0,
                document_type="error",
                confidence=0.0,
                entity_mentions=[],
                sample_lines=[],
                issues=[f"Error reading file: {e!s}"],
            )

    def determine_type(self, text: str, lines: list[str]) -> tuple[str, float]:
        """Determine document type and confidence score."""
        # Check for email patterns
        email_score = self._score_email(text, lines)

        # Check for narrative/article
        narrative_score = self._score_narrative(text, lines)

        # Check for HTML email
        html_score = self._score_html_email(text)

        # Pick highest scoring type
        scores = [
            ("email", email_score),
            ("narrative", narrative_score),
            ("html_email", html_score),
        ]

        doc_type, confidence = max(scores, key=lambda x: x[1])

        # If all scores are low, mark as unknown
        if confidence < 0.3:
            return "unknown", confidence

        return doc_type, confidence

    def _score_email(self, text: str, lines: list[str]) -> float:
        """Score likelihood this is an email."""
        score = 0.0
        max_score = len(self.EMAIL_PATTERNS)

        # Check first 20 lines for email headers
        header_text = "\n".join(lines[:20])

        for pattern, _ in self.EMAIL_PATTERNS:
            if re.search(pattern, header_text, re.IGNORECASE | re.MULTILINE):
                score += 1.0

        return score / max_score

    def _score_narrative(self, text: str, lines: list[str]) -> float:
        """Score likelihood this is narrative/article text."""
        score = 0.0

        # Long paragraphs
        if len(lines) > 100:
            score += 0.3

        # No email headers in first 10 lines
        header_text = "\n".join(lines[:10])
        if not re.search(r"^(From|To|Subject|Sent):", header_text, re.MULTILINE):
            score += 0.3

        # Narrative markers
        if re.search(r"\(L to R\)", text):
            score += 0.2
        if re.search(r"photograph(?:ed|er)", text, re.IGNORECASE):
            score += 0.2

        return min(score, 1.0)

    def _score_html_email(self, text: str) -> float:
        """Score likelihood this is HTML email."""
        score = 0.0

        # HTML tags
        if re.search(r"<https?://", text):
            score += 0.4
        if re.search(r"<!DOCTYPE|<html|<body", text, re.IGNORECASE):
            score += 0.3
        if text.count("<") > 20:  # Lots of HTML
            score += 0.3

        return min(score, 1.0)

    def find_entities(self, text: str) -> list[str]:
        """Find mentions of seed entities."""
        found = []
        for entity, pattern in self.SEED_ENTITIES.items():
            if re.search(pattern, text, re.IGNORECASE):
                found.append(entity)
        return found

    def extract_doc_id(self, filename: str) -> str:
        """Extract HOUSE_OVERSIGHT_XXXXXX from filename."""
        match = re.search(r"HOUSE_OVERSIGHT_\d+", filename)
        return match.group(0) if match else filename

    def _get_sample_lines(self, lines: list[str]) -> list[str]:
        """Get sample lines from document."""
        if len(lines) <= 20:
            return [line.strip() for line in lines if line.strip()]

        # First 10, last 10
        samples = lines[:10] + lines[-10:]
        return [line.strip() for line in samples if line.strip()]

    def _check_issues(self, text: str, lines: list[str]) -> list[str]:
        """Check for common issues."""
        issues = []

        if len(text) < 100:
            issues.append("Very short document")

        if text.count("�") > 5:
            issues.append("Encoding errors detected")

        if len(lines) == 0:
            issues.append("Empty file")

        return issues

    def generate_report(self) -> dict:
        """Generate aggregate statistics report."""
        total_docs = len(self.results)

        # Count by type
        type_counts = defaultdict(int)
        for result in self.results:
            type_counts[result.document_type] += 1

        # Entity mention counts
        entity_counts = defaultdict(int)
        for result in self.results:
            for entity in result.entity_mentions:
                entity_counts[entity] += 1

        # Confidence distribution
        high_conf = sum(1 for r in self.results if r.confidence > 0.7)

        # Issues
        total_issues = sum(len(r.issues) for r in self.results)

        return {
            "scan_date": None,  # Will be added when serialized
            "total_documents": total_docs,
            "total_size_mb": sum(r.file_size for r in self.results) / (1024 * 1024),
            "document_types": {
                dtype: {
                    "count": count,
                    "percentage": (count / total_docs * 100) if total_docs > 0 else 0,
                }
                for dtype, count in type_counts.items()
            },
            "entity_mentions": dict(
                sorted(entity_counts.items(), key=lambda x: x[1], reverse=True)
            ),
            "classification_quality": {
                "high_confidence_count": high_conf,
                "high_confidence_pct": (high_conf / total_docs * 100) if total_docs > 0 else 0,
            },
            "total_issues": total_issues,
        }

    def get_results(self) -> list[dict]:
        """Get all classification results as dicts."""
        return [asdict(r) for r in self.results]

    def get_emails(self, min_confidence: float = 0.7) -> list[DocumentClassification]:
        """Get all documents classified as emails above confidence threshold."""
        return [
            r for r in self.results if r.document_type == "email" and r.confidence >= min_confidence
        ]
