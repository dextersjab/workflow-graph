"""Data models for workflow graph components."""

from dataclasses import dataclass
from typing import Any, Callable, Hashable, Optional


@dataclass
class NodeSpec:
    """Specification for a node in the workflow graph."""
    action: Callable
    metadata: Optional[dict[str, Any]] = None
    input_type: Optional[type] = None
    output_type: Optional[type] = None
    retry_count: int = 0
    retry_delay: float = 0.1
    error_handler: Optional[Callable[[Exception], Any]] = None
    callback: Optional[Callable[[], None]] = None


@dataclass
class Branch:
    """Specification for a conditional branch in the workflow graph."""
    path: Callable[[Any], Hashable | list[Hashable]]
    ends: Optional[dict[Hashable, str]] = None
    then: Optional[str] = None 