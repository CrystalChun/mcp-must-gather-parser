from pathlib import Path
from typing import List, Dict, Any, Optional
import structlog
import json
import re
from datetime import datetime
from resources.tools import sanitize_data

logger = structlog.get_logger(__name__)

class LogParser:
    def __init__(self, must_gather_path: str = None):
        """
        Initialize the LogParser with an optional must-gather path.
        
        Args:
            must_gather_path (str, optional): Path to the must-gather directory
        """
        self.must_gather_path = Path(must_gather_path) if must_gather_path else None
        self.logger = logger

    def find_pod_logs(self, must_gather_path: Path = None, pod_name: str = None, namespace: str = None, cluster_name: str = None) -> List[Dict[str, Any]]:
        """
        Find and parse pod logs in the must-gather.
        
        Pod logs are found in:
        - namespaces/<namespace>/pods/<pod>/logs/
        - namespaces/<namespace>/pods/<pod>/logs/previous/
        """
        if must_gather_path:
            self.must_gather_path = must_gather_path
        elif not self.must_gather_path:
            raise ValueError("Must provide must_gather_path either in constructor or method call")

        logs = []
        
        # Look for pod logs
        namespaces_path = self.must_gather_path / "namespaces"
        if namespaces_path.exists():
            for namespace_dir in namespaces_path.iterdir():
                if namespace_dir.is_dir() and (namespace is None or namespace_dir.name.startswith(namespace)):
                    namespace = namespace_dir.name
                    # Check for pods in this namespace
                    pods_path = namespace_dir / "pods"
                    self.logger.info(f"Checking pods in namespace: {pods_path}")
                    if pods_path.exists():
                        for pod_dir in pods_path.iterdir():
                            if pod_dir.is_dir() and (pod_name is None or pod_dir.name.startswith(pod_name)):
                                pod_logs_dir = self.find_pod_logs_directory(pod_dir)
                                if pod_logs_dir:
                                    self.logger.info(f"Parsing logs for pod {pod_dir.name} in namespace {namespace} using logs directory {pod_logs_dir}")
                                    logs.extend(self._parse_pod_logs(pod_logs_dir, namespace, pod_dir.name, is_previous=False, cluster_name=cluster_name))
        
        self.logger.info(f"Found {len(logs)} pod log entries")
        return logs

    def find_pod_directory(self, pod_name: str = '', namespace: str = '') -> Path:
        """Find the pod directory in the must-gather."""
        # Look for pod logs
        namespaces_path = self.must_gather_path / "namespaces"
        if namespaces_path.exists():
            for namespace_dir in namespaces_path.iterdir():
                if namespace_dir.is_dir() and (namespace is None or namespace_dir.name.startswith(namespace)):
                    namespace = namespace_dir.name
                    # Check for pods in this namespace
                    pods_path = namespace_dir / "pods"
                    self.logger.info(f"Checking pods in namespace: {pods_path}")
                    if pods_path.exists():
                        for pod_dir in pods_path.iterdir():
                            if pod_dir.is_dir() and (pod_name is None or pod_dir.name.startswith(pod_name)):
                                return pod_dir
        return None

    def find_pod_logs_directory(self, pod_dir: Path) -> Path:
        """Recursively goes down directory tree to find the logs directory for a pod."""
        if pod_dir.is_dir() and pod_dir.name == 'logs':
            return pod_dir
        if not pod_dir.is_dir():
            return None
        for pdir in pod_dir.iterdir():
            return self.find_pod_logs_directory(pdir)
        return None

    def _parse_pod_logs(self, logs_path: Path, namespace: str, pod_name: str, is_previous: bool, cluster_name: str = None) -> List[Dict[str, Any]]:
        """Parse log files for a specific pod."""
        logs = []
        
        for log_file in logs_path.iterdir():
            if log_file.is_file():
                container_name = log_file.name
                log_entries = self._parse_log_file(log_file, namespace, pod_name, container_name, is_previous, cluster_name)
                if log_entries:
                    logs.extend(log_entries)
        
        return logs

    def _parse_log_file(self, log_file: Path, namespace: str, pod_name: str, container_name: str, is_previous: bool, cluster_name: str = None) -> List[Dict[str, Any]]:
        """Parse a single log file and extract log entries."""
        try:
            with open(log_file, 'r') as f:
                content = f.read()

            # Split content into lines and parse each line
            log_entries = []
            for line_number, line in enumerate(content.splitlines(), 1):
                entry = self._parse_log_line(line, line_number)
                if entry and entry['level'] == 'ERROR' and cluster_name in entry['message']:
                    entry.update({
                        #'namespace': namespace,
                        #'pod_name': pod_name,
                        #'container_name': container_name,
                        #'is_previous': is_previous,
                        'file_path': log_file,
                        #'type': 'log',
                    })
                    log_entries.append(entry)

            return log_entries
                            
        except Exception as e:
            self.logger.warning(f"Failed to parse log file {log_file}: {e}")
            return []

    def _parse_log_line(self, line: str, line_number: int) -> Optional[Dict[str, Any]]:
        """
        Parse a single log line. Sanitizes the line before returning.
        Attempts to extract timestamp and log level if present.
        """
        try:
            # Common timestamp patterns
            timestamp_patterns = [
                r'(\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(?:\.\d+)?(?:Z|[+-]\d{2}:?\d{2})?)',  # ISO format
                r'(\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2}(?:\.\d+)?)',  # Common datetime format
            ]
            
            # Common log level patterns
            level_pattern = r'\b(ERROR|WARN(?:ING)?|INFO|DEBUG|TRACE|FATAL)\b'
            
            timestamp = None
            for pattern in timestamp_patterns:
                match = re.search(pattern, line)
                if match:
                    timestamp = match.group(1)
                    break

            level_match = re.search(level_pattern, line, re.IGNORECASE)
            log_level = level_match.group(1).upper() if level_match else None
            return {
                'timestamp': timestamp,
                'level': log_level,
                'message': sanitize_data(line),
                'line_number': line_number,
            }
            
        except Exception as e:
            self.logger.warning(f"Failed to parse log line: {e}")
            return None


    def get_logs_by_pod(self, pod_name: str = "assisted-service", must_gather_path: str = None, namespace: str = None, cluster_name: str = None) -> List[Dict[str, Any]]:
        """Get all logs for a specific pod."""
        if must_gather_path:
            self.must_gather_path = Path(must_gather_path)
        elif not self.must_gather_path:
            raise ValueError("Must provide must_gather_path either in constructor or method call")

        logs = self.find_pod_logs(namespace=namespace, pod_name=pod_name, cluster_name=cluster_name)
        self.logger.info(f"Found {len(logs)} log entries for pod containing '{pod_name}'")
        return logs

