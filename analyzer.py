"""
MCP Analyzer Implementation
Analyzes parsed must-gather data and identifies issues
"""

import logging
from typing import List, Dict, Any, Optional
from datetime import datetime, timedelta

from .models import (
    MCPAnalysisResult,
    MCPIssue,
    MCPStatusInfo,
    MCPCondition,
    NodeInfo,
    MachineConfigInfo,
    ParsedMustGatherData,
    AnalysisConfig
)

logger = logging.getLogger(__name__)


class MCPAnalyzer:
    """Analyzer for MCP must-gather data"""
    
    def __init__(self, config: Optional[AnalysisConfig] = None):
        self.config = config or AnalysisConfig()
    
    def analyze(self, data: ParsedMustGatherData) -> MCPAnalysisResult:
        """
        Analyze parsed must-gather data and return analysis results
        """
        logger.info("Starting MCP analysis")
        
        result = MCPAnalysisResult()
        
        # Set cluster info
        result.cluster_info = {
            "version": data.cluster_version,
            "total_nodes": len(data.nodes),
            "total_mcps": len(data.mcps),
            "total_machine_configs": len(data.machine_configs)
        }
        
        # Convert raw data to structured models
        result.mcps = self._convert_mcps(data.mcps)
        result.nodes = self._convert_nodes(data.nodes)
        result.machine_configs = self._convert_machine_configs(data.machine_configs)
        
        # Perform analysis
        issues = []
        
        if self.config.check_degraded_mcps:
            issues.extend(self._check_degraded_mcps(result.mcps))
        
        if self.config.check_updating_mcps:
            issues.extend(self._check_updating_mcps(result.mcps))
        
        if self.config.check_node_readiness:
            issues.extend(self._check_node_readiness(result.nodes))
        
        if self.config.check_machine_config_drift:
            issues.extend(self._check_machine_config_drift(result.mcps, result.nodes))
        
        # Filter issues by severity threshold
        result.issues = self._filter_issues_by_severity(issues)
        
        # Generate summary
        result.summary = self._generate_summary(result)
        
        logger.info(f"Analysis completed. Found {len(result.issues)} issues.")
        return result
    
    def _convert_mcps(self, raw_mcps: List[Dict[str, Any]]) -> List[MCPStatusInfo]:
        """Convert raw MCP data to MCPStatusInfo objects"""
        mcps = []
        
        for mcp_data in raw_mcps:
            try:
                status = mcp_data.get('status', {})
                conditions = []
                
                for cond_data in status.get('conditions', []):
                    conditions.append(MCPCondition(
                        type=cond_data.get('type', ''),
                        status=cond_data.get('status', ''),
                        reason=cond_data.get('reason'),
                        message=cond_data.get('message')
                    ))
                
                mcp_info = MCPStatusInfo(
                    name=mcp_data.get('metadata', {}).get('name', 'unknown'),
                    ready_machine_count=status.get('readyMachineCount', 0),
                    updated_machine_count=status.get('updatedMachineCount', 0),
                    unavailable_machine_count=status.get('unavailableMachineCount', 0),
                    machine_count=status.get('machineCount', 0),
                    conditions=conditions,
                    configuration=status.get('configuration'),
                    observed_generation=status.get('observedGeneration')
                )
                
                mcps.append(mcp_info)
                
            except Exception as e:
                logger.warning(f"Failed to convert MCP data: {e}")
        
        return mcps
    
    def _convert_nodes(self, raw_nodes: List[Dict[str, Any]]) -> List[NodeInfo]:
        """Convert raw node data to NodeInfo objects"""
        nodes = []
        
        for node_data in raw_nodes:
            try:
                conditions = node_data.get('status', {}).get('conditions', [])
                is_ready = any(
                    cond.get('type') == 'Ready' and cond.get('status') == 'True'
                    for cond in conditions
                )
                
                # Determine MCP name from node labels
                labels = node_data.get('metadata', {}).get('labels', {})
                mcp_name = None
                if 'node-role.kubernetes.io/master' in labels:
                    mcp_name = 'master'
                elif 'node-role.kubernetes.io/worker' in labels:
                    mcp_name = 'worker'
                else:
                    # Look for custom node roles
                    for label_key in labels:
                        if label_key.startswith('node-role.kubernetes.io/'):
                            mcp_name = label_key.split('/')[-1]
                            break
                
                node_info = NodeInfo(
                    name=node_data.get('metadata', {}).get('name', 'unknown'),
                    labels=labels,
                    annotations=node_data.get('metadata', {}).get('annotations', {}),
                    conditions=conditions,
                    ready=is_ready,
                    mcp_name=mcp_name
                )
                
                nodes.append(node_info)
                
            except Exception as e:
                logger.warning(f"Failed to convert node data: {e}")
        
        return nodes
    
    def _convert_machine_configs(self, raw_mcs: List[Dict[str, Any]]) -> List[MachineConfigInfo]:
        """Convert raw machine config data to MachineConfigInfo objects"""
        machine_configs = []
        
        for mc_data in raw_mcs:
            try:
                spec = mc_data.get('spec', {})
                
                mc_info = MachineConfigInfo(
                    name=mc_data.get('metadata', {}).get('name', 'unknown'),
                    generation=mc_data.get('metadata', {}).get('generation'),
                    labels=mc_data.get('metadata', {}).get('labels', {}),
                    files=spec.get('config', {}).get('storage', {}).get('files', []),
                    systemd_units=spec.get('config', {}).get('systemd', {}).get('units', []),
                    kernel_arguments=spec.get('kernelArguments', [])
                )
                
                machine_configs.append(mc_info)
                
            except Exception as e:
                logger.warning(f"Failed to convert machine config data: {e}")
        
        return machine_configs
    
    def _check_degraded_mcps(self, mcps: List[MCPStatusInfo]) -> List[MCPIssue]:
        """Check for degraded MCPs"""
        issues = []
        
        for mcp in mcps:
            degraded_condition = next(
                (cond for cond in mcp.conditions if cond.type == "Degraded"),
                None
            )
            
            if degraded_condition and degraded_condition.status == "True":
                issue = MCPIssue(
                    severity="critical",
                    category="degraded",
                    title=f"MCP {mcp.name} is degraded",
                    description=f"Machine Config Pool '{mcp.name}' is in a degraded state: {degraded_condition.message}",
                    affected_nodes=[],  # TODO: Get affected nodes
                    suggested_actions=[
                        "Check machine-config-daemon logs on affected nodes",
                        "Verify machine config content and syntax",
                        "Check for resource constraints on nodes",
                        "Review recent configuration changes"
                    ]
                )
                issues.append(issue)
        
        return issues
    
    def _check_updating_mcps(self, mcps: List[MCPStatusInfo]) -> List[MCPIssue]:
        """Check for MCPs stuck in updating state"""
        issues = []
        
        for mcp in mcps:
            updating_condition = next(
                (cond for cond in mcp.conditions if cond.type == "Updating"),
                None
            )
            
            if updating_condition and updating_condition.status == "True":
                # Check if it's been updating for too long (> 30 minutes)
                if updating_condition.last_transition_time:
                    time_diff = datetime.now() - updating_condition.last_transition_time
                    if time_diff > timedelta(minutes=30):
                        issue = MCPIssue(
                            severity="warning",
                            category="updating",
                            title=f"MCP {mcp.name} stuck updating",
                            description=f"Machine Config Pool '{mcp.name}' has been updating for {time_diff}: {updating_condition.message}",
                            affected_nodes=[],
                            suggested_actions=[
                                "Check machine-config-daemon logs for errors",
                                "Verify node connectivity and resources",
                                "Check for failed systemd units",
                                "Consider pausing the MCP if necessary"
                            ]
                        )
                        issues.append(issue)
            
            # Check for mismatched machine counts
            if mcp.machine_count > 0 and mcp.updated_machine_count < mcp.machine_count:
                outdated_count = mcp.machine_count - mcp.updated_machine_count
                issue = MCPIssue(
                    severity="warning" if outdated_count <= 2 else "critical",
                    category="updating",
                    title=f"MCP {mcp.name} has outdated machines",
                    description=f"Machine Config Pool '{mcp.name}' has {outdated_count} machines that are not updated",
                    affected_nodes=[],
                    suggested_actions=[
                        "Check individual node status",
                        "Review machine-config-daemon logs",
                        "Verify machine config application"
                    ]
                )
                issues.append(issue)
        
        return issues
    
    def _check_node_readiness(self, nodes: List[NodeInfo]) -> List[MCPIssue]:
        """Check for node readiness issues"""
        issues = []
        
        not_ready_nodes = [node for node in nodes if not node.ready]
        
        if not_ready_nodes:
            for node in not_ready_nodes:
                # Get the reason for not being ready
                not_ready_condition = next(
                    (cond for cond in node.conditions if cond.get('type') == 'Ready'),
                    {}
                )
                
                reason = not_ready_condition.get('reason', 'Unknown')
                message = not_ready_condition.get('message', 'Node is not ready')
                
                issue = MCPIssue(
                    severity="critical",
                    category="nodes",
                    title=f"Node {node.name} is not ready",
                    description=f"Node '{node.name}' is not ready: {message}",
                    affected_nodes=[node.name],
                    suggested_actions=[
                        "Check node logs and system status",
                        "Verify kubelet service status",
                        "Check network connectivity",
                        "Review node resource usage"
                    ]
                )
                issues.append(issue)
        
        return issues
    
    def _check_machine_config_drift(self, mcps: List[MCPStatusInfo], nodes: List[NodeInfo]) -> List[MCPIssue]:
        """Check for machine config drift issues"""
        issues = []
        
        for mcp in mcps:
            if mcp.unavailable_machine_count > 0:
                issue = MCPIssue(
                    severity="warning",
                    category="configuration",
                    title=f"MCP {mcp.name} has unavailable machines",
                    description=f"Machine Config Pool '{mcp.name}' has {mcp.unavailable_machine_count} unavailable machines",
                    affected_nodes=[],
                    suggested_actions=[
                        "Check machine-config-daemon status on affected nodes",
                        "Review recent configuration changes",
                        "Verify node resources and connectivity"
                    ]
                )
                issues.append(issue)
        
        return issues
    
    def _filter_issues_by_severity(self, issues: List[MCPIssue]) -> List[MCPIssue]:
        """Filter issues by severity threshold"""
        severity_order = {"info": 0, "warning": 1, "critical": 2}
        threshold = severity_order.get(self.config.severity_threshold, 1)
        
        return [
            issue for issue in issues
            if severity_order.get(issue.severity, 0) >= threshold
        ]
    
    def _generate_summary(self, result: MCPAnalysisResult) -> Dict[str, Any]:
        """Generate analysis summary"""
        critical_issues = [issue for issue in result.issues if issue.severity == "critical"]
        warning_issues = [issue for issue in result.issues if issue.severity == "warning"]
        info_issues = [issue for issue in result.issues if issue.severity == "info"]
        
        healthy_mcps = []
        degraded_mcps = []
        updating_mcps = []
        
        for mcp in result.mcps:
            is_degraded = any(cond.type == "Degraded" and cond.status == "True" for cond in mcp.conditions)
            is_updating = any(cond.type == "Updating" and cond.status == "True" for cond in mcp.conditions)
            
            if is_degraded:
                degraded_mcps.append(mcp.name)
            elif is_updating:
                updating_mcps.append(mcp.name)
            else:
                healthy_mcps.append(mcp.name)
        
        ready_nodes = [node for node in result.nodes if node.ready]
        not_ready_nodes = [node for node in result.nodes if not node.ready]
        
        return {
            "total_issues": len(result.issues),
            "critical_issues": len(critical_issues),
            "warning_issues": len(warning_issues),
            "info_issues": len(info_issues),
            "mcp_status": {
                "healthy": len(healthy_mcps),
                "degraded": len(degraded_mcps),
                "updating": len(updating_mcps),
                "healthy_mcps": healthy_mcps,
                "degraded_mcps": degraded_mcps,
                "updating_mcps": updating_mcps
            },
            "node_status": {
                "ready": len(ready_nodes),
                "not_ready": len(not_ready_nodes),
                "ready_percentage": len(ready_nodes) / len(result.nodes) * 100 if result.nodes else 0
            },
            "overall_health": "healthy" if not critical_issues else "critical" if critical_issues else "warning"
        } 