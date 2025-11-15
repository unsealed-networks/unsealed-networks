# Document Processing Pipeline

A file-based document processing pipeline that executes extraction and analysis steps
in sequence, tracking progress via JSON manifests.

## Directory Structure

```
pipeline/
├── inbox/           # Drop new documents here for processing
├── processing/      # Documents currently being processed
├── completed/       # Successfully processed documents
├── dead_letters/    # Failed documents with error details
├── manifests/       # JSON manifests tracking processing state
└── steps/          # Pipeline step implementations
```

## Workflow

1. **Document Arrival**: Drop document in `inbox/`
2. **Processing Start**: Workflow moves doc to `processing/` and creates manifest
3. **Step Execution**: Each step runs sequentially, updating manifest
4. **Completion**: On success, move to `completed/`; on failure, move to `dead_letters/`

## Manifest Format

Each document has a corresponding JSON manifest in `manifests/{doc_id}.json`:

```json
{
  "doc_id": "HOUSE_OVERSIGHT_123456",
  "original_file": "HOUSE_OVERSIGHT_123456.txt",
  "created_at": "2025-11-14T19:30:00Z",
  "updated_at": "2025-11-14T19:35:00Z",
  "status": "completed|processing|failed",
  "steps": [
    {
      "step_name": "classify",
      "step_version": 1,
      "started_at": "2025-11-14T19:30:00Z",
      "completed_at": "2025-11-14T19:30:15Z",
      "status": "success",
      "outcome": {
        "doc_type": "email",
        "confidence": 0.95
      }
    },
    {
      "step_name": "extract_entities",
      "step_version": 2,
      "started_at": "2025-11-14T19:30:15Z",
      "completed_at": "2025-11-14T19:32:00Z",
      "status": "success",
      "outcome": {
        "entities_found": 42
      }
    }
  ],
  "metadata": {
    "doc_type": "email",
    "participants": ["Jeffrey Epstein", "Donald Trump"],
    "content_entities": ["Trump", "Bannon"],
    "urls": ["https://example.com"],
    "email_headers": {}
  },
  "error": null
}
```

## Pipeline Steps

Steps are **composable building blocks** located in `src/unsealed_networks/pipeline/steps/`. They declare dependencies explicitly and can be composed into different pipelines:

### Available Steps
- `classify.py` - Classify document type (email, memo, letter, etc.)
- `extract_email_metadata.py` - Extract email headers and participants
- `extract_urls.py` - Extract and validate URLs
- `extract_entities.py` - Extract people, organizations, locations using hybrid regex + LLM approach with low-confidence validation
- `assemble_metadata.py` - Final metadata consolidation

### Entity Extraction Quality Control

The `extract_entities.py` step uses a three-stage approach to ensure high-quality entity extraction:

1. **Regex Extraction**: Fast pattern matching for common entity formats
2. **LLM Extraction**: Finds entities regex patterns miss (e.g., single-word names like "Putin")
3. **Low-Confidence Validation**: Entities with confidence < 0.80 are validated by LLM to filter out:
   - OCR noise (e.g., "High\nAsk")
   - Gibberish text (e.g., "Zxqw Rtyp")
   - Partial words from OCR errors
   - Text fragments that aren't real entities

This multi-stage approach balances speed, accuracy, and quality.

### Example: Text Document Pipeline
```
classify → extract_email_metadata → extract_urls → extract_entities → assemble_metadata
```

### Example: Future OCR Pipeline
```
ocr → classify → extract_entities → assemble_metadata
```

Steps can be run individually:
```bash
uv run python -m unsealed_networks.pipeline.steps.classify DOC_ID path/to/doc.txt
```

## Step Invalidation & Reprocessing

When adding a new step (e.g., `step_05_deduplicate.py`):

1. Query manifests where `steps` array doesn't include `step_05`
2. For matching documents:
   - Truncate manifest.steps after step_04
   - Clear downstream metadata
   - Re-run from step_05 onward

This allows incremental enhancement without full reprocessing.

## Dead Letter Queue

Failed documents go to `dead_letters/` with:
- Original document file
- Manifest showing last successful step
- Error details in `manifest.error`

This enables forensic analysis and manual recovery.

## Entity Seeding

High-confidence entities (>=4 mentions) are exported to `pipeline/entity_seed.json`
for use in entity extraction and disambiguation.

## n8n Integration

The workflow engine orchestrates execution:
- File watcher triggers on new files in `inbox/`
- Atomic file moves prevent race conditions
- Sequential step execution with error handling
- Automatic retry logic for transient failures
