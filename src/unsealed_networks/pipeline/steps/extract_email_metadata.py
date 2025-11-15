#!/usr/bin/env python3
"""Pipeline Step 02: Extract email metadata.

This step:
1. Checks if document is classified as email
2. Parses email headers (From, To, Subject, Date)
3. Returns structured email metadata

This step depends on classification and only runs on email documents.
"""

from pathlib import Path
from typing import Any

from unsealed_networks.parsers.email_parser import EmailParser
from unsealed_networks.pipeline.manifest import Manifest
from unsealed_networks.pipeline.step import PipelineStep, run_step_cli


class ExtractEmailMetadataStep(PipelineStep):
    """Extract email metadata from document."""

    @property
    def name(self) -> str:
        return "extract_email_metadata"

    @property
    def version(self) -> int:
        return 4  # Removed participant_names field - use participants object instead

    @property
    def depends_on(self) -> list[str]:
        return ["classify"]

    def execute(self, doc_path: Path, manifest: Manifest) -> dict[str, Any]:
        """Extract email metadata from document.

        Args:
            doc_path: Path to document file
            manifest: Current manifest

        Returns:
            Dict with email metadata or skip indicator

        Note:
            Only processes documents classified as emails.
            Email metadata stored in this step's outcome.
        """
        # Check classification
        classify_step = manifest.get_step("classify")
        if not classify_step:
            return {"skipped": True, "reason": "No classification step found"}

        doc_type = classify_step.outcome.get("doc_type")
        if doc_type != "email":
            return {"skipped": True, "reason": f"Document type is '{doc_type}', not email"}

        # Parse email
        parser = EmailParser()
        metadata = parser.parse(doc_path)

        # Build participants list (all addresses across from/to/cc/bcc)
        participants = []
        if metadata.from_addr:
            participants.append(metadata.from_addr.to_dict())
        participants.extend([addr.to_dict() for addr in metadata.to_addrs])
        participants.extend([addr.to_dict() for addr in metadata.cc_addrs])
        participants.extend([addr.to_dict() for addr in metadata.bcc_addrs])

        return {
            "skipped": False,
            "from": metadata.from_addr.to_dict() if metadata.from_addr else None,
            "to": [addr.to_dict() for addr in metadata.to_addrs],
            "cc": [addr.to_dict() for addr in metadata.cc_addrs],
            "bcc": [addr.to_dict() for addr in metadata.bcc_addrs],
            "subject": metadata.subject,
            "date": metadata.date.isoformat() if metadata.date else None,
            "participants": participants,
        }


if __name__ == "__main__":
    run_step_cli(ExtractEmailMetadataStep)
