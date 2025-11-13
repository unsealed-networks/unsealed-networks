# Unsealed Networks - Project Checklist

**Last Updated:** 2025-01-13

---

## Phase 0: Project Setup
- [x] Initialize project structure with uv
- [x] Configure pre-commit hooks (ruff linting)
- [x] Set up test framework (pytest)
- [x] Add development documentation
- [x] Configure Docker build
- [x] Publish Docker image to Docker Hub

---

## Phase 1: Document Survey & Classification

### Core Implementation
- [x] Build document scanner (`survey/scanner.py`)
- [x] Implement CLI commands (survey, list-emails, stats)
- [x] Write tests for scanner (86% coverage)
- [x] Scan 2,897 documents from 7th production drop

### Results
- [x] Classify documents into initial types (email/narrative/HTML)
- [x] Track entity mentions (Trump, Epstein, Thiel, etc.)
- [x] Extract 23 Peter Thiel emails
- [x] Generate survey statistics

### Database Setup
- [x] Design SQLite schema with FTS5
- [x] Build database loader
- [x] Load all 2,897 documents (80MB database)
- [x] Implement entity tracking table

### MCP Server (Initial)
- [x] Build stdio MCP server
- [x] Implement 5 core tools:
  - [x] search_documents (full-text search)
  - [x] get_document (retrieve by doc_id)
  - [x] find_by_entity (entity-based search)
  - [x] list_entities (show all tracked entities)
  - [x] get_document_stats (database statistics)
- [x] Write MCP server tests
- [x] Document Claude Desktop setup
- [x] Test end-to-end with Claude Desktop

### Documentation
- [x] Write PHASE1_SURVEY.md
- [x] Write TONIGHT.md (scrappy MCP server summary)
- [x] Write MCP_SETUP.md
- [x] Update README.md

---

## Phase 2: Document Parsing

### Parser Infrastructure
- [x] Build document classifier (`parsers/classifier.py`)
  - [x] Email detection (95% confidence)
  - [x] Legal document detection (confidence scoring)
  - [x] News article detection (85% confidence)
  - [x] Narrative detection (70% confidence)
  - [x] "Other" category handling

### Email Parser
- [x] Build EmailParser (`parsers/email_parser.py`)
- [x] Extract email headers (From, To, CC, BCC, Subject, Date)
- [x] Parse email addresses with names
- [x] Handle multi-line header continuation
- [x] Implement RFC 5322 date parsing with fallback
- [x] Detect threading (Re:, Fwd:, In-Reply-To, References)
- [x] Extract quoted text from replies
- [x] Identify signature blocks
- [x] Handle UTF-8 BOM encoding
- [x] Return None for invalid email addresses
- [x] Test on dataset: 100% success rate (55 emails)

### Legal Parser
- [x] Build LegalDocumentParser (`parsers/legal_parser.py`)
- [x] Extract case numbers (63% success)
- [x] Extract court information (63% success)
- [x] Detect document types (84% success)
  - [x] Motions
  - [x] Depositions
  - [x] Briefs
  - [x] Orders
  - [x] Complaints
- [x] Extract filing dates (47% success)
- [x] Extract party names (plaintiffs/defendants)
  - [x] Fix multi-line party name matching (re.DOTALL)
- [x] Extract attorney information
- [x] Extract configuration constants for maintainability

### News Parser
- [x] Build NewsArticleParser (`parsers/news_parser.py`)
- [x] Detect publications (56% success)
- [x] Extract publication dates (52% success)
- [x] Extract author/byline (20% success)
  - [x] Support middle initials, hyphens, apostrophes
- [x] Extract headlines (9% success)
  - [x] Support Title Case and all-caps formats
- [x] Identify article sections (opinion, news, business)
- [x] Classify article types (editorial, news, profile)
- [x] Extract body and summary (first paragraph)
- [x] Extract configuration constants for maintainability

### Analysis & Testing
- [x] Analyze full dataset (2,897 documents)
- [x] Generate performance metrics per parser
- [x] Identify improvement areas
- [x] Test parsers on sample documents
- [x] Run full dataset analysis

### Code Quality
- [x] All parsers pass ruff linting
- [x] UTF-8 BOM handling throughout
- [x] Error resilient parsing
- [x] Type hints on all functions
- [x] Comprehensive docstrings
- [x] PEP 8 compliance
- [x] Configuration constants (no magic numbers)

### Documentation
- [x] Write PHASE2_PARSING.md
- [x] Document parser performance metrics
- [x] Identify next steps for Phase 3
- [x] Update CLAUDE.md with:
  - [x] Ollama access documentation
  - [x] Code review guidelines
  - [x] Python conventions
  - [x] Filter for unresolved review comments

### PR & Review
- [x] Create feature branch (feature/email-parser)
- [x] Address code review feedback
  - [x] Add configuration constants to all parsers
  - [x] Fix email address parsing (return None for invalid)
  - [x] Add re.DOTALL to legal PARTIES_PATTERN
  - [x] Skip SQL table normalization (defer to graph)
