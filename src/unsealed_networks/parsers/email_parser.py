"""Email parser for extracting structured metadata from email documents."""

import re
from dataclasses import dataclass, field
from datetime import datetime
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

        i = 0
        while i < len(lines):
            line = lines[i].strip()

            # Empty line signals end of headers
            if not line:
                return i + 1

            # Check each header pattern
            matched = False
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

                    matched = True
                    break

            # Handle continuation lines (headers can span multiple lines)
            if not matched and i > 0 and line.startswith((" ", "\t")):
                # This is a continuation of the previous header
                pass

            i += 1

        return i

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

    def _parse_email_address(self, addr_str: str) -> EmailAddress:
        """Parse a single email address with optional name.

        Args:
            addr_str: Email address string (e.g., "John Doe <john@example.com>")

        Returns:
            EmailAddress object
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

        # If no email found, treat whole thing as name
        return EmailAddress(email="", name=addr_str if addr_str else None)

    def _parse_email_list(self, addr_list_str: str) -> list[EmailAddress]:
        """Parse a list of email addresses.

        Args:
            addr_list_str: Semicolon or comma-separated email addresses

        Returns:
            List of EmailAddress objects
        """
        # Split by semicolon or comma
        parts = re.split(r"[;,]", addr_list_str)

        addresses = []
        for part in parts:
            part = part.strip()
            if part:
                addresses.append(self._parse_email_address(part))

        return addresses

    def _parse_date(self, date_str: str) -> datetime | None:
        """Parse email date string to datetime object.

        Args:
            date_str: Date string (e.g., "10/31/2015 11:24:38 AM")

        Returns:
            datetime object or None if parsing fails
        """
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
                # Extract the quoted section
                start = match.start()
                # Find the end of the quote (next non-quoted line or end)
                lines = body[start:].split("\n")
                quoted_lines = []
                for line in lines:
                    if line.strip().startswith(">") or not line.strip():
                        quoted_lines.append(line)
                    elif quoted_lines:  # Stop at first non-quoted line
                        break

                if quoted_lines:
                    quoted_sections.append("\n".join(quoted_lines).strip())

        return quoted_sections
