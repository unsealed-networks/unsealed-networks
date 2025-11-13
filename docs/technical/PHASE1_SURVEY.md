# Phase 1: Document Survey & Classification

## Overview

The survey phase scans all documents to understand their types before building specialized extractors. This prevents premature optimization and ensures we build the right tools.

## Implementation

### Scanner (`src/unsealed_networks/survey/scanner.py`)

Fast document classifier using regex patterns to identify:
- **Emails** (79.7% of documents) - Structured From/To/Subject headers
- **Narratives** (20.1%) - Long-form article/journalism text
- **HTML emails** (0.2%) - Newsletter/marketing with markup
- **Unknown** (0.0%) - Unclassified

### CLI (`src/unsealed_networks/cli.py`)

Three commands built with typer:

```bash
# Scan all documents
uv run unsealed-networks survey source_text/7th_production/TEXT/

# List emails with filters
uv run unsealed-networks list-emails classification_results.json
uv run unsealed-networks list-emails classification_results.json --entity "Peter Thiel"

# View statistics
uv run unsealed-networks stats survey_report.json
```

## Results from 7th Production Drop

**Documents scanned:** 2,897
**Total size:** 53.8 MB

**Document types:**
- Emails: 2,309 (79.7%)
- Narratives: 581 (20.1%)
- HTML emails: 6 (0.2%)
- Unknown: 1 (0.0%)

**Entity mentions:**
- Donald Trump: 2,001
- Jeffrey Epstein: 1,098
- Bill Clinton: 342
- Michael Wolff: 192 (journalist, "Fire and Fury" author)
- Ghislaine Maxwell: 164
- Landon Thomas: 149 (NY Times reporter)
- Bill Gates: 53
- **Peter Thiel: 33**
- Elon Musk: 25

## Peter Thiel Documents

**23 emails** mentioning Peter Thiel with confidence ≥0.7:

Key document IDs:
- `HOUSE_OVERSIGHT_032827` - Direct email exchange between Thiel and Epstein
- `HOUSE_OVERSIGHT_022894` - Vanity Fair article detailing lunch with Gates, Thiel, Zuckerman discussing Gates Foundation donor fund
- `HOUSE_OVERSIGHT_013484`, `017574`, `017581` - Thiel + Epstein + Michael Wolff (Trump book research)
- `HOUSE_OVERSIGHT_025875-028784` - Thiel + Gates + Clinton cluster
- `HOUSE_OVERSIGHT_026661-033306` - Thiel + Trump cluster (10+ docs)

Saved to: `emails_peter_thiel.json`

## Classification Methodology

### Email Detection
Pattern matching on headers:
- `From:` line
- `To:` line
- `Subject:` line
- `Sent: M/D/YYYY H:MM:SS` timestamp
- Epstein's email: `jeevacation@gmail.com`

Score: 5/5 patterns = 1.00 confidence

### Entity Extraction
Simple regex patterns for seed entities:
- `\bPeter\s+Thiel\b`
- `\b(?:Donald\s+)?Trump\b`
- etc.

**Limitations:**
- Name variations not caught (e.g., "Pete Thiel")
- No disambiguation (different people with same name)
- Context-free (can't distinguish mentions from participation)

**Future Philosophy:**

> **Important principle:** In future phases, all entities (people, organizations, etc.) should be extracted from the data itself using NLP/NER techniques, not hardcoded or asserted in the code.

The current regex-based seed entity list was necessary for the Phase 1 survey to quickly validate the project's viability. However, this approach has significant limitations:
- We only find what we're looking for (confirmation bias risk)
- Miss variations, nicknames, and titles
- Limited to predefined list of names

**Phase 2+ approach:** Use Named Entity Recognition (NER) from NLP libraries (spaCy, etc.) to discover all entities mentioned in the documents. This ensures we:
- Discover what's actually in the data
- Find unexpected relationships
- Avoid confirmation bias
- Capture all name variations automatically

This "discover, don't assert" principle applies to all future data modeling decisions.

### Confidence Scoring
- ≥0.7 = High confidence (used for filtering)
- 0.3-0.7 = Medium confidence
- <0.3 = Unknown/low confidence

## Next Steps

**Phase 2: Email Extractor**
- Build structured email parser
- Extract From/To/Subject/Date with confidence scores
- Handle threading/conversations
- Extract body text vs. legal footer
- Build test suite on Thiel emails

**Phase 3: Relationship Extraction**
- Who emailed whom (direct communication = high confidence)
- CC/BCC relationships
- Who was mentioned in whose emails (context-dependent)
- Meeting attendance (from email content)

## Files Generated

All outputs are gitignored (data files):
- `survey_report.json` - Aggregate statistics
- `classification_results.json` - Per-document classifications (2,897 records)
- `emails_peter_thiel.json` - Filtered Thiel emails (23 records)

## Testing

Tests in `tests/test_scanner.py`:
- Email classification
- Narrative classification
- Entity extraction
- Batch scanning
- Email filtering
- Document ID extraction

All tests pass with 86% coverage of scanner module.

## Performance

- **Speed:** ~200 docs/second on commodity hardware
- **Memory:** Processes one file at a time, minimal memory footprint
- **Scalability:** Linear O(n) with document count

For 10K documents: ~50 seconds total runtime.
