"""
Alpic Smoke Test - Minimal FastMCP Server

Provides 1 tool: ping
"""

from fastmcp import FastMCP

mcp = FastMCP("alpic-smoke-test")


@mcp.tool()
def ping(message: str = "hello") -> str:
    """Simple ping tool to verify deployment."""
    return f"pong: {message}"


if __name__ == "__main__":
    import sys
    if len(sys.argv) > 1 and sys.argv[1] == "remote":
        import uvicorn
        print("Starting smoke test MCP server (streamable-http) on 0.0.0.0:8081")
        app = mcp.http_app(stateless_http=True)
        uvicorn.run(app, host="0.0.0.0", port=8081, log_level="info")
    else:
        print("Starting smoke test MCP server (stdio)")
        mcp.run(transport="stdio")
