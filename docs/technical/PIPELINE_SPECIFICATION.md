# Document Processing Pipeline Specification

## Overview

The Unsealed Networks document processing pipeline is a file-based, incremental processing system that executes extraction and analysis steps on documents while tracking provenance, dependencies, and execution state through JSON manifests.

## Design Goals

1. **Repeatable**: New documents automatically processed through all steps
2. **Incrementally Upgradeable**: Add new steps without full reprocessing
3. **Traceable**: Complete audit trail of processing history
4. **Recoverable**: Failed documents isolated with forensic details
5. **Efficient**: Only reprocess dependent steps when upgrading

## Architecture

### File-Based Queue System

```
pipeline/
├── inbox/           # New documents dropped here
├── processing/      # Documents currently being processed
├── completed/       # Successfully processed documents
├── dead_letters/    # Failed documents with error details
├── manifests/       # JSON processing state for each document
└── steps/          # Pipeline step implementations
```

**Workflow:**
1. Document dropped in `inbox/`
2. n8n workflow moves to `processing/` (atomic operation)
3. Steps execute sequentially, updating manifest
4. On success: move to `completed/`
5. On failure: move to `dead_letters/`

### Document Provenance

Every document must track its origin for proper citation and data lineage.

**Document ID Format:**
```
{SOURCE}_{BATCH}_{ORIGINAL_ID}
```

Examples:
- `HOUSE_OVERSIGHT_7THPROD_000123`
- `SDNY_DISCOVERY_20240115_00042`
- `FBI_FOIA_2024Q1_00891`

**Provenance Metadata** (stored in manifest):
```json
{
  "provenance": {
    "source": "House Oversight Committee",
    "source_abbrev": "HOUSE_OVERSIGHT",
    "batch": "7th_production",
    "batch_date": "2024-01-15",
    "original_filename": "HOUSE_OVERSIGHT_000123.txt",
    "ingested_at": "2025-11-14T19:30:00Z",
    "file_hash": "sha256:abcd1234..."
  }
}
```

**Dropping Documents into Pipeline:**

Option 1: Use helper script
```bash
python pipeline/ingest_document.py \
  --source "HOUSE_OVERSIGHT" \
  --batch "7th_production" \
  --file source_text/7th_production/HOUSE_OVERSIGHT_000123.txt
```

Option 2: Manual with metadata sidecar
```bash
# Copy document
cp source.txt pipeline/inbox/HOUSE_OVERSIGHT_7THPROD_000123.txt

# Create metadata sidecar
cat > pipeline/inbox/HOUSE_OVERSIGHT_7THPROD_000123.meta.json <<EOF
{
  "source": "House Oversight Committee",
  "source_abbrev": "HOUSE_OVERSIGHT",
  "batch": "7th_production",
  "batch_date": "2024-01-15",
  "original_filename": "HOUSE_OVERSIGHT_000123.txt"
}
EOF
```

The ingestion step reads the `.meta.json` sidecar and incorporates it into the manifest.

## Manifest Schema

Each document has a JSON manifest tracking its processing state:

**File:** `pipeline/manifests/{doc_id}.json`

