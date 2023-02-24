from dataclasses import dataclass


@dataclass
class SharedWorkspaceReport:
    """Dataclass to store counts of shared workspaces."""

    workspace_type: str
    count: int = 0
