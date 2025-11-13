"""MCP server implementation for document search and retrieval."""

import sqlite3
from pathlib import Path

from mcp.server import Server
from mcp.types import TextContent, Tool

# Global database connection
_conn: sqlite3.Connection | None = None


def get_connection(db_path: str = "data/unsealed.db") -> sqlite3.Connection:
    """Get or create database connection."""
    global _conn
    if _conn is None:
        path = Path(db_path)
        if not path.exists():
            raise FileNotFoundError(
                f"Database not found at {path}. Run 'unsealed-networks load-db' first."
            )
        _conn = sqlite3.connect(path)
        _conn.row_factory = sqlite3.Row
    return _conn


def create_server(db_path: str = "data/unsealed.db") -> Server:
    """Create and configure MCP server."""
    server = Server("unsealed-networks")

    # Initialize connection
    get_connection(db_path)

    @server.list_tools()
    async def list_tools() -> list[Tool]:
        """List available tools."""
        return [
            Tool(
                name="search_documents",
                description="Full-text search across all Epstein documents using SQLite FTS5. "
                "Supports quoted phrases, AND/OR operators, and wildcards. "
                "Returns matching documents with doc_id, type, and text snippets.",
                inputSchema={
                    "type": "object",
                    "properties": {
                        "query": {
                            "type": "string",
                            "description": (
                                "Search query (e.g., 'Peter Thiel', 'Trump AND Epstein', "
                                "'\"donor advised fund\"')"
                            ),
                        },
                        "limit": {
                            "type": "integer",
                            "description": "Maximum number of results (default 10, max 50)",
                            "default": 10,
                        },
                    },
                    "required": ["query"],
                },
            ),
            Tool(
                name="get_document",
                description=(
                    "Retrieve the full text of a specific document by HOUSE_OVERSIGHT ID. "
                    "Returns complete document content with metadata."
                ),
                inputSchema={
                    "type": "object",
                    "properties": {
                        "doc_id": {
                            "type": "string",
                            "description": "Document ID (e.g., 'HOUSE_OVERSIGHT_032827')",
                        },
                    },
                    "required": ["doc_id"],
                },
            ),
            Tool(
                name="find_by_entity",
                description="Find all documents mentioning a specific person or entity. "
                "Tracks mentions of: Peter Thiel, Elon Musk, Bill Gates, Donald Trump, "
                "Bill Clinton, Jeffrey Epstein, Ghislaine Maxwell, Michael Wolff, Landon Thomas.",
                inputSchema={
                    "type": "object",
                    "properties": {
                        "entity": {
                            "type": "string",
                            "description": "Entity name (e.g., 'Peter Thiel', 'Bill Gates')",
                        },
                        "limit": {
                            "type": "integer",
                            "description": "Maximum number of results (default 20, max 100)",
                            "default": 20,
                        },
                    },
                    "required": ["entity"],
                },
            ),
            Tool(
                name="list_entities",
                description="List all tracked entities with document counts. "
                "Shows how many documents mention each person.",
                inputSchema={"type": "object", "properties": {}},
            ),
            Tool(
                name="get_document_stats",
                description="Get database statistics including total documents, "
                "document type breakdown, and top entities mentioned.",
                inputSchema={"type": "object", "properties": {}},
            ),
        ]

    @server.call_tool()
    async def call_tool(name: str, arguments: dict) -> list[TextContent]:
        """Handle tool calls."""
        conn = get_connection(db_path)

        if name == "search_documents":
            query = arguments["query"]
            limit = min(arguments.get("limit", 10), 50)

            # FTS5 search
            cursor = conn.execute(
                """
                SELECT
                    d.doc_id,
                    d.doc_type,
                    d.confidence,
                    snippet(documents_fts, 1, '**', '**', '...', 64) as snippet
                FROM documents_fts
                JOIN documents d ON documents_fts.doc_id = d.doc_id
                WHERE documents_fts MATCH ?
                ORDER BY rank
                LIMIT ?
                """,
                (query, limit),
            )

            results = []
            for row in cursor:
                doc_line = (
                    f"**{row['doc_id']}** ({row['doc_type']}, "
                    f"confidence: {row['confidence']:.2f})\n{row['snippet']}\n"
                )
                results.append(doc_line)

            if not results:
                return [TextContent(type="text", text=f"No documents found matching: {query}")]

            return [
                TextContent(
                    type="text",
                    text=f"Found {len(results)} documents:\n\n" + "\n---\n\n".join(results),
                )
            ]

        elif name == "get_document":
            doc_id = arguments["doc_id"]

            cursor = conn.execute(
                """
                SELECT doc_id, filepath, doc_type, confidence, line_count, full_text
                FROM documents
                WHERE doc_id = ?
                """,
                (doc_id,),
            )

            row = cursor.fetchone()
            if not row:
                return [TextContent(type="text", text=f"Document not found: {doc_id}")]

            # Get entity mentions
            cursor = conn.execute(
                "SELECT entity_name FROM entity_mentions WHERE doc_id = ?", (doc_id,)
            )
            entities = [r["entity_name"] for r in cursor]

            result = (
                f"**Document: {row['doc_id']}**\n\n"
                f"Type: {row['doc_type']}\n"
                f"Confidence: {row['confidence']:.2f}\n"
                f"Lines: {row['line_count']}\n"
                f"Entities mentioned: {', '.join(entities) if entities else 'None'}\n"
                f"Source: {row['filepath']}\n\n"
                f"---\n\n"
                f"{row['full_text']}"
            )

            return [TextContent(type="text", text=result)]

        elif name == "find_by_entity":
            entity = arguments["entity"]
            limit = min(arguments.get("limit", 20), 100)

            cursor = conn.execute(
                """
                SELECT d.doc_id, d.doc_type, d.confidence, d.line_count
                FROM documents d
                JOIN entity_mentions e ON d.doc_id = e.doc_id
                WHERE e.entity_name = ?
                ORDER BY d.confidence DESC
                LIMIT ?
                """,
                (entity, limit),
            )

            results = []
            for row in cursor:
                results.append(
                    f"- **{row['doc_id']}** ({row['doc_type']}, "
                    f"confidence: {row['confidence']:.2f}, {row['line_count']} lines)"
                )

            if not results:
                return [TextContent(type="text", text=f"No documents found mentioning: {entity}")]

            return [
                TextContent(
                    type="text",
                    text=f"Found {len(results)} documents mentioning **{entity}**:\n\n"
                    + "\n".join(results),
                )
            ]

        elif name == "list_entities":
            cursor = conn.execute(
                """
                SELECT entity_name, COUNT(*) as count
                FROM entity_mentions
                GROUP BY entity_name
                ORDER BY count DESC
                """
            )

            results = []
            for row in cursor:
                results.append(f"- **{row['entity_name']}**: {row['count']} documents")

            return [
                TextContent(
                    type="text",
                    text="**Tracked Entities:**\n\n" + "\n".join(results),
                )
            ]

        elif name == "get_document_stats":
            # Total documents
            total = conn.execute("SELECT COUNT(*) as count FROM documents").fetchone()["count"]

            # Document types
            cursor = conn.execute(
                """
                SELECT doc_type, COUNT(*) as count
                FROM documents
                GROUP BY doc_type
                ORDER BY count DESC
                """
            )
            doc_types = [f"- {row['doc_type']}: {row['count']}" for row in cursor]

            # Top entities
            cursor = conn.execute(
                """
                SELECT entity_name, COUNT(*) as count
                FROM entity_mentions
                GROUP BY entity_name
                ORDER BY count DESC
                LIMIT 10
                """
            )
            top_entities = [f"- {row['entity_name']}: {row['count']}" for row in cursor]

            result = (
                f"**Database Statistics**\n\n"
                f"Total documents: {total}\n\n"
                f"**Document Types:**\n" + "\n".join(doc_types) + "\n\n"
                "**Top 10 Entity Mentions:**\n" + "\n".join(top_entities)
            )

            return [TextContent(type="text", text=result)]

        else:
            return [TextContent(type="text", text=f"Unknown tool: {name}")]

    return server


async def main():
    """Run MCP server."""
    import argparse

    from mcp.server.stdio import stdio_server

    parser = argparse.ArgumentParser(description="Unsealed Networks MCP Server")
    parser.add_argument(
        "--db",
        default="data/unsealed.db",
        help="Path to SQLite database (default: data/unsealed.db)",
    )
    args = parser.parse_args()

    server = create_server(args.db)

    async with stdio_server() as (read_stream, write_stream):
        await server.run(read_stream, write_stream, server.create_initialization_options())


if __name__ == "__main__":
    import asyncio

    asyncio.run(main())
