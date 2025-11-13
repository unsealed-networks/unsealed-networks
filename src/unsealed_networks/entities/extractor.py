"""Hybrid entity extraction using regex + LLM validation."""

import json
import logging
import re
from dataclasses import dataclass
from typing import Any

import requests

from ..config import DEFAULT_OLLAMA_CONFIG, OllamaConfig

logger = logging.getLogger(__name__)


@dataclass
class Entity:
    """Extracted entity with metadata."""

    text: str
    type: str  # person, organization, location, date
    confidence: float  # 0.0 to 1.0
    context: str  # surrounding text
    method: str  # "regex" or "llm"


class HybridEntityExtractor:
    """Extract entities using regex patterns with optional LLM validation.

    Two-stage approach:
    1. Fast regex extraction for high-confidence patterns
    2. LLM validation for uncertain or missed entities

    Configuration:
    - REGEX_CONFIDENCE: Minimum confidence for regex-only extraction
    - LLM_VALIDATION_ENABLED: Whether to use LLM for validation
    - CONTEXT_WINDOW: Characters before/after entity for context
    """

    # Configuration constants
    REGEX_CONFIDENCE = 0.85  # High-confidence regex matches skip LLM
    LLM_VALIDATION_ENABLED = True  # Toggle LLM validation
    CONTEXT_WINDOW = 50  # Characters of context around entity
    MAX_TEXT_LENGTH = 3000  # Max chars to send to LLM

    # Regex patterns for entity extraction
    # Person names: Title + First + Last, or First + Last
    PERSON_PATTERNS = [
        # Formal: Mr./Ms./Dr. First Last (capture name after title)
        r"\b(?:Mr\.|Mrs\.|Ms\.|Dr\.|Prof\.)\s+([A-Z][a-z]{2,}(?:\s+[A-Z]\.?)?\s+[A-Z][a-z]{2,})\b",
        # First Middle? Last (both words at least 3 chars, not followed by org suffix)
        r"\b([A-Z][a-z]{2,}(?:\s+[A-Z]\.)?\s+[A-Z][a-z]{2,})(?!\s*(?:Inc\.|LLC|Corp\.|University|College|Foundation|Department))\b",  # noqa: E501
        # Email signature: "- John Smith" or "Best regards, John Smith"
        r"(?:^|\n)[-—]\s*([A-Z][a-z]{2,}\s+[A-Z][a-z]{2,})",
        r"(?:Regards|Sincerely|Best),?\s+([A-Z][a-z]{2,}\s+[A-Z][a-z]{2,})",
    ]

    # Organizations: Inc., LLC, Corp., University, Company, etc.
    ORG_PATTERNS = [
        # Corporate suffixes (limit length to avoid long matches)
        r"\b([A-Z][A-Za-z\s&]{2,40}(?:Inc\.|LLC|Corp\.|Corporation|Company|Co\.))\b",
        # Educational/research institutions (limit length)
        r"\b([A-Z][A-Za-z\s]{2,30}(?:University|College|Institute|Foundation))\b",
        # Government agencies (limit length)
        r"\b([A-Z][A-Za-z\s]{2,30}(?:Department|Agency|Commission|Bureau))\b",
        # Financial/professional (limit length)
        r"\b([A-Z][A-Za-z\s]{2,30}(?:Bank|Group|Partners|Associates))\b",
    ]

    # Locations: City, State/Country
    LOCATION_PATTERNS = [
        # City, State (e.g., "New York, NY") - match on same line
        r"\b([A-Z][a-z]+(?:\s+[A-Z][a-z]+)*),\s*([A-Z]{2})(?:\s|$)",
        # Street addresses with numbers (must have street suffix)
        r"\b(\d+\s+[A-Z][a-z]+(?:\s+[A-Z][a-z]+)*\s+(?:Street|St\.|Avenue|Ave\.|Road|Rd\.|Boulevard|Blvd\.|Way|Drive|Dr\.|Lane|Ln\.))\b",  # noqa: E501
    ]

    # Dates: Multiple formats
    DATE_PATTERNS = [
        r"\b(\d{1,2}/\d{1,2}/\d{2,4})\b",  # MM/DD/YYYY or M/D/YY
        r"\b(\d{4}-\d{2}-\d{2})\b",  # YYYY-MM-DD
        r"\b((?:January|February|March|April|May|June|July|August|September|October|November|December)\s+\d{1,2},?\s+\d{4})\b",  # noqa: E501
        r"\b((?:Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)\.?\s+\d{1,2},?\s+\d{4})\b",  # noqa: E501
    ]

    # Pre-compiled patterns for performance (avoid recompiling in loops)
    _COMPILED_PERSON_PATTERNS = [re.compile(p) for p in PERSON_PATTERNS]
    _COMPILED_ORG_PATTERNS = [re.compile(p) for p in ORG_PATTERNS]
    _COMPILED_LOCATION_PATTERNS = [re.compile(p) for p in LOCATION_PATTERNS]
    _COMPILED_DATE_PATTERNS = [re.compile(p, re.IGNORECASE) for p in DATE_PATTERNS]

    def __init__(
        self,
        ollama_config: OllamaConfig = None,
        enable_llm: bool = None,
    ):
        """Initialize extractor with optional configuration.

        Args:
            ollama_config: Ollama configuration (defaults to DEFAULT_OLLAMA_CONFIG)
            enable_llm: Whether to use LLM validation
        """
        self.ollama_config = ollama_config or DEFAULT_OLLAMA_CONFIG
        self.llm_enabled = enable_llm if enable_llm is not None else self.LLM_VALIDATION_ENABLED

    def extract(self, text: str, validate_with_llm: bool = None) -> dict[str, list[Entity]]:
        """Extract all entity types from text.

        Args:
            text: Document text to extract entities from
            validate_with_llm: Override LLM validation setting

        Returns:
            Dictionary mapping entity type to list of Entity objects
        """
        use_llm = validate_with_llm if validate_with_llm is not None else self.llm_enabled

        # Stage 1: Regex extraction
        entities = {
            "people": self._extract_people_regex(text),
            "organizations": self._extract_organizations_regex(text),
            "locations": self._extract_locations_regex(text),
            "dates": self._extract_dates_regex(text),
        }

        # Stage 2: LLM validation (optional)
        if use_llm:
            entities = self._validate_with_llm(text, entities)

        return entities

    def _extract_people_regex(self, text: str) -> list[Entity]:
        """Extract person names using regex patterns."""
        people = []
        seen = set()  # Deduplicate

        for pattern in self._COMPILED_PERSON_PATTERNS:
            for match in pattern.finditer(text):
                name = match.group(1) if match.lastindex else match.group(0)
                name = name.strip()

                # Filter out common false positives
                if self._is_likely_person_name(name) and name not in seen:
                    context = self._get_context(text, match.start(), match.end())
                    confidence = self._calculate_name_confidence(name, context)

                    people.append(
                        Entity(
                            text=name,
                            type="person",
                            confidence=confidence,
                            context=context,
                            method="regex",
                        )
                    )
                    seen.add(name)

        return people

    def _extract_organizations_regex(self, text: str) -> list[Entity]:
        """Extract organization names using regex patterns."""
        orgs = []
        seen = set()

        for pattern in self._COMPILED_ORG_PATTERNS:
            for match in pattern.finditer(text):
                org = match.group(1) if match.lastindex else match.group(0)
                org = org.strip()

                if org not in seen and len(org) > 3:  # Filter very short matches
                    context = self._get_context(text, match.start(), match.end())

                    orgs.append(
                        Entity(
                            text=org,
                            type="organization",
                            confidence=0.80,  # Org patterns are fairly reliable
                            context=context,
                            method="regex",
                        )
                    )
                    seen.add(org)

        return orgs

    def _extract_locations_regex(self, text: str) -> list[Entity]:
        """Extract location names using regex patterns."""
        locations = []
        seen = set()

        for pattern in self._COMPILED_LOCATION_PATTERNS:
            for match in pattern.finditer(text):
                loc = match.group(0).strip()

                if loc not in seen:
                    context = self._get_context(text, match.start(), match.end())

                    locations.append(
                        Entity(
                            text=loc,
                            type="location",
                            confidence=0.85,  # Location patterns are quite reliable
                            context=context,
                            method="regex",
                        )
                    )
                    seen.add(loc)

        return locations

    def _extract_dates_regex(self, text: str) -> list[Entity]:
        """Extract dates using regex patterns."""
        dates = []
        seen = set()

        for pattern in self._COMPILED_DATE_PATTERNS:
            for match in pattern.finditer(text):
                date = match.group(0).strip()

                if date not in seen:
                    context = self._get_context(text, match.start(), match.end())

                    dates.append(
                        Entity(
                            text=date,
                            type="date",
                            confidence=0.95,  # Date patterns are very reliable
                            context=context,
                            method="regex",
                        )
                    )
                    seen.add(date)

        return dates

    def _is_likely_person_name(self, name: str) -> bool:
        """Filter out common false positives for person names."""
        # Reject if all caps (likely heading/label)
        if name.isupper():
            return False

        # Reject if too short
        if len(name) < 4:
            return False

        # Reject if starts with "The " (organizational/title indicator)
        if name.startswith("The "):
            return False

        # Reject common organizational/location words that match name pattern
        false_positives = {
            "The Court",
            "The Judge",
            "The Plaintiff",
            "The Defendant",
            "United States",
            "New York",
            "District Court",
            "Supreme Court",
            "Dear Sir",
            "Dear Madam",
            "Dear Mr",
            "Dear Ms",
            "Dear Dr",
            "Palm Beach",
            "Los Angeles",
            "San Francisco",
            "El Paso",
            "Santa Barbara",
            "Fort Lauderdale",
        }
        if name in false_positives:
            return False

        # Reject if contains organization keywords
        org_keywords = [
            "University",
            "College",
            "Institute",
            "Foundation",
            "Department",
            "Agency",
            "Corporation",
            "Inc.",
            "LLC",
            "Corp.",
        ]  # noqa: E501
        if any(keyword in name for keyword in org_keywords):
            return False

        # Reject if ends with location indicator
        if name.endswith((" Beach", " City", " Island", " County", " Park")):
            return False

        # Reject if ends with street suffix (address)
        if name.endswith((" Way", " Street", " Avenue", " Road", " Boulevard", " Drive", " Lane")):
            return False

        # Must have at least two words (first + last)
        if len(name.split()) < 2:
            return False

        # Reject if contains numbers (addresses, document refs)
        if re.search(r"\d", name):
            return False

        return True

    def _calculate_name_confidence(self, name: str, context: str) -> float:
        """Calculate confidence score for person name based on context."""
        confidence = 0.70  # Base confidence

        # Boost if formal title nearby
        if re.search(r"\b(?:Mr\.|Mrs\.|Ms\.|Dr\.|Prof\.)\s*", context, re.IGNORECASE):
            confidence += 0.15

        # Boost if in signature context
        if re.search(r"(?:Sincerely|Regards|Best|From|Sent by)", context, re.IGNORECASE):
            confidence += 0.10

        # Boost if common name pattern (First M. Last)
        if re.search(r"\b[A-Z][a-z]+\s+[A-Z]\.\s+[A-Z][a-z]+\b", name):
            confidence += 0.05

        return min(confidence, 1.0)

    def _get_context(self, text: str, start: int, end: int) -> str:
        """Extract context around entity for validation."""
        context_start = max(0, start - self.CONTEXT_WINDOW)
        context_end = min(len(text), end + self.CONTEXT_WINDOW)
        return text[context_start:context_end]

    def _validate_with_llm(
        self, text: str, entities: dict[str, list[Entity]]
    ) -> dict[str, list[Entity]]:
        """Use LLM to validate and enhance entity extraction.

        Only validates entities with confidence < REGEX_CONFIDENCE threshold.
        """
        # Filter low-confidence entities that need validation
        low_confidence = []
        for _entity_type, entity_list in entities.items():
            for entity in entity_list:
                if entity.confidence < self.REGEX_CONFIDENCE:
                    low_confidence.append(entity)

        if not low_confidence:
            return entities  # All entities are high-confidence

        # Prepare text for LLM (truncate if too long)
        llm_text = text[: self.MAX_TEXT_LENGTH]

        # Build validation prompt
        prompt = self._build_validation_prompt(llm_text, low_confidence)

        try:
            # Call Ollama for validation
            validated = self._call_ollama_validation(prompt)

            # Update confidence scores based on LLM response
            entities = self._apply_llm_validation(entities, validated)

        except Exception as e:
            # If LLM fails, return original regex results
            logger.warning(f"LLM validation failed: {e}")

        return entities

    def _build_validation_prompt(self, text: str, entities: list[Entity]) -> str:
        """Build prompt for LLM entity validation."""
        entity_list = "\n".join(
            [f"- {e.text} (type: {e.type}, confidence: {e.confidence:.2f})" for e in entities]
        )

        prompt = f"""Validate the following entities extracted from a document.
For each entity, confirm if it's correctly identified and adjust confidence (0.0-1.0).

Document excerpt:
{text}

Entities to validate:
{entity_list}

Respond with JSON:
{{
  "validated_entities": [
    {{"text": "entity name", "type": "person|organization|location|date", "confidence": 0.95}},
    ...
  ]
}}"""
        return prompt

    def _call_ollama_validation(self, prompt: str) -> dict[str, Any]:
        """Call Ollama API for entity validation."""
        url = f"{self.ollama_config.host}/api/generate"
        payload = {
            "model": self.ollama_config.model,
            "prompt": prompt,
            "stream": False,
            "format": "json",
        }

        response = requests.post(url, json=payload, timeout=self.ollama_config.timeout)
        response.raise_for_status()

        result = response.json()

        try:
            validated = json.loads(result["response"])
        except json.JSONDecodeError as e:
            logger.warning(f"LLM returned invalid JSON: {result['response'][:200]}... Error: {e}")
            validated = {}

        return validated

    def _apply_llm_validation(
        self, entities: dict[str, list[Entity]], validated: dict[str, Any]
    ) -> dict[str, list[Entity]]:
        """Apply LLM validation results to entity list."""
        # Create lookup for validated entities
        validated_lookup = {v["text"]: v for v in validated.get("validated_entities", [])}

        # Update confidence scores
        for _entity_type, entity_list in entities.items():
            for entity in entity_list:
                if entity.text in validated_lookup:
                    val = validated_lookup[entity.text]
                    entity.confidence = val["confidence"]
                    entity.method = "llm"

        return entities
