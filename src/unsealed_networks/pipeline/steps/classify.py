#!/usr/bin/env python3
"""Pipeline Step 01: Classify document type.

This step:
1. Analyzes document structure and content
2. Classifies as email, legal, news, or other
3. Returns classification with confidence score

The classification determines which downstream extraction steps to run.
"""

from pathlib import Path
from typing import Any

from unsealed_networks.etl.classify import HybridDocumentClassifier
from unsealed_networks.pipeline.manifest import Manifest
from unsealed_networks.pipeline.step import PipelineStep, run_step_cli


class ClassifyStep(PipelineStep):
    """Classify document type using hybrid regex + LLM approach."""

    @property
    def name(self) -> str:
        return "classify"

    @property
    def version(self) -> int:
        return 2  # Updated to use hybrid classifier

    def execute(self, doc_path: Path, manifest: Manifest) -> dict[str, Any]:
        """Classify document type with LLM failover.

        Uses a two-stage hybrid approach:
        1. First tries regex-based classification (fast)
        2. If confidence < 0.85 or type is "other", uses LLM (accurate)

        Args:
            doc_path: Path to document file
            manifest: Current manifest

        Returns:
            Dict with:
                - doc_type: Document type (email, legal, news, etc.)
                - confidence: Classification confidence score
                - subtype: More specific document subtype (if available)
                - method: Classification method used ("regex" or "llm")
                - reasoning: LLM reasoning (if LLM was used)

        Note:
            Classification result is stored in this step's outcome.
            Later steps can access via: manifest.get_step("classify").outcome
        """
        # Classify document using hybrid approach
        classifier = HybridDocumentClassifier()
        result = classifier.classify(doc_path)

        return {
            "doc_type": result.document_type,
            "confidence": result.confidence,
            "subtype": result.subtype,
            "method": result.method,
            "reasoning": result.reasoning,
        }


if __name__ == "__main__":
    run_step_cli(ClassifyStep)
