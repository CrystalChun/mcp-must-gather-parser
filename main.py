import mcp
from mcp.server.fastmcp import FastMCP
from parse import parse_must_gather as parse_mg
from typing import List, Dict, Any
import structlog

logger = structlog.get_logger(__name__)

mcp = FastMCP("MustGather", host="0.0.0.0")

@mcp.tool()
def parse_must_gather(must_gather_path: str) -> str:
    """Parse a must-gather directory and extract Agent CRs"""
    logger.info(f"Parsing must-gather file: {must_gather_path}")
    return parse_mg(must_gather_path)

@mcp.tool()
def get_failed_agents(must_gather_path: str) -> List[Dict[str, Any]]:
    """
    Get the names and namespaces of the agents that have failed installation
        
    Args:
        must_gather_path (str, required): Path to the must-gather directory
    """
    failed_agents = parse_mg(must_gather_path, agents=True)
    for agent in failed_agents:
        logger.info(f"Agent {agent['name']} in namespace {agent['namespace']} is not installed")
    return failed_agents

@mcp.tool()
def get_failed_clusters(must_gather_path: str) -> List[Dict[str, Any]]:
    """
    Get the names and namespaces of the clusters that have failed installation
        
    Args:
        must_gather_path (str, required): Path to the must-gather directory
    """
    failed_clusters = parse_mg(must_gather_path, clusters=True)
    for cluster in failed_clusters:
        logger.info(f"Cluster {cluster['name']} in namespace {cluster['namespace']} is not installed")
    return failed_clusters

@mcp.tool()
def get_failed_agents_and_clusters(must_gather_path: str) -> List[Dict[str, Any]]:
    """
    Get the names and namespaces of the clusters and their hosts (agents) that have failed installation
        
    Args:
        must_gather_path (str, required): Path to the must-gather directory
    """
    failed_clusters = parse_mg(must_gather_path, clusters=True, find_agents=True)
    return failed_clusters

@mcp.tool()
def get_logs(must_gather_path: str, pod_name: str = '', namespace: str = '', cluster_name: str = '', start_index: int = 0, chunk_size: int = 0) -> List[Dict[str, Any]]:
    """
    Get logs in a must-gather file, pod name and namespace can be specified
        
    Args:
        must_gather_path (str, required): Path to the must-gather directory
        pod_name (str, optional): Name of the pod to get logs from
        namespace (str, optional): Namespace of the pod to get logs from
        cluster_name (str, optional): Name of the cluster to get logs from
        start_index (int, optional): Start index of the logs to get
        chunk_size (int, optional): Chunk size of the logs to get
    """
    logs = parse_mg(must_gather_path, find_logs=True, pod_name=pod_name, namespace=namespace, cluster_name=cluster_name)
    logger.info(f"Chunk size {chunk_size} and start index {start_index}")

    if chunk_size > 0:
        logs = logs[start_index:start_index+chunk_size]
    logger.info(f"Returning {len(logs)} logs")
    return logs

@mcp.tool()
def get_recommended_pod_names_and_namespaces() -> List[Dict[str, Any]]:
    """
    Get the recommended pod names and namespaces for a must-gather file for a failed cluster analysis
    """
    return_data = [{"pod_name": "assisted-service", "namespace": "multicluster-engine"}, 
        {"pod_name": "metal3", "namespace": "openshift-machine-api"},
        {"pod_name": "baremetal-operator", "namespace": "openshift-machine-api"}]
    return return_data

if __name__ == "__main__":
    mcp.run(transport="sse")
