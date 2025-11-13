"""Document classification ETL stage with regex + LLM hybrid approach."""

import json
import logging
from dataclasses import dataclass
from pathlib import Path

import requests

from unsealed_networks.parsers.classifier import DocumentClassifier

logger = logging.getLogger(__name__)


@dataclass
class ClassificationResult:
    """Enhanced classification result from ETL pipeline."""

    filepath: str
    document_type: str
    confidence: float
    subtype: str | None = None
    method: str = "regex"  # "regex" or "llm"
    reasoning: str | None = None  # For LLM classifications


class HybridDocumentClassifier:
    """Two-stage classifier: regex (fast) → LLM (for 'other' documents)."""

    # Configuration constants
    REGEX_CONFIDENCE_THRESHOLD = 0.85  # If regex confidence < this, use LLM
    LLM_CONFIDENCE_THRESHOLD = 0.70  # Minimum confidence to accept LLM result
    OLLAMA_TIMEOUT = 30  # Seconds
    MAX_CONTENT_LENGTH = 1000  # Characters to send to LLM

    # Improved classification prompt with hierarchy
    CLASSIFICATION_PROMPT = """Analyze this document excerpt and classify
it into ONE of these categories:

**IMPORTANT CLASSIFICATION RULES:**
1. If the document has email headers (From:, To:, Subject:, Sent:, Date:),
   classify as "email" EVEN IF it contains informal language or
   thread-style conversation
2. Only classify as "chat_transcript" if it has explicit chat/messaging
   metadata like "iMessage", "Service:", mobile UI timestamps, or lacks
   standard email headers
3. When in doubt between email and chat_transcript, choose email if ANY
   email headers are present

**Categories:**

1. email - Email correspondence (MUST have From:/To:/Subject: headers)
2. chat_transcript - Text message or chat conversation (iMessage, SMS,
   mobile chat apps - NO email headers)
3. letter - Formal or business letter (letterhead, formal salutation)
4. report - Analysis, research report, or data summary
5. memo - Internal memorandum or note
6. legal_document - Court filing, deposition, or legal document
7. news_article - News article or press report
8. list - Contact list, invitation list, or structured data
9. technical - Technical documentation or instructions
10. corrupted - Unreadable, heavily corrupted, or OCR errors

Return ONLY a JSON object with this format:
{{
  "category": "one_of_the_above",
  "confidence": 0.0-1.0,
  "reasoning": "brief explanation focusing on WHY you chose this category over similar ones"
}}

Document excerpt:
"""

    def __init__(
        self,
        ollama_url: str = "http://localhost:11434/api/generate",
        ollama_model: str = "qwen2.5:7b",
    ):
        """Initialize hybrid classifier.

        Args:
            ollama_url: Ollama API endpoint
            ollama_model: Model to use for LLM classification
        """
        self.regex_classifier = DocumentClassifier()
        self.ollama_url = ollama_url
        self.ollama_model = ollama_model

    def classify(self, filepath: Path) -> ClassificationResult:
        """Classify a document using hybrid approach.

        First tries regex classification. If confidence is low or type is "other",
        falls back to LLM classification.

        Args:
            filepath: Path to document

        Returns:
            ClassificationResult with method used and confidence
        """
        # Stage 1: Regex classification
        regex_result = self.regex_classifier.classify(filepath)

        # Check if regex classification is confident enough
        if (
            regex_result.doc_type != "other"
            and regex_result.confidence >= self.REGEX_CONFIDENCE_THRESHOLD
        ):
            # High confidence regex result, use it
            return ClassificationResult(
                filepath=str(filepath),
                document_type=regex_result.doc_type,
                confidence=regex_result.confidence,
                subtype=regex_result.subtype,
                method="regex",
            )

        # Stage 2: LLM classification for "other" or low-confidence documents
        logger.debug(
            f"Using LLM for {filepath.name} "
            f"(regex: {regex_result.doc_type}, confidence: {regex_result.confidence:.2f})"
        )

        try:
            llm_result = self._classify_with_llm(filepath)

            # If LLM confidence is acceptable, use it
            if llm_result["confidence"] >= self.LLM_CONFIDENCE_THRESHOLD:
                return ClassificationResult(
                    filepath=str(filepath),
                    document_type=llm_result["category"],
                    confidence=llm_result["confidence"],
                    method="llm",
                    reasoning=llm_result["reasoning"],
                )

            # LLM confidence too low, fall back to regex result
            logger.warning(
                f"LLM confidence too low for {filepath.name} "
                f"({llm_result['confidence']:.2f}), using regex result"
            )

        except Exception as e:
            logger.error(f"LLM classification failed for {filepath.name}: {e}, using regex result")

        # Fallback to regex result
        return ClassificationResult(
            filepath=str(filepath),
            document_type=regex_result.doc_type,
            confidence=regex_result.confidence,
            subtype=regex_result.subtype,
            method="regex",
        )

    def _classify_with_llm(self, filepath: Path) -> dict[str, str | float]:
        """Classify document using Ollama LLM.

        Args:
            filepath: Path to document

        Returns:
            Dict with category, confidence, reasoning

        Raises:
            Exception: If Ollama request fails
        """
        # Read content excerpt
        with open(filepath, encoding="utf-8-sig", errors="replace") as f:
            content = f.read(self.MAX_CONTENT_LENGTH)

        # Build prompt
        prompt = self.CLASSIFICATION_PROMPT + content

        # Call Ollama API
        payload = {
            "model": self.ollama_model,
            "prompt": prompt,
            "stream": False,
            "format": "json",
        }

        response = requests.post(self.ollama_url, json=payload, timeout=self.OLLAMA_TIMEOUT)
        response.raise_for_status()

        result_data = response.json()
        classification = json.loads(result_data["response"])

        return classification


