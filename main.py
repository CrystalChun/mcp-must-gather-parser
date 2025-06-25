#!/usr/bin/env python3
"""
OpenShift Must-Gather MCP Server
A Model Context Protocol server for analyzing OpenShift must-gather data
"""

import asyncio
import os
from typing import Any, Dict, List, Optional
import structlog
from mcp.server import Server
from mcp.types import (
    Resource,
    Tool,
    TextContent,
    ImageContent,
    EmbeddedResource,
    CallToolRequest,
    GetResourceRequest,
    ListResourcesRequest,
    ListToolsRequest,
)

from .tools import MustGatherTools
from .resources import MustGatherResources
from .config import MCPConfig

# Setup logging
logger = structlog.get_logger(__name__)

class OpenShiftMustGatherMCPServer:
    """MCP Server for OpenShift must-gather analysis"""
    
    def __init__(self, config: MCPConfig):
        self.config = config
        self.server = Server("openshift-must-gather")
        self.tools = MustGatherTools(config)
        self.resources = MustGatherResources(config)
        
        # Register handlers
        self._register_handlers()
    
    def _register_handlers(self):
        """Register MCP protocol handlers"""
        
        @self.server.list_tools()
        async def list_tools() -> List[Tool]:
            """List available tools"""
            logger.info("Listing available tools")
            return await self.tools.list_tools()
        
        @self.server.call_tool()
        async def call_tool(name: str, arguments: Dict[str, Any]) -> List[TextContent]:
            """Call a tool with the given arguments"""
            logger.info("Calling tool", tool_name=name, arguments=arguments)
            return await self.tools.call_tool(name, arguments)
        
        @self.server.list_resources()
        async def list_resources() -> List[Resource]:
            """List available resources"""
            logger.info("Listing available resources")
            return await self.resources.list_resources()
        
        @self.server.read_resource()
        async def read_resource(uri: str) -> str:
            """Read a specific resource"""
            logger.info("Reading resource", uri=uri)
            return await self.resources.read_resource(uri)
    
    async def run(self):
        """Run the MCP server"""
        logger.info("Starting OpenShift Must-Gather MCP Server")
        
        # Initialize tools and resources
        await self.tools.initialize()
        await self.resources.initialize()
        
        # Run the server
        async with self.server.create_session() as session:
            await session.run()


async def main():
    """Main entry point"""
    # Load configuration
    config = MCPConfig.from_env()
    
    # Create and run server
    server = OpenShiftMustGatherMCPServer(config)
    await server.run()


if __name__ == "__main__":
    asyncio.run(main()) 