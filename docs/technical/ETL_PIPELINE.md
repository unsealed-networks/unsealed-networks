# Document Processing ETL Pipeline

## Overview

The unsealed-networks project uses an ETL (Extract, Transform, Load) pipeline architecture to process document drops incrementally over time. This design supports:

- **Incremental processing** - Handle new document drops without reprocessing everything
- **Idempotency** - Can safely re-run without creating duplicates
- **Progress tracking** - Resume from failures
- **Multiple stages** - Classification → Parsing → Entity Extraction → Graph Building

## Pipeline Stages

### Stage 1: Document Classification

**Input**: Raw text documents from `source_text/`

**Process**:
1. Run regex-based classifier (fast, handles obvious cases)
2. For documents classified as "other" → Send to Ollama for LLM classification
3. Store classification results with confidence scores

**Output**: Classification results (document type + confidence + subtype)

**Implementation**: `src/unsealed_networks/etl/classify.py`

### Stage 2: Document Parsing

**Input**: Classified documents

**Process**:
1. Route to appropriate parser based on classification:
   - `email` → EmailParser
   - `legal` → LegalDocumentParser
   - `news` → NewsArticleParser
   - `chat_transcript` → ChatTranscriptParser (new)
   - `letter` → LetterParser (new)
   - etc.
2. Extract structured metadata
3. Handle parse failures gracefully

**Output**: Structured metadata for each document

**Implementation**: `src/unsealed_networks/etl/parse.py`

### Stage 3: Entity Extraction

**Input**: Parsed documents

**Process**:
1. Extract entities using Ollama/NER:
   - Person names
   - Organizations
   - Locations
   - Dates/events
2. Store entity mentions with context
3. Build entity resolution (handle name variations)

**Output**: Entity mentions and relationships

**Implementation**: `src/unsealed_networks/etl/extract_entities.py`

### Stage 4: Database Loading

**Input**: Structured metadata + entities

**Process**:
1. Load into SQLite database
2. Update FTS5 index for full-text search
3. Create relationship records
4. Update entity tracking tables

**Output**: Populated database ready for querying

**Implementation**: `src/unsealed_networks/etl/load.py`

### Stage 5: Graph Construction (Future)

**Input**: Entities and relationships from database

**Process**:
1. Build relationship graph (NetworkX or Neo4j)
2. Calculate network metrics
3. Identify communities/clusters

**Output**: Graph database for relationship queries

**Implementation**: `src/unsealed_networks/etl/build_graph.py`

## ETL Runner

The pipeline is orchestrated by a runner that:

1. **Tracks progress** - Stores state in `etl_state.json`
2. **Handles failures** - Can resume from last successful document
3. **Batches work** - Processes documents in configurable batches
4. **Logs progress** - Clear visibility into what's happening
5. **Validates input/output** - Ensures data quality

**Implementation**: `src/unsealed_networks/etl/runner.py`

**CLI**: `uv run unsealed-networks etl run`

## Design Principles

### Idempotency

Each stage checks if work is already done:
- Classification: Check if doc_id already in results
- Parsing: Check if metadata already extracted
- Loading: Use UPSERT operations

### Incremental Processing

New document drops:
1. Place files in `source_text/`
2. Run `uv run unsealed-networks etl run`
3. Pipeline detects new files and processes only those

### Error Handling

- **Document-level failures** - Log and continue (don't fail entire batch)
- **Stage failures** - Can re-run specific stage
- **Validation** - Verify output at each stage

### Performance

- **Batch processing** - Process N documents at a time
- **Caching** - Ollama results cached to avoid re-computation
- **Parallel processing** - Future: Use multiprocessing for independent docs
- **Progress indicators** - Show progress every N documents

## Configuration

Pipeline configuration in `etl_config.yaml`:

```yaml
# Batch sizes
classification_batch_size: 100
parsing_batch_size: 50
entity_extraction_batch_size: 20

# Ollama settings
ollama_url: "http://localhost:11434/api/generate"
ollama_model: "qwen2.5:7b"
ollama_timeout: 30

# Classification thresholds
regex_confidence_threshold: 0.85  # If regex confidence < this, use LLM
llm_confidence_threshold: 0.70    # Minimum confidence to accept LLM result

# Paths
source_dir: "source_text"
database_path: "unsealed_networks.db"
state_file: "etl_state.json"

# Logging
log_level: "INFO"
progress_interval: 50  # Log every N documents
```

## State Tracking

The `etl_state.json` file tracks:

```json
{
  "last_run": "2025-01-13T17:00:00Z",
  "stages": {
    "classify": {
      "documents_processed": 2897,
      "last_document": "HOUSE_OVERSIGHT_033434.txt",
      "status": "completed"
    },
    "parse": {
      "documents_processed": 2897,
      "last_document": "HOUSE_OVERSIGHT_033434.txt",
      "status": "completed"
    },
    "extract_entities": {
      "documents_processed": 0,
      "last_document": null,
      "status": "pending"
    }
  },
  "statistics": {
    "total_documents": 2897,
    "classified_by_regex": 371,
    "classified_by_llm": 2526,
    "parse_failures": 15,
    "entities_extracted": 0
  }
}
```

## CLI Commands

```bash
# Run full pipeline
uv run unsealed-networks etl run

# Run specific stage
uv run unsealed-networks etl classify
uv run unsealed-networks etl parse
uv run unsealed-networks etl extract-entities
uv run unsealed-networks etl load

# Reset and re-run
uv run unsealed-networks etl reset
uv run unsealed-networks etl run --force

# Show status
uv run unsealed-networks etl status
```

## Implementation Plan

1. **Phase 3.1** - Build classification ETL
   - Implement `etl/classify.py` with Ollama integration
   - Build runner framework
   - Test on full dataset

2. **Phase 3.2** - Extend parsers
   - Add ChatTranscriptParser
   - Add LetterParser
   - Add MemoParser
   - Add ReportParser

3. **Phase 3.3** - Entity extraction
   - Implement NER with Ollama
   - Build entity resolution
   - Create entity storage

4. **Phase 3.4** - Database loading
   - Design extended schema
   - Implement UPSERT logic
   - Add migration support

## Testing Strategy

- **Unit tests** - Test each ETL stage independently
- **Integration tests** - Test full pipeline on sample documents
- **Regression tests** - Ensure new drops don't break existing data
- **Performance tests** - Measure throughput and identify bottlenecks

## Monitoring

Track key metrics:
- Documents processed per minute
- Classification accuracy (sample validation)
- Parse success rate
- Entity extraction coverage
- Database size growth
- Query performance

## Future Enhancements

- **Parallel processing** - Use multiprocessing for faster throughput
- **Distributed processing** - Support multiple workers
- **Delta detection** - Only process changed documents
- **Versioning** - Track document processing versions
- **Rollback** - Ability to undo problematic runs