```json
{
  "doc_id": "HOUSE_OVERSIGHT_7THPROD_000123",
  "original_file": "HOUSE_OVERSIGHT_000123.txt",
  "created_at": "2025-11-14T19:30:00Z",
  "updated_at": "2025-11-14T19:35:00Z",
  "status": "completed",  // processing | completed | failed

  "provenance": {
    "source": "House Oversight Committee",
    "source_abbrev": "HOUSE_OVERSIGHT",
    "batch": "7th_production",
    "batch_date": "2024-01-15",
    "original_filename": "HOUSE_OVERSIGHT_000123.txt",
    "ingested_at": "2025-11-14T19:30:00Z",
    "file_hash": "sha256:abcd1234..."
  },

  "steps": [
    {
      "step_name": "classify",
      "step_version": 1,
      "depends_on": [],
      "started_at": "2025-11-14T19:30:00Z",
      "completed_at": "2025-11-14T19:30:15Z",
      "status": "success",
      "outcome": {
        "doc_type": "email",
        "confidence": 0.95
      }
    },
    {
      "step_name": "extract_email_headers",
      "step_version": 1,
      "depends_on": ["classify"],
      "started_at": "2025-11-14T19:30:15Z",
      "completed_at": "2025-11-14T19:32:00Z",
      "status": "success",
      "outcome": {
        "from": "epstein@example.com",
        "to": ["trump@example.com"],
        "date": "2016-03-15",
        "subject": "Meeting tomorrow"
      }
    },
    {
      "step_name": "extract_entities",
      "step_version": 2,
      "depends_on": [],
      "started_at": "2025-11-14T19:32:00Z",
      "completed_at": "2025-11-14T19:34:00Z",
      "status": "success",
      "outcome": {
        "entities_found": 42
      }
    },
    {
      "step_name": "extract_urls",
      "step_version": 1,
      "depends_on": [],
      "started_at": "2025-11-14T19:34:00Z",
      "completed_at": "2025-11-14T19:34:30Z",
      "status": "success",
      "outcome": {
        "urls_found": 5,
        "urls": [
          {
            "url": "https://example.com",
            "domain": "example.com",
            "type": "other",
            "position": 150
          }
        ]
      }
    },
    {
      "step_name": "fetch_url_metadata",
      "step_version": 1,
      "depends_on": ["extract_urls"],
      "started_at": "2025-11-14T19:34:30Z",
      "completed_at": "2025-11-14T19:35:00Z",
      "status": "success",
      "outcome": {
        "url_metadata": {
          "https://example.com": {
            "title": "Example Domain",
            "description": "Example website for documentation",
            "status_code": 200
          }
        }
      }
    },
    {
      "step_name": "assemble_metadata",
      "step_version": 1,
      "depends_on": ["classify", "extract_email_headers", "extract_entities", "fetch_url_metadata"],
      "started_at": "2025-11-14T19:35:00Z",
      "completed_at": "2025-11-14T19:35:10Z",
      "status": "success",
      "outcome": {
        "metadata_fields_assembled": 6
      }
    }
  ],

  "metadata": {
    "doc_type": "email",
    "from": "epstein@example.com",
    "to": ["trump@example.com"],
    "participants": ["Jeffrey Epstein", "Donald Trump"],
    "content_entities": ["Trump", "Bannon"],
    "urls": ["https://example.com"]
  },

  "error": null
}
```

## Manifest as Data Source

**Key Design Principle:** The manifest is not just a log - it's a **structured data source** that steps can read and query.

### Step Outcome vs Global Metadata

**IMPORTANT:** There's a critical distinction between step outcomes and global metadata:

**Step Outcomes (intermediate data):**
- Each step stores its extracted/processed data in its own `outcome` field
- This data is the raw result of what that step produced
- Later steps read from prior step outcomes to build on previous work
- Examples:
  - `extract_urls` outcome contains the full list of URLs with classification
  - `fetch_url_metadata` outcome contains a hash/dict of metadata per URL
  - `extract_entities` outcome contains the raw entity list

**Global Metadata (final assembled data):**
- The top-level `metadata` field is ONLY populated by the final `assemble_metadata` step
- This step consolidates data from all prior step outcomes into the final document metadata
- The metadata field represents the complete, queryable data for the document
- Only `assemble_metadata` writes to `manifest.metadata`

**Why this matters:**
- Keeps step responsibilities clear and focused
- Allows steps to be re-run without corrupting the final metadata
- Makes it easy to trace where each piece of data came from
- Enables debugging by inspecting intermediate step outcomes

