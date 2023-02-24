from dataclasses import dataclass


@dataclass
class SharedWorkspaceReport:
    """Dataclass to store counts of shared workspaces."""

    workspace_type: str
    workspace_name: str
    count: int = 0
