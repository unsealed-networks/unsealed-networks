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

    def to_dict(self) -> dict[str, str]:
        """Convert to dictionary with cleaned name and email."""
        # Clean up the name by removing special characters and extra whitespace
        clean_name = self._clean_name(self.name) if self.name else None

        # Use "redacted" for missing emails, otherwise clean the email
        clean_email = "redacted" if self.email == "[REDACTED]" else self._clean_email(self.email)

        return {"name": clean_name, "email": clean_email}

    @staticmethod
    def _clean_name(name: str | None) -> str | None:
        """Remove cruft from names (quotes, brackets, etc.)."""
        if not name:
            return None

        # Remove common cruft characters (iterate until no change)
        prev_name = None
        while prev_name != name:
            prev_name = name
            name = name.strip()
            name = name.strip("'\"[]()<>")  # Remove quotes and brackets
            name = name.strip()

        # Remove email prefixes like "mailto:"
        if name.lower().startswith("mailto:"):
            name = name[7:].strip()

        # Remove empty brackets that might be left over
        name = re.sub(r"\s*\[\s*\]\s*", " ", name)
        name = re.sub(r"\s*\(\s*\)\s*", " ", name)

        # Normalize whitespace
        name = " ".join(name.split())

        return name if name else None

    @staticmethod
    def _clean_email(email: str) -> str:
        """Clean up email address."""
        email = email.strip().lower()

        # Remove mailto: prefix
        if email.startswith("mailto:"):
            email = email[7:]

        # Remove any quotes or brackets
        email = email.strip("'\"[]()<>")

        return email


