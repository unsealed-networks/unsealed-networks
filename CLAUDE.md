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
