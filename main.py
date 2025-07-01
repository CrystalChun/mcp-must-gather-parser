import mcp
from mcp.server.fastmcp import FastMCP
from parse import parse_must_gather as parse_mg
import logging
from typing import List, Dict, Any

logger = logging.getLogger(__name__)

mcp = FastMCP("MustGather", host="0.0.0.0")

@mcp.tool()
def parse_must_gather(must_gather_path: str) -> str:
    """Parse a must-gather directory and extract Agent CRs"""
    logger.info(f"Parsing must-gather file: {must_gather_path}")
    return parse_mg(must_gather_path)

@mcp.tool()
def get_failed_agents(agents: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """Get the names and namespaces of the agents that are not installed"""
    failed_agents = get_failed_agents(agents)
    for agent in failed_agents:
        logger.info(f"Agent {agent['name']} in namespace {agent['namespace']} is not installed")
    return failed_agents

@mcp.tool()
def get_failed_clusters(clusters: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """Get the names and namespaces of the clusters that are not installed"""
    failed_clusters = get_failed_clusters(clusters)
    for cluster in failed_clusters:
        logger.info(f"Cluster {cluster['name']} in namespace {cluster['namespace']} is not installed")
    return failed_clusters

if __name__ == "__main__":
    mcp.run(transport="sse")