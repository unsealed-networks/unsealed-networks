#!/usr/bin/env python3
"""Pipeline Step 99: Assemble final metadata from all prior steps.

This is the ONLY step that populates the global manifest.metadata field.

This step:
1. Reads outcomes from all prior steps
2. Consolidates data into final metadata structure
3. Populates manifest.metadata with complete document metadata

This step depends on all extraction steps completing first.
"""

from pathlib import Path
from typing import Any

from unsealed_networks.pipeline.manifest import Manifest
from unsealed_networks.pipeline.step import PipelineStep, run_step_cli


class AssembleMetadataStep(PipelineStep):
    """Assemble final metadata from all pipeline steps."""

    # Constants for entity metadata limits
    TOP_N_PERSONS = 20  # Top persons to include in metadata
    TOP_N_ORGANIZATIONS = 10  # Top organizations to include in metadata
    TOP_N_LOCATIONS = 10  # Top locations to include in metadata

    @property
    def name(self) -> str:
        return "assemble_metadata"

    @property
    def version(self) -> int:
        return 1

    @property
    def depends_on(self) -> list[str]:
        return ["classify", "extract_email_metadata", "extract_urls", "extract_entities"]

    def execute(self, doc_path: Path, manifest: Manifest) -> dict[str, Any]:
        """Assemble final metadata from all steps.

        Args:
            doc_path: Path to document file
            manifest: Current manifest

        Returns:
            Dict with assembly statistics

        Note:
            This is the ONLY step that writes to manifest.metadata.
            All other steps store data in their own outcome fields.
        """
        # Get classification
        classify_step = manifest.get_step("classify")
        if classify_step:
            manifest.update_metadata("doc_type", classify_step.outcome["doc_type"])
            manifest.update_metadata("confidence", classify_step.outcome["confidence"])
            if classify_step.outcome.get("subtype"):
                manifest.update_metadata("subtype", classify_step.outcome["subtype"])

        # Get email metadata if available
        email_step = manifest.get_step("extract_email_metadata")
        if email_step and not email_step.outcome.get("skipped"):
            manifest.update_metadata("from", email_step.outcome.get("from"))
            manifest.update_metadata("to", email_step.outcome.get("to"))
            manifest.update_metadata("cc", email_step.outcome.get("cc"))
            manifest.update_metadata("subject", email_step.outcome.get("subject"))
            manifest.update_metadata("date", email_step.outcome.get("date"))
            manifest.update_metadata("participants", email_step.outcome.get("participants"))

        # Get URLs
        urls_step = manifest.get_step("extract_urls")
        if urls_step:
            urls = urls_step.outcome.get("urls", [])
            manifest.update_metadata("urls", [u["url"] for u in urls])
            manifest.update_metadata("urls_count", len(urls))

        # Get entities
        entities_step = manifest.get_step("extract_entities")
        if entities_step:
            persons = entities_step.outcome.get("persons", [])
            orgs = entities_step.outcome.get("organizations", [])
            locs = entities_step.outcome.get("locations", [])

            # Sort by confidence and take top entities
            persons_sorted = sorted(persons, key=lambda x: x.get("confidence", 0), reverse=True)
            orgs_sorted = sorted(orgs, key=lambda x: x.get("confidence", 0), reverse=True)
            locs_sorted = sorted(locs, key=lambda x: x.get("confidence", 0), reverse=True)

            manifest.update_metadata(
                "persons",
                [p["name"] for p in persons_sorted[: self.TOP_N_PERSONS]],
            )
            manifest.update_metadata(
                "organizations",
                [o["name"] for o in orgs_sorted[: self.TOP_N_ORGANIZATIONS]],
            )
            manifest.update_metadata(
                "locations",
                [loc["name"] for loc in locs_sorted[: self.TOP_N_LOCATIONS]],
            )
            manifest.update_metadata("entities_count", entities_step.outcome["entities_found"])

        # Mark manifest as completed
        manifest.mark_completed()

        # Return assembly statistics
        return {
            "metadata_fields_assembled": len(manifest.metadata),
            "has_email_metadata": email_step is not None and not email_step.outcome.get("skipped"),
            "has_urls": urls_step is not None and urls_step.outcome["urls_found"] > 0,
            "has_entities": entities_step is not None
            and entities_step.outcome["entities_found"] > 0,
        }


if __name__ == "__main__":
    run_step_cli(AssembleMetadataStep)
