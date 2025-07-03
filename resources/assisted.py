from pathlib import Path


def assisted_service_active(must_gather_path: Path) -> bool:
    """
    Check if assisted-service is active in the cluster.
    """
    cluster_agents_path = must_gather_path / "cluster-scoped-resources" / "agent-install.openshift.io" / "agentserviceconfigs"
    return cluster_agents_path.exists()