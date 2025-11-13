# Instructions for Claude Code

This document provides guidance for AI assistants (like Claude Code) working on the unsealed-networks project.

## Project Overview

This is the unsealed-networks project for analyzing public Epstein documents. The goal is to build open-source infrastructure that makes accountability queries trivial.

## Ollama Access

This project uses a local Ollama instance for LLM capabilities (entity extraction, NER, embeddings, etc.). Ollama is running in a Docker container.

### How to Access Ollama

**Via HTTP API:**
```bash
# List available models
curl http://localhost:11434/api/tags

# Generate completion
curl http://localhost:11434/api/generate -d '{
  "model": "qwen2.5:7b",
  "prompt": "Extract all person names from: John met with Jane",
  "stream": false
}'

# Generate embeddings
curl http://localhost:11434/api/embeddings -d '{
  "model": "nomic-embed-text",
  "prompt": "Document text to embed"
}'
```

**Via Docker Exec:**
```bash
# Pull a new model
docker exec -it ollama ollama pull qwen2.5:7b

# List models
docker exec -it ollama ollama list

# Run a model interactively
docker exec -it ollama ollama run qwen2.5:7b
```

### Available Models

The following models are installed for this project:

- **`qwen2.5:7b`** - Primary model for entity extraction, relationship detection, structured output
- **`llama3.1:8b`** - Backup model for entity extraction, good instruction following with native structured output
- **`nomic-embed-text`** - Lightweight embedding model for semantic search and document clustering
- **`deepseek-r1:8b`** - Reasoning model for complex inference tasks

### Using Ollama in Code

Example Python usage with the `ollama` library:

```python
import ollama

# Generate structured output
response = ollama.generate(
    model='qwen2.5:7b',
    prompt='Extract person names as JSON list: John met Jane and Bob',
    format='json'
)

# Generate embeddings
embedding = ollama.embeddings(
    model='nomic-embed-text',
    prompt='Document text'
)
```

See `.env.sample` for Ollama configuration variables.

## Working with Files

### Temporary Files and Scratch Work

When you need to create temporary files during development or analysis (e.g., extracted data, test outputs, experimental results):

- **Always use the `scratch/` folder** for temporary work files
- The `scratch/` folder is gitignored and will not be committed
- Examples of files that belong in `scratch/`:
  - Extracted email lists (e.g., `scratch/emails_peter_thiel.json`)
  - Test query results
  - Experimental data extractions
  - One-off analysis outputs

### Files That Should Be Committed

- Source code in `src/`
- Tests in `tests/`
- Documentation in `docs/`
- Configuration files (`pyproject.toml`, `.gitignore`, etc.)
- README and project docs

### Files That Should Never Be Committed

- Database files (`*.db`)
- Raw source documents (`source_text/**/*.txt`)
- Survey results (`classification_results.json`, `survey_report.json`)
- Anything in `scratch/`

## Code Style

### File Operations

- Always specify `encoding="utf-8"` when opening text files
- Example: `open(path, "w", encoding="utf-8")`

## Python Code Conventions

Follow these principles for writing clean, maintainable Python code:

This project follows PEP 8 strictly. Key points:

- **Import ordering**: All imports must be at the top of the file (standard library, third-party, local)
- Ruff enforces PEP 8 automatically via pre-commit hooks
- Run `uv run ruff check src/ tests/` to verify compliance

**Function Complexity:**
- **Single Responsibility Test:** If you need multiple "and"/"or" words to describe what a function does, it's doing too many things and should be broken down
- **Screen Size Rule:** Functions should generally be viewable in one screen (~40-60 lines)
- **Nested Functions Are Good:** When dealing with lots of context variables, nested functions can access outer scope without needing to pass everything as parameters
- **Break Down Complex Orchestrators:** Functions that orchestrate multiple steps (like parsers, CLI commands, or MCP tools) should delegate to smaller, single-purpose functions
- **Nested Function Naming:** Nested functions should start with an underscore (`_`) to indicate they are internal/private to the parent function

**Example of good decomposition:**
```python
def parse_document(filepath: Path) -> EmailMetadata:
    """Parse email document and extract structured metadata"""

    def _join_header_continuations(lines: list[str]) -> list[str]:
        """Join multi-line header continuations into single lines"""
        # Single clear purpose, ~20 lines

    def _parse_email_address(addr_str: str) -> EmailAddress:
        """Parse a single email address with optional name"""
        # Single clear purpose, ~15 lines

    # Main orchestration logic - simple and clear
    content = filepath.read_text(encoding="utf-8-sig")
    lines = content.split("\n")
    joined_lines = _join_header_continuations(lines)
    metadata = _extract_metadata(joined_lines)
    return metadata
```

**Anti-pattern to avoid:**
```python
def parse_document(filepath: Path):
    """Parse document AND extract metadata AND classify document type
    AND detect threading AND parse body AND extract quotes
    AND validate data AND handle errors AND log everything"""
    # 200 lines of mixed concerns - too complex!
```

## Secrets and Environment Variables

**Never commit sensitive values to git.** This includes:
- API keys for external services (e.g., Ollama endpoints, cloud services)
- Database connection strings with credentials
- Authentication tokens
- Any other secrets or sensitive configuration

**Use .env files for local development:**
1. Store sensitive values in `.env` (gitignored)
2. Create `.env.sample` with placeholder values as documentation
3. Any time a new variable is added to `.env`, add a corresponding placeholder to `.env.sample`

