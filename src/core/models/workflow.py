"""
Workflow models for visual node automation.
"""

from dataclasses import dataclass, field
from typing import Dict, Any, List


@dataclass
class WorkflowNodeData:
    """Data representation of a workflow node."""
    id: int
    title: str
    x: float = 0.0
    y: float = 0.0
    config: Dict[str, Any] = field(default_factory=dict)


@dataclass
class WorkflowEdgeData:
    """Data representation of a connection between two workflow nodes."""
    source_id: int
    target_id: int


@dataclass
class WorkflowPreset:
    """Full workflow configuration preset."""
    nodes: List[WorkflowNodeData] = field(default_factory=list)
    edges: List[WorkflowEdgeData] = field(default_factory=list)
