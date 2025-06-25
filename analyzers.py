"""
Analyzers for OpenShift Must-Gather data
Provides intelligent analysis of cluster health, node issues, and pod failures
"""

from typing import Any, Dict, List, Optional
import structlog

from .config import MCPConfig

logger = structlog.get_logger(__name__)


class BaseAnalyzer:
    """Base class for all analyzers"""
    
    def __init__(self, config: MCPConfig):
        self.config = config


class ClusterAnalyzer(BaseAnalyzer):
    """Analyzer for overall cluster health"""
    
    async def analyze(self, must_gather_id: str, include_degraded_only: bool = False) -> Dict[str, Any]:
        """Analyze cluster health"""
        logger.info("Analyzing cluster health", must_gather_id=must_gather_id)
        
        from .resources import MustGatherResources
        resources = MustGatherResources(self.config)
        data = await resources.get_parsed_data(must_gather_id)
        
        if not data:
            return {"error": "No data found for must-gather ID"}
        
        analysis = {
            "cluster_info": data.get("cluster_info", {}),
            "overall_health": "unknown",
            "critical_issues": [],
            "warnings": [],
            "info": [],
            "cluster_operators": {
                "total": 0,
                "available": 0,
                "degraded": 0,
                "progressing": 0,
                "details": []
            },
            "machine_config_pools": {
                "total": 0,
                "healthy": 0,
                "updating": 0,
                "degraded": 0,
                "details": []
            },
            "nodes": {
                "total": 0,
                "ready": 0,
                "not_ready": 0,
                "issues": []
            }
        }
        
        # Analyze cluster operators
        operators = data.get("cluster_operators", [])
        analysis["cluster_operators"]["total"] = len(operators)
        
        for operator in operators:
            if operator.get("available", False):
                analysis["cluster_operators"]["available"] += 1
            if operator.get("degraded", False):
                analysis["cluster_operators"]["degraded"] += 1
                analysis["critical_issues"].append(f"Cluster operator '{operator['name']}' is degraded")
            if operator.get("progressing", False):
                analysis["cluster_operators"]["progressing"] += 1
                analysis["info"].append(f"Cluster operator '{operator['name']}' is progressing")
            
            if not include_degraded_only or operator.get("degraded", False):
                analysis["cluster_operators"]["details"].append({
                    "name": operator["name"],
                    "available": operator.get("available", False),
                    "degraded": operator.get("degraded", False),
                    "progressing": operator.get("progressing", False),
                    "version": operator.get("version", "unknown")
                })
        
        # Analyze machine config pools
        mcps = data.get("machine_config_pools", [])
        analysis["machine_config_pools"]["total"] = len(mcps)
        
        for mcp in mcps:
            machine_count = mcp.get("machine_count", 0)
            ready_count = mcp.get("ready_machine_count", 0)
            degraded_count = mcp.get("degraded_machine_count", 0)
            
            if degraded_count > 0:
                analysis["machine_config_pools"]["degraded"] += 1
                analysis["critical_issues"].append(f"Machine Config Pool '{mcp['name']}' has {degraded_count} degraded machines")
            elif ready_count == machine_count and machine_count > 0:
                analysis["machine_config_pools"]["healthy"] += 1
            else:
                analysis["machine_config_pools"]["updating"] += 1
                analysis["warnings"].append(f"Machine Config Pool '{mcp['name']}' is updating ({ready_count}/{machine_count} ready)")
            
            if not include_degraded_only or degraded_count > 0:
                analysis["machine_config_pools"]["details"].append({
                    "name": mcp["name"],
                    "machine_count": machine_count,
                    "ready_count": ready_count,
                    "updated_count": mcp.get("updated_machine_count", 0),
                    "degraded_count": degraded_count,
                    "status": "degraded" if degraded_count > 0 else ("healthy" if ready_count == machine_count else "updating")
                })
        
        # Analyze nodes
        nodes = data.get("nodes", [])
        analysis["nodes"]["total"] = len(nodes)
        
        for node in nodes:
            if node.get("status") == "Ready":
                analysis["nodes"]["ready"] += 1
            else:
                analysis["nodes"]["not_ready"] += 1
                analysis["critical_issues"].append(f"Node '{node['name']}' is not ready (status: {node.get('status', 'unknown')})")
                
                # Check for node conditions indicating issues
                conditions = node.get("conditions", [])
                for condition in conditions:
                    if condition.get("type") in ["MemoryPressure", "DiskPressure", "PIDPressure"] and condition.get("status") == "True":
                        analysis["warnings"].append(f"Node '{node['name']}' has {condition['type']}")
                
                analysis["nodes"]["issues"].append({
                    "name": node["name"],
                    "status": node.get("status", "unknown"),
                    "roles": node.get("roles", []),
                    "conditions": conditions
                })
        
        # Determine overall health
        if analysis["critical_issues"]:
            analysis["overall_health"] = "critical"
        elif analysis["warnings"]:
            analysis["overall_health"] = "warning"
        elif analysis["cluster_operators"]["available"] == analysis["cluster_operators"]["total"] and \
             analysis["nodes"]["ready"] == analysis["nodes"]["total"]:
            analysis["overall_health"] = "healthy"
        else:
            analysis["overall_health"] = "degraded"
        
        return analysis


