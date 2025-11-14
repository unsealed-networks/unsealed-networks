"""LLM-assisted entity merge review."""

import json
import sqlite3
from pathlib import Path

import requests
from rich.console import Console
from rich.progress import track

from ..config import DEFAULT_OLLAMA_CONFIG, OllamaConfig
from .canonical import merge_entities

console = Console()


def ask_llm_merge_decision(
    entity1_text: str,
    entity1_count: int,
    entity2_text: str,
    entity2_count: int,
    context1: str = None,
    context2: str = None,
    confidence: float = 0.0,
    reason: str = "",
    ollama_config: OllamaConfig = None,
) -> dict:
    """Ask LLM if two entities should be merged.

    Args:
        entity1_text: First entity name
        entity1_count: Occurrence count of first entity
        entity2_text: Second entity name
        entity2_count: Occurrence count of second entity
        context1: Optional context snippet for entity1
        context2: Optional context snippet for entity2
        confidence: Pre-calculated confidence score
        reason: Reason for similarity
        ollama_config: Ollama configuration

    Returns:
        Dict with decision: {"should_merge": bool, "reasoning": str, "confidence": float}
    """
    config = ollama_config or DEFAULT_OLLAMA_CONFIG

    # Build prompt
    prompt = f"""You are reviewing whether two entity names refer to the same person.

Entity 1: "{entity1_text}" (appears {entity1_count} times)
Entity 2: "{entity2_text}" (appears {entity2_count} times)

Algorithm similarity: {confidence:.2f}
Algorithm reasoning: {reason}
"""

    if context1:
        prompt += f"\nContext where Entity 1 appears:\n{context1[:500]}\n"

    if context2:
        prompt += f"\nContext where Entity 2 appears:\n{context2[:500]}\n"

    prompt += """
Question: Do these two entity names refer to the same person or organization?

Consider:
- Typos and OCR errors:
  * "Jeffrey" vs "Jefffrey" (repeated letters)
  * "Stearns" vs "Steams" or "Sterns" (common: "rn" reads as "m", "ns" reads as "rn")
  * "Clinton" vs "Clint" (truncation)
- Middle names/initials (e.g., "Alan Dershowitz" vs "Alan M. Dershowitz")
- Name variations (e.g., "Kathy" vs "Kathryn", "Yasser" vs "Yasir")
- Well-known organizations: If one name matches a famous company/institution,
  variants are likely OCR errors

- BUT be careful of:
  * Different people with similar names
  * Different organizations (e.g., "Senate Majority" vs "Senate Minority")
  * Different places (e.g., "South Africa" vs "South America", "Santa Clara" vs "Santa Claus")

Respond with JSON:
{
  "should_merge": true/false,
  "reasoning": "explanation of your decision",
  "confidence": 0.95
}
"""

    try:
        url = f"{config.host}/api/generate"
        payload = {
            "model": config.model,
            "prompt": prompt,
            "stream": False,
            "format": "json",
        }

        response = requests.post(url, json=payload, timeout=config.timeout)
        response.raise_for_status()

        result = response.json()
        decision = json.loads(result["response"])

        return decision

    except Exception as e:
        console.print(f"[red]LLM error: {e}[/red]")
        return {"should_merge": False, "reasoning": f"Error: {e}", "confidence": 0.0}


