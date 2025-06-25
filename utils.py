"""
Utility functions for MCP Must-Gather Parser
"""

import logging
import sys
from pathlib import Path
from typing import Dict, Any, Optional


def setup_logging(level: str = "INFO", log_file: Optional[str] = None):
    """Setup logging configuration"""
    log_level = getattr(logging, level.upper(), logging.INFO)
    
    # Create formatter
    formatter = logging.Formatter(
        '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )
    
    # Setup handlers
    handlers = [logging.StreamHandler(sys.stdout)]
    
    if log_file:
        handlers.append(logging.FileHandler(log_file))
    
    # Configure logging
    logging.basicConfig(
        level=log_level,
        handlers=handlers,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )
    
    # Set specific logger levels
    logging.getLogger('uvicorn').setLevel(logging.WARNING)
    logging.getLogger('fastapi').setLevel(logging.WARNING)
    

def validate_must_gather_structure(directory: Path) -> bool:
    """
    Validate that the directory contains a valid must-gather structure
    """
    if not directory.exists() or not directory.is_dir():
        return False
    
    # Look for must-gather directories
    must_gather_dirs = list(directory.glob("must-gather*"))
    if not must_gather_dirs:
        return False
    
    # Check for expected subdirectories
    cluster_dir = must_gather_dirs[0]
    expected_paths = [
        cluster_dir / "cluster-scoped-resources",
        cluster_dir / "namespaces"
    ]
    
    return all(path.exists() for path in expected_paths)


def get_file_size_mb(file_path: str) -> float:
    """Get file size in MB"""
    try:
        return Path(file_path).stat().st_size / (1024 * 1024)
    except Exception:
        return 0.0


def sanitize_filename(filename: str) -> str:
    """Sanitize filename for safe storage"""
    import re
    # Remove or replace unsafe characters
    filename = re.sub(r'[<>:"/\\|?*]', '_', filename)
    # Limit length
    if len(filename) > 255:
        name, ext = filename.rsplit('.', 1) if '.' in filename else (filename, '')
        max_name_len = 255 - len(ext) - 1 if ext else 255
        filename = name[:max_name_len] + ('.' + ext if ext else '')
    
    return filename


def format_bytes(bytes_value: int) -> str:
    """Format bytes as human readable string"""
    for unit in ['B', 'KB', 'MB', 'GB', 'TB']:
        if bytes_value < 1024.0:
            return f"{bytes_value:.1f} {unit}"
        bytes_value /= 1024.0
    return f"{bytes_value:.1f} PB"


def extract_namespace_from_path(path: str) -> Optional[str]:
    """Extract namespace from a file path"""
    parts = Path(path).parts
    try:
        namespaces_idx = parts.index('namespaces')
        if namespaces_idx + 1 < len(parts):
            return parts[namespaces_idx + 1]
    except ValueError:
        pass
    return None


def is_mcp_related_resource(resource_path: str) -> bool:
    """Check if a resource path is related to MCPs"""
    mcp_indicators = [
        'machineconfiguration.openshift.io',
        'machine-config',
        'machineconfig',
        'mcp',
        'machineconfigpool'
    ]
    
    path_lower = resource_path.lower()
    return any(indicator in path_lower for indicator in mcp_indicators)


def parse_kubernetes_timestamp(timestamp_str: str) -> Optional[datetime]:
    """Parse Kubernetes timestamp string to datetime"""
    from datetime import datetime
    import dateutil.parser
    
    try:
        return dateutil.parser.parse(timestamp_str)
    except Exception:
        return None


def create_temp_directory(prefix: str = "mcp_parser_") -> Path:
    """Create a temporary directory with cleanup"""
    import tempfile
    return Path(tempfile.mkdtemp(prefix=prefix))


class TempDirContext:
    """Context manager for temporary directories"""
    
    def __init__(self, prefix: str = "mcp_parser_"):
        self.prefix = prefix
        self.temp_dir = None
    
    def __enter__(self) -> Path:
        self.temp_dir = create_temp_directory(self.prefix)
        return self.temp_dir
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        if self.temp_dir and self.temp_dir.exists():
            import shutil
            shutil.rmtree(self.temp_dir, ignore_errors=True)


def get_node_role_from_labels(labels: Dict[str, str]) -> Optional[str]:
    """Extract node role from labels"""
    for label_key in labels:
        if label_key.startswith('node-role.kubernetes.io/'):
            role = label_key.split('/')[-1]
            if role != '':  # Some roles might be empty string values
                return role
    return None


def filter_recent_events(events: list, hours: int = 24) -> list:
    """Filter events from the last N hours"""
    from datetime import datetime, timedelta
    
    cutoff_time = datetime.now() - timedelta(hours=hours)
    recent_events = []
    
    for event in events:
        event_time_str = event.get('metadata', {}).get('creationTimestamp')
        if event_time_str:
            event_time = parse_kubernetes_timestamp(event_time_str)
            if event_time and event_time > cutoff_time:
                recent_events.append(event)
    
    return recent_events


def extract_error_from_condition(condition: Dict[str, Any]) -> Optional[str]:
    """Extract error message from a condition"""
    if condition.get('status') == 'False' or condition.get('status') == 'True':
        message = condition.get('message', '')
        reason = condition.get('reason', '')
        
        if 'error' in message.lower() or 'failed' in message.lower():
            return f"{reason}: {message}" if reason else message
    
    return None


def group_by_severity(issues: list) -> Dict[str, list]:
    """Group issues by severity level"""
    grouped = {"critical": [], "warning": [], "info": []}
    
    for issue in issues:
        severity = getattr(issue, 'severity', 'info')
        if severity in grouped:
            grouped[severity].append(issue)
    
    return grouped


def calculate_health_score(mcps: list, nodes: list, issues: list) -> int:
    """Calculate overall health score (0-100)"""
    if not mcps and not nodes:
        return 100  # No resources to evaluate
    
    score = 100
    
    # Deduct for critical issues
    critical_issues = [i for i in issues if getattr(i, 'severity', '') == 'critical']
    score -= len(critical_issues) * 20
    
    # Deduct for warning issues
    warning_issues = [i for i in issues if getattr(i, 'severity', '') == 'warning']
    score -= len(warning_issues) * 5
    
    # Deduct for not ready nodes
    if nodes:
        not_ready_nodes = [n for n in nodes if not getattr(n, 'ready', True)]
        not_ready_percentage = len(not_ready_nodes) / len(nodes)
        score -= int(not_ready_percentage * 30)
    
    return max(0, min(100, score))


def create_summary_report(analysis_result) -> str:
    """Create a text summary report"""
    summary = analysis_result.summary
    
    report_lines = [
        "=== MCP Must-Gather Analysis Report ===",
        f"Timestamp: {analysis_result.timestamp}",
        f"Cluster Version: {analysis_result.cluster_info.get('version', 'Unknown')}",
        "",
        "=== Summary ===",
        f"Total Issues: {summary['total_issues']}",
        f"  - Critical: {summary['critical_issues']}",
        f"  - Warning: {summary['warning_issues']}",
        f"  - Info: {summary['info_issues']}",
        "",
        "=== MCP Status ===",
        f"Healthy MCPs: {summary['mcp_status']['healthy']} ({', '.join(summary['mcp_status']['healthy_mcps'])})",
        f"Degraded MCPs: {summary['mcp_status']['degraded']} ({', '.join(summary['mcp_status']['degraded_mcps'])})",
        f"Updating MCPs: {summary['mcp_status']['updating']} ({', '.join(summary['mcp_status']['updating_mcps'])})",
        "",
        "=== Node Status ===",
        f"Ready Nodes: {summary['node_status']['ready']}",
        f"Not Ready Nodes: {summary['node_status']['not_ready']}",
        f"Ready Percentage: {summary['node_status']['ready_percentage']:.1f}%",
        "",
        f"Overall Health: {summary['overall_health'].upper()}",
    ]
    
    if analysis_result.issues:
        report_lines.extend([
            "",
            "=== Issues Details ===",
        ])
        
        for issue in analysis_result.issues:
            report_lines.extend([
                f"[{issue.severity.upper()}] {issue.title}",
                f"  Category: {issue.category}",
                f"  Description: {issue.description}",
                f"  Affected Nodes: {', '.join(issue.affected_nodes) if issue.affected_nodes else 'None'}",
                f"  Suggested Actions:",
            ])
            for action in issue.suggested_actions:
                report_lines.append(f"    - {action}")
            report_lines.append("")
    
    return "\n".join(report_lines) 