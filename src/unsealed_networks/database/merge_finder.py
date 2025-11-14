"""Find entity merge candidates using similarity metrics."""

import sqlite3
from dataclasses import dataclass
from pathlib import Path

import Levenshtein
from rich.console import Console
from rich.progress import track

console = Console()


@dataclass
class MergeCandidate:
    """A potential entity merge with similarity metrics."""

    entity1_id: int
    entity1_text: str
    entity1_count: int
    entity2_id: int
    entity2_text: str
    entity2_count: int
    levenshtein_distance: int
    jaccard_similarity: float
    confidence: float
    reason: str


def calculate_jaccard_similarity(text1: str, text2: str) -> float:
    """Calculate Jaccard similarity between two texts based on word tokens.

    Args:
        text1: First text
        text2: Second text

    Returns:
        Jaccard similarity (0.0 to 1.0)
    """
    tokens1 = set(text1.lower().split())
    tokens2 = set(text2.lower().split())

    if not tokens1 or not tokens2:
        return 0.0

    intersection = len(tokens1 & tokens2)
    union = len(tokens1 | tokens2)

    return intersection / union if union > 0 else 0.0


def calculate_merge_confidence(
    text1: str,
    text2: str,
    count1: int,
    count2: int,
    lev_distance: int,
    jaccard: float,
) -> tuple[float, str]:
    """Calculate confidence score for merging two entities.

    Args:
        text1: First entity text
        text2: Second entity text
        count1: Occurrence count of first entity
        count2: Occurrence count of second entity
        lev_distance: Levenshtein distance between texts
        jaccard: Jaccard similarity

    Returns:
        Tuple of (confidence score 0.0-1.0, reason string)
    """
    reasons = []

    # Base confidence from Levenshtein distance
    if lev_distance == 0:
        return 1.0, "Exact match (different case)"
    elif lev_distance == 1:
        confidence = 0.95
        reasons.append("Edit distance=1 (likely typo)")
    elif lev_distance == 2:
        confidence = 0.85
        reasons.append("Edit distance=2 (possible typo)")
    elif lev_distance == 3:
        confidence = 0.70
        reasons.append("Edit distance=3")
    else:
        confidence = 0.50
        reasons.append(f"Edit distance={lev_distance}")

    # Boost for high token overlap
    if jaccard >= 0.8:
        confidence += 0.10
        reasons.append(f"High token overlap ({jaccard:.0%})")
    elif jaccard >= 0.5:
        confidence += 0.05
        reasons.append(f"Good token overlap ({jaccard:.0%})")

    # Boost if one entity is rare (likely typo of common one)
    total_count = count1 + count2
    if total_count > 0:
        ratio = min(count1, count2) / max(count1, count2)
        if ratio < 0.1 and max(count1, count2) > 10:
            confidence += 0.05
            reasons.append(f"Rare variant ({min(count1, count2)} vs {max(count1, count2)})")

    # Penalize if Jaccard is too low (might be different entities)
    if jaccard < 0.3:
        confidence -= 0.15
        reasons.append(f"Low token overlap ({jaccard:.0%})")

    # Cap at 1.0
    confidence = min(confidence, 1.0)

    return confidence, "; ".join(reasons)


