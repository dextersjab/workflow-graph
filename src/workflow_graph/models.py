"""Data models for workflow graph components."""

from dataclasses import dataclass, field
from typing import Any, Callable, Hashable, Optional, Awaitable


@dataclass
class NodeSpec:
    """Specification for a node in the workflow graph."""
    name: str
    action: Callable[..., Any | Awaitable[Any]]
    callback: Callable[[], None] | None = None
    error_handler: Callable[[Exception], Any | Awaitable[Any]] | None = None
    retry_count: int = 0
    retry_delay: float = 0.5  # Default delay in seconds
    backoff_factor: float | None = None # Add backoff_factor field
    metadata: Optional[dict[str, Any]] = None
    input_type: Optional[type] = None
    output_type: Optional[type] = None


@dataclass
class Branch:
    """Represents a conditional branch outgoing from a node."""
    path: Callable[[Any], Hashable | list[Hashable]]  # Function applied to node output to determine path(s)
    ends: Optional[dict[Hashable, str]] = None        # Map path results to destination node names
    then: Optional[str] = None                        # Default destination if path result not in ends

    # For add_conditional_edges compatibility
    source: str | None = None
    target: str | None = None
    condition: Callable[[Any], bool] | None = None
    branch_id: str | None = None # Optional unique identifier for the branch

    # For add_conditional_edges compatibility
    path: Callable[[Any], Hashable] | None = None
    ends: dict[Hashable, str] | None = None
    then: str | None = None 