**Pattern example:**
```python
# ❌ WRONG: Don't update global metadata in intermediate steps
class ExtractURLsStep(PipelineStep):
    def execute(self, doc_path, manifest):
        urls = self._extract_urls(doc_path)
        manifest.update_metadata("urls", urls)  # ❌ Don't do this!
        return {"urls": urls}

# ✅ CORRECT: Store data in step outcome only
class ExtractURLsStep(PipelineStep):
    def execute(self, doc_path, manifest):
        urls = self._extract_urls(doc_path)
        return {"urls": urls}  # ✅ Data stays in step outcome

# ✅ CORRECT: Later steps read from prior outcomes
class FetchURLMetadataStep(PipelineStep):
    depends_on = ["extract_urls"]

    def execute(self, doc_path, manifest):
        # Read URLs from prior step outcome
        urls_step = manifest.get_step("extract_urls")
        urls = urls_step.outcome["urls"]

        # Fetch metadata for each URL
        url_metadata = {}
        for url_data in urls:
            url_metadata[url_data["url"]] = self._fetch_metadata(url_data["url"])

        return {"url_metadata": url_metadata}  # ✅ Store in outcome

# ✅ CORRECT: Final step assembles all data into global metadata
class AssembleMetadataStep(PipelineStep):
    depends_on = ["classify", "extract_email_headers", "extract_entities", "fetch_url_metadata"]

    def execute(self, doc_path, manifest):
        # Gather data from all prior steps
        classify = manifest.get_step("classify").outcome
        headers = manifest.get_step("extract_email_headers").outcome
        entities = manifest.get_step("extract_entities").outcome
        url_meta = manifest.get_step("fetch_url_metadata").outcome

        # Assemble into final metadata structure
        manifest.update_metadata("doc_type", classify["doc_type"])
        manifest.update_metadata("from", headers["from"])
        manifest.update_metadata("to", headers["to"])
        manifest.update_metadata("entities", entities["entity_list"])
        manifest.update_metadata("url_titles", [
            meta["title"] for meta in url_meta["url_metadata"].values()
        ])

        return {"metadata_fields_assembled": 6}
```

### Reading Prior Step Results

Each step receives the manifest as a parameter and can access results from any previously executed step:

```python
class FixOCRURLsStep(PipelineStep):
    def execute(self, doc_path: Path, manifest: Manifest) -> dict:
        # Read URLs from previous step
        extract_urls_step = manifest.get_step("extract_urls")
        urls = extract_urls_step.outcome["urls"]

        # Process OCR-broken URLs
        fixed_urls = []
        for url_data in urls:
            if self._has_spaces(url_data["url"]):
                fixed = self._remove_spaces(url_data["url"])
                fixed_urls.append(fixed)

        return {"fixed_urls": fixed_urls}
```

### Reading Document Provenance

Steps can also access document metadata:

```python
class ClassifyStep(PipelineStep):
    def execute(self, doc_path: Path, manifest: Manifest) -> dict:
        # Access provenance to adapt classification
        source = manifest.provenance["source_abbrev"]

        # Use different heuristics for different sources
        if source == "HOUSE_OVERSIGHT":
            # These are mostly emails and letters
            classifiers = ["email", "letter", "memo"]
        elif source == "FBI_FOIA":
            # These are mostly reports and forms
            classifiers = ["report", "form", "investigation"]

        # Run classification...
```

### Conditional Execution Based on Prior Results

Steps can skip or adapt behavior based on dependencies:

```python
class ExtractEmailHeadersStep(PipelineStep):
    def execute(self, doc_path: Path, manifest: Manifest) -> dict:
        # Only run if document is classified as email
        classify_step = manifest.get_step("classify")
        if not classify_step or classify_step.outcome["doc_type"] != "email":
            return {
                "skipped": True,
                "reason": "Document is not an email"
            }

        # Extract email headers...
```

### Accessing Multiple Step Results

Steps can combine data from multiple prior steps:

