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

from unsealed_networks.entities.extractor import Entity, HybridEntityExtractor
from unsealed_networks.pipeline.manifest import Manifest
from unsealed_networks.pipeline.step import PipelineStep, run_step_cli


class ExtractEntitiesStep(PipelineStep):
    """Extract named entities from document using hybrid regex + LLM."""

    @property
    def name(self) -> str:
        return "extract_entities"

    @property
    def version(self) -> int:
        return 7  # Include position data (start/end) for entities

    @property
    def depends_on(self) -> list[str]:
        """This step depends on email metadata extraction for participant names."""
        return ["extract_email_metadata"]

    def execute(self, doc_path: Path, manifest: Manifest) -> dict[str, Any]:
        """Extract named entities from document.

        Args:
            doc_path: Path to document file
            manifest: Current manifest

        Returns:
            Dict with:
                - entities_found: Total number of entities extracted
                - persons: List of person entities with confidence scores
                - organizations: List of organization entities
                - locations: List of location entities

        Note:
            Entity data is stored in this step's outcome.
            Uses hybrid regex + LLM extraction for high accuracy.
            Automatically includes email participant names if available.
        """
        # Read document
        with open(doc_path, encoding="utf-8-sig", errors="replace") as f:
            text = f.read()

        # Extract entities using hybrid extractor with LLM
        extractor = HybridEntityExtractor(enable_llm=True)  # Enable LLM for better accuracy
        entities = extractor.extract(text)

        # Add email participant names as high-confidence entities
        email_metadata_step = manifest.get_step("extract_email_metadata")
        if email_metadata_step and email_metadata_step.status == "success":
            participants = email_metadata_step.outcome.get("participants", [])
            if participants:
                # Extract unique names from participants
                participant_names = set()
                for participant in participants:
                    name = participant.get("name")
                    if name:
                        participant_names.add(name)

                # Add each participant as a person entity if not already present
                existing_persons = {p.text.lower() for p in entities.get("people", [])}
                for name in participant_names:
                    if name and name.lower() not in existing_persons:
                        entities.setdefault("people", []).append(
                            Entity(
                                text=name,
                                type="person",
                                confidence=0.95,  # High confidence from email headers
                                context="",
                                method="email",
                            )
                        )
                        existing_persons.add(name.lower())

        # Convert to output format
        persons = [e.to_dict() for e in entities.get("people", [])]
        organizations = [e.to_dict() for e in entities.get("organizations", [])]
        locations = [e.to_dict() for e in entities.get("locations", [])]

        total = len(persons) + len(organizations) + len(locations)

        return {
            "entities_found": total,
            "persons": persons,
            "organizations": organizations,
            "locations": locations,
        }


if __name__ == "__main__":
    run_step_cli(ExtractEntitiesStep)