def batch_llm_review(
    db_path: Path,
    candidates_file: Path,
    min_confidence: float = 0.80,
    max_confidence: float = 0.95,
    dry_run: bool = False,
    ollama_config: OllamaConfig = None,
) -> dict:
    """Review merge candidates using LLM.

    Args:
        db_path: Path to SQLite database
        candidates_file: Path to merge candidates JSON file
        min_confidence: Minimum confidence for LLM review
        max_confidence: Maximum confidence for LLM review
        dry_run: If True, don't actually merge
        ollama_config: Ollama configuration

    Returns:
        Dict with review statistics
    """
    # Load candidates
    with open(candidates_file, encoding="utf-8") as f:
        report = json.load(f)

    # Filter for medium-confidence candidates
    llm_review_candidates = [
        c
        for c in report.get("llm_review", [])
        if min_confidence <= c["confidence"] <= max_confidence
    ]

    if not llm_review_candidates:
        console.print(
            f"[yellow]No candidates found with confidence between "
            f"{min_confidence} and {max_confidence}[/yellow]"
        )
        return {"reviewed": 0, "approved": 0, "rejected": 0, "merged": 0, "errors": 0}

    console.print(
        f"[bold]Reviewing {len(llm_review_candidates)} candidates with LLM "
        f"(confidence {min_confidence}-{max_confidence})[/bold]"
    )
    console.print(f"[dim]Using model: {(ollama_config or DEFAULT_OLLAMA_CONFIG).model}[/dim]\n")

    if dry_run:
        console.print("[yellow]DRY RUN - No actual merges will be performed[/yellow]\n")

    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row

    stats = {
        "total_candidates": len(llm_review_candidates),
        "reviewed": 0,
        "approved": 0,
        "rejected": 0,
        "merged": 0,
        "errors": 0,
        "decisions": [],
    }

    for candidate in track(llm_review_candidates, description="LLM reviewing"):
        e1 = candidate["entity1"]
        e2 = candidate["entity2"]

        # Get context snippets for entities
        context1 = conn.execute(
            """
            SELECT context FROM document_entities
            WHERE entity_id = ?
            LIMIT 1
            """,
            (e1["id"],),
        ).fetchone()

        context2 = conn.execute(
            """
            SELECT context FROM document_entities
            WHERE entity_id = ?
            LIMIT 1
            """,
            (e2["id"],),
        ).fetchone()

        # Ask LLM
        decision = ask_llm_merge_decision(
            entity1_text=e1["text"],
            entity1_count=e1["count"],
            entity2_text=e2["text"],
            entity2_count=e2["count"],
            context1=context1["context"] if context1 else None,
            context2=context2["context"] if context2 else None,
            confidence=candidate["confidence"],
            reason=candidate["reason"],
            ollama_config=ollama_config,
        )

        stats["reviewed"] += 1

        decision_record = {
            "entity1": e1["text"],
            "entity2": e2["text"],
            "algorithm_confidence": candidate["confidence"],
            "algorithm_reason": candidate["reason"],
            "llm_decision": decision.get("should_merge", False),
            "llm_reasoning": decision.get("reasoning", ""),
            "llm_confidence": decision.get("confidence", 0.0),
        }

        stats["decisions"].append(decision_record)

        if decision.get("should_merge", False):
            stats["approved"] += 1

            # Determine which should be canonical
            if e1["count"] >= e2["count"]:
                source_id = e2["id"]
                source_text = e2["text"]
                target_text = e1["text"]
            else:
                source_id = e1["id"]
                source_text = e1["text"]
                target_text = e2["text"]

            # Get target canonical_id
            target_canonical = conn.execute(
                "SELECT canonical_id FROM entity_aliases WHERE entity_id = ?",
                (e1["id"] if e1["count"] >= e2["count"] else e2["id"],),
            ).fetchone()

            if not target_canonical:
                console.print(f"[red]Error: Target canonical not found for {target_text}[/red]")
                stats["errors"] += 1
                continue

            if dry_run:
                console.print(
                    f"[dim]Would merge:[/dim] {source_text} → {target_text} "
                    f"(LLM confidence: {decision.get('confidence', 0.0):.2f})"
                )
                stats["merged"] += 1
            else:
                try:
                    result = merge_entities(
                        conn=conn,
                        source_entity_id=source_id,
                        target_canonical_id=target_canonical["canonical_id"],
                        method="llm",
                        confidence=decision.get("confidence", 0.0),
                        merged_by=f"llm:{(ollama_config or DEFAULT_OLLAMA_CONFIG).model}",
                    )

                    if result.get("status") == "merged":
                        stats["merged"] += 1
                        console.print(f"[green]✓[/green] Merged: {source_text} → {target_text}")
                    else:
                        stats["errors"] += 1

                except Exception as e:
                    console.print(f"[red]Error merging {source_text} → {target_text}: {e}[/red]")
                    stats["errors"] += 1
        else:
            stats["rejected"] += 1
            console.print(
                f"[yellow]✗[/yellow] Rejected: {e1['text']} ≠ {e2['text']} "
                f"({decision.get('reasoning', 'No reason')[:50]}...)"
            )

    conn.close()

    # Print summary
    console.print("\n[bold green]✓ LLM review complete![/bold green]")
    console.print(f"  Candidates reviewed: {stats['reviewed']}")
    console.print(f"  [green]Approved for merge: {stats['approved']}[/green]")
    console.print(f"  [yellow]Rejected: {stats['rejected']}[/yellow]")
    console.print(f"  Successfully merged: {stats['merged']}")
    if stats["errors"] > 0:
        console.print(f"  [red]Errors: {stats['errors']}[/red]")

    return stats


def save_review_log(stats: dict, output_file: Path):
    """Save LLM review log to JSON file.

    Args:
        stats: Review statistics dict
        output_file: Path to output file
    """
    with open(output_file, "w", encoding="utf-8") as f:
        json.dump(stats, f, indent=2)

    console.print(f"\n[bold]Review log saved to:[/bold] {output_file}")