- [x] Run all tests (11/11 passing)
- [ ] Merge PR to main **(PENDING MERGE)**

---

## Phase 3: Entity Extraction & "Other" Documents Investigation

### LLM-Assisted Classification (High Priority)
- [ ] Set up Ollama integration
  - [x] Install qwen2.5:7b model (4.7 GB)
  - [x] Install llama3.1:8b model (4.9 GB)
  - [x] Install nomic-embed-text model (274 MB)
  - [x] Verify deepseek-r1:8b available
  - [ ] Create Ollama client wrapper
- [ ] Classify "Other" documents (2,520 docs, 87%)
  - [ ] Send first ~500 words to LLM for classification
  - [ ] Build histogram of discovered document types
  - [ ] Identify categories:
    - [ ] CVs/Resumes
    - [ ] Transcripts
    - [ ] Letters/Correspondence
    - [ ] Proposals
    - [ ] Corrupted/OCR errors
    - [ ] Other types
- [ ] Create specialized parsers for common types
- [ ] Document unprocessable documents

### Entity Extraction with NLP/NER
- [ ] Choose NER approach:
  - [ ] Option A: spaCy with en_core_web_sm
  - [ ] Option B: Stanford NER
  - [ ] Option C: Local LLM (qwen2.5:7b or llama3.1:8b)
  - [ ] Option D: Hybrid (regex + NLP validation)
- [ ] Extract entities from all documents:
  - [ ] Person names
  - [ ] Organizations
  - [ ] Locations
  - [ ] Dates/events
- [ ] Build entity resolution (handle name variations)
- [ ] Store entities in database
- [ ] Create entity relationship tables

### Parser Improvements
- [ ] Improve legal parser party extraction
  - [x] Add re.DOTALL flag for multi-line matching
  - [ ] Test improved party extraction on dataset
  - [ ] Handle corporate names (with &, Inc., etc.)
  - [ ] Multi-step party extraction approach
- [ ] Improve news parser
  - [ ] Add more headline patterns
  - [ ] Expand author/byline recognition
  - [ ] Test on difficult articles
- [ ] Build narrative parser
  - [ ] Extract author/subject
  - [ ] Identify date ranges
  - [ ] Extract key events mentioned
  - [ ] Extract person names

### LLM Fallback for Failed Extractions (Optional)
- [ ] Implement hybrid approach:
  - [ ] Try regex first (fast)
  - [ ] Fall back to LLM if regex fails
- [ ] Use for:
  - [ ] Legal party extraction (currently 0%)
  - [ ] News headlines (currently 9%)
  - [ ] News authors (currently 20%)
- [ ] Measure performance improvement
- [ ] Document LLM usage and costs

---

## Phase 4: Database Schema Update & Relationship Storage

### Schema Design
- [ ] Design metadata tables:
  - [ ] email_metadata table
  - [ ] legal_metadata table
  - [ ] news_metadata table
  - [ ] narrative_metadata table (if applicable)
  - [ ] entity_mentions table
  - [ ] Skip separate email_recipients table (use JSON, defer to graph)
- [ ] Design relationship tables:
  - [ ] email_participants (from/to/cc)
  - [ ] email_threads (conversation chains)
  - [ ] legal_parties (case relationships)
  - [ ] cross_document_entities (people appearing in multiple docs)
- [ ] Add database migration support

### Database Update
- [ ] Write migration script
- [ ] Re-parse all documents with updated parsers
- [ ] Populate metadata tables
- [ ] Build relationship records
- [ ] Verify data integrity
- [ ] Update database size/performance metrics

### Indexing & Performance
- [ ] Add indexes on:
  - [ ] doc_id foreign keys
  - [ ] email addresses
  - [ ] entity names
  - [ ] dates
- [ ] Optimize FTS5 queries
- [ ] Benchmark query performance

---

## Phase 5: Relationship Graph Construction

### Graph Design
- [ ] Choose graph approach:
  - [ ] Option A: NetworkX (in-memory, Python)
  - [ ] Option B: Neo4j (dedicated graph database)
  - [ ] Option C: Hybrid (NetworkX + SQLite storage)
- [ ] Define node types:
  - [ ] People
  - [ ] Organizations
  - [ ] Documents
  - [ ] Events
- [ ] Define relationship types:
  - [ ] EMAIL_SENT (from → to)
  - [ ] EMAIL_CC (document → person)
  - [ ] MENTIONED_IN (person → document)
  - [ ] PARTY_TO (person → legal_case)
  - [ ] REPRESENTED_BY (party → attorney)
  - [ ] THREAD_PARTICIPANT (person → email_thread)

### Graph Construction
- [ ] Build graph from database
  - [ ] Load email relationships
  - [ ] Load legal case relationships
  - [ ] Load entity mentions
  - [ ] Load cross-document relationships
