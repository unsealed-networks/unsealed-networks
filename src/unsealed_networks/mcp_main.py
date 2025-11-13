#!/usr/bin/env python3
"""Entry point for MCP server."""

import asyncio

from unsealed_networks.mcp.server import main as async_main


def main():
    """Entry point wrapper."""
    asyncio.run(async_main())


if __name__ == "__main__":
    main()