def find_merge_candidates(
    db_path: Path,
    entity_type: str = "person",
    min_occurrences: int = 5,
    max_distance: int = 3,
    min_confidence: float = 0.70,
    limit: int = 100,
) -> list[MergeCandidate]:
    """Find entity merge candidates using similarity metrics.

    Uses blocking strategy to avoid N² comparisons:
    - Groups entities by type and first 3 characters
    - Only compares within each block

    Args:
        db_path: Path to SQLite database
        entity_type: Entity type to search (person, organization, etc.)
        min_occurrences: Minimum occurrences to consider (focus on frequent entities)
        max_distance: Maximum Levenshtein distance
        min_confidence: Minimum confidence score to include
        limit: Maximum candidates to return

    Returns:
        List of MergeCandidate objects sorted by confidence (high to low)
    """
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row

    # Get entities grouped by normalized_text prefix (blocking strategy)
    # Only consider entities that aren't already merged (is_canonical=1)
    query = """
        SELECT e.entity_id, e.text, e.normalized_text, e.occurrence_count,
               SUBSTR(e.normalized_text, 1, 3) as prefix
        FROM entities e
        JOIN entity_aliases ea ON e.entity_id = ea.entity_id
        WHERE e.type = ?
          AND e.occurrence_count >= ?
          AND ea.is_canonical = 1
        ORDER BY prefix, e.occurrence_count DESC
    """

    entities = conn.execute(query, (entity_type, min_occurrences)).fetchall()
    conn.close()

    if not entities:
        console.print(
            f"[yellow]No {entity_type} entities with >={min_occurrences} occurrences[/yellow]"
        )
        return []

    console.print(
        f"[bold]Finding merge candidates for {len(entities)} {entity_type} entities...[/bold]"
    )

    # Group by prefix for blocking
    blocks = {}
    for entity in entities:
        prefix = entity["prefix"]
        if prefix not in blocks:
            blocks[prefix] = []
        blocks[prefix].append(entity)

    console.print(f"  Blocked into {len(blocks)} groups by prefix")

    # Find candidates within each block
    candidates = []
    total_comparisons = 0

    for _prefix, block in track(list(blocks.items()), description="Comparing entities"):
        # Only compare within block (not across all entities)
        for i in range(len(block)):
            for j in range(i + 1, len(block)):
                e1 = block[i]
                e2 = block[j]
                total_comparisons += 1

                # Quick filter: length difference check
                len_diff = abs(len(e1["normalized_text"]) - len(e2["normalized_text"]))
                if len_diff > max_distance:
                    continue

                # Calculate Jaccard similarity first (faster than Levenshtein)
                jaccard = calculate_jaccard_similarity(e1["normalized_text"], e2["normalized_text"])

                # Skip if no token overlap at all
                if jaccard == 0.0:
                    continue

                # Calculate Levenshtein distance
                lev_distance = Levenshtein.distance(e1["normalized_text"], e2["normalized_text"])

                if lev_distance > max_distance:
                    continue

                # Calculate confidence
                confidence, reason = calculate_merge_confidence(
                    e1["text"],
                    e2["text"],
                    e1["occurrence_count"],
                    e2["occurrence_count"],
                    lev_distance,
                    jaccard,
                )

                if confidence >= min_confidence:
                    candidates.append(
                        MergeCandidate(
                            entity1_id=e1["entity_id"],
                            entity1_text=e1["text"],
                            entity1_count=e1["occurrence_count"],
                            entity2_id=e2["entity_id"],
                            entity2_text=e2["text"],
                            entity2_count=e2["occurrence_count"],
                            levenshtein_distance=lev_distance,
                            jaccard_similarity=jaccard,
                            confidence=confidence,
                            reason=reason,
                        )
                    )

    console.print(f"  Total comparisons: {total_comparisons:,}")
    console.print(f"  Candidates found: {len(candidates)}")

    # Sort by confidence (high to low) and limit
    candidates.sort(key=lambda c: c.confidence, reverse=True)
    return candidates[:limit]


def generate_merge_report(
    db_path: Path,
    entity_type: str = "person",
    min_occurrences: int = 5,
    output_file: Path = None,
) -> dict:
    """Generate a report of merge candidates.

    Args:
        db_path: Path to SQLite database
        entity_type: Entity type to search
        min_occurrences: Minimum occurrences
        output_file: Optional path to save JSON report

    Returns:
        Dict with merge candidates and statistics
    """
    candidates = find_merge_candidates(
        db_path=db_path,
        entity_type=entity_type,
        min_occurrences=min_occurrences,
        max_distance=3,
        min_confidence=0.70,
        limit=200,
    )

    # Group by confidence level
    auto_merge = [c for c in candidates if c.confidence >= 0.95]
    llm_review = [c for c in candidates if 0.80 <= c.confidence < 0.95]
    manual_review = [c for c in candidates if 0.70 <= c.confidence < 0.80]

    report = {
        "entity_type": entity_type,
        "min_occurrences": min_occurrences,
        "total_candidates": len(candidates),
        "auto_merge_count": len(auto_merge),
        "llm_review_count": len(llm_review),
        "manual_review_count": len(manual_review),
        "auto_merge": [
            {
                "entity1": {"id": c.entity1_id, "text": c.entity1_text, "count": c.entity1_count},
                "entity2": {"id": c.entity2_id, "text": c.entity2_text, "count": c.entity2_count},
                "distance": c.levenshtein_distance,
                "jaccard": c.jaccard_similarity,
                "confidence": c.confidence,
                "reason": c.reason,
            }
            for c in auto_merge
        ],
        "llm_review": [
            {
                "entity1": {"id": c.entity1_id, "text": c.entity1_text, "count": c.entity1_count},
                "entity2": {"id": c.entity2_id, "text": c.entity2_text, "count": c.entity2_count},
                "distance": c.levenshtein_distance,
                "jaccard": c.jaccard_similarity,
                "confidence": c.confidence,
                "reason": c.reason,
            }
            for c in llm_review
        ],
        "manual_review": [
            {
                "entity1": {"id": c.entity1_id, "text": c.entity1_text, "count": c.entity1_count},
                "entity2": {"id": c.entity2_id, "text": c.entity2_text, "count": c.entity2_count},
                "distance": c.levenshtein_distance,
                "jaccard": c.jaccard_similarity,
                "confidence": c.confidence,
                "reason": c.reason,
            }
            for c in manual_review
        ],
    }

    if output_file:
        import json

        with open(output_file, "w", encoding="utf-8") as f:
            json.dump(report, f, indent=2)
        console.print(f"\n[bold]Report saved to:[/bold] {output_file}")

    return report
