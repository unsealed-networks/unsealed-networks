# Phase 2: Document Parsing - Summary

## What Was Built

### Comprehensive Parser System

Built a complete document parsing system with three specialized parsers and an intelligent classifier.

#### 1. Email Parser (`src/unsealed_networks/parsers/email_parser.py`)

**Metadata Extracted:**
- **Headers**: From, To, CC, BCC, Subject, Date, Message-ID, Reply-To
- **Threading**: In-Reply-To, References, Reply/Forward detection
- **Body Structure**: Main content, quoted text (previous messages), signature
- **Email Addresses**: Full parsing with names and addresses separated

**Features:**
- Handles UTF-8 BOM in files
- Parses complex email address formats: "Name <email>", "Name email", "email"
- Detects threading from subjects (Re:, Fwd:) and headers
- Extracts quoted text from thread replies
- Identifies signature blocks

**Performance:** 100% metadata extraction on 55 emails in dataset

#### 2. Legal Document Parser (`src/unsealed_networks/parsers/legal_parser.py`)

**Metadata Extracted:**
- **Case Info**: Case number, Court, District
- **Parties**: Plaintiffs, Defendants
- **Document Info**: Document number, Type (motion, deposition, brief, order, etc.)
- **Filing**: Filing date
- **Attorneys**: Names, firms, roles

**Features:**
- Detects multiple document types (motions, depositions, briefs, orders, complaints)
- Handles "et al" in party names
- Extracts attorney information from signatures
- Cleans body text (removes headers/footers)

**Performance:**
- 63% case number extraction
- 84% document type detection
- 19 legal documents identified

#### 3. News Article Parser (`src/unsealed_networks/parsers/news_parser.py`)

**Metadata Extracted:**
- **Publication**: Name of newspaper/outlet
- **Author**: Byline extraction
- **Article Info**: Headline, Publication date
- **Content**: Body, Summary (first paragraph)
- **Classification**: Article type (editorial, news, profile), Section

**Features:**
- Recognizes major publications (Palm Beach Post, NYT, WSJ, etc.)
- Multiple byline format support
- Date format flexibility
- Body cleaning (removes headers/page markers)

**Performance:**
- 56% publication detection
- 52% date extraction
- 20% author extraction
- 258 news articles identified

#### 4. Document Classifier (`src/unsealed_networks/parsers/classifier.py`)

**Categories:**
- **Email**: Structured email messages
- **Legal**: Court documents, depositions, filings
- **News**: Newspaper articles, editorials
- **Narrative**: Long-form prose, personal accounts
- **Other**: Unclassified documents

**Features:**
- Pattern-based classification
- Confidence scoring (0.0-1.0)
- Subtype detection (court_filing, deposition, article, etc.)
- Fast classification using first 2000 characters

## Dataset Analysis Results

Analyzed all 2,897 documents in 7th production drop:

### Document Type Distribution

| Type | Count | Percentage | Metadata Quality |
|------|-------|------------|------------------|
| **Email** | 55 | 1.9% | **100%** (perfect extraction) |
| **Legal** | 19 | 0.7% | 63-84% (good) |
| **News** | 258 | 8.9% | 20-56% (fair to good) |
| **Narrative** | 45 | 1.6% | N/A (needs parser) |
| **Other** | 2,520 | 87.0% | **Needs investigation** |

### Email Parsing Quality (55 emails)

| Field | Success Rate |
|-------|-------------|
| From address | 100% |
| To address | 100% |
| Subject | 100% |
| Date | 100% |
| Body | 100% |
| Reply detection | 11% have replies |
| Forward detection | 7% are forwards |

### Legal Document Quality (19 docs)

| Field | Success Rate |
|-------|-------------|
| Case number | 63% |
| Court | 63% |
| Document type | 84% |
| Filing date | 47% |
| Parties | 0% (needs improvement) |

### News Article Quality (258 articles)

| Field | Success Rate |
|-------|-------------|
| Publication | 56% |
| Date | 52% |
| Author | 20% |
| Headline | 9% (needs improvement) |

## Key Findings

### ✅ Strengths

1. **Email parsing is excellent** - 100% success rate on all core fields
2. **Classifier works well** for distinct document types
3. **UTF-8 BOM handling** prevents parsing failures
4. **Robust error handling** allows parsing to continue despite malformed data

### ⚠️  Areas for Improvement

1. **87% "Other" documents** - Need to investigate what these are:
   - Possible types: CVs, proposals, transcripts, correspondence, miscellaneous
   - May need additional specialized parsers
   - Some may be poor OCR or corrupted files

2. **Legal document party extraction** - 0% success rate
   - Regex patterns may be too strict
   - Party names span multiple lines
   - Need to study actual document structure more

3. **News headline extraction** - Only 9% success
   - Headlines often formatted differently than expected
   - May need multiple pattern approaches
   - Some articles concatenated without clear headlines

4. **Author extraction** - Only 20% success
   - Byline formats vary widely
   - Staff writers vs columnists have different formats
   - Some articles have no byline

## Technical Achievements

### 1. UTF-8 BOM Handling
- Files start with UTF-8 BOM (`EF BB BF`)
- Using `encoding="utf-8-sig"` automatically strips BOM
- Prevents regex matching failures on first line

### 2. Email Address Parsing
Handles multiple formats:
```
john@example.com                    -> email: john@example.com, name: None
John Doe <john@example.com>         -> email: john@example.com, name: John Doe
John Doe john@example.com           -> email: john@example.com, name: John Doe
```

