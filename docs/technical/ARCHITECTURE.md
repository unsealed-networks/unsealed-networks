# Architecture

## Overview

Unsealed Networks is a document processing pipeline that extracts relationship networks from public Epstein documents.

## Design Principles

1. **Reproducible**: All code and data transformations committed to repo
2. **Distributed**: Users run locally, no central query server
3. **Evidence-based**: Only claim what documents support, cite everything
4. **Transparent**: Open methodology, document limitations
5. **Sustainable**: Minimal ongoing maintenance, can walk away

## Pipeline Phases

### Phase 1: Survey & Classification

Fast scan to understand document types before building extractors.

**Inputs:**
- Raw text files from House Oversight Committee releases

**Outputs:**
- `survey_report.json` - Aggregate statistics
- `classification_results.json` - Per-document classifications

**Purpose:**
- Validate data quality
- Identify extraction priorities
- Generate samples for extractor development

### Phase 2: Type-Specific Extraction

Build specialized extractors for each document type.

**Inputs:**
- Classified documents
- Document type samples

**Outputs:**
- Extracted entities (people, organizations, locations, events)
- Extracted relationships with context
- Confidence scores

### Phase 3: Data Model & Database

Store extracted data in queryable format.

**Schema:**
- Documents table with full-text search
- Entities table (canonical names + aliases)
- Relationships table with provenance

**Technology:** SQLite with FTS5 for portability and reproducibility

### Phase 4: Graph Construction

Build NetworkX graph for analysis.

**Formats:**
- GraphML (human-readable, version control friendly)
- Pickle (fast loading)
- JSON (web visualization)

### Phase 5: Query Interfaces

Enable querying via multiple interfaces.

**Interfaces:**
- MCP server (primary - for AI systems)
- Jupyter notebooks (research)
- Command-line tools

## Technology Choices

### Python 3.11+
- Modern type hints
- Good performance
- Excellent ecosystem

### uv for dependency management
- Reproducible builds
- Fast resolution
- Lock file for exact versions

### SQLite
- Portable
- No server required
- Excellent full-text search (FTS5)
- Can be committed to git (with Git LFS)

### NetworkX
- Fits in memory (<10K nodes expected)
- Rich analysis algorithms
- Easy serialization

### ruff for linting
- Fast
- Combines multiple tools
- Good defaults

## Data Flow

```
Raw TXT files
    ↓ (Phase 1: Scanner)
Classification JSON
    ↓ (Phase 2: Extractors)
Structured data (JSON/CSV)
    ↓ (Phase 3: Database builder)
SQLite DB
    ↓ (Phase 4: Graph builder)
NetworkX graph (GraphML/Pickle)
    ↓ (Phase 5: Query layer)
MCP server / Notebooks / CLI
```

## Failure Modes & Mitigations

### OCR Quality Issues
- **Mitigation:** Confidence scoring, manual correction lists, fuzzy matching

### Entity Disambiguation
- **Mitigation:** Aliases table, canonical names, context validation

### Scale
- **Current:** ~3K documents, expect <10K entities
- **If growth:** Can migrate SQLite→Postgres, NetworkX→Neo4j
- **Design:** Abstractions support migration

## Evolution Over Revolution

Start simple:
- Text files → JSON → SQLite → NetworkX
- Only optimize when measured bottleneck
- No premature distributed systems

If scale demands:
- Add Postgres for complex queries
- Add Neo4j for very large graphs
- Add web API if needed

But don't start there.