**Example:**
```bash
# .env (gitignored - actual values for your local environment)
DATABASE_PATH=/home/user/data/unsealed_networks.db
OLLAMA_API_URL=http://localhost:11434
OLLAMA_MODEL=deepseek-r1:8b
LOG_LEVEL=INFO

# .env.sample (committed - placeholders)
DATABASE_PATH=/path/to/database.db
OLLAMA_API_URL=http://localhost:11434
OLLAMA_MODEL=your-preferred-model
LOG_LEVEL=INFO
```

**Note:** For this project, most configuration should be explicit arguments to functions/CLIs rather than environment variables. Use `.env` only when truly needed for sensitive values or deployment-specific configuration.

## Entity Extraction Philosophy

**Important principle**: All entities (people, organizations, etc.) we work with should come from the data itself, not be asserted or hardcoded in the code.

- ❌ Bad: Hardcoding a list of names to search for
- ✅ Good: Extracting entities from the documents using NLP/NER

This ensures we discover what's actually in the data rather than only finding what we're looking for.

## Development Workflow

1. Make changes on a feature branch
2. Run tests: `uv run pytest`
3. Run linting: `uv run ruff check src/ tests/`
4. Commit with descriptive messages
5. Push and create PR

## Code Reviews

When receiving code review feedback (e.g., from Gemini Code Assist or other reviewers), **DO NOT blindly implement all suggestions**. Instead, follow this critical evaluation process:

### Step 0: Filter for Unresolved Comments

**IMPORTANT**: When fetching code review comments from GitHub, only consider **unresolved** comments. Resolved comments have already been addressed.

When using the GitHub API to fetch comments:
```bash
# Filter for unresolved comments only
gh api repos/owner/repo/pulls/PR_NUMBER/comments --jq '.[] | select(.resolved != true)'
```

Skip any comments that have been marked as resolved - they represent issues that have already been handled.

### Step 1: Analyze Each Suggestion

For each code review comment, evaluate:

1. **Is this a real problem?**
   - Does it actually cause bugs or incorrect behavior?
   - Is it addressing a genuine edge case we'll encounter?
   - Or is it theoretical/over-engineering?

2. **What's the cost vs benefit?**
   - How much complexity does the fix add?
   - Does it make the code harder to understand?
   - Is the improvement worth the added complexity?

3. **Does it fit our use case?**
   - Is this optimization needed for our specific dataset?
   - Are we solving problems we don't actually have?
   - Does it align with project goals?

### Step 2: Categorize Recommendations

**Must Fix:**
- Security vulnerabilities
- Actual bugs causing incorrect results
- Data loss or corruption issues
- Clear violations of project standards (PEP 8, etc.)

**Should Consider:**
- Performance improvements for known bottlenecks
- Maintainability improvements that reduce complexity
- Handling edge cases we've actually observed in data
- Better error messages for debugging

**Can Ignore:**
- Over-engineering for hypothetical edge cases
- Premature optimization
- Suggestions that add complexity without clear benefit
- Style preferences that conflict with project conventions
- "Best practices" that don't apply to our context

### Step 3: Provide Recommendation

When presenting code review findings to the user, structure your response as:

```
## Code Review Analysis

Found X issues: Y high priority, Z medium priority

### High Priority Issues:
1. **[Issue Title]** (line N)
   - **Problem**: [What's actually wrong]
   - **Recommendation**: [Should we fix? Why/why not?]
   - **Proposed Fix**: [If fixing, how]

2. ...

### Medium Priority Issues:
3. **[Issue Title]** (line N)
   - **Problem**: [What's suggested]
   - **Recommendation**: [Agree/disagree and reasoning]
   - **Alternative**: [If disagreeing, suggest alternative approach]

### Issues to Ignore:
- **[Issue Title]**: [Why we're not addressing this]
```

### Example Evaluation

**❌ Bad Response:**
"Gemini suggested 9 improvements. Let me implement all of them."

**✅ Good Response:**
"Gemini found 9 issues. After analysis:
- **Must fix (4)**: Multi-line header bug causes data loss, date parser fails on RFC 5322 format, party extraction regex too restrictive, quoted text logic is broken
- **Worth fixing (3)**: Magic numbers reduce maintainability, byline patterns too strict for real data
- **Questionable (2)**: Narrative verb expansion is premature - we haven't seen false negatives yet. Suggest waiting for data-driven evidence.

Recommendation: Fix the 7 issues with clear benefit, defer the 2 premature optimizations until we have evidence they're needed."

### Guidelines

**Be skeptical of:**
- Suggestions to handle formats we don't have in our data
- Complex error handling for errors we've never seen
- "Should support X" when X isn't in our requirements
- Refactoring that adds abstraction without clear benefit

**Favor:**
- Fixes for bugs we can demonstrate
- Improvements based on actual data patterns we've observed
- Simplifications that reduce complexity
- Changes that make debugging easier

**Remember:**
- Perfect is the enemy of good
- Code should be as simple as possible, but no simpler
- Solve problems we have, not problems we might have
- Every line of code is a liability that needs to be maintained

## Testing

- Tests are in `tests/`
- Run with `uv run pytest`
- Coverage target: Aim for >80%
- Test databases directly for query logic
- Integration tests for CLI and MCP tools

## Documentation

- Keep `README.md` up to date
- Technical docs go in `docs/technical/`
- Document architecture decisions
- Include examples in docs

## Questions?

See `docs/technical/DEVELOPMENT.md` for more detailed development guidelines.