class NodeAnalyzer(BaseAnalyzer):
    """Analyzer for node-specific issues"""
    
    async def analyze(self, must_gather_id: str, node_name: Optional[str] = None) -> Dict[str, Any]:
        """Analyze node issues"""
        logger.info("Analyzing node issues", must_gather_id=must_gather_id, node_name=node_name)
        
        from .resources import MustGatherResources
        resources = MustGatherResources(self.config)
        data = await resources.get_parsed_data(must_gather_id)
        
        if not data:
            return {"error": "No data found for must-gather ID"}
        
        nodes = data.get("nodes", [])
        if node_name:
            nodes = [node for node in nodes if node.get("name") == node_name]
            if not nodes:
                return {"error": f"Node '{node_name}' not found"}
        
        analysis = {
            "total_nodes": len(nodes),
            "node_issues": [],
            "summary": {
                "ready_nodes": 0,
                "not_ready_nodes": 0,
                "nodes_with_pressure": 0,
                "nodes_with_warnings": 0
            }
        }
        
        for node in nodes:
            node_analysis = {
                "name": node.get("name", "unknown"),
                "status": node.get("status", "unknown"),
                "roles": node.get("roles", []),
                "version": node.get("version", "unknown"),
                "os": node.get("os", "unknown"),
                "issues": [],
                "warnings": [],
                "conditions": node.get("conditions", [])
            }
            
            # Check node readiness
            if node.get("status") == "Ready":
                analysis["summary"]["ready_nodes"] += 1
            else:
                analysis["summary"]["not_ready_nodes"] += 1
                node_analysis["issues"].append(f"Node is not ready (status: {node.get('status', 'unknown')})")
            
            # Check node conditions
            has_pressure = False
            has_warnings = False
            
            for condition in node.get("conditions", []):
                condition_type = condition.get("type", "")
                condition_status = condition.get("status", "")
                condition_reason = condition.get("reason", "")
                condition_message = condition.get("message", "")
                
                if condition_type in ["MemoryPressure", "DiskPressure", "PIDPressure"] and condition_status == "True":
                    has_pressure = True
                    node_analysis["issues"].append(f"{condition_type}: {condition_message}")
                
                elif condition_type == "Ready" and condition_status != "True":
                    node_analysis["issues"].append(f"Not Ready: {condition_message}")
                
                elif condition_type in ["NetworkUnavailable"] and condition_status == "True":
                    has_warnings = True
                    node_analysis["warnings"].append(f"Network issues: {condition_message}")
                
                elif condition_reason in ["KubeletNotReady", "ContainerRuntimeNotReady"]:
                    node_analysis["issues"].append(f"{condition_reason}: {condition_message}")
            
            if has_pressure:
                analysis["summary"]["nodes_with_pressure"] += 1
            if has_warnings:
                analysis["summary"]["nodes_with_warnings"] += 1
            
            # Add pod-related issues from events
            events = data.get("events", [])
            node_events = [event for event in events if 
                          event.get("object", {}).get("kind") == "Node" and 
                          event.get("object", {}).get("name") == node.get("name")]
            
            for event in node_events:
                if event.get("type") == "Warning":
                    node_analysis["warnings"].append(f"Event: {event.get('reason', '')}: {event.get('message', '')}")
            
            analysis["node_issues"].append(node_analysis)
        
        return analysis


