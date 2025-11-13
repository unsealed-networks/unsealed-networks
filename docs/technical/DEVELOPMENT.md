# Development Workflow

## Adding New Features

1. **Branch** (if applicable)
   ```bash
   git checkout -b feature/your-feature
   ```

2. **Write tests first**
   - Create test file in `tests/`
   - Run: `uv run pytest tests/test_your_feature.py`

3. **Implement feature**
   - Add code to appropriate module in `src/unsealed_networks/`
   - Follow existing patterns

4. **Verify**
   ```bash
   # Run tests
   uv run pytest

   # Check linting
   uv run ruff check src/ tests/

   # Format code
   uv run ruff format src/ tests/
   ```

5. **Commit**
   - Pre-commit hooks run automatically
   - Commit message format: Brief description of change
   ```bash
   git add .
   git commit -m "Add document scanner for Phase 1 classification"
   ```

6. **Document**
   - Update relevant docs in `docs/technical/`
   - Update README if user-facing change

## Running Commands

All Python tools run via `uv run`:

```bash
# Run the main CLI
uv run unsealed-networks

# Run pytest
uv run pytest

# Run ruff
uv run ruff check src/

# Run pre-commit manually
uv run pre-commit run --all-files

# Run Python scripts directly
uv run python scripts/your_script.py
```

## Adding Dependencies

```bash
# Add runtime dependency
uv add package-name

# Add dev dependency
uv add --dev package-name

# Sync lock file
uv sync
```

## Code Style

- **Line length:** 100 characters
- **Imports:** Sorted by ruff (isort rules)
- **Formatting:** Handled by ruff
- **Type hints:** Use when helpful, not required everywhere
- **Docstrings:** Required for public functions/classes

## Testing

- **Unit tests:** Test individual functions/classes in isolation
- **Integration tests:** Test components working together
- **Coverage target:** Aim for >80%, don't obsess
- **Test data:** Use small fixtures in `tests/fixtures/`

## Documentation

Keep in sync with code:

- **README.md:** User-facing setup and usage
- **docs/technical/ARCHITECTURE.md:** System design and decisions
- **docs/technical/DEVELOPMENT.md:** This file - how to contribute
- **Module docstrings:** What the module does
- **Function docstrings:** For complex or public functions

## Reproducibility Checklist

Before committing data transformations:

- [ ] Document methodology in `docs/technical/`
- [ ] Include source data provenance
- [ ] Script is idempotent (can run multiple times safely)
- [ ] Output format is documented
- [ ] Commit both script and output (if appropriate)

## Pre-commit Hooks

Automatically run on commit:

1. Trailing whitespace removal
2. End-of-file fixer
3. YAML validation
4. Large file check
5. Merge conflict check
6. Private key detection
7. Ruff linting (with auto-fix)
8. Ruff formatting

To skip (use sparingly):
```bash
git commit --no-verify
```

## Common Tasks

### Add a new document type classifier

1. Add patterns to `src/unsealed_networks/survey/scanner.py`
2. Add test cases to `tests/test_scanner.py`
3. Document in `docs/technical/DOCUMENT_TYPES.md`

### Add entity extraction

1. Create extractor in `src/unsealed_networks/extractors/`
2. Add tests in `tests/test_extractors/`
3. Update schema docs

### Update dependencies

```bash
# Update all to latest compatible versions
uv sync --upgrade

# Update specific package
uv add --upgrade package-name

# Commit updated uv.lock
git add uv.lock
git commit -m "Update dependencies"
```

## Debugging

```bash
# Run with verbose output
uv run pytest -vv

# Run with print statements visible
uv run pytest -s

# Drop into debugger on failure
uv run pytest --pdb

# Run specific test
uv run pytest tests/test_file.py::test_function
```

## Performance

- Profile before optimizing
- Use `pytest --durations=10` to find slow tests
- For data processing, prefer pandas/numpy bulk operations over loops

## Git Workflow

We keep it simple:

- Main branch: `main`
- Feature branches optional for complex work
- Commit often, push when ready
- Squash if commit history is messy

## Questions?

Check existing code for patterns. When in doubt, ask.