```python
class AssembleMetadataStep(PipelineStep):
    def execute(self, doc_path: Path, manifest: Manifest) -> dict:
        # Gather data from all prior steps
        classification = manifest.get_step("classify").outcome
        entities = manifest.get_step("extract_entities").outcome
        urls = manifest.get_step("fix_ocr_urls").outcome

        # Assemble final metadata
        return {
            "doc_type": classification["doc_type"],
            "participants": entities["people"],
            "organizations": entities["organizations"],
            "urls": urls["valid_urls"],
            "source": manifest.provenance["source"]
        }
```

This makes the manifest a **living document** that grows richer as steps execute, with each step contributing to a shared knowledge base about the document.

## Step Dependencies

Each pipeline step declares which other steps it depends on. This enables intelligent invalidation and reprocessing.

### Declaring Dependencies

Steps declare dependencies via the `depends_on` property:

```python
class ExtractEmailHeadersStep(PipelineStep):
    @property
    def name(self) -> str:
        return "extract_email_headers"

    @property
    def version(self) -> int:
        return 1

    @property
    def depends_on(self) -> list[str]:
        """This step only runs if document is classified as email."""
        return ["classify"]

    def execute(self, doc_path: Path, manifest: Manifest) -> dict[str, Any]:
        # Validation: check dependency results
        classify_step = manifest.get_step("classify")
        if classify_step.outcome["doc_type"] != "email":
            return {"skipped": True, "reason": "Not an email document"}

        # Extract email headers...
        return {"from": "...", "to": [...], ...}
```

### Dependency Graph Example

```
classify (v1)
    │
    ├──> extract_email_headers (v1) [depends on: classify]
    │
    ├──> extract_urls (v1) [depends on: none]
    │
    ├──> extract_entities (v2) [depends on: none]
    │
    └──> fix_ocr_urls (v1) [depends on: extract_urls]
              │
              └──> fetch_url_metadata (v1) [depends on: fix_ocr_urls]
```

### Invalidation Rules

When a step is updated (version bumped or logic changed):

1. **Direct invalidation**: The updated step must be rerun
2. **Cascade invalidation**: All steps that depend on the updated step must be rerun

**Example:**

If `classify` is updated from v1 to v2:
- `classify` is invalidated (direct)
- `extract_email_headers` is invalidated (depends on classify)
- `extract_urls` is NOT invalidated (no dependency)
- `extract_entities` is NOT invalidated (no dependency)

If `extract_urls` is updated from v1 to v2:
- `extract_urls` is invalidated (direct)
- `fix_ocr_urls` is invalidated (depends on extract_urls)
- `fetch_url_metadata` is invalidated (depends on fix_ocr_urls, transitively depends on extract_urls)
- `classify` is NOT invalidated
- `extract_entities` is NOT invalidated

### Detecting Invalidated Documents

When updating a step, find documents that need reprocessing:

```python
def find_invalidated_documents(step_name: str, new_version: int) -> list[str]:
    """Find documents where a step or its dependents need reprocessing."""
    invalidated_docs = []

    for manifest_path in Path("pipeline/manifests").glob("*.json"):
        manifest = Manifest.load_from_file(manifest_path)

        # Check if step needs updating
        step = manifest.get_step(step_name)
        if not step or step.step_version < new_version:
            invalidated_docs.append(manifest.doc_id)
            continue

        # Check if any dependent steps exist
        if has_dependent_steps(manifest, step_name):
            invalidated_docs.append(manifest.doc_id)

    return invalidated_docs
```

## Pipeline Steps

### Design Principle: Keep Steps Granular

Each step should do **one thing well**. Steps that read from the entity/URL database should be separate from steps that extract raw data.

**Example: Entity Extraction vs Entity Merging**

