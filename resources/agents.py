from pathlib import Path
from typing import List, Dict, Any, Optional
import yaml
import json
import structlog

logger = structlog.get_logger(__name__)

class AgentParser:
    def __init__(self, must_gather_path: str = None):
        """
        Initialize the AgentParser with an optional must-gather path.
        
        Args:
            must_gather_path (str, optional): Path to the must-gather directory
        """
        self.must_gather_path = Path(must_gather_path) if must_gather_path else None
        self.logger = logger

    def find_agent_crs(self, must_gather_path: Path = None) -> List[Dict[str, Any]]:
        """
        Find and parse Agent Custom Resources in the must-gather.
        
        Agent CRs are found in:
        - namespaces/<namespace>/agent-install.openshift.io/agents/
        """
        if must_gather_path:
            self.must_gather_path = must_gather_path
        elif not self.must_gather_path:
            raise ValueError("Must provide must_gather_path either in constructor or method call")

        agents = []
        
        # Look for namespaced Agent CRs
        namespaces_path = self.must_gather_path / "namespaces"
        if namespaces_path.exists():
            for namespace_dir in namespaces_path.iterdir():
                if namespace_dir.is_dir():
                    namespace = namespace_dir.name
                    # Check for agents in this namespace
                    agents.extend(self.find_agent_crs_in_directory(namespace_dir))
        
        self.logger.info(f"Found {len(agents)} Agent CRs")
        return agents
    
    def find_agent_crs_in_directory(self, directory: Path) -> List[Dict[str, Any]]:
        agents = []
        ns_agents_path = directory / "agent-install.openshift.io" / "agents"
        if ns_agents_path.exists():
            agents.extend(self._parse_agent_files(ns_agents_path))
        return agents

    def find_agents_belonging_to_cluster(self, cluster_name: str, cluster_namespace: str) -> List[Dict[str, Any]]:
        """Find agents belonging to a cluster."""
        agents = []
        for agent in self.find_agent_crs():
            if agent['cluster_deployment_name'] == cluster_name and agent['cluster_namespace'] == cluster_namespace:
                agents.append(agent)
        return agents

    def _parse_agent_files(self, agents_dir: Path, namespace: str = None) -> List[Dict[str, Any]]:
        """Parse individual Agent CR files in a directory."""
        agents = []
        
        for agent_file in agents_dir.iterdir():
            if agent_file.is_file() and agent_file.suffix in ['.yaml', '.yml']:
                agents.extend(self._parse_agent_yaml_file(agent_file, namespace))
        
        return agents

    def _parse_agent_yaml_file(self, file_path: Path, namespace: str = None) -> List[Dict[str, Any]]:
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
                        
                        agent = self._parse_single_agent(doc, namespace)
                        if agent:
                            agents.append(agent)
                            
        except Exception as e:
            self.logger.warning(f"Failed to parse {file_path}: {e}")
        
        return agents

    def _parse_single_agent(self, agent_doc: Dict[str, Any], namespace: str = None) -> Optional[Dict[str, Any]]:
        """Parse a single Agent CR document."""
        try:
            metadata = agent_doc.get('metadata', {})
            spec = agent_doc.get('spec', {})
            status = agent_doc.get('status', {})
            conditions = status.get('conditions', [])
            failed = False
            reason = None
            for condition in conditions:
                if condition.get('type') == 'Installed' and condition.get('status') == 'False' and condition.get('reason') == 'InstallationFailed':
                    failed = True
                    reason = condition.get('message')

            agent = {
                'name': metadata.get('name', 'unknown'),
                'namespace': namespace or metadata.get('namespace'),
                'creation_timestamp': metadata.get('creationTimestamp'),
                #'labels': metadata.get('labels', {}),
                #'annotations': metadata.get('annotations', {}),
                #'api_version': agent_doc.get('apiVersion'),
                'type': 'agent',
                #'spec': spec,
                #'status': status,
                
                # Extract key information for easier analysis
                'cluster_deployment_name': spec.get('clusterDeploymentName',{}).get('name'),
                'cluster_namespace': spec.get('clusterDeploymentName',{}).get('namespace'),
                'approved': spec.get('approved', False),
                'hostname': spec.get('hostname'),
                'role': spec.get('role'),
                #'installation_disk_path': spec.get('installationDiskPath'),
                
                # Status information
                'conditions': conditions,
                'debug_info': status.get('debugInfo', {}),
                #'inventory': status.get('inventory', {}),
                'progress': status.get('progress', {}),
                'validation_info': status.get('validationInfo', {}),
                #'installation_disk_id': status.get('installationDiskID'),
                #'node_name': status.get('nodeName'),
                'failed': failed,
                'reason': reason,
                # Raw document for detailed analysis
                #'raw': agent_doc
            }
            
            return agent
            
        except Exception as e:
            self.logger.warning(f"Failed to parse agent document: {e}")
            return None

    def get_failed_agents(self, agents: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Get a list of agents that have failed installation."""
        failed_agents = []
        for agent in agents:
            if agent['failed']:
                failed_agents.append(agent)
        return failed_agents

    def find_failed_agents(self, must_gather_path: str = None) -> List[Dict[str, Any]]:
        """Find and return a list of failed agents from the must-gather."""
        if must_gather_path:
            self.must_gather_path = Path(must_gather_path)
        elif not self.must_gather_path:
            raise ValueError("Must provide must_gather_path either in constructor or method call")

        agents = self.find_agent_crs()
        failed_agents = self.get_failed_agents(agents)
        self.logger.info(f"Found {len(failed_agents)} failed agents")
        for agent in failed_agents:
            self.logger.info(f"Agent {agent['name']} in namespace {agent['namespace']} has failed installation. Cluster deployment name: {agent['cluster_deployment_name']}. Reason: {agent['reason']}")
        return failed_agents
