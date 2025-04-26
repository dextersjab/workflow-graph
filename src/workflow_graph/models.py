"""Data models for workflow graph components."""

from dataclasses import dataclass, field
from typing import Any, Callable, Generic, Optional, TypeVar

T = TypeVar("T")

@dataclass
class State(Generic[T]):
    """State of a workflow graph execution.
    
    Attributes:
        value: The current value being processed through the workflow
        data: Dictionary of node-specific data that can be read/written by nodes
        current_node: Name of the current node being executed
        processed_by: List of nodes that have processed this state
        trajectory: List of branches taken during execution
        errors: List of errors encountered during execution
    """
    value: T | None
    data: dict[str, Any] = field(default_factory=dict)
    current_node: str | None = None
    processed_by: list[str] = field(default_factory=list)
    trajectory: list[str] = field(default_factory=list)
    errors: list[Exception] = field(default_factory=list)

    def add_error(self, error: Exception, node: str | None = None) -> None:
        """Add an error to the state."""
        error_msg = str(error)
        if node:
            error_msg = f"{node}: {error_msg}"
        self.errors.append(error_msg)

    def update_value(self, new_value: T) -> None:
        """Update the value being processed through the workflow."""
        self.value = new_value

    def set_data(self, key: str, value: Any) -> None:
        """Set a node-specific data value."""
        self.data[key] = value

    def get_data(self, key: str, default: Any = None) -> Any:
        """Get a node-specific data value."""
        return self.data.get(key, default)

    def __str__(self) -> str:
        """String representation of the state."""
        return f"State(value={self.value}, data={self.data}, current_node={self.current_node}, processed_by={self.processed_by}, trajectory={self.trajectory}, errors={self.errors})"

@dataclass
class Branch[T]:
    """A branch in the workflow graph that defines conditional execution paths.
    
    Attributes:
        source: The source node name
        branch_id: Unique identifier for this branch
        condition: Function that determines the branch path
        ends: Mapping of condition results to destination node names
        callback: Optional callback function that receives (source, target, state)
    """
    source: str
    branch_id: str
    condition: Callable[[T], Any]
    ends: dict[Any, str] | None = None
    callback: Callable[[str, str, Any], None] | None = None

@dataclass
class Edge:
    """An edge in the workflow graph."""
    source: str
    target: str
    branch: Branch[Any] | None = None

@dataclass
class Node(Generic[T]):
    """A node in the workflow graph."""
    name: str
    func: Callable[[T], T]
    callback: Optional[Callable[[T], None]] = None
    error_handler: Optional[Callable[[Exception, T], T]] = None
    retries: int = 0
    retry_delay: float = 0.5
    backoff_factor: Optional[float] = None
    metadata: Optional[dict[str, Any]] = None
    input_type: Optional[type[T]] = None
    output_type: Optional[type[T]] = None 