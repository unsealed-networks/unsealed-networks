"""Email parser for extracting structured metadata from email documents."""

import re
from dataclasses import dataclass, field
from datetime import datetime
from email.utils import parsedate_to_datetime
from pathlib import Path


@dataclass
class EmailAddress:
    """Structured email address with name."""

    email: str
    name: str | None = None

    def __str__(self) -> str:
        if self.name:
            return f"{self.name} <{self.email}>"
        return self.email


@dataclass
class EmailMetadata:
    """Complete email metadata extraction."""

    # Core headers
    from_addr: EmailAddress | None = None
    to_addrs: list[EmailAddress] = field(default_factory=list)
    cc_addrs: list[EmailAddress] = field(default_factory=list)
    bcc_addrs: list[EmailAddress] = field(default_factory=list)
    subject: str | None = None
    date: datetime | None = None
    date_str: str | None = None  # Original date string

    # Threading
    in_reply_to: str | None = None  # Message-ID of parent
    references: list[str] = field(default_factory=list)  # Thread chain
    is_reply: bool = False
    is_forward: bool = False

    # Body structure
    body: str | None = None
    quoted_text: list[str] = field(default_factory=list)  # Previous messages in thread
    signature: str | None = None

    # Additional metadata
    message_id: str | None = None
    reply_to: EmailAddress | None = None
    attachments: list[str] = field(default_factory=list)

    # Raw data
    raw_headers: dict[str, str] = field(default_factory=dict)
    raw_text: str | None = None