❌ **Bad** - Monolithic step:
```python
class ExtractAndMergeEntitiesStep:
    """Extract entities AND merge with canonical database (two concerns!)"""
    def execute(self, doc_path, manifest):
        # Extract entities from text
        raw_entities = self.extract(doc_path)

        # Load entity seed from database
        canonical_entities = self.load_entity_seed()

        # Match and merge
        merged = self.merge(raw_entities, canonical_entities)

        return merged  # Mixed raw + canonical data
```

✅ **Good** - Separate steps:
```python
class ExtractEntitiesStep:
    """Extract raw entities from document text (pure extraction)."""
    def execute(self, doc_path, manifest):
        # Just find entities in the text
        entities = self.extract_from_text(doc_path)
        return {"entities": entities}  # Raw extraction

class MergeEntitiesStep:
    """Map extracted entities to canonical forms."""
    depends_on = ["extract_entities"]

    def execute(self, doc_path, manifest):
        # Read extracted entities from prior step
        raw_entities = manifest.get_step("extract_entities").outcome["entities"]

        # Load canonical entity seed
        canonical_db = self.load_entity_seed()

        # Match and create mappings
        mappings = self.match_to_canonical(raw_entities, canonical_db)

        return {"entity_mappings": mappings}
```

**Benefits:**
- Can update entity seed and re-merge without re-extracting
- Extraction step has no DB dependency (faster, simpler testing)
- Can swap extraction models without touching merge logic
- Database only stores canonical entity IDs, not all aliases

### Standard Step Sequence

1. **classify** (v1)
   - Depends on: none
   - Classifies document type (email, memo, letter, report, etc.)

2. **extract_email_headers** (v1)
   - Depends on: classify
   - Only runs if doc_type == "email"
   - Extracts From, To, Date, Subject

3. **extract_entities** (v2)
   - Depends on: none
   - Extracts raw entities from text (people, organizations, locations, dates)
   - Output: List of entity mentions with positions

4. **merge_entities** (v1)
   - Depends on: extract_entities
   - Maps extracted entities to canonical forms using entity seed DB
   - Output: Entity mentions with canonical_entity_id mappings

5. **extract_urls** (v1)
   - Depends on: none
   - Finds all URLs in document text

6. **fix_ocr_urls** (v1)
   - Depends on: extract_urls
   - Detects and repairs space-broken URLs from OCR errors

7. **fetch_url_metadata** (v1)
   - Depends on: fix_ocr_urls
   - Fetches titles/descriptions for URLs

8. **assemble_metadata** (v1)
   - Depends on: all prior steps
   - Consolidates all step outcomes into final metadata object

### Conditional Steps

Some steps only run based on prior results:

```python
class ExtractEmailHeadersStep(PipelineStep):
    def execute(self, doc_path: Path, manifest: Manifest) -> dict[str, Any]:
        classify_result = manifest.get_step("classify")

        if classify_result.outcome["doc_type"] != "email":
            return {"skipped": True, "reason": "Not an email"}

        # Extract headers...
```

This allows the pipeline to adapt to document types.

## Entity Seeding

High-confidence entities (appearing >=4 times) are exported as a "seed set" for entity extraction and disambiguation.

**Seed Generation:**
```bash
python pipeline/generate_entity_seed.py --min-mentions 4
```

**Output:** `pipeline/entity_seed.json`
```json
{
  "generated_at": "2025-11-14T20:00:00Z",
  "min_mentions": 4,
  "entities": [
    {
      "canonical_id": "PERSON_000042",
      "canonical_name": "Donald Trump",
      "entity_type": "PERSON",
      "total_mentions": 1847,
      "known_variations": ["Trump", "Donald J. Trump", "Donald Trump"]
    },
    ...
  ]
}
```

**Usage in Pipeline:**

The `extract_entities` step loads the seed and uses it for disambiguation:

```python
class ExtractEntitiesStep(PipelineStep):
    def __init__(self):
        super().__init__()
        self.entity_seed = self.load_entity_seed()

    def load_entity_seed(self) -> dict:
        seed_path = Path("pipeline/entity_seed.json")
        if seed_path.exists():
            with open(seed_path) as f:
                return json.load(f)
        return {"entities": []}

    def execute(self, doc_path: Path, manifest: Manifest) -> dict:
        # Extract entities and match against seed...
```

