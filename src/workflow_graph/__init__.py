"""Workflow Graph - A library for building and executing directed graphs of tasks.

This module provides a simple yet powerful way to define and execute workflows
as directed graphs. It supports conditional branching, error handling, and
type validation.
"""

from typing import Any, Callable, TypeVar, Optional, Generic

# Version
__version__ = "0.3.1"

# Core components
from .builder import WorkflowGraph
from .executor import CompiledGraph
from .models import (
    Node,
    Edge,
    Branch,
    State,
)

# Type utilities
T = TypeVar("T")

# Exceptions
from .exceptions import (
    WorkflowGraphError,
    InvalidNodeNameError,
    DuplicateNodeError,
    InvalidEdgeError,
    TypeMismatchError,
    ExecutionError,
    ValidationError,
    EntryExitValidationError,
)

# Type validation utilities
from .utils import (
    get_return_type_hint,
    get_first_param_type_hint,
    is_type_compatible,
)

# Constants
from .constants import START, END

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