"""Document processing manifest management."""

import json
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any

from unsealed_networks.utils import atomic_write_json


@dataclass
class StepResult:
    """Result from executing a pipeline step."""

    step_name: str
    step_version: int
    started_at: str
    completed_at: str | None = None
    status: str = "running"  # running, success, failed
    outcome: dict[str, Any] = field(default_factory=dict)
    error: str | None = None

    def to_dict(self) -> dict:
        """Convert to dictionary for JSON serialization."""
        return {
            "step_name": self.step_name,
            "step_version": self.step_version,
            "started_at": self.started_at,
            "completed_at": self.completed_at,
            "status": self.status,
            "outcome": self.outcome,
            "error": self.error,
        }

    @classmethod
    def from_dict(cls, data: dict) -> "StepResult":
        """Create StepResult from dictionary."""
        return cls(
            step_name=data["step_name"],
            step_version=data["step_version"],
            started_at=data["started_at"],
            completed_at=data.get("completed_at"),
            status=data.get("status", "running"),
            outcome=data.get("outcome", {}),
            error=data.get("error"),
        )


@dataclass
class Manifest:
    """Document processing manifest tracking pipeline execution state."""

    doc_id: str
    original_file: str
    created_at: str
    updated_at: str
    status: str = "processing"  # processing, completed, failed
    provenance: dict[str, Any] = field(default_factory=dict)
    steps: list[StepResult] = field(default_factory=list)
    metadata: dict[str, Any] = field(default_factory=dict)
    error: str | None = None

    @property
    def manifest_path(self) -> Path:
        """Get path to manifest file."""
        # Strip .json extension from doc_id if present to avoid .json.json
        doc_id_base = self.doc_id.removesuffix(".json")
        return Path("pipeline/manifests") / f"{doc_id_base}.json"

    @property
    def last_step(self) -> StepResult | None:
        """Get the last executed step."""
        return self.steps[-1] if self.steps else None

    def has_step(self, step_name: str) -> bool:
        """Check if a step has been executed."""
        return any(s.step_name == step_name for s in self.steps)

    def get_step(self, step_name: str) -> StepResult | None:
        """Get step result by name."""
        for step in self.steps:
            if step.step_name == step_name:
                return step
        return None

    def add_step(self, step: StepResult) -> None:
        """Add a step result to the manifest, replacing any existing step with the same name."""
        # Find and replace existing step with the same name
        for i, existing_step in enumerate(self.steps):
            if existing_step.step_name == step.step_name:
                self.steps[i] = step
                self.updated_at = datetime.utcnow().isoformat() + "Z"
                return

        # No existing step found, append new one
        self.steps.append(step)
        self.updated_at = datetime.utcnow().isoformat() + "Z"

    def update_metadata(self, key: str, value: Any) -> None:
        """Update metadata field."""
        self.metadata[key] = value
        self.updated_at = datetime.utcnow().isoformat() + "Z"

    def mark_completed(self) -> None:
        """Mark manifest as completed."""
        self.status = "completed"
        self.updated_at = datetime.utcnow().isoformat() + "Z"

    def mark_failed(self, error: str) -> None:
        """Mark manifest as failed with error."""
        self.status = "failed"
        self.error = error
        self.updated_at = datetime.utcnow().isoformat() + "Z"

    def truncate_steps_after(self, step_name: str) -> None:
        """Remove all steps after the given step (for reprocessing)."""
        for i, step in enumerate(self.steps):
            if step.step_name == step_name:
                self.steps = self.steps[: i + 1]
                self.updated_at = datetime.utcnow().isoformat() + "Z"
                return

    def invalidate_dependent_steps(self, step_name: str) -> None:
        """Remove steps that depend on the given step.

        When a step is re-run (e.g., version changed), any steps that depend on it
        need to be invalidated and re-run to ensure consistency.

        Args:
            step_name: Name of the step that changed
        """
        steps_to_remove = []

        for step in self.steps:
            # Check if this step depends on the changed step
            depends_on = step.outcome.get("depends_on", [])
            if step_name in depends_on:
                steps_to_remove.append(step.step_name)

        # Remove dependent steps
        if steps_to_remove:
            self.steps = [s for s in self.steps if s.step_name not in steps_to_remove]
            self.updated_at = datetime.utcnow().isoformat() + "Z"

    def to_dict(self) -> dict:
        """Convert to dictionary for JSON serialization."""
        return {
            "doc_id": self.doc_id,
            "original_file": self.original_file,
            "created_at": self.created_at,
            "updated_at": self.updated_at,
            "status": self.status,
            "provenance": self.provenance,
            "steps": [s.to_dict() for s in self.steps],
            "metadata": self.metadata,
            "error": self.error,
        }

    def save(self) -> None:
        """Save manifest to disk using atomic write (write to .tmp then rename)."""
        atomic_write_json(self.manifest_path, self.to_dict())

    @classmethod
    def load(cls, doc_id: str) -> "Manifest":
        """Load manifest from disk."""
        # Strip .json extension from doc_id if present to avoid .json.json
        doc_id_base = doc_id.removesuffix(".json")
        manifest_path = Path("pipeline/manifests") / f"{doc_id_base}.json"
        with open(manifest_path, encoding="utf-8") as f:
            data = json.load(f)
        return cls.from_dict(data)

    @classmethod
    def from_dict(cls, data: dict) -> "Manifest":
        """Create Manifest from dictionary."""
        # Deduplicate steps - keep only the latest execution of each step
        steps_dict = {}
        for step_data in data.get("steps", []):
            step = StepResult.from_dict(step_data)
            # Keep the step with the latest started_at time
            if (
                step.step_name not in steps_dict
                or step.started_at > steps_dict[step.step_name].started_at
            ):
                steps_dict[step.step_name] = step

        # Convert back to list, preserving original order
        seen = set()
        steps = []
        for step_data in data.get("steps", []):
            step_name = step_data["step_name"]
            if step_name not in seen:
                steps.append(steps_dict[step_name])
                seen.add(step_name)

        return cls(
            doc_id=data["doc_id"],
            original_file=data["original_file"],
            created_at=data["created_at"],
            updated_at=data["updated_at"],
            status=data.get("status", "processing"),
            provenance=data.get("provenance", {}),
            steps=steps,
            metadata=data.get("metadata", {}),
            error=data.get("error"),
        )

    @classmethod
    def create_new(
        cls, doc_id: str, original_file: str, provenance: dict[str, Any] | None = None
    ) -> "Manifest":
        """Create a new manifest for a document.

        Args:
            doc_id: Unique document ID
            original_file: Original filename
            provenance: Optional provenance metadata (source, batch, etc.)
        """
        now = datetime.utcnow().isoformat() + "Z"
        return cls(
            doc_id=doc_id,
            original_file=original_file,
            created_at=now,
            updated_at=now,
            status="processing",
            provenance=provenance or {},
        )

    @classmethod
    def exists(cls, doc_id: str) -> bool:
        """Check if a manifest exists for a document."""
        # Strip .json extension from doc_id if present to avoid .json.json
        doc_id_base = doc_id.removesuffix(".json")
        manifest_path = Path("pipeline/manifests") / f"{doc_id_base}.json"
        return manifest_path.exists()
