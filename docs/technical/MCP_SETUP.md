# MCP Server Setup

## Overview

The Unsealed Networks MCP server provides AI systems (like Claude) with tools to search and retrieve Epstein documents with full-text search capabilities.

## Quick Start

### 1. Build the Database

```bash
# Load documents into SQLite (only need to do once)
uv run unsealed-networks load-db classification_results.json source_text/7th_production/TEXT/
```

This creates `data/unsealed.db` (~80MB) with:
- 2,897 documents with full text
- FTS5 full-text search index
- Entity mention tracking

### 2. Test the MCP Server

```bash
# The MCP server runs as a stdio server
uv run unsealed-networks-mcp --db data/unsealed.db
```

### 3. Configure Claude Desktop

Add to your Claude Desktop config file:

**macOS:** `~/Library/Application Support/Claude/claude_desktop_config.json`
**Linux:** `~/.config/Claude/claude_desktop_config.json`

```json
{
  "mcpServers": {
    "unsealed-networks": {
      "command": "uv",
      "args": [
        "run",
        "--directory",
        "/path/to/unsealed-networks",
        "unsealed-networks-mcp"
      ],
      "env": {}
    }
  }
}
```

**Important:** Update the `--directory` path to match your installation location.

### 4. Restart Claude Desktop

The MCP server will start automatically when Claude Desktop launches.

## Available Tools

### search_documents

Full-text search across all documents using SQLite FTS5.

**Example queries:**
- `"Peter Thiel"` - Find mentions of Peter Thiel
- `"Trump AND Epstein"` - Documents mentioning both
- `"donor advised fund"` - Exact phrase search
- `Gates OR Clinton` - Either entity

**Parameters:**
- `query` (required): Search string
- `limit` (optional): Max results (default 10, max 50)

### get_document

Retrieve full text of a specific document.

**Parameters:**
- `doc_id` (required): e.g., "HOUSE_OVERSIGHT_032827"

### find_by_entity

Find all documents mentioning a tracked entity.

**Tracked entities:**
- Peter Thiel
- Elon Musk
- Bill Gates
- Donald Trump
- Bill Clinton
- Jeffrey Epstein
- Ghislaine Maxwell
- Michael Wolff
- Landon Thomas

**Parameters:**
- `entity` (required): Entity name
- `limit` (optional): Max results (default 20, max 100)

### list_entities

List all tracked entities with document counts.

### get_document_stats

Get database statistics (document counts, types, top entities).

## Usage Examples

Once configured in Claude Desktop, you can ask:

**Simple search:**
> "What documents mention Peter Thiel?"

**Complex queries:**
> "Find emails from 2017 about Trump"
> "Show me documents mentioning both Gates and Thiel"

**Document retrieval:**
> "Get the full text of HOUSE_OVERSIGHT_032827"

**Entity exploration:**
> "How many documents mention each person?"
> "List all documents mentioning Bill Gates"

## Database Schema

```sql
-- Main documents table
CREATE TABLE documents (
    doc_id TEXT PRIMARY KEY,
    filepath TEXT NOT NULL,
    doc_type TEXT NOT NULL,        -- email, narrative, html_email
    confidence REAL NOT NULL,       -- 0.0 - 1.0
    line_count INTEGER NOT NULL,
    full_text TEXT NOT NULL
);

-- FTS5 virtual table
CREATE VIRTUAL TABLE documents_fts USING fts5(
    doc_id UNINDEXED,
    full_text,
    content='documents'
);

-- Entity mentions
CREATE TABLE entity_mentions (
    doc_id TEXT NOT NULL,
    entity_name TEXT NOT NULL,
    PRIMARY KEY (doc_id, entity_name)
);
```

## Performance

- **Search:** ~10-50ms for typical queries
- **Document retrieval:** ~5ms
- **Entity lookup:** ~10ms
- **Database size:** 80MB (2,897 documents)

## Troubleshooting

### "Database not found" error

Make sure you've loaded the database:
```bash
uv run unsealed-networks load-db classification_results.json source_text/7th_production/TEXT/
```

### MCP server not showing in Claude Desktop

1. Check the config file path is correct
2. Verify the `--directory` path in config
3. Restart Claude Desktop completely
4. Check Claude Desktop logs for errors

### Search returns no results

- FTS5 is case-insensitive but requires exact word matches
- Use quotes for phrases: `"donor advised fund"`
- Use AND/OR for boolean queries: `Trump AND Epstein`
- Check spelling of entity names

## Updating the Database

When new document drops arrive:

1. Run survey: `uv run unsealed-networks survey source_text/8th_production/TEXT/`
2. Reload database: `uv run unsealed-networks load-db classification_results.json source_text/`
3. MCP server automatically uses updated database

No need to restart Claude Desktop - it reconnects automatically.