## Error Handling & Dead Letter Queue

### Failure Modes

1. **Transient Failures**
   - Network timeouts
   - Temporary resource unavailability
   - Action: Retry with exponential backoff (3 attempts)

2. **Permanent Failures**
   - Malformed document
   - Step logic error
   - Unrecoverable data issue
   - Action: Move to dead letters

### Dead Letter Structure

```
pipeline/dead_letters/
├── HOUSE_OVERSIGHT_7THPROD_000123.txt    # Original document
└── HOUSE_OVERSIGHT_7THPROD_000123.error.json  # Error details
```

**Error manifest:**
```json
{
  "doc_id": "HOUSE_OVERSIGHT_7THPROD_000123",
  "failed_at": "2025-11-14T19:35:00Z",
  "failed_step": "extract_entities",
  "error": "ValueError: Invalid entity format in line 42",
  "stack_trace": "...",
  "last_successful_step": "classify",
  "manifest": {
    // Full manifest at time of failure
  }
}
```

### Recovery Process

1. **Diagnose**: Review error details
2. **Fix**: Correct data or update step logic
3. **Reprocess**:
   ```bash
   python pipeline/reprocess_dead_letter.py \
     HOUSE_OVERSIGHT_7THPROD_000123 \
     --from-step extract_entities
   ```

## Reprocessing & Step Invalidation

### Adding a New Step

When inserting a new step (e.g., `deduplicate` after `extract_entities`):

1. **Implement step** with proper dependencies:
   ```python
   class DeduplicateStep(PipelineStep):
       @property
       def depends_on(self) -> list[str]:
           return ["extract_entities"]
   ```

2. **Update workflow** to include new step

3. **Find affected documents**:
   ```bash
   python pipeline/find_missing_step.py deduplicate
   ```

4. **Reprocess documents**:
   ```bash
   python pipeline/reprocess.py \
     --step deduplicate \
     --input completed/ \
     --output inbox/
   ```

### Upgrading a Step

When upgrading a step's version (e.g., `extract_entities` v2 -> v3):

1. **Update step code** and bump version:
   ```python
   @property
   def version(self) -> int:
       return 3
   ```

2. **Find invalidated documents**:
   ```bash
   python pipeline/find_outdated_step.py extract_entities --version 3
   ```

3. **Cascade analysis**:
   ```bash
   # Find all documents where extract_entities or dependent steps need rerun
   python pipeline/find_invalidated_cascade.py extract_entities
   ```

4. **Reprocess**:
   ```bash
   python pipeline/reprocess.py \
     --step extract_entities \
     --cascade \
     --input completed/ \
     --output inbox/
   ```

## Orchestration with n8n

See `pipeline/N8N_WORKFLOW.md` for detailed n8n setup.

**Key points:**
- File watcher triggers on new files in `inbox/`
- Atomic file moves prevent race conditions
- Each step is an Execute Command node
- Error handling branches to dead letter handler
- Retry logic for transient failures

## Database Integration

Final metadata from `assemble_metadata` step is written to database:

```python
class AssembleMetadataStep(PipelineStep):
    @property
    def depends_on(self) -> list[str]:
        return ["classify", "extract_entities", "extract_urls", "fix_ocr_urls"]

    def execute(self, doc_path: Path, manifest: Manifest) -> dict:
        # Consolidate all step outcomes
        metadata = {
            "doc_type": manifest.get_step("classify").outcome["doc_type"],
            "entities": manifest.get_step("extract_entities").outcome,
            "urls": manifest.get_step("fix_ocr_urls").outcome["urls"],
            // ...
        }

        manifest.update_metadata("final", metadata)

        # Write to database
        self.write_to_database(manifest)

        return metadata
```

