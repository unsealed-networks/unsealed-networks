"""Base class for pipeline steps."""

import sys
from abc import ABC, abstractmethod
from datetime import datetime
from pathlib import Path
from typing import Any

from rich.console import Console

from unsealed_networks.pipeline.manifest import Manifest, StepResult

console = Console()


class PipelineStep(ABC):
    """Base class for all pipeline steps.

    Each step:
    1. Loads the document and manifest
    2. Executes processing logic
    3. Updates the manifest with results
    4. Saves the manifest

    Subclasses must implement:
    - name: Step name (e.g., "extract_urls")
    - version: Step version for tracking changes
    - depends_on: List of step names this step depends on
    - execute(): Core processing logic
    """

    @property
    @abstractmethod
    def name(self) -> str:
        """Step name (e.g., 'extract_urls')."""
        pass

    @property
    @abstractmethod
    def version(self) -> int:
        """Step version for tracking model/logic changes."""
        pass

    @property
    def depends_on(self) -> list[str]:
        """List of step names this step depends on.

        Returns:
            List of step names (empty list if no dependencies)

        Example:
            return ["classify"]  # This step depends on classify step
            return ["extract_urls", "extract_entities"]  # Multiple dependencies
            return []  # No dependencies
        """
        return []

    @abstractmethod
    def execute(self, doc_path: Path, manifest: Manifest) -> dict[str, Any]:
        """Execute the step logic.

        Args:
            doc_path: Path to the document file
            manifest: Current manifest with prior step results

        Returns:
            Dict with step outcome data to be stored in manifest

        Raises:
            Exception on failure (will be caught and logged)
        """
        pass

    def run(self, doc_id: str, doc_path: Path) -> bool:
        """Run the pipeline step with error handling and manifest management.

        Args:
            doc_id: Document ID
            doc_path: Path to document file

        Returns:
            True if successful, False on failure
        """
        # Load or create manifest
        if Manifest.exists(doc_id):
            manifest = Manifest.load(doc_id)
        else:
            manifest = Manifest.create_new(doc_id, doc_path.name)

        # Check if step already executed successfully
        existing_step = manifest.get_step(self.name)
        if existing_step and existing_step.status == "success":
            console.print(f"[yellow]Step {self.name} already completed, skipping[/yellow]")
            return True

        # Create step result with dependencies
        step_result = StepResult(
            step_name=self.name,
            step_version=self.version,
            started_at=datetime.utcnow().isoformat() + "Z",
        )
        # Store dependencies in outcome for later reference
        step_result.outcome["depends_on"] = self.depends_on

        try:
            console.print(f"[bold]Running step: {self.name}[/bold]")

            # Execute step logic
            outcome = self.execute(doc_path, manifest)

            # Mark success
            step_result.completed_at = datetime.utcnow().isoformat() + "Z"
            step_result.status = "success"
            step_result.outcome = outcome

            manifest.add_step(step_result)
            manifest.save()

            console.print(f"[green]✓ Step {self.name} completed[/green]")
            return True

        except Exception as e:
            # Mark failure
            step_result.completed_at = datetime.utcnow().isoformat() + "Z"
            step_result.status = "failed"
            step_result.error = str(e)

            manifest.add_step(step_result)
            manifest.mark_failed(f"Step {self.name} failed: {e}")
            manifest.save()

            console.print(f"[red]✗ Step {self.name} failed: {e}[/red]")
            return False


def run_step_cli(step_class: type[PipelineStep]) -> None:
    """CLI wrapper for running a pipeline step.

    Usage:
        python step_03_extract_urls.py <doc_id> <doc_path>
    """
    if len(sys.argv) != 3:
        console.print("[red]Usage: <script> <doc_id> <doc_path>[/red]")
        sys.exit(1)

    doc_id = sys.argv[1]
    doc_path = Path(sys.argv[2])

    if not doc_path.exists():
        console.print(f"[red]Error: Document not found: {doc_path}[/red]")
        sys.exit(1)

    step = step_class()
    success = step.run(doc_id, doc_path)

    sys.exit(0 if success else 1)
