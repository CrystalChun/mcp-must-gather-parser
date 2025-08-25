"""
OpenShift Must-Gather Parser for assisted service CRs
"""

import json
import os
import tarfile
import tempfile
import yaml
from pathlib import Path
from typing import Dict, List, Any, Optional, Union
import structlog
from resources.agents import AgentParser
from resources.assisted import assisted_service_active
from resources.clusters import ClusterParser
from resources.logs import LogParser

default_logger = structlog.get_logger(__name__)


def parse_must_gather(must_gather_path: str, logger: structlog.stdlib.BoundLogger, clusters: bool = False, find_agents: bool = False, find_logs: bool = False, pod_name: str = '', namespace: str = '', cluster_name: str = '' ) -> List[Any]:
    """
    Parse a must-gather archive or directory and extract Agent CRs.
    
    Args:
        must_gather_path: Path to must-gather tar.gz file or extracted directory
        clusters: bool, optional: Whether to find failed clusters
        find_agents: bool, optional: Whether to find failed agents
        find_logs: bool, optional: Whether to find logs
        pod_name: str, optional: Name of the pod to find logs for
        namespace: str, optional: Namespace of the pod to find logs for
        cluster_name: str, optional: Name of the cluster to find logs for
        
    Returns:
        JSON string containing CR information
    """
    try:
        # Determine if input is a file or directory
        path = Path(must_gather_path)
        
        if path.is_file() and path.suffix in ['.gz', '.tgz'] or path.name.endswith('.tar.gz'):
            # Extract tar.gz file
            extracted_path = extract_must_gather_archive(must_gather_path)
            cleanup_needed = True
        elif path.is_dir():
            # Use directory directly
            extracted_path = path
            cleanup_needed = False
        else:
            return json.dumps({
                "error": f"Invalid must-gather path: {must_gather_path}. Must be a .tar.gz file or directory.",
                "return_data": [],
                "summary": {}
            })

        return_data = []
        logger.info(f"Extracted path: {extracted_path}")
        # Check that assisted-service is active in cluster before parsing
        if assisted_service_active(extracted_path):
            logger.info("assisted-service is enabled")
            if find_agents and cluster_name != '' and namespace != '':
                logger.info(f"Finding agents for cluster {cluster_name} in namespace {namespace}")
                return_data = AgentParser(extracted_path).find_agents_belonging_to_cluster(cluster_name, namespace)
            elif clusters:
                logger.info(f"Finding failed clusters")
                return_data = ClusterParser(extracted_path).get_failed_clusters()
                if find_agents:
                    for cluster in return_data:
                        agents = AgentParser(extracted_path).find_agents_belonging_to_cluster(cluster['cluster_deployment_name'], cluster['namespace'])
                        return_data.extend(agents)
            elif find_logs:
                logger.info(f"Finding logs for pod {pod_name} in namespace {namespace} and cluster {cluster_name}")
                return_data = LogParser(extracted_path).get_logs_by_pod(pod_name=pod_name, namespace=namespace, cluster_name=cluster_name)
        # Clean up extracted files if needed
        if cleanup_needed:
            cleanup_extraction(extracted_path)
        
        return return_data
        
    except Exception as e:
        logger.error(f"Error parsing must-gather in parse.py: {str(e)}")
        return json.dumps({
            "error": f"Failed to parse must-gather: {str(e)}",
            "return_data": [],
            "summary": {},
            "total_agents": 0
        })


def extract_must_gather_archive(archive_path: str) -> Path:
    """Extract must-gather tar.gz archive to temporary directory."""
    logger.info(f"Extracting must-gather archive: {archive_path}")
    
    # Create temporary directory
    temp_dir = Path(tempfile.mkdtemp(prefix="must_gather_"))
    
    # Extract archive
    with tarfile.open(archive_path, 'r:gz') as tar:
        tar.extractall(temp_dir)
    
    # Find the actual must-gather directory (usually has timestamp in name)
    extracted_dirs = [d for d in temp_dir.iterdir() if d.is_dir()]
    if extracted_dirs:
        return extracted_dirs[0]  # Return first directory found
    else:
        return temp_dir


def cleanup_extraction(extracted_path: Path):
    """Clean up extracted temporary files."""
    try:
        import shutil
        # Remove the temporary directory and all contents
        temp_root = extracted_path.parent
        if 'must_gather_' in temp_root.name:
            shutil.rmtree(temp_root)
            logger.info(f"Cleaned up temporary extraction: {temp_root}")
    except Exception as e:
        logger.warning(f"Failed to clean up extraction: {e}")

if __name__ == "__main__":
    # Test the function with a must-gather path
    import sys
    if len(sys.argv) > 1:
        #return_data = parse_must_gather(sys.argv[1], find_logs=True, pod_name=sys.argv[2], namespace=sys.argv[3], cluster_name=sys.argv[4])
        return_data = parse_must_gather(sys.argv[1], find_agents=True, cluster_name=sys.argv[2], namespace=sys.argv[3])
        print(return_data)
    else:
        print("Usage: python parse.py <must-gather-path>")