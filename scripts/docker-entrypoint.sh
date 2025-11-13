#!/bin/bash
set -e

# Entrypoint script for Docker container

DB_PATH="${DB_PATH:-/app/data/unsealed.db}"

# Check if database exists
if [ ! -f "$DB_PATH" ]; then
    echo "Error: Database not found at $DB_PATH"
    echo "The image should include the database at /app/data/unsealed.db"
    echo "Or mount a custom database: docker run -v \$(pwd)/data:/data -e DB_PATH=/data/unsealed.db unsealed-networks"
    exit 1
fi

case "${1}" in
    stdio)
        echo "Starting MCP server (stdio mode)" >&2
        exec python -m unsealed_networks.mcp_main --db "$DB_PATH"
        ;;
    sse)
        echo "Starting MCP SSE server on port ${PORT:-8765}" >&2
        exec python -m unsealed_networks.mcp_sse_main \
            --db "$DB_PATH" \
            --host "${HOST:-0.0.0.0}" \
            --port "${PORT:-8765}"
        ;;
    bash)
        exec /bin/bash
        ;;
    *)
        exec "$@"
        ;;
esac
