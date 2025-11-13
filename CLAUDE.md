# Instructions for Claude Code

This document provides guidance for AI assistants (like Claude Code) working on the unsealed-networks project.

## Project Overview

This is the unsealed-networks project for analyzing public Epstein documents. The goal is to build open-source infrastructure that makes accountability queries trivial.

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

### PEP 8 Compliance

This project follows PEP 8 strictly. Key points:

- **Import ordering**: All imports must be at the top of the file (standard library, third-party, local)
- Ruff enforces PEP 8 automatically via pre-commit hooks
- Run `uv run ruff check src/ tests/` to verify compliance

### File Operations

- Always specify `encoding="utf-8"` when opening text files
- Example: `open(path, "w", encoding="utf-8")`

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
