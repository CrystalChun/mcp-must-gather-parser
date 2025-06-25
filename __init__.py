"""
OpenShift Must-Gather MCP Server

A Model Context Protocol server for analyzing OpenShift must-gather data.
Provides tools and resources that AI models can use to parse, analyze, 
and extract insights from OpenShift cluster diagnostics.
"""

__version__ = "1.0.0"
__author__ = "OpenShift Team"
__description__ = "Model Context Protocol server for OpenShift must-gather analysis"

from .main import OpenShiftMustGatherMCPServer
from .config import MCPConfig
from .tools import MustGatherTools
from .resources import MustGatherResources

# Make main components easily importable
__all__ = [
    "OpenShiftMustGatherMCPServer",
    "MCPConfig", 
    "MustGatherTools",
    "MustGatherResources",
] 