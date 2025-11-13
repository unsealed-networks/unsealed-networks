# Installation Guide

This guide covers installation on Linux, macOS, Windows (WSL2), and Docker.

## Prerequisites

All platforms require:
- Python 3.11 or higher
- [uv](https://docs.astral.sh/uv/) package manager

## Platform-Specific Installation

### Linux (Native)

```bash
# Install uv
curl -LsSf https://astral.sh/uv/install.sh | sh

# Clone repository
git clone https://github.com/unsealed-networks/unsealed-networks.git
cd unsealed-networks

# Install dependencies
uv sync --extra dev

# Install pre-commit hooks (optional, for development)
uv run pre-commit install
```

**Claude Desktop Configuration:**

File: `~/.config/Claude/claude_desktop_config.json`

```json
{
  "mcpServers": {
    "unsealed-networks": {
      "command": "bash",
      "args": [
        "-c",
        "cd /path/to/unsealed-networks && uv run unsealed-networks-mcp"
      ],
      "env": {}
    }
  }
}
```

---

### macOS

```bash
# Install uv
curl -LsSf https://astral.sh/uv/install.sh | sh

# Clone repository
git clone https://github.com/unsealed-networks/unsealed-networks.git
cd unsealed-networks

# Install dependencies
uv sync --extra dev

# Install pre-commit hooks (optional, for development)
uv run pre-commit install
```

**Claude Desktop Configuration:**

File: `~/Library/Application Support/Claude/claude_desktop_config.json`

```json
{
  "mcpServers": {
    "unsealed-networks": {
      "command": "bash",
      "args": [
        "-c",
        "cd /path/to/unsealed-networks && uv run unsealed-networks-mcp"
      ],
      "env": {}
    }
  }
}
```

---

### Windows with WSL2 (Recommended)

**In WSL2 (Ubuntu/Debian):**

```bash
# Install uv
curl -LsSf https://astral.sh/uv/install.sh | sh

# Clone repository
git clone https://github.com/unsealed-networks/unsealed-networks.git
cd unsealed-networks

# Install dependencies
uv sync
```

**Claude Desktop Configuration (Windows):**

File: `%APPDATA%\Claude\claude_desktop_config.json`

```json
{
  "mcpServers": {
    "unsealed-networks": {
      "command": "wsl",
      "args": [
        "bash",
        "-c",
        "cd ~/unsealed-networks && ~/.local/bin/uv run unsealed-networks-mcp"
      ],
      "env": {}
    }
  }
}
```

**PowerShell Quick Setup:**

```powershell
# Create config directory
mkdir -Force "$env:APPDATA\Claude"

# Create config file
@'
{
  "mcpServers": {
    "unsealed-networks": {
      "command": "wsl",
      "args": [
        "bash",
        "-c",
        "cd ~/unsealed-networks && ~/.local/bin/uv run unsealed-networks-mcp"
      ],
      "env": {}
    }
  }
}
'@ | Out-File -FilePath "$env:APPDATA\Claude\claude_desktop_config.json" -Encoding UTF8
```

---

### Docker (All Platforms)

The Docker image includes the complete database (2,897 documents, ~80MB) so you can run it immediately without any setup.

**Quick Start - Pull from Docker Hub:**

```bash
# Pull pre-built image (recommended)
docker pull devonsjones/unsealed-networks:latest

# Run with stdio (for Claude Desktop)
docker run -i --rm devonsjones/unsealed-networks:latest stdio
```

**Or Build Locally:**

```bash
# From the project root
docker build -t unsealed-networks .

# Run with stdio
docker run -i --rm unsealed-networks stdio
```

**Image size:** 355MB (includes Python 3.11, dependencies, and full database)

**Claude Desktop Configuration (Docker stdio):**

```json
{
  "mcpServers": {
    "unsealed-networks": {
      "command": "docker",
      "args": [
        "run",
        "-i",
        "--rm",
        "devonsjones/unsealed-networks:latest",
        "stdio"
      ],
      "env": {}
    }
  }
}
```

**Run as HTTP/SSE server:**

```bash
docker run -d \
  -p 8765:8765 \
  --name unsealed-networks \
  devonsjones/unsealed-networks:latest sse
```

**Using a Custom Database (Optional):**

If you want to use a different database, mount it as a volume:

```bash
docker run -i --rm \
  -v $(pwd)/data:/data:ro \
  -e DB_PATH=/data/unsealed.db \
  devonsjones/unsealed-networks:latest stdio
```

**Docker Compose:**

Create `docker-compose.yml`:

```yaml
version: '3.8'

services:
  unsealed-networks:
    image: devonsjones/unsealed-networks:latest
    container_name: unsealed-networks-mcp
    ports:
      - "8765:8765"
    command: sse
    restart: unless-stopped
```

Run:
```bash
docker-compose up -d
```

---

## Loading the Database

Before using the MCP server, you need to load documents into the database.

### 1. Survey Documents

```bash
uv run unsealed-networks survey <path-to-text-files>/
```

Example:
```bash
uv run unsealed-networks survey source_text/7th_production/TEXT/
```

This creates:
- `survey_report.json` - Statistics
- `classification_results.json` - Per-document metadata

### 2. Load Database

```bash
uv run unsealed-networks load-db classification_results.json <path-to-text-files>/
```

Example:
```bash
uv run unsealed-networks load-db \
  classification_results.json \
  source_text/7th_production/TEXT/
```

This creates `data/unsealed.db` (~80MB for 2,897 documents).

### 3. Verify Database

```bash
sqlite3 data/unsealed.db "SELECT COUNT(*) FROM documents"
```

Should show: `2897` (or your document count)

---

## Verifying Installation

### Test CLI Tools

```bash
# Show help
uv run unsealed-networks --help

# List available commands
uv run unsealed-networks survey --help
uv run unsealed-networks list-emails --help
uv run unsealed-networks stats --help
```

### Test MCP Server Locally

```bash
# Run MCP server (stdio)
uv run unsealed-networks-mcp --help

# Test with echo
echo '{"jsonrpc":"2.0","id":1,"method":"initialize","params":{"protocolVersion":"2024-11-05","capabilities":{},"clientInfo":{"name":"test","version":"1.0"}}}' | \
  uv run unsealed-networks-mcp
```

Should return a JSON response with server info.

### Test Docker

```bash
# Build
docker build -t unsealed-networks .

# Test stdio
echo '{"jsonrpc":"2.0","id":1,"method":"initialize","params":{"protocolVersion":"2024-11-05","capabilities":{},"clientInfo":{"name":"test","version":"1.0"}}}' | \
  docker run -i --rm -v $(pwd)/data:/data:ro unsealed-networks stdio
```

---

## Using with Claude Desktop

1. **Configure** using the platform-specific config above
2. **Restart Claude Desktop** completely (exit from system tray)
3. **Verify tools loaded** - Ask: "What tools do you have available?"
4. **Test query** - Ask: "What documents mention Peter Thiel?"

---

## Troubleshooting

### Database not found

**Error:** `Database not found at data/unsealed.db`

**Solution:** Run the survey and load-db commands first.

### Command not found: uv

**Linux/macOS:**
```bash
# Add to PATH
echo 'export PATH="$HOME/.local/bin:$PATH"' >> ~/.bashrc
source ~/.bashrc
```

**WSL2:**
```bash
# Add to PATH
echo 'export PATH="$HOME/.local/bin:$PATH"' >> ~/.bashrc
source ~/.bashrc
```

### Claude Desktop: Server disconnected

**Check logs:**
- Linux: `~/.config/Claude/logs/`
- macOS: `~/Library/Logs/Claude/`
- Windows: `%APPDATA%\Claude\logs\`

**Common fixes:**
- Ensure absolute paths in config
- Verify server runs manually first
- Check database exists at specified path

### WSL2: wsl command not found

**Windows:**
- Ensure WSL2 is installed: `wsl --status`
- Install: `wsl --install`

### Docker: Permission denied

```bash
# Add user to docker group (Linux)
sudo usermod -aG docker $USER
newgrp docker
```

---

## Performance

**Expected performance (2,897 documents, 80MB database):**
- Search query: 10-50ms
- Document retrieval: 5ms
- Entity lookup: 10ms
- Database load time: ~2 seconds

**Memory usage:**
- MCP server: ~60MB
- Database: 80MB on disk
- Total: ~150MB RAM

---

## Development Setup

For development with linting and testing:

```bash
# Install with dev dependencies
uv sync --extra dev

# Install pre-commit hooks
uv run pre-commit install

# Run tests
uv run pytest

# Run linting
uv run ruff check src/ tests/

# Format code
uv run ruff format src/ tests/
```

---

## Security Notes

- Database is read-only for MCP server
- No data modification via MCP tools
- Source documents are public records
- Runs locally - no external API calls

---

## Next Steps

After installation:
1. Review `docs/technical/MCP_SETUP.md` for query examples
2. See `docs/technical/PHASE1_SURVEY.md` for methodology
3. Check `TONIGHT.md` for what's been built
4. Read `docs/technical/ARCHITECTURE.md` for system design
