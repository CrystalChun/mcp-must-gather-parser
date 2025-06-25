"""
Parsers for OpenShift Must-Gather data
"""

import asyncio
import json
import tarfile
import tempfile
import uuid
import yaml
from pathlib import Path
from typing import Any, Dict, List, Optional
import structlog

from .config import MCPConfig

logger = structlog.get_logger(__name__)


class MustGatherParser:
    """Parser for OpenShift must-gather archives"""
    
    def __init__(self, config: MCPConfig):
        self.config = config
        self._extraction_cache: Dict[str, Path] = {}
    
    async def initialize(self):
        """Initialize the parser"""
        logger.info("Initializing must-gather parser")
    
    async def parse_archive(self, archive_path: str, extract_logs: bool = False) -> str:
        """Parse a must-gather archive and return a unique ID"""
        must_gather_id = str(uuid.uuid4())
        logger.info("Parsing archive", archive_path=archive_path, must_gather_id=must_gather_id)
        
        # Create temporary extraction directory
        extract_dir = self.config.storage_dir / must_gather_id
        extract_dir.mkdir(parents=True, exist_ok=True)
        
        try:
            # Extract the archive
            with tarfile.open(archive_path, 'r:gz') as tar:
                tar.extractall(extract_dir)
            
            self._extraction_cache[must_gather_id] = extract_dir
            
            # Parse the extracted data
            parsed_data = await self._parse_extracted_data(extract_dir, extract_logs)
            
            # Store the parsed data
            from .resources import MustGatherResources
            resources = MustGatherResources(self.config)
            await resources.add_parsed_data(must_gather_id, parsed_data)
            
            return must_gather_id
            
        except Exception as e:
            logger.exception("Failed to parse archive", error=str(e))
            # Clean up on failure
            if extract_dir.exists():
                import shutil
                shutil.rmtree(extract_dir)
            raise
    
    async def _parse_extracted_data(self, extract_dir: Path, extract_logs: bool) -> Dict[str, Any]:
        """Parse extracted must-gather data"""
        data = {
            "cluster_info": {},
            "nodes": [],
            "namespaces": {},
            "events": [],
            "cluster_operators": [],
            "machine_config_pools": [],
            "analysis": {}
        }
        
        # Find the must-gather root directory
        mg_root = self._find_must_gather_root(extract_dir)
        if not mg_root:
            raise ValueError("Could not find must-gather root directory")
        
        # Parse cluster version and info
        await self._parse_cluster_info(mg_root, data)
        
        # Parse nodes
        await self._parse_nodes(mg_root, data)
        
        # Parse namespaces and pods
        await self._parse_namespaces_and_pods(mg_root, data, extract_logs)
        
        # Parse events
        await self._parse_events(mg_root, data)
        
        # Parse cluster operators
        await self._parse_cluster_operators(mg_root, data)
        
        # Parse machine config pools
        await self._parse_machine_config_pools(mg_root, data)
        
        return data
    
    def _find_must_gather_root(self, extract_dir: Path) -> Optional[Path]:
        """Find the root directory of the must-gather data"""
        # Look for common must-gather directory patterns
        for item in extract_dir.iterdir():
            if item.is_dir():
                # Check if this looks like a must-gather directory
                if (item / "cluster-scoped-resources").exists() or \
                   (item / "namespaces").exists():
                    return item
        
        # If not found, check if the extract_dir itself is the root
        if (extract_dir / "cluster-scoped-resources").exists() or \
           (extract_dir / "namespaces").exists():
            return extract_dir
        
        return None
    
    async def _parse_cluster_info(self, mg_root: Path, data: Dict):
        """Parse cluster information"""
        cluster_info = {}
        
        # Parse cluster version
        version_file = mg_root / "cluster-scoped-resources" / "config.openshift.io" / "clusterversions.yaml"
        if version_file.exists():
            try:
                with open(version_file, 'r') as f:
                    content = f.read()
                    docs = list(yaml.safe_load_all(content))
                    for doc in docs:
                        if doc and doc.get('kind') == 'ClusterVersion':
                            cluster_info['version'] = doc.get('status', {}).get('history', [{}])[0].get('version', 'unknown')
                            cluster_info['cluster_id'] = doc.get('spec', {}).get('clusterID', 'unknown')
                            break
            except Exception as e:
                logger.warning("Failed to parse cluster version", error=str(e))
        
        # Parse infrastructure
        infra_file = mg_root / "cluster-scoped-resources" / "config.openshift.io" / "infrastructures.yaml"
        if infra_file.exists():
            try:
                with open(infra_file, 'r') as f:
                    content = f.read()
                    docs = list(yaml.safe_load_all(content))
                    for doc in docs:
                        if doc and doc.get('kind') == 'Infrastructure':
                            cluster_info['platform'] = doc.get('status', {}).get('platform', 'unknown')
                            cluster_info['region'] = doc.get('status', {}).get('platformStatus', {}).get('aws', {}).get('region', 'unknown')
                            break
            except Exception as e:
                logger.warning("Failed to parse infrastructure", error=str(e))
        
        data['cluster_info'] = cluster_info
    
    async def _parse_nodes(self, mg_root: Path, data: Dict):
        """Parse node information"""
        nodes = []
        
        nodes_file = mg_root / "cluster-scoped-resources" / "core" / "nodes.yaml"
        if nodes_file.exists():
            try:
                with open(nodes_file, 'r') as f:
                    content = f.read()
                    docs = list(yaml.safe_load_all(content))
                    for doc in docs:
                        if doc and doc.get('kind') == 'Node':
                            node_info = {
                                'name': doc.get('metadata', {}).get('name', 'unknown'),
                                'roles': self._get_node_roles(doc),
                                'status': self._get_node_status(doc),
                                'version': doc.get('status', {}).get('nodeInfo', {}).get('kubeletVersion', 'unknown'),
                                'os': doc.get('status', {}).get('nodeInfo', {}).get('osImage', 'unknown'),
                                'conditions': doc.get('status', {}).get('conditions', [])
                            }
                            nodes.append(node_info)
            except Exception as e:
                logger.warning("Failed to parse nodes", error=str(e))
        
        data['nodes'] = nodes
    
    def _get_node_roles(self, node_doc: Dict) -> List[str]:
        """Extract node roles from node document"""
        labels = node_doc.get('metadata', {}).get('labels', {})
        roles = []
        for label, value in labels.items():
            if label.startswith('node-role.kubernetes.io/'):
                role = label.replace('node-role.kubernetes.io/', '')
                roles.append(role)
        return roles or ['worker']
    
    def _get_node_status(self, node_doc: Dict) -> str:
        """Get node status from conditions"""
        conditions = node_doc.get('status', {}).get('conditions', [])
        for condition in conditions:
            if condition.get('type') == 'Ready':
                return 'Ready' if condition.get('status') == 'True' else 'NotReady'
        return 'Unknown'
    
    async def _parse_namespaces_and_pods(self, mg_root: Path, data: Dict, extract_logs: bool):
        """Parse namespace and pod information"""
        namespaces = {}
        
        ns_dir = mg_root / "namespaces"
        if ns_dir.exists():
            for ns_path in ns_dir.iterdir():
                if ns_path.is_dir():
                    namespace = ns_path.name
                    ns_data = {
                        'pods': [],
                        'services': [],
                        'deployments': [],
                        'events': []
                    }
                    
                    # Parse pods
                    pods_file = ns_path / "core" / "pods.yaml"
                    if pods_file.exists():
                        ns_data['pods'] = await self._parse_pods_file(pods_file)
                    
                    # Parse services
                    services_file = ns_path / "core" / "services.yaml"
                    if services_file.exists():
                        ns_data['services'] = await self._parse_services_file(services_file)
                    
                    # Parse deployments
                    deployments_file = ns_path / "apps" / "deployments.yaml"
                    if deployments_file.exists():
                        ns_data['deployments'] = await self._parse_deployments_file(deployments_file)
                    
                    namespaces[namespace] = ns_data
        
        data['namespaces'] = namespaces
    
    async def _parse_pods_file(self, pods_file: Path) -> List[Dict]:
        """Parse pods from YAML file"""
        pods = []
        try:
            with open(pods_file, 'r') as f:
                content = f.read()
                docs = list(yaml.safe_load_all(content))
                for doc in docs:
                    if doc and doc.get('kind') == 'Pod':
                        pod_info = {
                            'name': doc.get('metadata', {}).get('name', 'unknown'),
                            'phase': doc.get('status', {}).get('phase', 'unknown'),
                            'ready': self._get_pod_ready_status(doc),
                            'restarts': self._get_pod_restart_count(doc),
                            'containers': self._get_container_info(doc)
                        }
                        pods.append(pod_info)
        except Exception as e:
            logger.warning("Failed to parse pods file", file=str(pods_file), error=str(e))
        return pods
    
    def _get_pod_ready_status(self, pod_doc: Dict) -> str:
        """Get pod ready status"""
        conditions = pod_doc.get('status', {}).get('conditions', [])
        for condition in conditions:
            if condition.get('type') == 'Ready':
                return 'True' if condition.get('status') == 'True' else 'False'
        return 'Unknown'
    
    def _get_pod_restart_count(self, pod_doc: Dict) -> int:
        """Get total restart count for pod"""
        container_statuses = pod_doc.get('status', {}).get('containerStatuses', [])
        return sum(status.get('restartCount', 0) for status in container_statuses)
    
    def _get_container_info(self, pod_doc: Dict) -> List[Dict]:
        """Get container information"""
        containers = []
        container_statuses = pod_doc.get('status', {}).get('containerStatuses', [])
        for status in container_statuses:
            container_info = {
                'name': status.get('name', 'unknown'),
                'ready': status.get('ready', False),
                'restarts': status.get('restartCount', 0),
                'image': status.get('image', 'unknown'),
                'state': list(status.get('state', {}).keys())[0] if status.get('state') else 'unknown'
            }
            containers.append(container_info)
        return containers
    
    async def _parse_services_file(self, services_file: Path) -> List[Dict]:
        """Parse services from YAML file"""
        services = []
        try:
            with open(services_file, 'r') as f:
                content = f.read()
                docs = list(yaml.safe_load_all(content))
                for doc in docs:
                    if doc and doc.get('kind') == 'Service':
                        service_info = {
                            'name': doc.get('metadata', {}).get('name', 'unknown'),
                            'type': doc.get('spec', {}).get('type', 'ClusterIP'),
                            'cluster_ip': doc.get('spec', {}).get('clusterIP', 'unknown'),
                            'ports': doc.get('spec', {}).get('ports', [])
                        }
                        services.append(service_info)
        except Exception as e:
            logger.warning("Failed to parse services file", file=str(services_file), error=str(e))
        return services
    
    async def _parse_deployments_file(self, deployments_file: Path) -> List[Dict]:
        """Parse deployments from YAML file"""
        deployments = []
        try:
            with open(deployments_file, 'r') as f:
                content = f.read()
                docs = list(yaml.safe_load_all(content))
                for doc in docs:
                    if doc and doc.get('kind') == 'Deployment':
                        deployment_info = {
                            'name': doc.get('metadata', {}).get('name', 'unknown'),
                            'replicas': doc.get('spec', {}).get('replicas', 0),
                            'ready_replicas': doc.get('status', {}).get('readyReplicas', 0),
                            'available_replicas': doc.get('status', {}).get('availableReplicas', 0),
                            'conditions': doc.get('status', {}).get('conditions', [])
                        }
                        deployments.append(deployment_info)
        except Exception as e:
            logger.warning("Failed to parse deployments file", file=str(deployments_file), error=str(e))
        return deployments
    
    async def _parse_events(self, mg_root: Path, data: Dict):
        """Parse cluster events"""
        events = []
        
        # Parse cluster-scoped events
        events_file = mg_root / "cluster-scoped-resources" / "core" / "events.yaml"
        if events_file.exists():
            events.extend(await self._parse_events_file(events_file))
        
        # Parse namespace events
        ns_dir = mg_root / "namespaces"
        if ns_dir.exists():
            for ns_path in ns_dir.iterdir():
                if ns_path.is_dir():
                    ns_events_file = ns_path / "core" / "events.yaml"
                    if ns_events_file.exists():
                        ns_events = await self._parse_events_file(ns_events_file)
                        events.extend(ns_events)
        
        data['events'] = events
    
    async def _parse_events_file(self, events_file: Path) -> List[Dict]:
        """Parse events from YAML file"""
        events = []
        try:
            with open(events_file, 'r') as f:
                content = f.read()
                docs = list(yaml.safe_load_all(content))
                for doc in docs:
                    if doc and doc.get('kind') == 'Event':
                        event_info = {
                            'namespace': doc.get('metadata', {}).get('namespace', 'default'),
                            'name': doc.get('metadata', {}).get('name', 'unknown'),
                            'type': doc.get('type', 'Normal'),
                            'reason': doc.get('reason', 'unknown'),
                            'message': doc.get('message', ''),
                            'source': doc.get('source', {}).get('component', 'unknown'),
                            'object': doc.get('involvedObject', {}),
                            'first_timestamp': doc.get('firstTimestamp', ''),
                            'last_timestamp': doc.get('lastTimestamp', ''),
                            'count': doc.get('count', 1)
                        }
                        events.append(event_info)
        except Exception as e:
            logger.warning("Failed to parse events file", file=str(events_file), error=str(e))
        return events
    
    async def _parse_cluster_operators(self, mg_root: Path, data: Dict):
        """Parse cluster operators"""
        operators = []
        
        operators_file = mg_root / "cluster-scoped-resources" / "config.openshift.io" / "clusteroperators.yaml"
        if operators_file.exists():
            try:
                with open(operators_file, 'r') as f:
                    content = f.read()
                    docs = list(yaml.safe_load_all(content))
                    for doc in docs:
                        if doc and doc.get('kind') == 'ClusterOperator':
                            operator_info = {
                                'name': doc.get('metadata', {}).get('name', 'unknown'),
                                'version': self._get_operator_version(doc),
                                'available': self._get_operator_condition(doc, 'Available'),
                                'progressing': self._get_operator_condition(doc, 'Progressing'),
                                'degraded': self._get_operator_condition(doc, 'Degraded'),
                                'conditions': doc.get('status', {}).get('conditions', [])
                            }
                            operators.append(operator_info)
            except Exception as e:
                logger.warning("Failed to parse cluster operators", error=str(e))
        
        data['cluster_operators'] = operators
    
    def _get_operator_version(self, operator_doc: Dict) -> str:
        """Get operator version"""
        versions = operator_doc.get('status', {}).get('versions', [])
        for version in versions:
            if version.get('name') == 'operator':
                return version.get('version', 'unknown')
        return 'unknown'
    
    def _get_operator_condition(self, operator_doc: Dict, condition_type: str) -> bool:
        """Get operator condition status"""
        conditions = operator_doc.get('status', {}).get('conditions', [])
        for condition in conditions:
            if condition.get('type') == condition_type:
                return condition.get('status') == 'True'
        return False
    
    async def _parse_machine_config_pools(self, mg_root: Path, data: Dict):
        """Parse machine config pools"""
        mcps = []
        
        mcps_file = mg_root / "cluster-scoped-resources" / "machineconfiguration.openshift.io" / "machineconfigpools.yaml"
        if mcps_file.exists():
            try:
                with open(mcps_file, 'r') as f:
                    content = f.read()
                    docs = list(yaml.safe_load_all(content))
                    for doc in docs:
                        if doc and doc.get('kind') == 'MachineConfigPool':
                            mcp_info = {
                                'name': doc.get('metadata', {}).get('name', 'unknown'),
                                'machine_count': doc.get('status', {}).get('machineCount', 0),
                                'ready_machine_count': doc.get('status', {}).get('readyMachineCount', 0),
                                'updated_machine_count': doc.get('status', {}).get('updatedMachineCount', 0),
                                'degraded_machine_count': doc.get('status', {}).get('degradedMachineCount', 0),
                                'conditions': doc.get('status', {}).get('conditions', [])
                            }
                            mcps.append(mcp_info)
            except Exception as e:
                logger.warning("Failed to parse machine config pools", error=str(e))
        
        data['machine_config_pools'] = mcps
    
    async def get_parse_summary(self, must_gather_id: str) -> Dict[str, Any]:
        """Get summary of parsed data"""
        from .resources import MustGatherResources
        resources = MustGatherResources(self.config)
        data = await resources.get_parsed_data(must_gather_id)
        
        if not data:
            return {}
        
        summary = {
            'cluster_version': data.get('cluster_info', {}).get('version', 'unknown'),
            'platform': data.get('cluster_info', {}).get('platform', 'unknown'),
            'node_count': len(data.get('nodes', [])),
            'namespace_count': len(data.get('namespaces', {})),
            'total_pods': sum(len(ns.get('pods', [])) for ns in data.get('namespaces', {}).values()),
            'events_count': len(data.get('events', [])),
            'cluster_operators_count': len(data.get('cluster_operators', [])),
            'degraded_operators': len([op for op in data.get('cluster_operators', []) if op.get('degraded', False)]),
            'machine_config_pools': len(data.get('machine_config_pools', []))
        }
        
        return summary
    
    async def extract_resources(self, must_gather_id: str, resource_type: str, 
                              namespace: Optional[str] = None, name: Optional[str] = None) -> List[Dict]:
        """Extract specific resources from parsed data"""
        from .resources import MustGatherResources
        resources = MustGatherResources(self.config)
        data = await resources.get_parsed_data(must_gather_id)
        
        if not data:
            return []
        
        if resource_type == "nodes":
            nodes = data.get('nodes', [])
            if name:
                return [node for node in nodes if node.get('name') == name]
            return nodes
        
        elif resource_type == "pods":
            if namespace:
                return data.get('namespaces', {}).get(namespace, {}).get('pods', [])
            else:
                all_pods = []
                for ns_data in data.get('namespaces', {}).values():
                    all_pods.extend(ns_data.get('pods', []))
                return all_pods
        
        elif resource_type == "events":
            events = data.get('events', [])
            if namespace:
                return [event for event in events if event.get('namespace') == namespace]
            return events
        
        elif resource_type == "services":
            if namespace:
                return data.get('namespaces', {}).get(namespace, {}).get('services', [])
            else:
                all_services = []
                for ns_data in data.get('namespaces', {}).values():
                    all_services.extend(ns_data.get('services', []))
                return all_services
        
        elif resource_type == "deployments":
            if namespace:
                return data.get('namespaces', {}).get(namespace, {}).get('deployments', [])
            else:
                all_deployments = []
                for ns_data in data.get('namespaces', {}).values():
                    all_deployments.extend(ns_data.get('deployments', []))
                return all_deployments
        
        return []
    
    async def get_cluster_info(self, must_gather_id: str) -> Dict[str, Any]:
        """Get cluster information"""
        from .resources import MustGatherResources
        resources = MustGatherResources(self.config)
        data = await resources.get_parsed_data(must_gather_id)
        
        if not data:
            return {}
        
        return data.get('cluster_info', {}) 