- [ ] Add confidence scoring to edges
- [ ] Implement graph queries:
  - [ ] Find all connections between two people
  - [ ] Find shortest path between entities
  - [ ] Identify central figures (degree centrality)
  - [ ] Find communities/clusters
  - [ ] Temporal analysis (relationships over time)
- [ ] Export graph formats (GraphML, JSON, etc.)

### Visualization
- [ ] Choose visualization tool:
  - [ ] Option A: NetworkX + Matplotlib
  - [ ] Option B: Cytoscape
  - [ ] Option C: D3.js web interface
  - [ ] Option D: Gephi export
- [ ] Create basic visualizations:
  - [ ] Full relationship network
  - [ ] Ego networks (single person + connections)
  - [ ] Subgraphs (specific topics/timeframes)
- [ ] Add interactive features:
  - [ ] Node filtering
  - [ ] Edge filtering
  - [ ] Zoom/pan
  - [ ] Node details on hover

---

## Phase 6: Enhanced MCP Tools

### New Graph Query Tools
- [ ] find_connections (path between two entities)
- [ ] get_ego_network (person's direct connections)
- [ ] find_communities (identify groups/clusters)
- [ ] temporal_analysis (relationships over time)
- [ ] central_figures (most connected people)

### Enhanced Search Tools
- [ ] Advanced filters:
  - [ ] Date ranges
  - [ ] Document types
  - [ ] Confidence thresholds
  - [ ] Relationship types
- [ ] Faceted search
- [ ] Relevance scoring
- [ ] Search result aggregation

### Analysis Tools
- [ ] get_timeline (events for a person/entity)
- [ ] compare_entities (overlap analysis)
- [ ] get_document_context (related documents)
- [ ] extract_relationships (structured relationship output)

### Testing & Documentation
- [ ] Write tests for new tools
- [ ] Update MCP_SETUP.md
- [ ] Create usage examples
- [ ] Document query patterns

---

## Phase 7: Additional Data & Scaling

### Data Expansion
- [ ] Load remaining production drops (when available)
- [ ] Implement incremental database updates
- [ ] Add historical tracking
- [ ] Handle document updates/corrections

### Performance Optimization
- [ ] Profile query performance at scale
- [ ] Optimize slow queries
- [ ] Consider database partitioning
- [ ] Add caching layer if needed

### Data Quality
- [ ] Implement data validation
- [ ] Add duplicate detection
- [ ] Create data quality reports
- [ ] Build correction/annotation system

---

## Phase 8: Embedding-Based Features (Optional)

### Document Embeddings
- [ ] Generate embeddings with nomic-embed-text
- [ ] Store embeddings in database
- [ ] Build similarity search
- [ ] Create document clusters
- [ ] Identify similar documents

### Entity Embeddings
- [ ] Generate entity embeddings from context
- [ ] Build entity similarity search
- [ ] Create entity disambiguation

### Applications
- [ ] "Find similar documents" tool
- [ ] Topic modeling/clustering
- [ ] Anomaly detection
- [ ] Pattern discovery

---

## Deployment & Distribution

### Docker
- [x] Create Dockerfile
- [x] Build Docker image
- [x] Publish to Docker Hub
- [x] Document Docker usage
- [ ] Create docker-compose for development
- [ ] Add Docker health checks

### Documentation
- [x] Write comprehensive README
- [x] Add installation guide
- [x] Document MCP setup
- [x] Create development guide
- [ ] Write API documentation
- [ ] Add troubleshooting guide
- [ ] Create contribution guidelines

### Testing & CI/CD
- [x] Unit tests (11 tests, 86% scanner coverage)
- [ ] Integration tests
- [ ] End-to-end tests
- [x] GitHub Actions CI (runs tests + linting)
- [ ] Automated Docker builds
- [ ] Release process

### Community
- [ ] Choose license
- [ ] Create contribution guidelines
- [ ] Set up issue templates
- [ ] Add PR template
- [ ] Create roadmap
- [ ] Build community docs

---

## Current Status: Phase 2 Complete, Pending Merge

**Branch:** `feature/email-parser`

**Recent Work:**
- ✅ Built 3 specialized parsers (email, legal, news)
- ✅ Built document classifier
- ✅ Analyzed full dataset (2,897 documents)
- ✅ Addressed code review feedback
- ✅ Added Ollama documentation and installed recommended models
- ✅ Fixed legal parser for multi-line party names
- ✅ Updated code review guidelines in CLAUDE.md

**Next Immediate Steps:**
1. Merge Phase 2 PR to main
2. Begin Phase 3: LLM-assisted classification of "Other" documents
3. Implement entity extraction with NER/LLM
4. Update database schema for parsed metadata

---

## Notes

- **Philosophy:** "Discover, don't assert" - Extract entities from data, don't hardcode searches
- **Quality over perfection:** Working system > perfect system that doesn't exist
- **Iterative development:** Build, test, iterate based on actual usage
- **Open source:** Build infrastructure that enables accountability queries for everyone