## Performance Considerations

### Parallel Processing

- n8n workflow handles one document at a time sequentially
- For batch processing, run multiple n8n instances with sharded inbox directories:
  ```
  pipeline/inbox_shard_1/
  pipeline/inbox_shard_2/
  pipeline/inbox_shard_3/
  ```

### Expensive Steps

Steps with expensive operations (LLM calls, HTTP requests) should:
1. Implement caching
2. Use batch processing where possible
3. Report progress for long operations

### Manifest Size

Manifests grow as steps are added. For very large outcomes:
- Store full outcome data in separate file: `pipeline/manifests/{doc_id}/{step_name}.json`
- Store only summary in manifest: `{"outcome_file": "manifests/{doc_id}/extract_entities.json"}`

## Testing Requirements

**Every pipeline step MUST have unit tests.** This is non-negotiable for maintainability.

### Unit Test Structure

Each step should have a test file in `tests/pipeline/steps/` with this structure:

```python
# tests/pipeline/steps/test_extract_urls.py

import pytest
from pathlib import Path
from unsealed_networks.pipeline.manifest import Manifest
from pipeline.steps.step_03_extract_urls import ExtractURLsStep


@pytest.fixture
def temp_doc(tmp_path):
    """Create a temporary test document."""
    doc_path = tmp_path / "test_doc.txt"
    return doc_path


@pytest.fixture
def empty_manifest():
    """Create a fresh manifest for testing."""
    return Manifest.create_new("TEST_DOC_001", "test.txt")


class TestExtractURLsStep:
    """Test suite for URL extraction step."""

    def test_extracts_single_url(self, temp_doc, empty_manifest):
        """Should extract a single URL from document."""
        temp_doc.write_text("Visit https://example.com for details")

        step = ExtractURLsStep()
        outcome = step.execute(temp_doc, empty_manifest)

        assert outcome["urls_found"] == 1
        assert outcome["urls"][0]["url"] == "https://example.com"
        assert outcome["urls"][0]["domain"] == "example.com"
        assert outcome["urls"][0]["type"] == "other"

    def test_extracts_multiple_urls(self, temp_doc, empty_manifest):
        """Should extract multiple URLs from document."""
        content = """
        Check out https://youtube.com/watch?v=abc123
        and also https://news.bbc.com/article.html
        """
        temp_doc.write_text(content)

        step = ExtractURLsStep()
        outcome = step.execute(temp_doc, empty_manifest)

        assert outcome["urls_found"] == 2
        # Check YouTube classification
        youtube_url = next(u for u in outcome["urls"] if "youtube" in u["url"])
        assert youtube_url["type"] == "youtube"
        # Check news classification
        news_url = next(u for u in outcome["urls"] if "bbc" in u["url"])
        assert news_url["type"] == "news"

    def test_deduplicates_urls(self, temp_doc, empty_manifest):
        """Should not return duplicate URLs."""
        content = """
        Visit https://example.com
        Visit https://example.com again
        """
        temp_doc.write_text(content)

        step = ExtractURLsStep()
        outcome = step.execute(temp_doc, empty_manifest)

        assert outcome["urls_found"] == 1

    def test_handles_no_urls(self, temp_doc, empty_manifest):
        """Should handle documents with no URLs."""
        temp_doc.write_text("This document has no URLs at all.")

        step = ExtractURLsStep()
        outcome = step.execute(temp_doc, empty_manifest)

        assert outcome["urls_found"] == 0
        assert outcome["urls"] == []

    def test_stores_data_in_outcome(self, temp_doc, empty_manifest):
        """Should store extracted URLs in step outcome, not global metadata."""
        temp_doc.write_text("Visit https://example.com")

        step = ExtractURLsStep()
        outcome = step.execute(temp_doc, empty_manifest)

        # Check data is in outcome
        assert "urls" in outcome
        assert outcome["urls"][0]["url"] == "https://example.com"

        # Verify global metadata is NOT updated by this step
        assert "urls" not in empty_manifest.metadata

    def test_step_properties(self):
        """Should have correct step metadata."""
        step = ExtractURLsStep()

        assert step.name == "extract_urls"
        assert step.version == 1
        assert step.depends_on == []  # No dependencies
```

