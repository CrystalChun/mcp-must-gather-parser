"""
MCP Must-Gather Parser Implementation
"""

import os
import json
import yaml
import tarfile
import logging
from pathlib import Path
from typing import List, Dict, Any, Optional
import tempfile
import asyncio
from concurrent.futures import ThreadPoolExecutor

from .models import (
    ParsedMustGatherData,
    MCPStatusInfo,
    MCPConfig,
    MCPSelector,
    MCPCondition,
    NodeInfo,
    MachineConfigInfo
)

logger = logging.getLogger(__name__)


class MCPMustGatherParser:
    """Parser for MCP must-gather data"""
    
    def __init__(self):
        self.executor = ThreadPoolExecutor(max_workers=4)
        self.current_data: Optional[ParsedMustGatherData] = None
    
    async def parse_must_gather(self, file_path: str) -> ParsedMustGatherData:
        """
        Parse a must-gather tar.gz file and extract MCP-related data
        """
        logger.info(f"Starting to parse must-gather file: {file_path}")
        
        # Extract the tar.gz file
        with tempfile.TemporaryDirectory() as temp_dir:
            await self._extract_tarfile(file_path, temp_dir)
            
            # Parse the extracted content
            parsed_data = await self._parse_directory(temp_dir)
            
        self.current_data = parsed_data
        logger.info("Must-gather parsing completed")
        return parsed_data
    
    async def _extract_tarfile(self, file_path: str, extract_dir: str):
        """Extract tar.gz file asynchronously"""
        def _extract():
            with tarfile.open(file_path, 'r:gz') as tar:
                tar.extractall(extract_dir)
        
        loop = asyncio.get_event_loop()
        await loop.run_in_executor(self.executor, _extract)
    
    async def _parse_directory(self, directory: str) -> ParsedMustGatherData:
        """Parse the extracted must-gather directory"""
        parsed_data = ParsedMustGatherData()
        
        # Find the cluster directory (usually follows pattern like must-gather.local.xxx)
        cluster_dirs = [d for d in os.listdir(directory) if d.startswith('must-gather')]
        if not cluster_dirs:
            raise ValueError("No must-gather directory found in archive")
        
        cluster_dir = os.path.join(directory, cluster_dirs[0])
        
        # Parse different resource types
        await asyncio.gather(
            self._parse_cluster_info(cluster_dir, parsed_data),
            self._parse_mcps(cluster_dir, parsed_data),
            self._parse_nodes(cluster_dir, parsed_data),
            self._parse_machine_configs(cluster_dir, parsed_data),
            self._parse_events(cluster_dir, parsed_data),
            self._parse_logs(cluster_dir, parsed_data)
        )
        
        return parsed_data
    
    async def _parse_cluster_info(self, cluster_dir: str, parsed_data: ParsedMustGatherData):
        """Parse cluster version and basic info"""
        try:
            cv_path = os.path.join(cluster_dir, "cluster-scoped-resources", "config.openshift.io", "clusterversions")
            if os.path.exists(cv_path):
                for file in os.listdir(cv_path):
                    if file.endswith('.yaml'):
                        with open(os.path.join(cv_path, file), 'r') as f:
                            cv_data = yaml.safe_load(f)
                            if cv_data and cv_data.get('status', {}).get('desired', {}).get('version'):
                                parsed_data.cluster_version = cv_data['status']['desired']['version']
                                break
        except Exception as e:
            logger.warning(f"Failed to parse cluster version: {e}")
    
    async def _parse_mcps(self, cluster_dir: str, parsed_data: ParsedMustGatherData):
        """Parse Machine Config Pools"""
        try:
            mcp_path = os.path.join(cluster_dir, "cluster-scoped-resources", "machineconfiguration.openshift.io", "machineconfigpools")
            if os.path.exists(mcp_path):
                for file in os.listdir(mcp_path):
                    if file.endswith('.yaml'):
                        with open(os.path.join(mcp_path, file), 'r') as f:
                            mcp_data = yaml.safe_load(f)
                            if mcp_data:
                                parsed_data.mcps.append(mcp_data)
        except Exception as e:
            logger.error(f"Failed to parse MCPs: {e}")
    
    async def _parse_nodes(self, cluster_dir: str, parsed_data: ParsedMustGatherData):
        """Parse Node resources"""
        try:
            nodes_path = os.path.join(cluster_dir, "cluster-scoped-resources", "core", "nodes")
            if os.path.exists(nodes_path):
                for file in os.listdir(nodes_path):
                    if file.endswith('.yaml'):
                        with open(os.path.join(nodes_path, file), 'r') as f:
                            node_data = yaml.safe_load(f)
                            if node_data:
                                parsed_data.nodes.append(node_data)
        except Exception as e:
            logger.error(f"Failed to parse nodes: {e}")
    
    async def _parse_machine_configs(self, cluster_dir: str, parsed_data: ParsedMustGatherData):
        """Parse Machine Configs"""
        try:
            mc_path = os.path.join(cluster_dir, "cluster-scoped-resources", "machineconfiguration.openshift.io", "machineconfigs")
            if os.path.exists(mc_path):
                for file in os.listdir(mc_path):
                    if file.endswith('.yaml'):
                        with open(os.path.join(mc_path, file), 'r') as f:
                            mc_data = yaml.safe_load(f)
                            if mc_data:
                                parsed_data.machine_configs.append(mc_data)
        except Exception as e:
            logger.error(f"Failed to parse machine configs: {e}")
    
    async def _parse_events(self, cluster_dir: str, parsed_data: ParsedMustGatherData):
        """Parse cluster events"""
        try:
            # Parse events from different namespaces
            namespaces_dir = os.path.join(cluster_dir, "namespaces")
            if os.path.exists(namespaces_dir):
                for namespace in os.listdir(namespaces_dir):
                    events_path = os.path.join(namespaces_dir, namespace, "core", "events")
                    if os.path.exists(events_path):
                        for file in os.listdir(events_path):
                            if file.endswith('.yaml'):
                                with open(os.path.join(events_path, file), 'r') as f:
                                    event_data = yaml.safe_load(f)
                                    if event_data:
                                        parsed_data.events.append(event_data)
        except Exception as e:
            logger.warning(f"Failed to parse events: {e}")
    
    async def _parse_logs(self, cluster_dir: str, parsed_data: ParsedMustGatherData):
        """Parse relevant logs"""
        try:
            # Look for machine-config-daemon logs
            pods_dirs = []
            namespaces_dir = os.path.join(cluster_dir, "namespaces")
            if os.path.exists(namespaces_dir):
                for namespace in os.listdir(namespaces_dir):
                    pods_dir = os.path.join(namespaces_dir, namespace, "pods")
                    if os.path.exists(pods_dir):
                        pods_dirs.append((namespace, pods_dir))
            
            for namespace, pods_dir in pods_dirs:
                for pod_dir in os.listdir(pods_dir):
                    if 'machine-config-daemon' in pod_dir or 'machine-config-controller' in pod_dir:
                        logs_dir = os.path.join(pods_dir, pod_dir, "logs")
                        if os.path.exists(logs_dir):
                            log_key = f"{namespace}/{pod_dir}"
                            parsed_data.logs[log_key] = []
                            for log_file in os.listdir(logs_dir):
                                if log_file.endswith('.log'):
                                    log_path = os.path.join(logs_dir, log_file)
                                    with open(log_path, 'r') as f:
                                        parsed_data.logs[log_key].extend(f.readlines())
        except Exception as e:
            logger.warning(f"Failed to parse logs: {e}")
    
    async def get_mcp_status(self, mcp_name: str) -> Optional[MCPStatusInfo]:
        """Get status for a specific MCP"""
        if not self.current_data:
            return None
        
        for mcp_data in self.current_data.mcps:
            if mcp_data.get('metadata', {}).get('name') == mcp_name:
                return self._convert_mcp_to_status(mcp_data)
        
        return None
    
    async def list_mcps(self) -> List[str]:
        """List all available MCPs"""
        if not self.current_data:
            return []
        
        return [mcp.get('metadata', {}).get('name', 'unknown') for mcp in self.current_data.mcps]
    
    async def get_mcp_config(self, mcp_name: str) -> Optional[MCPConfig]:
        """Get configuration for a specific MCP"""
        if not self.current_data:
            return None
        
        for mcp_data in self.current_data.mcps:
            if mcp_data.get('metadata', {}).get('name') == mcp_name:
                return self._convert_mcp_to_config(mcp_data)
        
        return None
    
    async def get_mcp_nodes(self, mcp_name: str) -> List[str]:
        """Get nodes associated with a specific MCP"""
        if not self.current_data:
            return []
        
        # Get MCP selector
        mcp_config = await self.get_mcp_config(mcp_name)
        if not mcp_config:
            return []
        
        # Find matching nodes
        matching_nodes = []
        for node_data in self.current_data.nodes:
            node_labels = node_data.get('metadata', {}).get('labels', {})
            if self._node_matches_selector(node_labels, mcp_config.node_selector):
                matching_nodes.append(node_data.get('metadata', {}).get('name', 'unknown'))
        
        return matching_nodes
    
    def _convert_mcp_to_status(self, mcp_data: Dict[str, Any]) -> MCPStatusInfo:
        """Convert raw MCP data to MCPStatusInfo"""
        status = mcp_data.get('status', {})
        
        conditions = []
        for cond_data in status.get('conditions', []):
            conditions.append(MCPCondition(
                type=cond_data.get('type', ''),
                status=cond_data.get('status', ''),
                reason=cond_data.get('reason'),
                message=cond_data.get('message')
            ))
        
        return MCPStatusInfo(
            name=mcp_data.get('metadata', {}).get('name', 'unknown'),
            ready_machine_count=status.get('readyMachineCount', 0),
            updated_machine_count=status.get('updatedMachineCount', 0),
            unavailable_machine_count=status.get('unavailableMachineCount', 0),
            machine_count=status.get('machineCount', 0),
            conditions=conditions,
            configuration=status.get('configuration'),
            observed_generation=status.get('observedGeneration')
        )
    
    def _convert_mcp_to_config(self, mcp_data: Dict[str, Any]) -> MCPConfig:
        """Convert raw MCP data to MCPConfig"""
        spec = mcp_data.get('spec', {})
        
        node_selector = MCPSelector(
            match_labels=spec.get('nodeSelector', {}).get('matchLabels', {}),
            match_expressions=spec.get('nodeSelector', {}).get('matchExpressions', [])
        )
        
        mc_selector = MCPSelector(
            match_labels=spec.get('machineConfigSelector', {}).get('matchLabels', {}),
            match_expressions=spec.get('machineConfigSelector', {}).get('matchExpressions', [])
        )
        
        return MCPConfig(
            name=mcp_data.get('metadata', {}).get('name', 'unknown'),
            node_selector=node_selector,
            machine_config_selector=mc_selector,
            max_unavailable=spec.get('maxUnavailable'),
            paused=spec.get('paused', False),
            generation=mcp_data.get('metadata', {}).get('generation')
        )
    
    def _node_matches_selector(self, node_labels: Dict[str, str], selector: MCPSelector) -> bool:
        """Check if a node matches the MCP selector"""
        # Check match labels
        for key, value in selector.match_labels.items():
            if node_labels.get(key) != value:
                return False
        
        # TODO: Implement match expressions logic if needed
        
        return True 