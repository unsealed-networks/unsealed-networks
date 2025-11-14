"""Automated entity merging based on merge candidates."""

import json
import sqlite3
from pathlib import Path

from rich.console import Console
from rich.progress import track

from .canonical import merge_entities

console = Console()


def batch_auto_merge(
    db_path: Path,
    candidates_file: Path,
    min_confidence: float = 0.95,
    dry_run: bool = False,
) -> dict:
    """Automatically merge high-confidence entity candidates.

    Args:
        db_path: Path to SQLite database
        candidates_file: Path to merge candidates JSON file
        min_confidence: Minimum confidence to auto-merge (default 0.95)
        dry_run: If True, don't actually merge, just report what would be merged

    Returns:
        Dict with merge statistics
    """
    # Load candidates
    with open(candidates_file, encoding="utf-8") as f:
        report = json.load(f)

    # Filter for high-confidence candidates
    auto_merge_candidates = [
        c for c in report.get("auto_merge", []) if c["confidence"] >= min_confidence
    ]

    if not auto_merge_candidates:
        console.print(f"[yellow]No candidates found with confidence >= {min_confidence}[/yellow]")
        return {"merged": 0, "errors": 0}

    console.print(
        f"[bold]Found {len(auto_merge_candidates)} candidates to auto-merge "
        f"(confidence >= {min_confidence})[/bold]"
    )

    if dry_run:
        console.print("[yellow]DRY RUN - No actual merges will be performed[/yellow]\n")

    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row

    stats = {
        "total_candidates": len(auto_merge_candidates),
        "merged": 0,
        "errors": 0,
        "skipped": 0,
        "merges": [],
    }

    for candidate in track(auto_merge_candidates, description="Auto-merging entities"):
        e1 = candidate["entity1"]
        e2 = candidate["entity2"]

        # Determine which should be canonical (pick the one with more mentions)
        if e1["count"] >= e2["count"]:
            source_id = e2["id"]
            source_text = e2["text"]
            target_text = e1["text"]
        else:
            source_id = e1["id"]
            source_text = e1["text"]
            target_text = e2["text"]

        # Get the canonical_id for the target entity
        target_canonical = conn.execute(
            """
            SELECT canonical_id FROM entity_aliases WHERE entity_id = ?
            """,
            (e1["id"] if e1["count"] >= e2["count"] else e2["id"],),
        ).fetchone()

        if not target_canonical:
            console.print(f"[red]Error: Target canonical not found for {target_text}[/red]")
            stats["errors"] += 1
            continue

        if dry_run:
            console.print(
                f"[dim]Would merge:[/dim] {source_text} → {target_text} "
                f"(confidence: {candidate['confidence']:.2f})"
            )
            stats["merged"] += 1
            stats["merges"].append(
                {
                    "source": source_text,
                    "target": target_text,
                    "confidence": candidate["confidence"],
                    "reason": candidate["reason"],
                }
            )
        else:
            try:
                result = merge_entities(
                    conn=conn,
                    source_entity_id=source_id,
                    target_canonical_id=target_canonical["canonical_id"],
                    method="auto",
                    confidence=candidate["confidence"],
                    merged_by="auto_merge_script",
                )

                if result.get("status") == "merged":
                    stats["merged"] += 1
                    stats["merges"].append(
                        {
                            "source": source_text,
                            "target": target_text,
                            "confidence": candidate["confidence"],
                            "reason": candidate["reason"],
                        }
                    )
                else:
                    stats["skipped"] += 1

            except Exception as e:
                console.print(f"[red]Error merging {source_text} → {target_text}: {e}[/red]")
                stats["errors"] += 1

    conn.close()

    # Print summary
    console.print("\n[bold green]✓ Auto-merge complete![/bold green]")
    console.print(f"  Candidates processed: {stats['total_candidates']}")
    console.print(f"  Successfully merged: {stats['merged']}")
    if stats["errors"] > 0:
        console.print(f"  [red]Errors: {stats['errors']}[/red]")
    if stats["skipped"] > 0:
        console.print(f"  [yellow]Skipped: {stats['skipped']}[/yellow]")

    return stats


def save_merge_log(stats: dict, output_file: Path):
    """Save merge log to JSON file.

    Args:
        stats: Merge statistics dict
        output_file: Path to output file
    """
    with open(output_file, "w", encoding="utf-8") as f:
        json.dump(stats, f, indent=2)

    console.print(f"\n[bold]Merge log saved to:[/bold] {output_file}")
