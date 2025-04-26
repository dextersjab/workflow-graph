"""Data models for workflow graph components."""

from dataclasses import dataclass, field
from typing import Any, Callable, Generic, Optional, TypeVar

T = TypeVar("T")

@dataclass
class State(Generic[T]):
    """State of a workflow graph execution."""
    value: T | None
    current_node: str | None = None
    processed_by: list[str] = field(default_factory=list)
    branch_taken: str | None = None
    errors: list[Exception] = field(default_factory=list)

    def add_error(self, error: Exception, node: str | None = None) -> None:
        """Add an error to the state."""
        error_msg = str(error)
        if node:
            error_msg = f"{node}: {error_msg}"
        self.errors.append(error_msg)

    def __str__(self) -> str:
        """String representation of the state."""
        return f"State(value={self.value}, current_node={self.current_node}, processed_by={self.processed_by}, branch_taken={self.branch_taken}, errors={self.errors})"

@dataclass
class Branch[T]:
    """A branch in the workflow graph that defines conditional execution paths.
    
    Attributes:
        source: The source node name
        branch_id: Unique identifier for this branch
        condition: Function that determines the branch path
        ends: Mapping of condition results to destination node names
    """
    source: str
    branch_id: str
    condition: Callable[[T], Any]
    ends: dict[Any, str] | None = None

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

@dataclass
class ExecutionResult(Generic[T]):
    """Result of a workflow graph execution."""
    result: T | None
    processed_by: list[str]
    branch_taken: str | None
    errors: list[Exception] 