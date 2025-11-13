#!/usr/bin/env python3
"""Entry point for MCP SSE server."""

import asyncio

from unsealed_networks.mcp.sse_server import main


def main_sync():
    """Entry point wrapper."""
    asyncio.run(main())


if __name__ == "__main__":
    main_sync()
