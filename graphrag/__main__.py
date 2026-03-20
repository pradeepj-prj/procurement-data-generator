"""Allow running graphrag as a module: python -m graphrag.mcp_server or python -m graphrag.api."""

import sys

if __name__ == "__main__":
    print("Usage:")
    print("  python -m graphrag.mcp_server   # MCP server")
    print("  python -m graphrag.api          # REST API")
    sys.exit(1)
