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
                'labels': metadata.get('labels', {}),
                'annotations': metadata.get('annotations', {}),
                'api_version': agent_doc.get('apiVersion'),
                'spec': spec,
                'status': status,
                
                # Extract key information for easier analysis
                'cluster_deployment_name': spec.get('clusterDeploymentName',{}).get('name'),
                'cluster_namespace': spec.get('clusterDeploymentName',{}).get('namespace'),
                'approved': spec.get('approved', False),
                'hostname': spec.get('hostname'),
                'machine_config_pool': spec.get('machineConfigPool'),
                'role': spec.get('role'),
                'installation_disk_path': spec.get('installationDiskPath'),
                
                # Status information
                'conditions': conditions,
                'debug_info': status.get('debugInfo', {}),
                'inventory': status.get('inventory', {}),
                'progress': status.get('progress', {}),
                'validation_info': status.get('validationInfo', {}),
                'installation_disk_id': status.get('installationDiskID'),
                'node_name': status.get('nodeName'),
                'failed': failed,
                'reason': reason,
                # Raw document for detailed analysis
                'raw': agent_doc
            }
            
            return agent
            
        except Exception as e:
            self.logger.warning(f"Failed to parse agent document: {e}")
            return None

    def analyze_agents(self, agents: List[Dict[str, Any]]) -> Dict[str, Any]:
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
            agent_status = self._get_agent_status_from_conditions(conditions)
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

    def _get_agent_status_from_conditions(self, conditions: List[Dict[str, Any]]) -> str:
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

    def get_failed_agents(self, agents: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Get a list of agents that have failed installation."""
        failed_agents = []
        for agent in agents:
            if agent['failed']:
                failed_agents.append(agent)
        return failed_agents

    def analyze(self, must_gather_path: str = None) -> str:
        """Analyze the must-gather and return a JSON string with the results."""
        if must_gather_path:
            self.must_gather_path = Path(must_gather_path)
        elif not self.must_gather_path:
            raise ValueError("Must provide must_gather_path either in constructor or method call")

        agents = self.find_agent_crs()
        # Analyze the agents
        analysis = self.analyze_agents(agents)
        
        result = {
            "success": True,
            "must_gather_path": str(self.must_gather_path),
            "agents": agents,
            "summary": analysis,
            "total_agents": len(agents)
        }
            
        return json.dumps(result, indent=2, default=str)

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
