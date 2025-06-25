"""
Data models for OpenShift Must-Gather MCP Server
"""

from dataclasses import dataclass
from typing import Any, Dict, List, Optional
from pydantic import BaseModel


@dataclass
class ClusterInfo:
    """Basic cluster information"""
    version: str
    cluster_id: str
    platform: str
    region: Optional[str] = None


@dataclass
class NodeInfo:
    """Node information"""
    name: str
    roles: List[str]
    status: str
    version: str
    os: str
    conditions: List[Dict[str, Any]]


@dataclass
class PodInfo:
    """Pod information"""
    name: str
    namespace: str
    phase: str
    ready: str
    restarts: int
    containers: List[Dict[str, Any]]


@dataclass
class EventInfo:
    """Event information"""
    namespace: str
    name: str
    type: str
    reason: str 
    message: str
    source: str
    object: Dict[str, Any]
    first_timestamp: str
    last_timestamp: str
    count: int


@dataclass
class OperatorInfo:
    """Cluster operator information"""
    name: str
    version: str
    available: bool
    progressing: bool
    degraded: bool
    conditions: List[Dict[str, Any]]


@dataclass
class MCPInfo:
    """Machine Config Pool information"""
    name: str
    machine_count: int
    ready_machine_count: int
    updated_machine_count: int
    degraded_machine_count: int
    conditions: List[Dict[str, Any]]


# For backward compatibility, we can keep some simple Pydantic models
class AnalysisResult(BaseModel):
    """Analysis result model"""
    status: str
    summary: Dict[str, Any]
    issues: List[Dict[str, Any]]
    recommendations: List[str] 