#!/bin/bash
# Wrapper script for MCP server over SSH
# Ensures clean stdio by suppressing SSH login messages

# Disable buffering and set clean environment
export PYTHONUNBUFFERED=1
export PYTHONIOENCODING=utf-8

cd /home/devon/Projects/unsealed-networks/unsealed-networks

# Use stdbuf to disable buffering
exec stdbuf -i0 -o0 -e0 /home/devon/.local/bin/uv run unsealed-networks-mcp "$@"
