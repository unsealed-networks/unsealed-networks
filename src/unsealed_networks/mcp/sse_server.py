#!/usr/bin/env python3
"""MCP server with SSE transport for network access."""

import sys
from pathlib import Path

from mcp.server.sse import SseServerTransport
from starlette.applications import Starlette
from starlette.routing import Route

from .server import create_server


def create_sse_app(db_path: str = "data/unsealed.db") -> Starlette:
    """Create Starlette app with MCP SSE endpoint."""

    # Create MCP server
    mcp_server = create_server(db_path)

    # Create SSE transport
    sse = SseServerTransport("/messages")

    async def handle_sse(request):
        """Handle SSE connections."""
        async with sse.connect_sse(
            request.scope, request.receive, request._send
        ) as streams:
            await mcp_server.run(
                streams[0], streams[1], mcp_server.create_initialization_options()
            )

    async def handle_messages(request):
        """Handle message endpoint."""
        await sse.handle_post_message(request.scope, request.receive, request._send)

    app = Starlette(
        debug=False,
        routes=[
            Route("/sse", endpoint=handle_sse),
            Route("/messages", endpoint=handle_messages, methods=["POST"]),
        ],
    )

    return app


async def main():
    """Run SSE server."""
    import argparse

    import uvicorn

    parser = argparse.ArgumentParser(description="Unsealed Networks MCP SSE Server")
    parser.add_argument(
        "--db",
        default="data/unsealed.db",
        help="Path to SQLite database (default: data/unsealed.db)",
    )
    parser.add_argument(
        "--host",
        default="0.0.0.0",
        help="Host to bind to (default: 0.0.0.0)",
    )
    parser.add_argument(
        "--port",
        type=int,
        default=8765,
        help="Port to bind to (default: 8765)",
    )
    args = parser.parse_args()

    # Verify database exists
    db_path = Path(args.db)
    if not db_path.exists():
        print(f"Error: Database not found at {db_path}", file=sys.stderr)
        print("Run: uv run unsealed-networks load-db <classifications> <text_dir>", file=sys.stderr)
        sys.exit(1)

    print(f"Starting MCP SSE server on {args.host}:{args.port}")
    print(f"Database: {db_path.absolute()}")
    print(f"Endpoint: http://{args.host}:{args.port}/sse")

    app = create_sse_app(args.db)

    config = uvicorn.Config(
        app,
        host=args.host,
        port=args.port,
        log_level="info"
    )
    server = uvicorn.Server(config)
    await server.serve()


if __name__ == "__main__":
    import asyncio

    asyncio.run(main())
