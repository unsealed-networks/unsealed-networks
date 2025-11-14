#!/usr/bin/env python3
"""Pipeline Step 04: Extract named entities from document.

This step:
1. Extracts person names using NER
2. Identifies organizations and locations
3. Returns list of entities with counts

This step runs independently and doesn't depend on classification.
"""

from pathlib import Path
from typing import Any

from unsealed_networks.entities.extractor import EntityExtractor
from unsealed_networks.pipeline.manifest import Manifest
from unsealed_networks.pipeline.step import PipelineStep, run_step_cli


class ExtractEntitiesStep(PipelineStep):
    """Extract named entities from document."""

    @property
    def name(self) -> str:
        return "extract_entities"

    @property
    def version(self) -> int:
        return 1

    def execute(self, doc_path: Path, manifest: Manifest) -> dict[str, Any]:
        """Extract named entities from document.

        Args:
            doc_path: Path to document file
            manifest: Current manifest

        Returns:
            Dict with:
                - entities_found: Total number of entities extracted
                - persons: List of person entities with mention counts
                - organizations: List of organization entities
                - locations: List of location entities

        Note:
            Entity data is stored in this step's outcome.
            Later steps can merge with canonical entity database.
        """
        # Read document
        with open(doc_path, encoding="utf-8-sig", errors="replace") as f:
            text = f.read()

        # Extract entities
        extractor = EntityExtractor()
        entities = extractor.extract_entities(text)

        # Organize by type
        persons = [e for e in entities if e.entity_type == "PERSON"]
        organizations = [e for e in entities if e.entity_type == "ORG"]
        locations = [e for e in entities if e.entity_type == "GPE"]

        return {
            "entities_found": len(entities),
            "persons": [{"name": e.text, "mention_count": e.mention_count} for e in persons],
            "organizations": [
                {"name": e.text, "mention_count": e.mention_count} for e in organizations
            ],
            "locations": [{"name": e.text, "mention_count": e.mention_count} for e in locations],
        }


if __name__ == "__main__":
    run_step_cli(ExtractEntitiesStep)
