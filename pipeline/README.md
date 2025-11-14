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

Steps are executed in order:

1. `step_01_classify.py` - Classify document type (email, memo, letter, etc.)
2. `step_02_extract_entities.py` - Extract people, organizations, locations
3. `step_03_extract_urls.py` - Extract and validate URLs
4. `step_04_fix_ocr_urls.py` - Detect and repair OCR-broken URLs
5. `step_99_assemble_metadata.py` - Final metadata assembly

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