def classify_documents(
    source_dir: Path,
    output_path: Path,
    ollama_url: str = "http://localhost:11434/api/generate",
    ollama_model: str = "qwen2.5:7b",
    progress_interval: int = 50,
) -> list[ClassificationResult]:
    """Classify all documents in a directory.

    Args:
        source_dir: Directory containing text files
        output_path: Path to save classification results JSON
        ollama_url: Ollama API endpoint
        ollama_model: Model to use for LLM classification
        progress_interval: Log progress every N documents

    Returns:
        List of classification results
    """
    classifier = HybridDocumentClassifier(ollama_url=ollama_url, ollama_model=ollama_model)

    # Find all text files
    text_files = sorted(source_dir.rglob("*.txt"))
    total_files = len(text_files)

    logger.info(f"Found {total_files} text files to classify")

    results = []

    for i, filepath in enumerate(text_files, 1):
        try:
            result = classifier.classify(filepath)
            results.append(result)

            if i % progress_interval == 0:
                logger.info(f"Classified {i}/{total_files} documents...")

        except Exception as e:
            logger.error(f"Failed to classify {filepath.name}: {e}")
            # Continue with next document
            continue

    # Save results
    results_data = [
        {
            "filepath": r.filepath,
            "document_type": r.document_type,
            "confidence": r.confidence,
            "subtype": r.subtype,
            "method": r.method,
            "reasoning": r.reasoning,
        }
        for r in results
    ]

    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(results_data, f, indent=2)

    logger.info(f"Saved {len(results)} classification results to {output_path}")

    # Log statistics
    from collections import Counter

    type_counts = Counter(r.document_type for r in results)
    method_counts = Counter(r.method for r in results)

    logger.info("Classification distribution:")
    for doc_type, count in type_counts.most_common():
        percentage = count / len(results) * 100
        logger.info(f"  {doc_type:20s}: {count:5d} ({percentage:5.1f}%)")

    logger.info(f"Methods used: regex={method_counts['regex']}, llm={method_counts['llm']}")

    return results
