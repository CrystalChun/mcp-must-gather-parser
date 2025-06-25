"""
Configuration for OpenShift Must-Gather MCP Server
"""

import os
from dataclasses import dataclass
from pathlib import Path
from typing import Optional
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()


@dataclass
class MCPConfig:
    """Configuration for the MCP server"""
    
    # Server configuration
    server_name: str = "openshift-must-gather"
    server_version: str = "1.0.0"
    
    # Storage configuration
    storage_dir: Path = Path("/tmp/mcp-must-gather")
    max_file_size_mb: int = 500
    
    # Analysis configuration
    enable_cluster_analysis: bool = True
    enable_node_analysis: bool = True
    enable_pod_analysis: bool = True
    enable_log_analysis: bool = False
    
    # Tool configuration
    max_concurrent_operations: int = 5
    operation_timeout_seconds: int = 300
    
    # Logging configuration
    log_level: str = "INFO"
    structured_logging: bool = True
    
    @classmethod
    def from_env(cls) -> "MCPConfig":
        """Create configuration from environment variables"""
        return cls(
            server_name=os.getenv("MCP_SERVER_NAME", "openshift-must-gather"),
            server_version=os.getenv("MCP_SERVER_VERSION", "1.0.0"),
            storage_dir=Path(os.getenv("MCP_STORAGE_DIR", "/tmp/mcp-must-gather")),
            max_file_size_mb=int(os.getenv("MCP_MAX_FILE_SIZE_MB", "500")),
            enable_cluster_analysis=os.getenv("MCP_ENABLE_CLUSTER_ANALYSIS", "true").lower() == "true",
            enable_node_analysis=os.getenv("MCP_ENABLE_NODE_ANALYSIS", "true").lower() == "true",
            enable_pod_analysis=os.getenv("MCP_ENABLE_POD_ANALYSIS", "true").lower() == "true",
            enable_log_analysis=os.getenv("MCP_ENABLE_LOG_ANALYSIS", "false").lower() == "true",
            max_concurrent_operations=int(os.getenv("MCP_MAX_CONCURRENT_OPS", "5")),
            operation_timeout_seconds=int(os.getenv("MCP_OPERATION_TIMEOUT", "300")),
            log_level=os.getenv("MCP_LOG_LEVEL", "INFO"),
            structured_logging=os.getenv("MCP_STRUCTURED_LOGGING", "true").lower() == "true",
        )
    
    def __post_init__(self):
        """Post-initialization setup"""
        # Ensure storage directory exists
        self.storage_dir.mkdir(parents=True, exist_ok=True) 