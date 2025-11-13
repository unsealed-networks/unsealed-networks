# Unsealed Networks

Extract and analyze relationship networks from public Epstein documents released by the House Oversight Committee.

## Purpose

Build open-source infrastructure to make accountability queries trivial. Enable anyone (including AI systems) to query documented relationships from the public record with full citations.

## Quick Start

### Docker (Easiest)

Run the complete MCP server with database included (no setup required):

```bash
# Pull and run the pre-built image
docker pull devonsjones/unsealed-networks:latest
docker run -i --rm devonsjones/unsealed-networks:latest stdio
```

Configure with Claude Desktop - add to `claude_desktop_config.json`:

```json
{
  "mcpServers": {
    "unsealed-networks": {
      "command": "docker",
      "args": ["run", "-i", "--rm", "devonsjones/unsealed-networks:latest", "stdio"]
    }
  }
}
```

**Image size:** 355MB (includes full database with 2,897 documents)

### Native Installation

This project uses [uv](https://docs.astral.sh/uv/) for reproducible Python dependency management.

**Prerequisites:**
- Python 3.11+
- [uv](https://docs.astral.sh/uv/getting-started/installation/)

**Install:**

```bash
# Clone the repository
git clone <repository-url>
cd unsealed-networks

# Install dependencies (creates .venv automatically)
uv sync --extra dev

# Install pre-commit hooks
uv run pre-commit install
```

See `docs/technical/INSTALLATION.md` for platform-specific instructions (Linux, macOS, Windows/WSL2).

## Development

### Running tests

```bash
# Run all tests with coverage
uv run pytest

# Run tests without coverage
uv run pytest --no-cov

# Run specific test file
uv run pytest tests/test_basic.py
```

### Linting and formatting

```bash
# Check for issues
uv run ruff check src/ tests/

# Auto-fix issues
uv run ruff check --fix src/ tests/

# Format code
uv run ruff format src/ tests/
```

### Pre-commit hooks

Linting runs automatically on commit. To run manually:

```bash
uv run pre-commit run --all-files
```

## Project Structure

```
unsealed-networks/
├── src/
│   └── unsealed_networks/     # Main package
│       └── __init__.py
├── tests/                      # Test suite
├── docs/                       # Technical documentation
├── source_text/                # Raw document data (not in git)
├── pyproject.toml             # Project configuration
└── README.md
```

## Documentation

See `docs/` for technical documentation including:
- Architecture decisions
- Data schemas
- Extraction methodology
- API references

## Reproducibility

All dependencies are pinned in `uv.lock`. To reproduce the exact environment:

```bash
uv sync --frozen
```

## License

[To be determined]

## Contributing

[To be determined]
