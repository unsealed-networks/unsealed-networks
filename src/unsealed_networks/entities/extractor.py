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
    start: int | None = None  # Character position in document
    end: int | None = None  # Character position in document

    def to_dict(self) -> dict[str, Any]:
        """Convert entity to dictionary for serialization."""
        return {
            "name": self.text,
            "confidence": self.confidence,
            "method": self.method,
            "start": self.start,
            "end": self.end,
        }


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
    LOW_CONFIDENCE_THRESHOLD = 0.80  # Entities below this get LLM validation

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

        # Stage 2: LLM extraction + validation (optional)
        if use_llm:
            # First, do fresh LLM extraction to find entities regex missed
            llm_entities = self._extract_with_llm(text)

            # Merge LLM entities with regex entities (deduplicate)
            entities = self._merge_entities(entities, llm_entities)

            # Stage 3: Validate low-confidence entities
            entities = self._validate_low_confidence_entities(entities, text)

        return entities

    def _extract_people_regex(self, text: str) -> list[Entity]:
        """Extract person names using regex patterns."""
        people = []
        seen = set()  # Deduplicate

        for pattern in self._COMPILED_PERSON_PATTERNS:
            for match in pattern.finditer(text):
                name = match.group(1) if match.lastindex else match.group(0)
                # Get positions for the captured group or full match
                start_pos = match.start(1) if match.lastindex else match.start()
                end_pos = match.end(1) if match.lastindex else match.end()
                name = name.strip()

                # Filter out common false positives
                if self._is_likely_person_name(name) and name not in seen:
                    context = self._get_context(text, start_pos, end_pos)
                    confidence = self._calculate_name_confidence(name, context)

                    people.append(
                        Entity(
                            text=name,
                            type="person",
                            confidence=confidence,
                            context=context,
                            method="regex",
                            start=start_pos,
                            end=end_pos,
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
                start_pos = match.start(1) if match.lastindex else match.start()
                end_pos = match.end(1) if match.lastindex else match.end()
                org = org.strip()

                if org not in seen and len(org) > 3:  # Filter very short matches
                    context = self._get_context(text, start_pos, end_pos)

                    orgs.append(
                        Entity(
                            text=org,
                            type="organization",
                            confidence=0.80,  # Org patterns are fairly reliable
                            context=context,
                            method="regex",
                            start=start_pos,
                            end=end_pos,
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
                start_pos = match.start()
                end_pos = match.end()

                if loc not in seen:
                    context = self._get_context(text, start_pos, end_pos)

                    locations.append(
                        Entity(
                            text=loc,
                            type="location",
                            confidence=0.85,  # Location patterns are quite reliable
                            context=context,
                            method="regex",
                            start=start_pos,
                            end=end_pos,
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
                start_pos = match.start()
                end_pos = match.end()

                if date not in seen:
                    context = self._get_context(text, start_pos, end_pos)

                    dates.append(
                        Entity(
                            text=date,
                            type="date",
                            confidence=0.95,  # Date patterns are very reliable
                            context=context,
                            method="regex",
                            start=start_pos,
                            end=end_pos,
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

    def _extract_with_llm(self, text: str) -> dict[str, list[Entity]]:
        """Use LLM to extract entities from text.

        This does fresh extraction, not validation of existing entities.
        Useful for finding entities that regex patterns miss (e.g., single-word names).
        """
        # Prepare text for LLM (truncate if too long)
        llm_text = text[: self.MAX_TEXT_LENGTH]

        # Build extraction prompt
        prompt = self._build_extraction_prompt(llm_text)

        try:
            # Call Ollama for extraction
            result = self._call_ollama_extraction(prompt)

            # Parse LLM response into Entity objects
            entities = self._parse_llm_entities(result, llm_text)

        except Exception as e:
            # If LLM fails, return empty results
            logger.warning(f"LLM extraction failed: {e}")
            entities = {"people": [], "organizations": [], "locations": [], "dates": []}

        return entities

    def _build_extraction_prompt(self, text: str) -> str:
        """Build prompt for LLM entity extraction."""
        prompt = f"""Extract all named entities from the following document.

Focus on:
- **People**: All person names, including single-word references (e.g., "Putin",
  "Trump"), nicknames (e.g., "Bubba"), and full names
- **Organizations**: Companies, institutions, government agencies
- **Locations**: Cities, countries, addresses, geographic locations

Document excerpt:
{text}

Respond with JSON in this exact format:
{{
  "people": ["Name 1", "Name 2", ...],
  "organizations": ["Org 1", "Org 2", ...],
  "locations": ["Location 1", "Location 2", ...]
}}

Important:
- Include ALL person references, even single-word names or nicknames
- Do not include common words that happen to be capitalized
- Do not include pronouns (he, she, they, etc.)
- Focus on proper nouns that refer to specific entities"""
        return prompt

    def _call_ollama_extraction(self, prompt: str) -> dict[str, Any]:
        """Call Ollama API for entity extraction."""
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
            extracted = json.loads(result["response"])
        except json.JSONDecodeError as e:
            logger.warning(f"LLM returned invalid JSON: {result['response'][:200]}... Error: {e}")
            extracted = {}

        return extracted

    def _parse_llm_entities(self, llm_result: dict[str, Any], text: str) -> dict[str, list[Entity]]:
        """Parse LLM extraction results into Entity objects."""
        entities = {"people": [], "organizations": [], "locations": [], "dates": []}

        # Map LLM response keys to our entity types
        type_mapping = {
            "people": "person",
            "organizations": "organization",
            "locations": "location",
        }

        for llm_key, entity_type in type_mapping.items():
            for entity_text in llm_result.get(llm_key, []):
                # Find entity in original text for context
                pattern = re.compile(re.escape(entity_text), re.IGNORECASE)
                match = pattern.search(text)

                if match:
                    context = self._get_context(text, match.start(), match.end())
                else:
                    context = ""

                entities[llm_key].append(
                    Entity(
                        text=entity_text,
                        type=entity_type,
                        confidence=0.90,  # LLM extractions get high confidence
                        context=context,
                        method="llm",
                    )
                )

        return entities

    def _merge_entities(
        self, regex_entities: dict[str, list[Entity]], llm_entities: dict[str, list[Entity]]
    ) -> dict[str, list[Entity]]:
        """Merge regex and LLM entity extractions, removing duplicates."""
        merged = {}

        for entity_type in regex_entities.keys():
            # Combine both lists
            all_entities = regex_entities[entity_type] + llm_entities.get(entity_type, [])

            # Deduplicate by normalized text (case-insensitive)
            seen = {}
            for entity in all_entities:
                normalized = entity.text.lower().strip()
                if normalized not in seen:
                    seen[normalized] = entity
                else:
                    # Keep the one with higher confidence
                    if entity.confidence > seen[normalized].confidence:
                        seen[normalized] = entity

            merged[entity_type] = list(seen.values())

        return merged

    def _validate_low_confidence_entities(
        self, entities: dict[str, list[Entity]], text: str
    ) -> dict[str, list[Entity]]:
        """Validate low-confidence entities with LLM to filter out OCR noise.

        Entities below LOW_CONFIDENCE_THRESHOLD are sent to LLM for validation.
        Entities that LLM confirms as invalid are filtered out.
        """
        # Collect all low-confidence entities
        low_conf_entities = []
        for entity_list in entities.values():
            for entity in entity_list:
                if entity.confidence < self.LOW_CONFIDENCE_THRESHOLD:
                    low_conf_entities.append(entity)

        # If no low-confidence entities, skip validation
        if not low_conf_entities:
            return entities

        logger.info(f"Validating {len(low_conf_entities)} low-confidence entities with LLM")

        # Build validation prompt
        prompt = self._build_low_confidence_validation_prompt(text, low_conf_entities)

        try:
            # Call LLM for validation
            result = self._call_ollama_validation(prompt)

            # Apply validation results (filter out invalid entities)
            entities = self._apply_low_confidence_validation(entities, result)

        except Exception as e:
            # If LLM validation fails, keep original entities
            logger.warning(f"Low-confidence entity validation failed: {e}")

        return entities

    def _build_low_confidence_validation_prompt(self, text: str, entities: list[Entity]) -> str:
        """Build prompt for validating low-confidence entities."""
        # Truncate text for LLM
        llm_text = text[: self.MAX_TEXT_LENGTH]

        # Build entity list with context
        entity_entries = []
        for entity in entities:
            entity_entries.append(
                f'- "{entity.text}" (type: {entity.type}, context: ...{entity.context}...)'
            )
        entity_list = "\n".join(entity_entries)

        prompt = f"""The following entities were extracted from a document,
but have low confidence scores. Your task is to determine if each entity is VALID
(a real entity) or INVALID (OCR noise, parsing error, or not an entity).

Common signs of invalid entities:
- Contains newline characters or strange whitespace (e.g., "High\\nAsk")
- Nonsense text or gibberish (e.g., "Zxqw Rtyp")
- Partial words or broken text from OCR errors
- Common words that aren't actually entity names
- Text fragments that don't make sense as entities

Document excerpt:
{llm_text}

Entities to validate:
{entity_list}

Respond with JSON in this exact format:
{{
  "validation_results": [
    {{"text": "entity name", "is_valid": true, "reasoning": "why it's valid"}},
    {{"text": "entity name", "is_valid": false, "reasoning": "why it's invalid"}},
    ...
  ]
}}

Mark entities as "is_valid": false if they are clearly OCR errors,
nonsense text, or not real entities."""
        return prompt

    def _apply_low_confidence_validation(
        self, entities: dict[str, list[Entity]], validation_result: dict[str, Any]
    ) -> dict[str, list[Entity]]:
        """Apply LLM validation results by filtering out invalid entities."""
        # Build lookup of validation results
        validation_lookup = {v["text"]: v for v in validation_result.get("validation_results", [])}

        # Filter entities based on validation
        filtered = {}
        for entity_type, entity_list in entities.items():
            filtered_list = []
            for entity in entity_list:
                # Check if entity was validated
                if entity.text in validation_lookup:
                    validation = validation_lookup[entity.text]
                    if validation.get("is_valid", True):
                        # Keep valid entities
                        filtered_list.append(entity)
                        logger.debug(
                            f"Validated '{entity.text}': {validation.get('reasoning', 'N/A')}"
                        )
                    else:
                        # Filter out invalid entities
                        reason = validation.get("reasoning", "N/A")
                        logger.info(f"Filtered out invalid entity '{entity.text}': {reason}")
                else:
                    # Keep entities that weren't checked (high confidence)
                    filtered_list.append(entity)

            filtered[entity_type] = filtered_list

        return filtered

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
