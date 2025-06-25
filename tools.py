"""
Tools for OpenShift Must-Gather MCP Server
Implements various tools for analyzing OpenShift must-gather data
"""

import asyncio
import json
import tarfile
import tempfile
import yaml
from pathlib import Path
from typing import Any, Dict, List, Optional
import structlog
from mcp.types import Tool, TextContent

from .config import MCPConfig
from .parsers import MustGatherParser
from .analyzers import ClusterAnalyzer, NodeAnalyzer, PodAnalyzer

logger = structlog.get_logger(__name__)


class MustGatherTools:
    """Tools for analyzing OpenShift must-gather data"""
    
    def __init__(self, config: MCPConfig):
        self.config = config
        self.parser = MustGatherParser(config)
        self.cluster_analyzer = ClusterAnalyzer(config)
        self.node_analyzer = NodeAnalyzer(config)
        self.pod_analyzer = PodAnalyzer(config)
        
        # Tool definitions
        self._tools = {
            "parse_must_gather": Tool(
                name="parse_must_gather",
                description="Parse and extract data from an OpenShift must-gather archive",
                inputSchema={
                    "type": "object",
                    "properties": {
                        "file_path": {
                            "type": "string",
                            "description": "Path to the must-gather tar.gz file"
                        },
                        "extract_logs": {
                            "type": "boolean",
                            "description": "Whether to extract pod logs",
                            "default": False
                        }
                    },
                    "required": ["file_path"]
                }
            ),
            "analyze_cluster_health": Tool(
                name="analyze_cluster_health",
                description="Analyze overall cluster health from must-gather data",
                inputSchema={
                    "type": "object",
                    "properties": {
                        "must_gather_id": {
                            "type": "string",
                            "description": "ID of the parsed must-gather data"
                        },
                        "include_degraded_only": {
                            "type": "boolean",
                            "description": "Only include degraded components",
                            "default": False
                        }
                    },
                    "required": ["must_gather_id"]
                }
            ),
            "analyze_node_issues": Tool(
                name="analyze_node_issues",
                description="Analyze node-specific issues and status",
                inputSchema={
                    "type": "object",
                    "properties": {
                        "must_gather_id": {
                            "type": "string",
                            "description": "ID of the parsed must-gather data"
                        },
                        "node_name": {
                            "type": "string",
                            "description": "Specific node to analyze (optional)"
                        }
                    },
                    "required": ["must_gather_id"]
                }
            ),
            "analyze_pod_failures": Tool(
                name="analyze_pod_failures",
                description="Analyze failed or problematic pods",
                inputSchema={
                    "type": "object",
                    "properties": {
                        "must_gather_id": {
                            "type": "string",
                            "description": "ID of the parsed must-gather data"
                        },
                        "namespace": {
                            "type": "string",
                            "description": "Specific namespace to analyze (optional)"
                        },
                        "include_logs": {
                            "type": "boolean",
                            "description": "Include pod logs in analysis",
                            "default": False
                        }
                    },
                    "required": ["must_gather_id"]
                }
            ),
            "extract_resource": Tool(
                name="extract_resource",
                description="Extract specific Kubernetes resources from must-gather",
                inputSchema={
                    "type": "object",
                    "properties": {
                        "must_gather_id": {
                            "type": "string",
                            "description": "ID of the parsed must-gather data"
                        },
                        "resource_type": {
                            "type": "string",
                            "description": "Type of resource (e.g., pods, nodes, events)",
                            "enum": ["pods", "nodes", "events", "deployments", "services", "configmaps", "secrets"]
                        },
                        "namespace": {
                            "type": "string",
                            "description": "Namespace to filter by (optional)"
                        },
                        "name": {
                            "type": "string",
                            "description": "Specific resource name (optional)"
                        }
                    },
                    "required": ["must_gather_id", "resource_type"]
                }
            ),
            "get_cluster_info": Tool(
                name="get_cluster_info",
                description="Get basic cluster information and version details",
                inputSchema={
                    "type": "object",
                    "properties": {
                        "must_gather_id": {
                            "type": "string",
                            "description": "ID of the parsed must-gather data"
                        }
                    },
                    "required": ["must_gather_id"]
                }
            )
        }
    
    async def initialize(self):
        """Initialize the tools"""
        logger.info("Initializing must-gather tools")
        await self.parser.initialize()
    
    async def list_tools(self) -> List[Tool]:
        """Return list of available tools"""
        return list(self._tools.values())
    
    async def call_tool(self, name: str, arguments: Dict[str, Any]) -> List[TextContent]:
        """Call a specific tool with arguments"""
        logger.info("Calling tool", tool_name=name, arguments=arguments)
        
        if name not in self._tools:
            return [TextContent(
                type="text",
                text=f"Error: Unknown tool '{name}'"
            )]
        
        try:
            if name == "parse_must_gather":
                return await self._parse_must_gather(arguments)
            elif name == "analyze_cluster_health":
                return await self._analyze_cluster_health(arguments)
            elif name == "analyze_node_issues":
                return await self._analyze_node_issues(arguments)
            elif name == "analyze_pod_failures":
                return await self._analyze_pod_failures(arguments)
            elif name == "extract_resource":
                return await self._extract_resource(arguments)
            elif name == "get_cluster_info":
                return await self._get_cluster_info(arguments)
            else:
                return [TextContent(
                    type="text",
                    text=f"Error: Tool '{name}' not implemented"
                )]
                
        except Exception as e:
            logger.exception("Tool execution failed", tool_name=name, error=str(e))
            return [TextContent(
                type="text",
                text=f"Error executing tool '{name}': {str(e)}"
            )]
    
    async def _parse_must_gather(self, arguments: Dict[str, Any]) -> List[TextContent]:
        """Parse a must-gather archive"""
        file_path = arguments["file_path"]
        extract_logs = arguments.get("extract_logs", False)
        
        logger.info("Parsing must-gather", file_path=file_path)
        
        # Validate file exists and is readable
        if not Path(file_path).exists():
            return [TextContent(
                type="text",
                text=f"Error: File '{file_path}' does not exist"
            )]
        
        # Parse the must-gather
        must_gather_id = await self.parser.parse_archive(file_path, extract_logs)
        
        # Get summary information
        summary = await self.parser.get_parse_summary(must_gather_id)
        
        result = {
            "must_gather_id": must_gather_id,
            "status": "success",
            "summary": summary
        }
        
        return [TextContent(
            type="text",
            text=f"Successfully parsed must-gather archive.\n\n"
                 f"Must-Gather ID: {must_gather_id}\n"
                 f"Summary:\n{json.dumps(summary, indent=2)}"
        )]
    
    async def _analyze_cluster_health(self, arguments: Dict[str, Any]) -> List[TextContent]:
        """Analyze cluster health"""
        must_gather_id = arguments["must_gather_id"]
        include_degraded_only = arguments.get("include_degraded_only", False)
        
        if not self.config.enable_cluster_analysis:
            return [TextContent(
                type="text",
                text="Cluster analysis is disabled in configuration"
            )]
        
        analysis = await self.cluster_analyzer.analyze(must_gather_id, include_degraded_only)
        
        return [TextContent(
            type="text",
            text=f"Cluster Health Analysis:\n\n{json.dumps(analysis, indent=2)}"
        )]
    
    async def _analyze_node_issues(self, arguments: Dict[str, Any]) -> List[TextContent]:
        """Analyze node issues"""
        must_gather_id = arguments["must_gather_id"]
        node_name = arguments.get("node_name")
        
        if not self.config.enable_node_analysis:
            return [TextContent(
                type="text",
                text="Node analysis is disabled in configuration"
            )]
        
        analysis = await self.node_analyzer.analyze(must_gather_id, node_name)
        
        return [TextContent(
            type="text",
            text=f"Node Analysis:\n\n{json.dumps(analysis, indent=2)}"
        )]
    
    async def _analyze_pod_failures(self, arguments: Dict[str, Any]) -> List[TextContent]:
        """Analyze pod failures"""
        must_gather_id = arguments["must_gather_id"]
        namespace = arguments.get("namespace")
        include_logs = arguments.get("include_logs", False)
        
        if not self.config.enable_pod_analysis:
            return [TextContent(
                type="text",
                text="Pod analysis is disabled in configuration"
            )]
        
        analysis = await self.pod_analyzer.analyze(must_gather_id, namespace, include_logs)
        
        return [TextContent(
            type="text",
            text=f"Pod Failure Analysis:\n\n{json.dumps(analysis, indent=2)}"
        )]
    
    async def _extract_resource(self, arguments: Dict[str, Any]) -> List[TextContent]:
        """Extract specific resources"""
        must_gather_id = arguments["must_gather_id"]
        resource_type = arguments["resource_type"]
        namespace = arguments.get("namespace")
        name = arguments.get("name")
        
        resources = await self.parser.extract_resources(
            must_gather_id, resource_type, namespace, name
        )
        
        return [TextContent(
            type="text",
            text=f"Extracted {resource_type} resources:\n\n{json.dumps(resources, indent=2)}"
        )]
    
    async def _get_cluster_info(self, arguments: Dict[str, Any]) -> List[TextContent]:
        """Get cluster information"""
        must_gather_id = arguments["must_gather_id"]
        
        cluster_info = await self.parser.get_cluster_info(must_gather_id)
        
        return [TextContent(
            type="text",
            text=f"Cluster Information:\n\n{json.dumps(cluster_info, indent=2)}"
        )] 