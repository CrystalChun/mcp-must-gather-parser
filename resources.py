"""
Resources for OpenShift Must-Gather MCP Server
Exposes must-gather data as MCP resources
"""

import json
from pathlib import Path
from typing import Dict, List, Optional
import structlog
from mcp.types import Resource

from .config import MCPConfig

logger = structlog.get_logger(__name__)


class MustGatherResources:
    """Manages MCP resources for must-gather data"""
    
    def __init__(self, config: MCPConfig):
        self.config = config
        self._parsed_data: Dict[str, Dict] = {}
    
    async def initialize(self):
        """Initialize the resources manager"""
        logger.info("Initializing must-gather resources")
        # Load any existing parsed data from storage
        await self._load_existing_data()
    
    async def list_resources(self) -> List[Resource]:
        """List available resources"""
        resources = []
        
        for must_gather_id, data in self._parsed_data.items():
            # Main cluster info resource
            resources.append(Resource(
                uri=f"must-gather://{must_gather_id}/cluster-info",
                name=f"Cluster Info - {must_gather_id}",
                description=f"Basic cluster information for must-gather {must_gather_id}",
                mimeType="application/json"
            ))
            
            # Nodes resource
            if "nodes" in data:
                resources.append(Resource(
                    uri=f"must-gather://{must_gather_id}/nodes",
                    name=f"Nodes - {must_gather_id}",
                    description=f"Node information for must-gather {must_gather_id}",
                    mimeType="application/json"
                ))
            
            # Pods resource by namespace
            if "namespaces" in data:
                for namespace in data["namespaces"]:
                    resources.append(Resource(
                        uri=f"must-gather://{must_gather_id}/pods/{namespace}",
                        name=f"Pods in {namespace} - {must_gather_id}",
                        description=f"Pod information for namespace {namespace} in must-gather {must_gather_id}",
                        mimeType="application/json"
                    ))
            
            # Events resource
            if "events" in data:
                resources.append(Resource(
                    uri=f"must-gather://{must_gather_id}/events",
                    name=f"Events - {must_gather_id}",
                    description=f"Cluster events for must-gather {must_gather_id}",
                    mimeType="application/json"
                ))
            
            # Cluster operators resource
            if "cluster_operators" in data:
                resources.append(Resource(
                    uri=f"must-gather://{must_gather_id}/cluster-operators",
                    name=f"Cluster Operators - {must_gather_id}",
                    description=f"Cluster operator status for must-gather {must_gather_id}",
                    mimeType="application/json"
                ))
            
            # Machine config pools resource
            if "machine_config_pools" in data:
                resources.append(Resource(
                    uri=f"must-gather://{must_gather_id}/machine-config-pools",
                    name=f"Machine Config Pools - {must_gather_id}",
                    description=f"Machine config pool status for must-gather {must_gather_id}",
                    mimeType="application/json"
                ))
            
            # Analysis results resource
            resources.append(Resource(
                uri=f"must-gather://{must_gather_id}/analysis",
                name=f"Analysis Results - {must_gather_id}",
                description=f"Analysis results for must-gather {must_gather_id}",
                mimeType="application/json"
            ))
        
        return resources
    
    async def read_resource(self, uri: str) -> str:
        """Read a specific resource"""
        logger.info("Reading resource", uri=uri)
        
        # Parse the URI
        if not uri.startswith("must-gather://"):
            raise ValueError(f"Invalid resource URI: {uri}")
        
        path_parts = uri[14:].split("/")  # Remove "must-gather://" prefix
        if len(path_parts) < 2:
            raise ValueError(f"Invalid resource URI format: {uri}")
        
        must_gather_id = path_parts[0]
        resource_type = path_parts[1]
        
        if must_gather_id not in self._parsed_data:
            raise ValueError(f"Must-gather {must_gather_id} not found")
        
        data = self._parsed_data[must_gather_id]
        
        try:
            if resource_type == "cluster-info":
                return json.dumps(data.get("cluster_info", {}), indent=2)
            
            elif resource_type == "nodes":
                return json.dumps(data.get("nodes", []), indent=2)
            
            elif resource_type == "pods" and len(path_parts) >= 3:
                namespace = path_parts[2]
                pods = data.get("namespaces", {}).get(namespace, {}).get("pods", [])
                return json.dumps(pods, indent=2)
            
            elif resource_type == "events":
                return json.dumps(data.get("events", []), indent=2)
            
            elif resource_type == "cluster-operators":
                return json.dumps(data.get("cluster_operators", []), indent=2)
            
            elif resource_type == "machine-config-pools":
                return json.dumps(data.get("machine_config_pools", []), indent=2)
            
            elif resource_type == "analysis":
                return json.dumps(data.get("analysis", {}), indent=2)
            
            else:
                raise ValueError(f"Unknown resource type: {resource_type}")
                
        except Exception as e:
            logger.exception("Failed to read resource", uri=uri, error=str(e))
            raise ValueError(f"Failed to read resource {uri}: {str(e)}")
    
    async def add_parsed_data(self, must_gather_id: str, data: Dict):
        """Add parsed must-gather data"""
        logger.info("Adding parsed data", must_gather_id=must_gather_id)
        self._parsed_data[must_gather_id] = data
        
        # Persist to storage
        await self._save_data(must_gather_id, data)
    
    async def get_parsed_data(self, must_gather_id: str) -> Optional[Dict]:
        """Get parsed data for a specific must-gather"""
        return self._parsed_data.get(must_gather_id)
    
    async def remove_parsed_data(self, must_gather_id: str):
        """Remove parsed data"""
        if must_gather_id in self._parsed_data:
            del self._parsed_data[must_gather_id]
            # Remove from storage
            storage_file = self.config.storage_dir / f"{must_gather_id}.json"
            if storage_file.exists():
                storage_file.unlink()
    
    async def list_parsed_data(self) -> List[str]:
        """List all parsed must-gather IDs"""
        return list(self._parsed_data.keys())
    
    async def _load_existing_data(self):
        """Load existing parsed data from storage"""
        if not self.config.storage_dir.exists():
            return
        
        for json_file in self.config.storage_dir.glob("*.json"):
            try:
                must_gather_id = json_file.stem
                with open(json_file, 'r') as f:
                    data = json.load(f)
                self._parsed_data[must_gather_id] = data
                logger.info("Loaded existing data", must_gather_id=must_gather_id)
            except Exception as e:
                logger.warning("Failed to load data file", file=str(json_file), error=str(e))
    
    async def _save_data(self, must_gather_id: str, data: Dict):
        """Save parsed data to storage"""
        try:
            storage_file = self.config.storage_dir / f"{must_gather_id}.json"
            with open(storage_file, 'w') as f:
                json.dump(data, f, indent=2, default=str)
            logger.info("Saved data to storage", must_gather_id=must_gather_id)
        except Exception as e:
            logger.warning("Failed to save data", must_gather_id=must_gather_id, error=str(e)) 