"""News article parser for extracting structured metadata from news documents."""

import re
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path


@dataclass
class NewsMetadata:
    """Metadata extracted from news articles."""

    # Article information
    headline: str | None = None
    author: str | None = None
    publication: str | None = None
    publication_date: datetime | None = None
    publication_date_str: str | None = None

    # Content
    body: str | None = None
    summary: str | None = None  # First paragraph or lede

    # Classification
    section: str | None = None  # Opinion, News, Business, etc.
    article_type: str | None = None  # Editorial, news, profile, etc.

    # Raw data
    raw_text: str | None = None


class NewsArticleParser:
    """Parse news articles to extract structured metadata."""

    # Configuration constants - extracted from magic numbers for maintainability
    MAX_HEADER_LINES = 50  # Maximum lines to search for article header
    MAX_HEADER_CHARS = 1000  # Maximum characters to extract for header analysis
    MAX_BODY_LINES = 1000  # Maximum body lines to extract
    MIN_BODY_START_LINE_LENGTH = 50  # Minimum line length to identify body start
    MIN_BODY_LINE_LENGTH = 20  # Minimum length for body content lines

    # Byline patterns - updated to handle middle initials, hyphens, apostrophes
    BYLINE_PATTERNS = [
        re.compile(r"^By\s+([A-Z][A-Za-z.'\\s-]+?)(?:,|$)", re.MULTILINE),
        re.compile(
            r"^([A-Z][A-Za-z.'\\s-]+?)(?:,|$)\s+(?:Staff\s+Writer|Correspondent)", re.MULTILINE
        ),
    ]

    # Publication patterns
    PUBLICATION_PATTERNS = {
        "Palm Beach Post": re.compile(r"Palm\s+Beach\s+Post", re.IGNORECASE),
        "New York Times": re.compile(r"New\s+York\s+Times", re.IGNORECASE),
        "Washington Post": re.compile(r"Washington\s+Post", re.IGNORECASE),
        "Wall Street Journal": re.compile(r"Wall\s+Street\s+Journal", re.IGNORECASE),
        "Miami Herald": re.compile(r"Miami\s+Herald", re.IGNORECASE),
    }

    # Date patterns for news articles
    DATE_PATTERNS = [
        re.compile(r"([A-Z][a-z]+)\s+(\d{1,2}),\s+(\d{4})"),  # Month DD, YYYY
        re.compile(r"(\d{1,2})/(\d{1,2})/(\d{4})"),  # MM/DD/YYYY
    ]

    # Section patterns
    SECTION_PATTERNS = {
        "editorial": re.compile(r"EDITORIAL|OPINION", re.IGNORECASE),
        "news": re.compile(r"NEWS|LOCAL", re.IGNORECASE),
        "business": re.compile(r"BUSINESS|ECONOMY", re.IGNORECASE),
    }

    def parse(self, filepath: Path) -> NewsMetadata:
        """Parse a news article and extract all metadata.

        Args:
            filepath: Path to news article file

        Returns:
            NewsMetadata with all extracted fields
        """
        with open(filepath, encoding="utf-8-sig", errors="replace") as f:
            content = f.read()

        metadata = NewsMetadata(raw_text=content)

        # Get first characters for header analysis
        header = content[: self.MAX_HEADER_CHARS]

        # Extract publication
        for pub_name, pattern in self.PUBLICATION_PATTERNS.items():
            if pattern.search(header):
                metadata.publication = pub_name
                break

        # Extract author/byline
        for pattern in self.BYLINE_PATTERNS:
            match = pattern.search(header)
            if match:
                metadata.author = match.group(1).strip()
                break

        # Extract date
        for pattern in self.DATE_PATTERNS:
            match = pattern.search(header)
            if match:
                metadata.publication_date_str = match.group(0)
                metadata.publication_date = self._parse_date(match)
                break

        # Extract headline (can be Title Case or all-caps)
        headline_match = re.search(
            r"^([A-Z][a-z]+(?:\s+[A-Za-z].*)+|[A-Z\s]{10,100})$",
            header,
            re.MULTILINE,
        )
        if headline_match:
            metadata.headline = headline_match.group(1).strip()

        # Detect section
        for section, pattern in self.SECTION_PATTERNS.items():
            if pattern.search(header):
                metadata.section = section
                break

        # Extract body and summary
        metadata.body = self._extract_body(content)
        if metadata.body:
            # First paragraph as summary
            paragraphs = [p.strip() for p in metadata.body.split("\n\n") if p.strip()]
            if paragraphs:
                metadata.summary = paragraphs[0]

        # Detect article type
        if re.search(r"editorial|opinion", header, re.IGNORECASE):
            metadata.article_type = "editorial"
        elif re.search(r"profile|about|biography", header, re.IGNORECASE):
            metadata.article_type = "profile"
        else:
            metadata.article_type = "news"

        return metadata

    def _extract_body(self, content: str) -> str:
        """Extract article body, removing headers and footers.

        Args:
            content: Full article text

        Returns:
            Cleaned body text
        """
        lines = content.split("\n")

        # Find where body starts (after byline/date/headline)
        # Search within MAX_HEADER_LINES instead of hardcoded 30
        body_start = 0
        search_limit = min(len(lines), self.MAX_HEADER_LINES)
        for i, line in enumerate(lines[:search_limit]):
            line = line.strip()
            # Body usually starts after a blank line following headers
            if len(line) > self.MIN_BODY_START_LINE_LENGTH and not line.isupper():
                body_start = i
                break

        # Extract body lines up to MAX_BODY_LINES
        body_lines = []
        for line in lines[body_start:]:
            line = line.strip()

            # Skip short lines and page markers
            if len(line) < self.MIN_BODY_LINE_LENGTH:
                continue
            if re.match(r"^Page\s+\d+", line, re.IGNORECASE):
                continue

            body_lines.append(line)

            # Stop at configurable length instead of hardcoded 500
            if len(body_lines) >= self.MAX_BODY_LINES:
                break

        return "\n\n".join(body_lines)

    def _parse_date(self, match: re.Match) -> datetime | None:
        """Parse date from regex match.

        Args:
            match: Regex match object containing date parts

        Returns:
            datetime object or None
        """
        groups = match.groups()

        # Month name format (January 15, 2020)
        if len(groups) == 3 and groups[0].isalpha():
            month_names = {
                "january": 1,
                "february": 2,
                "march": 3,
                "april": 4,
                "may": 5,
                "june": 6,
                "july": 7,
                "august": 8,
                "september": 9,
                "october": 10,
                "november": 11,
                "december": 12,
            }
            month_name = groups[0].lower()
            day = int(groups[1])
            year = int(groups[2])

            if month_name in month_names:
                try:
                    return datetime(year, month_names[month_name], day)
                except ValueError:
                    pass

        # Numeric format (MM/DD/YYYY)
        elif len(groups) == 3:
            try:
                month, day, year = int(groups[0]), int(groups[1]), int(groups[2])
                return datetime(year, month, day)
            except ValueError:
                pass

        return None
