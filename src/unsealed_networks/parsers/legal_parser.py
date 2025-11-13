"""Legal document parser for court filings, depositions, and other legal documents."""

import re
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path


@dataclass
class LegalMetadata:
    """Metadata extracted from legal documents."""

    # Case information
    case_number: str | None = None
    court: str | None = None
    district: str | None = None

    # Parties
    plaintiffs: list[str] = field(default_factory=list)
    defendants: list[str] = field(default_factory=list)

    # Document information
    document_number: str | None = None
    document_type: str | None = None  # motion, deposition, brief, order, etc.
    filing_date: datetime | None = None
    filing_date_str: str | None = None

    # Attorneys
    attorneys: list[dict[str, str]] = field(default_factory=list)  # name, firm, role

    # Content sections
    title: str | None = None
    summary: str | None = None  # First paragraph or abstract
    body: str | None = None

    # Raw data
    raw_text: str | None = None


class LegalDocumentParser:
    """Parse legal documents to extract structured metadata."""

    # Configuration constants - extracted for maintainability
    MAX_HEADER_CHARS = 3000  # Characters to search for header metadata
    MAX_ATTORNEY_SEARCH_CHARS = 5000  # Characters to search for attorney information
    MIN_BODY_LINE_LENGTH = 10  # Minimum length for body content lines
    MAX_BODY_LINES = 1000  # Maximum lines of body to extract

    # Case number patterns
    CASE_NUMBER_PATTERN = re.compile(r"Case\s+(\d+:\d+-[a-z]+-\d+)", re.IGNORECASE)

    # Document filed pattern
    DOCUMENT_FILED_PATTERN = re.compile(r"Document\s+(\d+)\s+Filed\s+(\d+/\d+/\d+)", re.IGNORECASE)

    # Court patterns
    COURT_PATTERN = re.compile(
        r"(UNITED\s+STATES\s+(?:DISTRICT\s+COURT|COURT\s+OF\s+APPEALS))\s+"
        r"([A-Z\s]+(?:DISTRICT|CIRCUIT))",
        re.IGNORECASE,
    )

    # Party patterns (Plaintiff v. Defendant)
    # Updated to allow mixed-case names, not just all-caps
    PARTIES_PATTERN = re.compile(
        r"([A-Za-z][A-Za-z\s,.]+?),?\s+(?:et\s+al\.?)?,?\s+"
        r"(?:Plaintiff|Petitioner)s?,?\s+"
        r"v\.?\s+"
        r"([A-Za-z][A-Za-z\s,.]+?),?\s+(?:et\s+al\.?)?,?\s+"
        r"(?:Defendant|Respondent)s?",
        re.IGNORECASE,
    )

    # Attorney patterns
    ATTORNEY_PATTERN = re.compile(
        r"([A-Z][a-z]+\s+[A-Z][a-z]+(?:\s+[A-Z][a-z]+)?)\s+"  # Name
        r"(?:,\s*)?([^,\n]+?)?\s+"  # Optional firm
        r"(?:Bar\s+No\.|Attorney\s+for)",
        re.IGNORECASE,
    )

    # Document type patterns
    DOCUMENT_TYPE_PATTERNS = {
        "motion": re.compile(r"MOTION\s+(?:TO|FOR)", re.IGNORECASE),
        "memorandum": re.compile(r"MEMORANDUM\s+(?:OF\s+LAW|IN\s+SUPPORT)", re.IGNORECASE),
        "deposition": re.compile(r"DEPOSITION|EXAMINATION\s+OF", re.IGNORECASE),
        "order": re.compile(r"ORDER(?:\s+AND|\s+GRANTING|\s+DENYING)", re.IGNORECASE),
        "complaint": re.compile(r"COMPLAINT", re.IGNORECASE),
        "answer": re.compile(r"ANSWER\s+TO", re.IGNORECASE),
        "brief": re.compile(r"BRIEF\s+IN\s+SUPPORT", re.IGNORECASE),
    }

    def parse(self, filepath: Path) -> LegalMetadata:
        """Parse a legal document and extract all metadata.

        Args:
            filepath: Path to legal document file

        Returns:
            LegalMetadata with all extracted fields
        """
        with open(filepath, encoding="utf-8-sig", errors="replace") as f:
            content = f.read()

        metadata = LegalMetadata(raw_text=content)

        # Get first characters for header analysis
        header = content[: self.MAX_HEADER_CHARS]

        # Extract case number
        case_match = self.CASE_NUMBER_PATTERN.search(header)
        if case_match:
            metadata.case_number = case_match.group(1)

        # Extract document number and filing date
        doc_match = self.DOCUMENT_FILED_PATTERN.search(header)
        if doc_match:
            metadata.document_number = doc_match.group(1)
            metadata.filing_date_str = doc_match.group(2)
            metadata.filing_date = self._parse_date(doc_match.group(2))

        # Extract court information
        court_match = self.COURT_PATTERN.search(header)
        if court_match:
            metadata.court = court_match.group(1).strip()
            metadata.district = court_match.group(2).strip()

        # Extract parties
        parties_match = self.PARTIES_PATTERN.search(header)
        if parties_match:
            plaintiff_text = parties_match.group(1).strip()
            defendant_text = parties_match.group(2).strip()

            # Split if multiple parties (et al, commas, etc.)
            metadata.plaintiffs = [
                p.strip() for p in re.split(r",\s*(?:et\s+al\.?)?", plaintiff_text) if p.strip()
            ]
            metadata.defendants = [
                d.strip() for d in re.split(r",\s*(?:et\s+al\.?)?", defendant_text) if d.strip()
            ]

        # Detect document type
        for doc_type, pattern in self.DOCUMENT_TYPE_PATTERNS.items():
            if pattern.search(header):
                metadata.document_type = doc_type
                break

        # Extract attorneys
        metadata.attorneys = self._extract_attorneys(content)

        # Extract title (usually in all caps near top)
        title_match = re.search(
            r"^([A-Z][A-Z\s]{10,100})$",
            header,
            re.MULTILINE,
        )
        if title_match:
            metadata.title = title_match.group(1).strip()

        # Extract body (skip headers and footers)
        metadata.body = self._extract_body(content)

        return metadata

    def _extract_attorneys(self, content: str) -> list[dict[str, str]]:
        """Extract attorney information from document.

        Args:
            content: Full document text

        Returns:
            List of attorney dictionaries with name, firm, role
        """
        attorneys = []

        # Look for attorney sections
        attorney_section_pattern = re.compile(
            r"(?:Attorneys?\s+for\s+(?:Plaintiff|Defendant)s?:?)\s*\n(.+?)(?:\n\n|\Z)",
            re.IGNORECASE | re.DOTALL,
        )

        search_content = content[: self.MAX_ATTORNEY_SEARCH_CHARS]
        for section_match in attorney_section_pattern.finditer(search_content):
            section_text = section_match.group(1)

            # Extract individual attorneys from section
            for match in self.ATTORNEY_PATTERN.finditer(section_text):
                attorney = {
                    "name": match.group(1).strip(),
                    "firm": match.group(2).strip() if match.group(2) else None,
                    "role": "attorney",
                }
                attorneys.append(attorney)

        return attorneys

    def _extract_body(self, content: str) -> str:
        """Extract main body text, removing headers and footers.

        Args:
            content: Full document text

        Returns:
            Cleaned body text
        """
        lines = content.split("\n")

        # Find where body starts by looking for substantial content
        # Body typically starts after headers/case info/party listings
        body_start = 0
        for i, line in enumerate(lines):
            stripped = line.strip()

            # Look for first substantial line (>50 chars, not all caps)
            # that doesn't look like a header
            if (
                len(stripped) > 50
                and not stripped.isupper()
                and not re.match(r"^Case\s+\d+:", stripped)
                and not re.match(r"^Document\s+\d+", stripped)
            ):
                body_start = i
                break

        # Extract body lines, filtering out page numbers and case headers
        body_lines = []
        for line in lines[body_start:]:
            line = line.strip()

            # Skip short lines, page numbers, headers
            if len(line) < self.MIN_BODY_LINE_LENGTH:
                continue
            if re.match(r"^\d+$", line):  # Page numbers
                continue
            if re.match(r"^Case\s+\d+:", line):  # Case headers
                continue

            body_lines.append(line)

            # Return first configured lines of body content
            if len(body_lines) >= self.MAX_BODY_LINES:
                break

        return "\n".join(body_lines)

    def _parse_date(self, date_str: str) -> datetime | None:
        """Parse legal document date (MM/DD/YYYY or MM/DD/YY).

        Args:
            date_str: Date string

        Returns:
            datetime object or None
        """
        # Try MM/DD/YYYY
        match = re.match(r"(\d{1,2})/(\d{1,2})/(\d{4})", date_str)
        if match:
            month, day, year = match.groups()
            try:
                return datetime(int(year), int(month), int(day))
            except ValueError:
                pass

        # Try MM/DD/YY
        match = re.match(r"(\d{1,2})/(\d{1,2})/(\d{2})", date_str)
        if match:
            month, day, year = match.groups()
            year = int(year)
            # Assume 20xx for years < 50, 19xx for >= 50
            full_year = 2000 + year if year < 50 else 1900 + year
            try:
                return datetime(full_year, int(month), int(day))
            except ValueError:
                pass

        return None
