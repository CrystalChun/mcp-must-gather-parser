import mcp
from mcp.server.fastmcp import FastMCP

mcp = FastMCP("MustGather", host="0.0.0.0")

@mcp.tool()
def parse_must_gather(must_gather_path: str) -> str:
    """Parse a must-gather directory and return a JSON object"""
    return "Hello, World!"

if __name__ == "__main__":
    mcp.run(transport="sse")