#!/usr/bin/env python3
"""Pipeline Step 03: Extract URLs from document.

This step:
1. Scans document text for URLs using regex
2. Classifies URLs by type (youtube, pdf, news, social, other)
3. Returns list of extracted URLs with metadata

The extracted URLs are stored in the manifest for later processing steps
(e.g., fetching metadata, detecting OCR errors).
"""

import re
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

from unsealed_networks.pipeline.manifest import Manifest
from unsealed_networks.pipeline.step import PipelineStep, run_step_cli

# URL pattern: matches http/https URLs without spaces or special chars
URL_PATTERN = re.compile(r'https?://[^\s<>"{}|\\^`\[\]]+', re.IGNORECASE)


def classify_url_type(url: str, domain: str) -> str:
    """Classify URL by type based on domain and path.

    Args:
        url: Full URL string
        domain: Domain portion (netloc)

    Returns:
        URL type: youtube, pdf, news, social, other
    """
    url_lower = url.lower()

    if "youtube.com" in domain or "youtu.be" in domain:
        return "youtube"
    elif any(ext in url_lower for ext in [".pdf"]):
        return "pdf"
    elif any(news in domain for news in ["news", "times", "post", "reuters", "cnn", "bbc"]):
        return "news"
    elif "t.co" in domain or "twitter.com" in domain or "x.com" in domain:
        return "social"
    else:
        return "other"


class ExtractURLsStep(PipelineStep):
    """Extract URLs from document text."""

    @property
    def name(self) -> str:
        return "extract_urls"

    @property
    def version(self) -> int:
        return 1

    def execute(self, doc_path: Path, manifest: Manifest) -> dict[str, Any]:
        """Extract URLs from document.

        Args:
            doc_path: Path to document file
            manifest: Current manifest

        Returns:
            Dict with:
                - urls_found: Number of URLs extracted
                - urls: List of URL dicts with url, domain, type, position

        Note:
            Data is stored in this step's outcome. Later steps can access
            URLs via: manifest.get_step("extract_urls").outcome["urls"]
        """
        # Read document
        with open(doc_path, encoding="utf-8-sig", errors="replace") as f:
            text = f.read()

        # Find all URLs
        url_matches = URL_PATTERN.finditer(text)

        # Extract and classify URLs
        urls = []
        seen_urls = set()

        for match in url_matches:
            url = match.group(0)

            # Skip duplicates
            if url in seen_urls:
                continue
            seen_urls.add(url)

            # Parse and classify
            parsed = urlparse(url)
            domain = parsed.netloc.lower()
            url_type = classify_url_type(url, domain)

            urls.append(
                {
                    "url": url,
                    "domain": domain,
                    "type": url_type,
                    "position": match.start(),
                }
            )

        # Return data in step outcome (not in global metadata)
        return {
            "urls_found": len(urls),
            "urls": urls,
        }


if __name__ == "__main__":
    run_step_cli(ExtractURLsStep)
