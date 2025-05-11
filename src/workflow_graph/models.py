"""Data models for workflow graph components."""

from dataclasses import dataclass, field, replace
from typing import Any, Callable, Generic, Optional, TypeVar

T = TypeVar("T")


@dataclass
class State(Generic[T]):
    """State of a workflow graph execution.

    Attributes:
        value: The current value being processed through the workflow
        current_node: Name of the current node being executed
        trajectory: List of nodes traversed during execution
        errors: List of error messages encountered during execution
    """

    value: T = field()  # Required field, no default
    current_node: str | None = field(default=None)
    trajectory: list[str] = field(default_factory=list)
    errors: list[str] = field(default_factory=list)

    def add_error(self, error: Exception, node: str | None = None) -> "State[T]":
        """Return a new State with an added error message.

        Args:
            error: The exception that occurred
            node: Optional name of the node where the error occurred

        Returns:
            A new State instance with the error message added
        """
        error_msg = str(error)
        if node:
            error_msg = f"{node}: {error_msg}"
        new_errors = self.errors + [error_msg]
        return self.updated(errors=new_errors)

    def updated(self, **kwargs) -> "State[T]":
        """Return a new State with updated fields (immutable pattern).

        This method automatically handles copying of mutable fields (trajectory, errors)
        to ensure immutability.

        Args:
            **kwargs: Field names and values to update

        Returns:
            A new State instance with the specified fields updated
        """
        # Handle mutable fields
        if "trajectory" in kwargs and isinstance(kwargs["trajectory"], list):
            kwargs["trajectory"] = kwargs["trajectory"].copy()
        if "errors" in kwargs and isinstance(kwargs["errors"], list):
            kwargs["errors"] = kwargs["errors"].copy()

        return replace(self, **kwargs)

    def __str__(self) -> str:
        """Return a string representation of the state."""
        return f"State(value={self.value}, current_node={self.current_node}, trajectory={self.trajectory}, errors={self.errors})"


@dataclass
class Branch(Generic[T]):
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
    """An edge in the workflow graph.

    Attributes:
        source: The source node name
        target: The target node name
        callback: Optional callback function that receives (source, target, state)
        branch: Optional branch that this edge is part of
    """

    source: str
    target: str
    callback: Callable[[str, str, Any], None] | None = None
    branch: Branch[Any] | None = None

    def __hash__(self) -> int:
        """Make Edge hashable for use in sets."""
        return hash((self.source, self.target, self.callback))

    def __eq__(self, other: object) -> bool:
        """Compare edges for equality."""
        if not isinstance(other, Edge):
            return False
        return (
            self.source == other.source
            and self.target == other.target
            and self.callback == other.callback
        )


@dataclass
class Node(Generic[T]):
    """A node in the workflow graph.

    Attributes:
        name: The name of the node
        func: The function to execute for this node
        callback: Optional callback function that receives the final result
        stream_callback: Optional callback function that receives streaming tokens/chunks
        on_error: Optional error handler function
        retries: Number of times to retry on failure
        retry_delay: Delay between retries in seconds
        backoff_factor: Optional exponential backoff factor for retries
        metadata: Optional metadata dictionary
        input_type: Optional type hint for input
        output_type: Optional type hint for output
    """

    name: str
    func: Callable[[T], T]
    callback: Optional[Callable[[T], None]] = None
    stream_callback: Optional[Callable[[str], None]] = None
    on_error: Optional[Callable[[Exception, T], T]] = None
    retries: int = 0
    retry_delay: float = 0.5
    backoff_factor: Optional[float] = None
    metadata: Optional[dict[str, Any]] = None
    input_type: Optional[type[T]] = None
    output_type: Optional[type[T]] = None