class EmailParser:
    """Parse email documents to extract maximum metadata."""

    # Configuration constants - extracted for maintainability
    MAX_QUOTE_EXTRACTION_LINES = 50  # Maximum lines to extract for quoted text sections

    # Email address pattern
    EMAIL_PATTERN = re.compile(r"([a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,})")

    # Name + email pattern (e.g., "John Doe <john@example.com>")
    NAME_EMAIL_PATTERN = re.compile(
        r"([^<]+?)\s*<([a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,})>"
    )

    # Date patterns
    DATE_PATTERN = re.compile(r"(\d{1,2})/(\d{1,2})/(\d{4})\s+(\d{1,2}):(\d{2}):(\d{2})\s+(AM|PM)")

    # Threading patterns
    REPLY_SUBJECT_PATTERN = re.compile(r"^Re:\s*", re.IGNORECASE)
    FORWARD_SUBJECT_PATTERN = re.compile(r"^Fwd?:\s*", re.IGNORECASE)

    # Quote markers
    QUOTE_PATTERNS = [
        re.compile(r"^>\s*", re.MULTILINE),  # > prefix
        re.compile(r"^On .+ wrote:$", re.MULTILINE),  # "On DATE, NAME wrote:"
        re.compile(r"^-+\s*Original Message\s*-+", re.IGNORECASE | re.MULTILINE),
        re.compile(r"^From:.*\nSent:.*\nTo:.*\nSubject:", re.MULTILINE),  # Forwarded headers
    ]

    # Signature markers
    SIGNATURE_PATTERN = re.compile(r"^--\s*$", re.MULTILINE)

    def parse(self, filepath: Path) -> EmailMetadata:
        """Parse an email file and extract all metadata.

        Args:
            filepath: Path to email text file

        Returns:
            EmailMetadata with all extracted fields
        """
        with open(filepath, encoding="utf-8-sig", errors="replace") as f:
            content = f.read()

        metadata = EmailMetadata(raw_text=content)

        # Split into lines for processing
        lines = content.split("\n")

        # Extract headers
        header_end = self._parse_headers(lines, metadata)

        # Extract body and signature
        self._parse_body(lines[header_end:], metadata)

        # Detect threading from subject
        if metadata.subject:
            if self.REPLY_SUBJECT_PATTERN.match(metadata.subject):
                metadata.is_reply = True
            if self.FORWARD_SUBJECT_PATTERN.match(metadata.subject):
                metadata.is_forward = True

        return metadata

    def _parse_headers(self, lines: list[str], metadata: EmailMetadata) -> int:
        """Parse email headers and return line number where headers end.

        Args:
            lines: List of lines from email
            metadata: EmailMetadata object to populate

        Returns:
            Line number where headers end
        """
        header_patterns = {
            "from": r"^From:\s*(.+)$",
            "to": r"^To:\s*(.+)$",
            "cc": r"^Cc:\s*(.+)$",
            "bcc": r"^Bcc:\s*(.+)$",
            "subject": r"^Subject:\s*(.+)$",
            "sent": r"^Sent:\s*(.+)$",
            "date": r"^Date:\s*(.+)$",
            "message-id": r"^Message-ID:\s*(.+)$",
            "in-reply-to": r"^In-Reply-To:\s*(.+)$",
            "references": r"^References:\s*(.+)$",
            "reply-to": r"^Reply-To:\s*(.+)$",
        }

        # Pre-process lines to join continuation lines
        joined_lines = []
        i = 0
        while i < len(lines):
            line = lines[i]

            # Empty line signals end of headers
            if not line.strip():
                header_end = i + 1
                break

            # If this is a continuation line (starts with space/tab), skip it
            # It will be joined by the logic below
            if line.startswith((" ", "\t")):
                i += 1
                continue

            # Start with this line
            current_line = line

            # Look ahead for continuation lines
            j = i + 1
            while j < len(lines) and lines[j].startswith((" ", "\t")):
                # Join continuation line, removing the leading whitespace
                current_line += " " + lines[j].strip()
                j += 1

            joined_lines.append(current_line)
            i = j
        else:
            # If we exit the loop without finding an empty line
            header_end = len(lines)

        # Now parse the joined header lines
        for line in joined_lines:
            line = line.strip()

            # Check each header pattern
            for header_name, pattern in header_patterns.items():
                match = re.match(pattern, line, re.IGNORECASE)
                if match:
                    value = match.group(1).strip()
                    metadata.raw_headers[header_name] = value

                    # Process specific headers
                    if header_name == "from":
                        metadata.from_addr = self._parse_email_address(value)
                    elif header_name == "to":
                        metadata.to_addrs = self._parse_email_list(value)
                    elif header_name == "cc":
                        metadata.cc_addrs = self._parse_email_list(value)
                    elif header_name == "bcc":
                        metadata.bcc_addrs = self._parse_email_list(value)
                    elif header_name == "subject":
                        metadata.subject = value
                    elif header_name in ("sent", "date"):
                        metadata.date_str = value
                        metadata.date = self._parse_date(value)
                    elif header_name == "message-id":
                        metadata.message_id = value
                    elif header_name == "in-reply-to":
                        metadata.in_reply_to = value
                        metadata.is_reply = True
                    elif header_name == "references":
                        metadata.references = [ref.strip() for ref in value.split()]
                    elif header_name == "reply-to":
                        metadata.reply_to = self._parse_email_address(value)

                    break

        return header_end

    def _parse_body(self, body_lines: list[str], metadata: EmailMetadata):
        """Parse email body, extracting main content, quotes, and signature.

        Args:
            body_lines: Lines after headers
            metadata: EmailMetadata to populate
        """
        body_text = "\n".join(body_lines)

        # Find signature (-- separator)
        sig_match = self.SIGNATURE_PATTERN.search(body_text)
        if sig_match:
            metadata.body = body_text[: sig_match.start()].strip()
            metadata.signature = body_text[sig_match.start() :].strip()
        else:
            metadata.body = body_text.strip()

        # Extract quoted text (previous messages in thread)
        if metadata.body:
            metadata.quoted_text = self._extract_quoted_text(metadata.body)

    def _parse_email_address(self, addr_str: str) -> EmailAddress | None:
        """Parse a single email address with optional name.

        Args:
            addr_str: Email address string (e.g., "John Doe <john@example.com>")

        Returns:
            EmailAddress object or None if no valid email found
        """
        addr_str = addr_str.strip()

        # Try name + email format first
        match = self.NAME_EMAIL_PATTERN.search(addr_str)
        if match:
            name = match.group(1).strip()
            email = match.group(2).strip()
            return EmailAddress(email=email, name=name if name else None)

        # Try just email
        match = self.EMAIL_PATTERN.search(addr_str)
        if match:
            email = match.group(1)
            # Extract name if present before email (e.g., "John Doe john@example.com")
            name_part = addr_str[: match.start()].strip()
            return EmailAddress(email=email, name=name_part if name_part else None)

        # If no email found, return None to indicate parsing failure
        return None

    def _parse_email_list(self, addr_list_str: str) -> list[EmailAddress]:
        """Parse a list of email addresses.

        Args:
            addr_list_str: Semicolon or comma-separated email addresses

        Returns:
            List of EmailAddress objects (invalid addresses are filtered out)
        """
        # Split by semicolon or comma
        parts = re.split(r"[;,]", addr_list_str)

        addresses = []
        for part in parts:
            part = part.strip()
            if part:
                addr = self._parse_email_address(part)
                if addr:  # Only add valid addresses
                    addresses.append(addr)

        return addresses

    def _parse_date(self, date_str: str) -> datetime | None:
        """Parse email date string to datetime object.

        Supports both RFC 5322 format (standard email dates) and custom formats.

        Args:
            date_str: Date string (RFC 5322 or custom "MM/DD/YYYY HH:MM:SS AM/PM" format)

        Returns:
            datetime object or None if parsing fails
        """
        # Try RFC 5322 format first (standard email Date header)
        try:
            return parsedate_to_datetime(date_str)
        except (TypeError, ValueError):
            pass

        # Fall back to custom format for non-standard dates (e.g., "Sent:" header)
        match = self.DATE_PATTERN.match(date_str)
        if not match:
            return None

        month, day, year, hour, minute, second, ampm = match.groups()

        # Convert to 24-hour format
        hour = int(hour)
        if ampm.upper() == "PM" and hour != 12:
            hour += 12
        elif ampm.upper() == "AM" and hour == 12:
            hour = 0

        try:
            return datetime(
                year=int(year),
                month=int(month),
                day=int(day),
                hour=hour,
                minute=int(minute),
                second=int(second),
            )
        except ValueError:
            return None

    def _extract_quoted_text(self, body: str) -> list[str]:
        """Extract quoted text from previous messages in thread.

        Args:
            body: Email body text

        Returns:
            List of quoted text sections
        """
        quoted_sections = []

        # Look for quote patterns
        for pattern in self.QUOTE_PATTERNS:
            matches = pattern.finditer(body)
            for match in matches:
                # Extract the quoted section starting from the match
                start = match.start()
                remaining_text = body[start:]

                # Different extraction strategies based on pattern type
                # Check if this is a > prefix pattern
                if pattern.pattern.startswith("^>"):
                    # Extract lines with > prefix
                    lines = remaining_text.split("\n")
                    quoted_lines = []
                    for line in lines:
                        if line.strip().startswith(">") or not line.strip():
                            quoted_lines.append(line)
                        elif quoted_lines:  # Stop at first non-quoted line
                            break
                    if quoted_lines:
                        quoted_sections.append("\n".join(quoted_lines).strip())

                else:
                    # For header-style quotes ("On ... wrote:", "Original Message", etc.)
                    # Extract until double newline or a significant break
                    lines = remaining_text.split("\n")
                    quoted_lines = []
                    empty_line_count = 0

                    for i, line in enumerate(lines):
                        # Stop at double empty lines (paragraph break)
                        if not line.strip():
                            empty_line_count += 1
                            if empty_line_count >= 2:
                                break
                        else:
                            empty_line_count = 0

                        quoted_lines.append(line)

                        # Limit extraction to reasonable size
                        if i >= self.MAX_QUOTE_EXTRACTION_LINES:
                            break

                    if quoted_lines:
                        quoted_sections.append("\n".join(quoted_lines).strip())

        return quoted_sections