### Test Coverage Requirements

Each step test suite must cover:

1. **Happy path**: Normal execution with expected input
2. **Edge cases**:
   - Empty input
   - Malformed input
   - Boundary conditions
3. **Manifest interaction**:
   - Reads from dependencies correctly (if any)
   - Updates manifest metadata properly
4. **Step metadata**:
   - `name` property
   - `version` property
   - `depends_on` property

### Testing Steps with Dependencies

Steps that depend on other steps should mock the manifest state:

```python
# tests/pipeline/steps/test_merge_entities.py

def test_merge_entities_reads_from_extract_step(temp_doc, empty_manifest):
    """Should read entities from extract_entities step."""
    # Mock the extract_entities step result
    from unsealed_networks.pipeline.manifest import StepResult

    extract_result = StepResult(
        step_name="extract_entities",
        step_version=2,
        started_at="2025-11-14T20:00:00Z",
        completed_at="2025-11-14T20:01:00Z",
        status="success",
        outcome={
            "entities": [
                {"text": "Trump", "type": "PERSON", "start": 10, "end": 15},
                {"text": "Epstein", "type": "PERSON", "start": 20, "end": 27}
            ]
        }
    )
    empty_manifest.add_step(extract_result)

    # Now test merge step
    step = MergeEntitiesStep()
    outcome = step.execute(temp_doc, empty_manifest)

    assert "entity_mappings" in outcome
    # Verify merge logic worked correctly
```

### Running Tests

```bash
# Run all pipeline step tests
pytest tests/pipeline/steps/ -v

# Run tests for specific step
pytest tests/pipeline/steps/test_extract_urls.py -v

# Run with coverage
pytest tests/pipeline/steps/ --cov=pipeline.steps --cov-report=html
```

### Coverage Targets

- **Minimum**: 80% line coverage for each step
- **Goal**: 90%+ line coverage
- **Critical paths**: 100% coverage (error handling, data validation)

### Continuous Integration

Pre-commit hook should enforce:
```bash
# .pre-commit-config.yaml
- repo: local
  hooks:
    - id: pytest-check
      name: pytest-check
      entry: pytest tests/pipeline/steps/ --cov=pipeline.steps --cov-fail-under=80
      language: system
      pass_filenames: false
```

### Integration Tests

Full pipeline tests in `tests/integration/test_pipeline.py`:

```python
def test_full_pipeline_execution():
    """Test complete pipeline from inbox to completion."""
    # Drop test document in inbox
    # Run all steps sequentially
    # Verify document in completed/
    # Verify manifest has all steps
    # Verify database records created
```

## Monitoring

### Metrics to Track

1. **Processing Rate**: Documents/hour
2. **Failure Rate**: % of documents in dead letters
3. **Step Duration**: Average time per step
4. **Queue Depth**: Documents in inbox/processing

### Monitoring Script

```bash
python pipeline/monitor.py --summary

# Output:
# Pipeline Status (2025-11-14 20:00:00)
# =====================================
# Inbox: 15 documents
# Processing: 2 documents
# Completed: 2,897 documents
# Failed: 8 documents (0.3%)
#
# Average Processing Time: 45 seconds
# Slowest Step: extract_entities (25s avg)
```

## Future Enhancements

1. **Vector DB Integration**: Document deduplication
2. **Distributed Processing**: Celery task queue
3. **Real-time Dashboard**: Web UI for monitoring
4. **A/B Testing**: Run multiple step versions, compare results
5. **Provenance Chain**: Link to source PDFs, scan quality metrics
