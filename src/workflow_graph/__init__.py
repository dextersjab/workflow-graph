"""Workflow Graph - A library for building and executing directed graphs of tasks.

This module provides a simple yet powerful way to define and execute workflows
as directed graphs. It supports conditional branching, error handling, and
type validation.
"""

from typing import TypeVar

from .builder import WorkflowGraph
from .constants import END, START
from .exceptions import (
    DuplicateNodeError,
    ExecutionError,
    InvalidEdgeError,
    InvalidNodeNameError,
    TypeMismatchError,
    ValidationError,
    WorkflowGraphError,
)
from .executor import CompiledGraph
from .models import (
    Branch,
    Edge,
    Node,
    State,
)
from .utils import (
    get_first_param_type_hint,
    get_return_type_hint,
    is_type_compatible,
)

# Type utilities
T = TypeVar("T")

__all__ = [
    # Core components
    "WorkflowGraph",
    "CompiledGraph",
    "Node",
    "Edge",
    "Branch",
    "State",
    # Type utilities
    "T",
    # Exceptions
    "WorkflowGraphError",
    "InvalidNodeNameError",
    "DuplicateNodeError",
    "InvalidEdgeError",
    "TypeMismatchError",
    "ExecutionError",
    "ValidationError",
    "EntryExitValidationError",
    # Type validation utilities
    "get_return_type_hint",
    "get_first_param_type_hint",
    "is_type_compatible",
    # Constants
    "START",
    "END",
]