@dataclass
class ThreadMessage:
    """A single message in an email thread."""

    author: str  # Name or email of sender
    date_str: str | None = None  # Date string from "On X wrote:"
    date: datetime | None = None  # Parsed datetime if possible
    content_preview: str | None = None  # First 200 chars of message


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

    # Thread participants - extracted from "On X, Y wrote:" patterns
    thread_messages: list[ThreadMessage] = field(default_factory=list)
    all_participants: set[str] = field(default_factory=set)  # All people in thread

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

    # Parsing issues - DLQ for reprocessing
    parsing_issues: list[str] = field(default_factory=list)  # Track what failed to parse


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

    # Thread attribution patterns - "On DATE, PERSON wrote:" in various formats
    THREAD_PATTERNS = [
        # Norwegian/German: "son. 24. jun. 2018 kl. 15:18 skrev Name <email>:"
        # (Check this first as it's most specific)
        re.compile(
            r"(?:søn|son|man|tir|ons|tor|fre|lør)\.\s+(\d{1,2}\.\s+\w+\.\s+\d{4}\s+kl\.\s+[\d:]+)\s+skrev\s+(.+?)\s*<([^>]+)>:",
            re.IGNORECASE,
        ),
        # English with "wrote:" on same line: "On Apr 5, 2018, at 1:41 PM, Name <email> wrote:"
        re.compile(
            r"On\s+(\w+\s+\d{1,2},\s+\d{4},?\s+at\s+[\d:]+\s+(?:AM|PM)),\s*(.+?)\s*<([^>]+)>\s*wrote:",
            re.IGNORECASE,
        ),
        # English: "On Sun, Jun 24, 2018 at 3:28 PM, Name" (may have newlines before "wrote:")
        # Look for the pattern without requiring "wrote:" in the same match
        re.compile(
            r"On\s+((?:Sun|Mon|Tue|Wed|Thu|Fri|Sat),\s+\w+\s+\d{1,2},\s+\d{4}\s+at\s+[\d:]+\s+(?:AM|PM)),\s*([^<\n]+)",
            re.IGNORECASE,
        ),
        # English without weekday: "On Apr 5, 2018, at 2:04 PM, Name"
        re.compile(
            r"On\s+(\w+\s+\d{1,2},\s+\d{4},?\s+at\s+[\d:]+\s+(?:AM|PM)),\s*([^<\n]+)",
            re.IGNORECASE,
        ),
        # Forwarded headers: "From: ... Sent: ... To: ..."
        re.compile(
            r"^From:\s*(.+?)\s*(?:<([^>]+)>)?\s*$.*?^Sent:\s*(.+?)\s*$",
            re.MULTILINE | re.DOTALL,
        ),
    ]

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

        # Add top-level participants to all_participants
        if metadata.from_addr:
            metadata.all_participants.add(str(metadata.from_addr))
        for addr in metadata.to_addrs:
            metadata.all_participants.add(str(addr))
        for addr in metadata.cc_addrs:
            metadata.all_participants.add(str(addr))
        for addr in metadata.bcc_addrs:
            metadata.all_participants.add(str(addr))

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

            # Check if this line looks like a header (contains ":" near start)
            # If not, this is where body starts
            if i > 0:  # Skip first line check
                line_stripped = line.strip()
                # If line doesn't have a colon in first 20 chars, it's probably body
                colon_pos = line_stripped.find(":")
                if colon_pos < 0 or colon_pos > 20:
                    # Check if it matches any known header pattern
                    looks_like_header = any(
                        re.match(pattern, line_stripped, re.IGNORECASE)
                        for pattern in header_patterns.values()
                    )
                    if not looks_like_header:
                        header_end = i
                        break

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

        # Extract thread participants and dates
        if metadata.body:
            (
                metadata.thread_messages,
                metadata.all_participants,
                thread_parse_issues,
            ) = self._extract_thread_participants(body_text)
            metadata.parsing_issues.extend(thread_parse_issues)

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

        # If no email found, treat the entire string as a name (for redacted emails)
        # This handles cases like "From: Mark L. Epstein" where email is redacted
        if addr_str:
            return EmailAddress(email="[REDACTED]", name=addr_str)

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
            date_str: Date string (RFC 5322 or custom formats)

        Returns:
            datetime object or None if parsing fails
        """
        # Try RFC 5322 format first (standard email Date header)
        try:
            return parsedate_to_datetime(date_str)
        except (TypeError, ValueError, AttributeError):
            pass

        # Try "Sun, Jun 24, 2018 at 3:28 PM" format (with weekday)
        try:
            # Remove "at" and weekday prefix
            cleaned = re.sub(r"^(?:Sun|Mon|Tue|Wed|Thu|Fri|Sat),\s*", "", date_str)
            cleaned = cleaned.replace(" at ", " ")
            return datetime.strptime(cleaned, "%b %d, %Y %I:%M %p")
        except (ValueError, AttributeError):
            pass

        # Try "Apr 5, 2018, at 2:04 PM" format (without weekday)
        try:
            cleaned = date_str.replace(" at ", " ").replace(",", "")
            return datetime.strptime(cleaned, "%b %d %Y %I:%M %p")
        except (ValueError, AttributeError):
            pass

        # Try Norwegian format: "24. jun. 2018 kl. 15:18"
        norwegian_months = {
            "jan": 1,
            "feb": 2,
            "mar": 3,
            "apr": 4,
            "mai": 5,
            "jun": 6,
            "jul": 7,
            "aug": 8,
            "sep": 9,
            "okt": 10,
            "nov": 11,
            "des": 12,
        }
        match = re.match(
            r"(\d{1,2})\.\s*(\w+)\.\s*(\d{4})\s*kl\.\s*(\d{1,2}):(\d{2})", date_str, re.IGNORECASE
        )
        if match:
            day, month_str, year, hour, minute = match.groups()
            month = norwegian_months.get(month_str.lower()[:3])
            if month:
                try:
                    return datetime(
                        year=int(year),
                        month=month,
                        day=int(day),
                        hour=int(hour),
                        minute=int(minute),
                    )
                except ValueError:
                    pass

        # Fall back to custom MM/DD/YYYY format for non-standard dates (e.g., "Sent:" header)
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

    def _extract_thread_participants(
        self, content: str
    ) -> tuple[list[ThreadMessage], set[str], list[str]]:
        """Extract all participants and their timestamps from threaded email.

        Args:
            content: Full email body content

        Returns:
            Tuple of (thread_messages, all_participants, parsing_issues)
        """
        thread_messages = []
        all_participants = set()
        parsing_issues = []

        # Try each thread pattern
        for pattern in self.THREAD_PATTERNS:
            for match in pattern.finditer(content):
                # Extract based on pattern type
                groups = match.groups()

                # Determine which groups are date vs author based on pattern
                if "skrev" in pattern.pattern:
                    # Norwegian pattern: date in group 1, name in group 2, email in group 3
                    date_str = groups[0] if len(groups) > 0 else None
                    author = groups[1] if len(groups) > 1 else None
                    email = groups[2] if len(groups) > 2 else None
                elif "From:" in pattern.pattern:
                    # Forwarded pattern: name in group 1, email in group 2, date in group 3
                    author = groups[0] if len(groups) > 0 else None
                    email = groups[1] if len(groups) > 1 else None
                    date_str = groups[2] if len(groups) > 2 else None
                else:
                    # English "On ... " pattern: date in group 1, name in group 2
                    # (no email captured in this simplified version)
                    date_str = groups[0] if len(groups) > 0 else None
                    author = groups[1] if len(groups) > 1 else None
                    email = None

                # Clean up author name
                if author:
                    author = author.strip()
                    # Remove any trailing characters
                    author = author.rstrip(",<> \t")

                    # If we have an email, use full format "Name <email>"
                    if email and email.strip():
                        author = f"{author} <{email.strip()}>"

                    all_participants.add(author)

                    # Try to parse the date
                    parsed_date = None
                    if date_str:
                        parsed_date = self._parse_date(date_str.strip())
                        # Track when date parsing fails
                        if not parsed_date:
                            issue = f"Failed to parse thread date: '{date_str.strip()}' "
                            issue += f"for author '{author}'"
                            parsing_issues.append(issue)

                    # Extract content preview (next 200 chars after match)
                    preview_start = match.end()
                    preview_end = min(len(content), preview_start + 200)
                    content_preview = content[preview_start:preview_end].strip()

                    # Create thread message
                    thread_msg = ThreadMessage(
                        author=author,
                        date_str=date_str.strip() if date_str else None,
                        date=parsed_date,
                        content_preview=content_preview if content_preview else None,
                    )
                    thread_messages.append(thread_msg)

        return thread_messages, all_participants, parsing_issues
