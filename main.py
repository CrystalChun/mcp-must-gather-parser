import mcp
from mcp.server.fastmcp import FastMCP
from parse import parse_must_gather as parse_mg
from typing import List, Dict, Any
import structlog
from resources.logs import LogParser
from pathlib import Path
from resources.clusters import Cluster

logger = structlog.get_logger(__name__)

mcp = FastMCP("MustGather", host="0.0.0.0")

@mcp.tool()
def parse_must_gather(must_gather_path: str) -> str:
    """Parse a must-gather directory and extract Agent CRs"""
    logger.info(f"Parsing must-gather file: {must_gather_path}")
    return parse_mg(must_gather_path, logger=logger)

@mcp.tool()
def get_failed_clusters(must_gather_path: str) -> List[Cluster]:
    """
    Get the clusters that have failed installation
        
    Args:
        must_gather_path (str, required): Path to the must-gather directory
    """
    logger.info(f"Getting failed clusters from must-gather path: {must_gather_path}")
    failed_clusters = parse_mg(must_gather_path, logger=logger, clusters=True)
    logger.info(f"Found {len(failed_clusters)} failed clusters")
    for cluster in failed_clusters:
        if cluster:
            logger.info(f"Cluster {cluster.name} in namespace {cluster.namespace} is not installed")
        #logger.info(f"cluster: {cluster}")
    logger.info(f"Returning {len(failed_clusters)} failed clusters")
    return failed_clusters

@mcp.tool()
def get_failed_agents(must_gather_path: str, cluster_name: str, namespace: str) -> List[Dict[str, Any]]:
    """
    Get the agents (hosts) for a cluster
        
    Args:
        must_gather_path (str, required): Path to the must-gather directory
        cluster_name (str, required): Name of the cluster that failed installation
        namespace (str, required): Namespace of the cluster that failed installation
    """
    logger.info(f"Finding agents for cluster {cluster_name} in namespace {namespace}")
    agents = parse_mg(must_gather_path, clusters=False, find_agents=True, cluster_name=cluster_name, namespace=namespace, logger=logger)
    return agents

@mcp.tool()
def get_assisted_logs(must_gather_path: str, cluster_name: str = '', start_index: int = 0) -> List[Dict[str, Any]]:
    """
    Get logs of assisted-service pod from a must-gather file or directory. Cluster name is required to get the logs of a specific cluster.
        
    Args:
        must_gather_path (str, required): Path to the must-gather directory
        cluster_name (str, required): Name of the cluster to get logs from
        start_index (int, optional): Start index of the logs to get
    """
    chunk_size = 25
    pod_name = 'assisted-service'
    namespace = 'multicluster-engine'
    logs = get_logs(must_gather_path, pod_name, namespace, cluster_name, start_index)
    return logs

@mcp.tool()
def get_logs(must_gather_path: str, pod_name: str = '', namespace: str = '', cluster_name: str = '', start_index: int = 0) -> List[Dict[str, Any]]:
    """
    Get logs of assisted-service pod from a must-gather file or directory. Cluster name is required to get the logs of a specific cluster.
        
    Args:
        must_gather_path (str, required): Path to the must-gather directory
        pod_name (str, required): Name of the pod to get logs from
        namespace (str, required): Namespace of the pod to get logs from
        cluster_name (str, required): Name of the cluster to get logs from
        start_index (int, optional): Start index of the logs to get
    """
    chunk_size = 25
    logs = parse_mg(must_gather_path, find_logs=True, pod_name=pod_name, namespace=namespace, cluster_name=cluster_name, logger=logger)
    logger.info(f"Chunk size {chunk_size}, start index {start_index}, cluster name {cluster_name}")

    if chunk_size > 0:
        logs = logs[start_index:start_index+chunk_size]
    logger.info(f"Returning {len(logs)} logs")
    return logs

@mcp.tool()
def find_pod_logs_file_path(must_gather_path: str, pod_name: str, namespace: str) -> str:
    """
    Find the path of the logs file of a pod in the must-gather directory

    Args:
        must_gather_path (str, required): Path to the must-gather directory
        pod_name (str, required): Name of the pod to find
        namespace (str, required): Namespace of the pod to find
    """
    pod_dir = LogParser(must_gather_path).find_pod_directory(pod_name=pod_name, namespace=namespace)
    if pod_dir:
        logs_path = LogParser(must_gather_path).find_pod_logs_directory(pod_dir=pod_dir)
        logger.info(f"Logs path: {logs_path}")
        for log_file in logs_path.iterdir():
            if log_file.is_file():
                logger.info(f"Log file: {log_file}")
                return log_file
    return None



if __name__ == "__main__":
    mcp.run(transport="sse")
