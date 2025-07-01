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

logger = structlog.get_logger(__name__)


def parse_must_gather(must_gather_path: str) -> List[Dict[str, Any]]:
    """
    Parse a must-gather archive or directory and extract Agent CRs.
    
    Args:
        must_gather_path: Path to must-gather tar.gz file or extracted directory
        
    Returns:
        JSON string containing Agent CR information and analysis
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
                "agents": [],
                "summary": {}
            })

        # Check that assisted-service is active in cluster
        if assisted_service_active(extracted_path):
            logger.info("assisted-service is enabled, finding agent crs")
            agents = find_agent_crs(extracted_path)
       
        # Clean up extracted files if needed
        if cleanup_needed:
            cleanup_extraction(extracted_path)
        
        return agents
        
    except Exception as e:
        logger.error(f"Error parsing must-gather: {str(e)}")
        return json.dumps({
            "error": f"Failed to parse must-gather: {str(e)}",
            "agents": [],
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

def assisted_service_active(must_gather_path: Path) -> bool:
    """
    Check if assisted-service is active in the cluster.
    """
    cluster_agents_path = must_gather_path / "cluster-scoped-resources" / "agent-install.openshift.io" / "agentserviceconfigs"
    return cluster_agents_path.exists()

def find_agent_crs(must_gather_path: Path) -> List[Dict[str, Any]]:
    """
    Find and parse Agent Custom Resources in the must-gather.
    
    Agent CRs are found in:
    - namespaces/<namespace>/agent-install.openshift.io/agents/
    """
    agents = []
    
    # Look for namespaced Agent CRs
    namespaces_path = must_gather_path / "namespaces"
    logger.info(f"Checking namespaces: {namespaces_path}")
    if namespaces_path.exists():
        for namespace_dir in namespaces_path.iterdir():
            if namespace_dir.is_dir():
                namespace = namespace_dir.name
                logger.info(f"Checking namespace: {namespace}")
                # Check for agents in this namespace
                ns_agents_path = namespace_dir / "agent-install.openshift.io" / "agents"
                logger.info(f"Checking agents in namespace: {ns_agents_path}")
                if ns_agents_path.exists():
                    agents.extend(parse_agent_files(ns_agents_path, scope="namespaced", namespace=namespace))
                else:
                    logger.info(f"No agents found in namespace: {namespace}")

    
    logger.info(f"Found {len(agents)} Agent CRs")
    return agents

def find_agentclusterinstall_crs(must_gather_path: Path) -> List[Dict[str, Any]]:
    """
    Find and parse AgentClusterInstall Custom Resources in the must-gather.
    
    AgentClusterInstall CRs are found in:
    - namespaces/<namespace>/extensions.hive.openshift.io/agentclusterinstalls/
    """
    clusters = []
    
    # Look for AgentClusterInstall CRs
    namespaces_path = must_gather_path / "namespaces"
    logger.info(f"Checking namespaces: {namespaces_path}")
    if namespaces_path.exists():
        for namespace_dir in namespaces_path.iterdir():
            if namespace_dir.is_dir():
                namespace = namespace_dir.name
                logger.info(f"Checking namespace: {namespace}")
                # Check for agentclusterinstalls in this namespace
                ns_cluster_path = namespace_dir / "extensions.hive.openshift.io" / "agentclusterinstalls"
                logger.info(f"Checking agentclusterinstalls in namespace: {ns_cluster_path}")
                if ns_cluster_path.exists():
                    clusters.extend(parse_cluster_files(ns_cluster_path, scope="namespaced", namespace=namespace))
                else:
                    logger.info(f"No agentclusterinstalls found in namespace: {namespace}")

    
    logger.info(f"Found {len(clusters)} AgentClusterInstall CRs")
    return clusters

def parse_cluster_files(clusters_dir: Path, scope: str, namespace: str = None) -> List[Dict[str, Any]]:
    """Parse individual Cluster CR files in a directory."""
    clusters = []
    
    for cluster_file in clusters_dir.iterdir():
        if cluster_file.is_file() and cluster_file.suffix in ['.yaml', '.yml']:
            clusters.extend(parse_cluster_yaml_file(cluster_file, scope, namespace))
        
    return clusters

def parse_cluster_yaml_file(file_path: Path, scope: str, namespace: str = None) -> List[Dict[str, Any]]:
    """Parse a YAML file containing Cluster CRs."""
    clusters = []
    
    try:
        with open(file_path, 'r') as f:
            content = f.read()

        # Parse YAML documents (may contain multiple clusters)
        documents = list(yaml.safe_load_all(content))
        
        for doc in documents:
            if doc and isinstance(doc, dict):
                # Check if this is an AgentClusterInstall CR
                if doc.get('kind') == 'AgentClusterInstall' and doc.get('apiVersion', '').startswith('extensions.hive.openshift.io'):
                    cluster = parse_single_cluster(doc, scope, namespace)
                    if cluster:
                        clusters.append(cluster)
                        
    except Exception as e:
        logger.warning(f"Failed to parse {file_path}: {e}")
    
    return clusters

def parse_single_cluster(cluster_doc: Dict[str, Any], scope: str, namespace: str = None) -> Optional[Dict[str, Any]]:
    """Parse a single AgentClusterInstall CR document."""
    try:
        metadata = cluster_doc.get('metadata', {})
        spec = cluster_doc.get('spec', {})
        status = cluster_doc.get('status', {})
        
        cluster = {
            'name': metadata.get('name', 'unknown'),
            'namespace': namespace or metadata.get('namespace'),
            'scope': scope,
            'creation_timestamp': metadata.get('creationTimestamp'),
            'labels': metadata.get('labels', {}),
            'annotations': metadata.get('annotations', {}),
            'api_version': cluster_doc.get('apiVersion'),
            'spec': spec,
            'status': status,
        }

        return cluster
        
    except Exception as e:
        logger.warning(f"Failed to parse cluster document: {e}")
        return None


def parse_agent_files(agents_dir: Path, scope: str, namespace: str = None) -> List[Dict[str, Any]]:
    """Parse individual Agent CR files in a directory."""
    agents = []
    
    for agent_file in agents_dir.iterdir():
        if agent_file.is_file() and agent_file.suffix in ['.yaml', '.yml']:
            agents.extend(parse_agent_yaml_file(agent_file, scope, namespace))
    
    return agents

def parse_agent_yaml_file(file_path: Path, scope: str, namespace: str = None) -> List[Dict[str, Any]]:
    """Parse a YAML file containing Agent CRs."""
    agents = []
    
    try:
        with open(file_path, 'r') as f:
            content = f.read()
            
        # Parse YAML documents (may contain multiple agents)
        documents = list(yaml.safe_load_all(content))
        
        for doc in documents:
            if doc and isinstance(doc, dict):
                # Check if this is an Agent CR
                if (doc.get('kind') == 'Agent' and 
                    doc.get('apiVersion', '').startswith('agent-install.openshift.io')):
                    
                    agent = parse_single_agent(doc, scope, namespace)
                    if agent:
                        agents.append(agent)
                        
    except Exception as e:
        logger.warning(f"Failed to parse {file_path}: {e}")
    
    return agents


def parse_single_agent(agent_doc: Dict[str, Any], scope: str, namespace: str = None) -> Optional[Dict[str, Any]]:
    """Parse a single Agent CR document."""
    try:
        metadata = agent_doc.get('metadata', {})
        spec = agent_doc.get('spec', {})
        status = agent_doc.get('status', {})
        
        agent = {
            'name': metadata.get('name', 'unknown'),
            'namespace': namespace or metadata.get('namespace'),
            'scope': scope,
            'creation_timestamp': metadata.get('creationTimestamp'),
            'labels': metadata.get('labels', {}),
            'annotations': metadata.get('annotations', {}),
            'api_version': agent_doc.get('apiVersion'),
            'spec': spec,
            'status': status,
            
            # Extract key information for easier analysis
            'cluster_deployment_name': spec.get('clusterDeploymentName'),
            'approved': spec.get('approved', False),
            'hostname': spec.get('hostname'),
            'machine_config_pool': spec.get('machineConfigPool'),
            'role': spec.get('role'),
            'installation_disk_path': spec.get('installationDiskPath'),
            
            # Status information
            'conditions': status.get('conditions', []),
            'debug_info': status.get('debugInfo', {}),
            'inventory': status.get('inventory', {}),
            'progress': status.get('progress', {}),
            'validation_info': status.get('validationInfo', {}),
            'installation_disk_id': status.get('installationDiskID'),
            'node_name': status.get('nodeName'),
            
            # Raw document for detailed analysis
            'raw': agent_doc
        }
        
        return agent
        
    except Exception as e:
        logger.warning(f"Failed to parse agent document: {e}")
        return None


def analyze_agents(agents: List[Dict[str, Any]]) -> Dict[str, Any]:
    """Analyze the collected Agent CRs and provide summary information."""
    if not agents:
        return {
            'total_agents': 0,
            'status': 'No agents found',
            'recommendations': ['No Agent CRs found in must-gather. This cluster may not be using Assisted Installer.']
        }
    
    analysis = {
        'total_agents': len(agents),
        'agents_by_status': {},
        'agents_by_role': {},
        'agents_by_cluster': {},
        'agents_by_namespace': {},
        'approved_agents': 0,
        'pending_agents': 0,
        'installed_agents': 0,
        'failed_agents': 0,
        'issues': [],
        'recommendations': []
    }
    
    for agent in agents:
        # Count by role
        role = agent.get('role', 'unknown')
        analysis['agents_by_role'][role] = analysis['agents_by_role'].get(role, 0) + 1
        
        # Count by cluster deployment
        cluster = agent.get('cluster_deployment_name', 'unknown')
        analysis['agents_by_cluster'][cluster] = analysis['agents_by_cluster'].get(cluster, 0) + 1
        
        # Count by namespace
        namespace = agent.get('namespace', 'cluster-scoped')
        analysis['agents_by_namespace'][namespace] = analysis['agents_by_namespace'].get(namespace, 0) + 1
        
        # Approval status
        if agent.get('approved'):
            analysis['approved_agents'] += 1
        else:
            analysis['pending_agents'] += 1
        
        # Installation status from conditions
        conditions = agent.get('conditions', [])
        agent_status = get_agent_status_from_conditions(conditions)
        analysis['agents_by_status'][agent_status] = analysis['agents_by_status'].get(agent_status, 0) + 1
        
        if agent_status == 'installed':
            analysis['installed_agents'] += 1
        elif 'failed' in agent_status.lower() or 'error' in agent_status.lower():
            analysis['failed_agents'] += 1
            analysis['issues'].append(f"Agent {agent['name']} has failed status: {agent_status}")
        
        # Check for validation issues
        validation_info = agent.get('validation_info', {})
        if validation_info and 'validationsInfo' in validation_info:
            for validation in validation_info.get('validationsInfo', []):
                if validation.get('status') == 'failure':
                    analysis['issues'].append(
                        f"Agent {agent['name']} validation failure: {validation.get('message', 'unknown')}"
                    )
    
    # Generate recommendations
    if analysis['failed_agents'] > 0:
        analysis['recommendations'].append(f"{analysis['failed_agents']} agents have failed. Check individual agent conditions and debug info.")
    
    if analysis['pending_agents'] > 0:
        analysis['recommendations'].append(f"{analysis['pending_agents']} agents are not approved. Consider approving them to proceed with installation.")
    
    if analysis['total_agents'] > 0 and analysis['installed_agents'] == 0:
        analysis['recommendations'].append("No agents have completed installation. Check cluster deployment status and agent conditions.")
    
    if len(analysis['agents_by_cluster']) > 1:
        analysis['recommendations'].append("Multiple cluster deployments found. Verify this is expected for your environment.")
    
    return analysis


def get_agent_status_from_conditions(conditions: List[Dict[str, Any]]) -> str:
    """Determine agent status from conditions."""
    if not conditions:
        return 'unknown'
    
    # Look for specific condition types that indicate status
    status_conditions = ['AgentIsConnected', 'RequirementsMet', 'SpecSynced', 'Validated', 'Installed']
    
    for condition in conditions:
        condition_type = condition.get('type', '')
        condition_status = condition.get('status', '')
        condition_reason = condition.get('reason', '')
        
        if condition_type == 'Installed' and condition_status == 'True':
            return 'installed'
        elif condition_type == 'RequirementsMet' and condition_status == 'False':
            return f'requirements_not_met: {condition_reason}'
        elif condition_type == 'Validated' and condition_status == 'False':
            return f'validation_failed: {condition_reason}'
        elif 'failed' in condition_reason.lower() or 'error' in condition_reason.lower():
            return f'failed: {condition_reason}'
    
    # If no specific status found, look at the last condition
    if conditions:
        last_condition = conditions[-1]
        return f"{last_condition.get('type', 'unknown')}: {last_condition.get('status', 'unknown')}"
    
    return 'unknown'

def get_failed_agents(agents: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    failed_agents = []
    for agent in agents:
        conditions = agent.get('conditions', [])
        #logger.info(f"Conditions: {conditions}")
        for condition in conditions:
            if condition.get('type') == 'Installed' and condition.get('status') == 'False' and condition.get('reason') == 'InstallationFailed':
                failed_agents.append(agent)
    return failed_agents

def analyze(must_gather_path: str) -> str:
    agents = parse_must_gather(must_gather_path)
    # Analyze the agents
    analysis = analyze_agents(agents)
    
    result = {
        "success": True,
        "must_gather_path": must_gather_path,
        "agents": agents,
        "summary": analysis,
        "total_agents": len(agents)
    }
        
    return json.dumps(result, indent=2, default=str)

def failed_agents(must_gather_path: str) -> List[Dict[str, Any]]:
    agents = parse_must_gather(must_gather_path)
    failed_agents = get_failed_agents(agents)
    logger.info(f"Found {len(failed_agents)} failed agents")
    for agent in failed_agents:
        logger.info(f"Agent {agent['name']} in namespace {agent['namespace']} has failed installation. Cluster deployment name: {agent['cluster_deployment_name']}")
        for condition in agent['conditions']:
            if condition.get('type') == 'Installed':
                logger.info(f"Installed condition: {condition.get('message')}")
    return failed_agents


# TODO: give me the names and namespaces of the agents that are not installed
# TODO: give me the names and namespaces of the agents that failed installation
# TODO: give me the names and namespaces of the clusters that are not installed or have failed installation
# TODO: find relevant logs in assisted-service logs for clusters and agents that are not installed

if __name__ == "__main__":
    # Test the function with a must-gather path
    import sys
    if len(sys.argv) > 1:
        result = failed_agents(sys.argv[1])
        #print(result)
    else:
        print("Usage: python parse.py <must-gather-path>")