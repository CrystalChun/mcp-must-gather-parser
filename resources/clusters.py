from pathlib import Path
from typing import List, Dict, Any, Optional
import yaml
import json
import structlog

logger = structlog.get_logger(__name__)

class ClusterParser:
    def __init__(self, must_gather_path: str = None):
        """
        Initialize the ClusterParser with an optional must-gather path.
        
        Args:
            must_gather_path (str, optional): Path to the must-gather directory
        """
        self.must_gather_path = Path(must_gather_path) if must_gather_path else None
        self.logger = logger

    def find_agentclusterinstall_crs(self, must_gather_path: Path = None) -> List[Dict[str, Any]]:
        """
        Find and parse AgentClusterInstall Custom Resources in the must-gather.
        
        AgentClusterInstall CRs are found in:
        - namespaces/<namespace>/extensions.hive.openshift.io/agentclusterinstalls/
        """
        if must_gather_path:
            self.must_gather_path = must_gather_path
        elif not self.must_gather_path:
            raise ValueError("Must provide must_gather_path either in constructor or method call")

        clusters = []
        
        # Look for AgentClusterInstall CRs
        namespaces_path = self.must_gather_path / "namespaces"
        self.logger.info(f"Checking namespaces: {namespaces_path}")
        if namespaces_path.exists():
            for namespace_dir in namespaces_path.iterdir():
                if namespace_dir.is_dir():
                    namespace = namespace_dir.name
                    self.logger.info(f"Checking namespace: {namespace}")
                    # Check for agentclusterinstalls in this namespace
                    ns_cluster_path = namespace_dir / "extensions.hive.openshift.io" / "agentclusterinstalls"
                    self.logger.info(f"Checking agentclusterinstalls in namespace: {ns_cluster_path}")
                    if ns_cluster_path.exists():
                        clusters.extend(self._parse_cluster_files(ns_cluster_path, scope="namespaced", namespace=namespace))
                    else:
                        self.logger.info(f"No agentclusterinstalls found in namespace: {namespace}")

        
        self.logger.info(f"Found {len(clusters)} AgentClusterInstall CRs")
        return clusters

    def _parse_cluster_files(self, clusters_dir: Path, scope: str, namespace: str = None) -> List[Dict[str, Any]]:
        """Parse individual Cluster CR files in a directory."""
        clusters = []
        
        for cluster_file in clusters_dir.iterdir():
            if cluster_file.is_file() and cluster_file.suffix in ['.yaml', '.yml']:
                clusters.extend(self._parse_cluster_yaml_file(cluster_file, scope, namespace))
            
        return clusters

    def _parse_cluster_yaml_file(self, file_path: Path, scope: str, namespace: str = None) -> List[Dict[str, Any]]:
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
                        cluster = self._parse_single_cluster(doc, scope, namespace)
                        if cluster:
                            clusters.append(cluster)
                            
        except Exception as e:
            self.logger.warning(f"Failed to parse {file_path}: {e}")
        
        return clusters

    def _parse_single_cluster(self, cluster_doc: Dict[str, Any], scope: str, namespace: str = None) -> Optional[Dict[str, Any]]:
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
            self.logger.warning(f"Failed to parse cluster document: {e}")
            return None

    def get_failed_clusters(self, must_gather_path: str = None) -> List[Dict[str, Any]]:
        """Find and return a list of failed clusters from the must-gather."""
        if must_gather_path:
            self.must_gather_path = Path(must_gather_path)
        elif not self.must_gather_path:
            raise ValueError("Must provide must_gather_path either in constructor or method call")

        clusters = self.find_agentclusterinstall_crs()
        failed = self._failed_clusters(clusters)
        self.logger.info(f"Found {len(failed)} failed clusters")
        for cluster in failed:
            self.logger.info(f"Cluster {cluster['name']} in namespace {cluster['namespace']} has failed installation.")
            for condition in cluster['status']['conditions']:
                if condition.get('type') == 'Completed':
                    self.logger.info(f"Completed condition: {condition.get('message')}")
        return failed

    def _failed_clusters(self, clusters: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Get a list of clusters that have failed installation."""
        failed_clusters = []
        for cluster in clusters:
            conditions = cluster.get('status', {}).get('conditions', [])
            for condition in conditions:
                if condition.get('type') == 'Completed' and condition.get('status') == 'False' and condition.get('reason') == 'InstallationFailed':
                    failed_clusters.append(cluster)
        return failed_clusters