class PodAnalyzer(BaseAnalyzer):
    """Analyzer for pod failures and issues"""
    
    async def analyze(self, must_gather_id: str, namespace: Optional[str] = None, 
                     include_logs: bool = False) -> Dict[str, Any]:
        """Analyze pod failures"""
        logger.info("Analyzing pod failures", must_gather_id=must_gather_id, namespace=namespace)
        
        from .resources import MustGatherResources
        resources = MustGatherResources(self.config)
        data = await resources.get_parsed_data(must_gather_id)
        
        if not data:
            return {"error": "No data found for must-gather ID"}
        
        analysis = {
            "total_pods": 0,
            "failed_pods": [],
            "warning_pods": [],
            "summary": {
                "running_pods": 0,
                "pending_pods": 0,
                "failed_pods": 0,
                "succeeded_pods": 0,
                "unknown_pods": 0,
                "pods_with_restarts": 0,
                "pods_not_ready": 0
            },
            "namespace_breakdown": {}
        }
        
        namespaces_data = data.get("namespaces", {})
        if namespace:
            namespaces_data = {namespace: namespaces_data.get(namespace, {})}
        
        for ns_name, ns_data in namespaces_data.items():
            pods = ns_data.get("pods", [])
            analysis["total_pods"] += len(pods)
            
            ns_summary = {
                "total": len(pods),
                "running": 0,
                "pending": 0,
                "failed": 0,
                "succeeded": 0,
                "unknown": 0,
                "with_issues": 0
            }
            
            for pod in pods:
                pod_name = pod.get("name", "unknown")
                pod_phase = pod.get("phase", "unknown")
                pod_ready = pod.get("ready", "Unknown")
                pod_restarts = pod.get("restarts", 0)
                containers = pod.get("containers", [])
                
                # Update phase counters
                phase_lower = pod_phase.lower()
                if phase_lower == "running":
                    analysis["summary"]["running_pods"] += 1
                    ns_summary["running"] += 1
                elif phase_lower == "pending":
                    analysis["summary"]["pending_pods"] += 1
                    ns_summary["pending"] += 1
                elif phase_lower == "failed":
                    analysis["summary"]["failed_pods"] += 1
                    ns_summary["failed"] += 1
                elif phase_lower == "succeeded":
                    analysis["summary"]["succeeded_pods"] += 1
                    ns_summary["succeeded"] += 1
                else:
                    analysis["summary"]["unknown_pods"] += 1
                    ns_summary["unknown"] += 1
                
                # Check for issues
                has_issues = False
                pod_issues = []
                pod_warnings = []
                
                # Check if pod is not ready
                if pod_ready == "False":
                    analysis["summary"]["pods_not_ready"] += 1
                    has_issues = True
                    pod_issues.append("Pod is not ready")
                
                # Check for restarts
                if pod_restarts > 0:
                    analysis["summary"]["pods_with_restarts"] += 1
                    if pod_restarts > 5:
                        has_issues = True
                        pod_issues.append(f"High restart count: {pod_restarts}")
                    else:
                        pod_warnings.append(f"Pod has restarted {pod_restarts} times")
                
                # Check container states
                for container in containers:
                    container_name = container.get("name", "unknown")
                    container_ready = container.get("ready", False)
                    container_restarts = container.get("restarts", 0)
                    container_state = container.get("state", "unknown")
                    
                    if not container_ready:
                        has_issues = True
                        pod_issues.append(f"Container '{container_name}' is not ready")
                    
                    if container_state in ["waiting", "terminated"]:
                        has_issues = True
                        pod_issues.append(f"Container '{container_name}' is in {container_state} state")
                    
                    if container_restarts > 10:
                        has_issues = True
                        pod_issues.append(f"Container '{container_name}' has high restart count: {container_restarts}")
                
                # Check for failed or pending states
                if pod_phase in ["Failed", "Pending"]:
                    has_issues = True
                    pod_issues.append(f"Pod is in {pod_phase} state")
                
                # Get related events
                events = data.get("events", [])
                pod_events = [event for event in events if 
                             event.get("object", {}).get("kind") == "Pod" and 
                             event.get("object", {}).get("name") == pod_name and
                             event.get("namespace") == ns_name]
                
                warning_events = [event for event in pod_events if event.get("type") == "Warning"]
                for event in warning_events:
                    event_message = f"{event.get('reason', '')}: {event.get('message', '')}"
                    if event.get("reason") in ["Failed", "FailedMount", "FailedScheduling", "Unhealthy"]:
                        has_issues = True
                        pod_issues.append(f"Event: {event_message}")
                    else:
                        pod_warnings.append(f"Event: {event_message}")
                
                if has_issues:
                    ns_summary["with_issues"] += 1
                    analysis["failed_pods"].append({
                        "namespace": ns_name,
                        "name": pod_name,
                        "phase": pod_phase,
                        "ready": pod_ready,
                        "restarts": pod_restarts,
                        "containers": containers,
                        "issues": pod_issues,
                        "warnings": pod_warnings,
                        "events": warning_events
                    })
                elif pod_warnings:
                    analysis["warning_pods"].append({
                        "namespace": ns_name,
                        "name": pod_name,
                        "phase": pod_phase,
                        "ready": pod_ready,
                        "restarts": pod_restarts,
                        "warnings": pod_warnings
                    })
            
            analysis["namespace_breakdown"][ns_name] = ns_summary
        
        return analysis 