### 3. Threading Detection
Multiple signals:
- Subject line (Re:, Fwd:)
- In-Reply-To header
- References header
- Quoted text detection (>)

### 4. Multi-Format Date Parsing
- Email format: `10/31/2015 11:24:38 AM`
- Legal format: `MM/DD/YYYY` or `MM/DD/YY`
- News format: `January 15, 2020` or `1/15/2020`

## Next Steps

### 1. Investigate "Other" Documents (Priority: High)

**Action**: Use agent to analyze sample "other" documents and categorize
- Create sub-classifiers for common patterns
- Identify if additional parsers needed
- Document what can't be parsed (corrupted, OCR errors, etc.)

### 2. Improve Legal Parser (Priority: Medium)

**Problems:**
- Party name extraction failing
- Need better multi-line pattern matching

**Action**:
- Study actual legal document samples
- Improve party extraction regex
- Handle edge cases (corporations, vs., et al)

### 3. Improve News Parser (Priority: Medium)

**Problems:**
- Headline extraction low (9%)
- Author extraction low (20%)

**Action**:
- Study article header formats
- Add more headline patterns
- Expand byline recognition

### 4. Build Narrative Parser (Priority: Low)

**Current**: 45 documents classified as narratives
**Need**: Specialized parser to extract:
- Author/subject
- Date ranges
- Key events mentioned
- Person names

### 5. Update Database Schema (Priority: High)

**Current schema** only stores:
- doc_id, filepath, doc_type, confidence, line_count, full_text

**New schema needs**:

```sql
-- Email metadata
CREATE TABLE email_metadata (
    doc_id TEXT PRIMARY KEY,
    from_email TEXT,
    from_name TEXT,
    to_emails TEXT,  -- JSON array
    cc_emails TEXT,   -- JSON array
    subject TEXT,
    date TIMESTAMP,
    is_reply BOOLEAN,
    is_forward BOOLEAN,
    message_id TEXT,
    in_reply_to TEXT,
    body TEXT,
    quoted_text TEXT,  -- JSON array
    signature TEXT,
    FOREIGN KEY (doc_id) REFERENCES documents(doc_id)
);

-- Legal metadata
CREATE TABLE legal_metadata (
    doc_id TEXT PRIMARY KEY,
    case_number TEXT,
    court TEXT,
    district TEXT,
    plaintiffs TEXT,  -- JSON array
    defendants TEXT,  -- JSON array
    document_type TEXT,
    document_number TEXT,
    filing_date DATE,
    attorneys TEXT,  -- JSON array
    FOREIGN KEY (doc_id) REFERENCES documents(doc_id)
);

-- News metadata
CREATE TABLE news_metadata (
    doc_id TEXT PRIMARY KEY,
    publication TEXT,
    author TEXT,
    headline TEXT,
    publication_date DATE,
    section TEXT,
    article_type TEXT,
    summary TEXT,
    FOREIGN KEY (doc_id) REFERENCES documents(doc_id)
);
```

### 6. Build Relationship Graph (Priority: High)

**Now that we have structured data, we can build connections:**

**Email connections:**
- Who emailed whom (From -> To)
- CC relationships
- Thread participants
- Reply chains

**Legal connections:**
- Cases involving multiple parties
- Attorneys representing clients
- Related cases (same attorneys/parties)

**Cross-document connections:**
- People mentioned in multiple documents
- Time-based clustering
- Topic/event grouping

### 7. Entity Extraction from Content (Priority: High)

**Use NLP/NER to extract:**
- All person names from body text
- Organizations
- Locations
- Dates/events

**Tools to consider:**
- spaCy with en_core_web_sm model
- Stanford NER
- Custom entity recognizers

**Philosophy**: Extract entities FROM the data, don't hardcode names to search for.

## File Locations

### Source Code
- `src/unsealed_networks/parsers/classifier.py` - Document type classification
- `src/unsealed_networks/parsers/email_parser.py` - Email parsing
- `src/unsealed_networks/parsers/legal_parser.py` - Legal document parsing
- `src/unsealed_networks/parsers/news_parser.py` - News article parsing

### Test/Analysis Scripts
- `scratch/test_parsers.py` - Unit tests for parsers
- `scratch/analyze_all_parsers.py` - Full dataset analysis
- `scratch/parser_test_results.json` - Test results (20 docs)
- `scratch/full_parser_analysis.json` - Full analysis results (2,897 docs)
- `scratch/analysis_output.txt` - Analysis console output

### Branch
- `feature/email-parser` - All parser work committed here

## Recommendations

1. **Merge parsers to main** after review
2. **Investigate "Other" category** - 87% of documents need classification
3. **Update database schema** to store parsed metadata
4. **Build relationship extraction** using parsed email/legal metadata
5. **Add NLP entity extraction** to find all people/orgs in documents
6. **Create graph database** or NetworkX graph of relationships

## Performance Notes

- **Parsing speed**: ~13 docs/sec (2,897 docs in ~2 minutes)
- **Memory usage**: Minimal (streaming one doc at a time)
- **Accuracy**: Excellent on emails (100%), good on legal (63-84%), fair on news (20-56%)

## Code Quality

- ✅ All parsers pass linting (ruff)
- ✅ UTF-8 BOM handling
- ✅ Error resilient (continue on parse failures)
- ✅ Type hints throughout
- ✅ Comprehensive docstrings
- ✅ Follows PEP 8

Ready for review and next phase!
