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

logger = structlog.get_logger(__name__)


def parse_must_gather(must_gather_path: str, clusters: bool = False, find_agents: bool = False) -> List[Dict[str, Any]]:
    """
    Parse a must-gather archive or directory and extract Agent CRs.
    
    Args:
        must_gather_path: Path to must-gather tar.gz file or extracted directory
        
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

        # Check that assisted-service is active in cluster before parsing
        if assisted_service_active(extracted_path):
            logger.info("assisted-service is enabled")
            if clusters:
                return_data = ClusterParser(extracted_path).get_failed_clusters()
                if find_agents:
                    for cluster in return_data:
                        agents = AgentParser(extracted_path).find_agents_belonging_to_cluster(cluster['cluster_deployment_name'], cluster['namespace'])
                        return_data.extend(agents)
       
        # Clean up extracted files if needed
        if cleanup_needed:
            cleanup_extraction(extracted_path)
        
        return return_data
        
    except Exception as e:
        logger.error(f"Error parsing must-gather: {str(e)}")
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

# TODO: give me the names and namespaces of the agents that are not installed
# TODO: give me the names and namespaces of the clusters that are not installed 
# TODO: give me the names and namespaces of the agents associated with the failed clusters
# TODO: find relevant logs in assisted-service logs for clusters and agents that are not installed

if __name__ == "__main__":
    # Test the function with a must-gather path
    import sys
    if len(sys.argv) > 1:
        return_data = parse_must_gather(sys.argv[1], clusters=True, find_agents=True)
        for item in return_data:
            print(f"{item['type']}: {item['name']} in namespace {item['namespace']} has failed installation. Reason: {item['reason']}")
    else:
        print("Usage: python parse.py <must-gather-path>")