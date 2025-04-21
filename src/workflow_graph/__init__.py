"""Workflow Graph - A package for building and executing workflow graphs.

This package provides a simple and flexible way to build workflow graphs
and execute them with proper error handling and retries.
"""

from .builder import WorkflowGraph
from .constants import START, END
from .executor import CompiledGraph
from .models import Branch, NodeSpec
from .exceptions import (
    WorkflowGraphError,
    InvalidNodeNameError,
    DuplicateNodeError,
    InvalidEdgeError,
    TypeMismatchError,
    ExecutionError
)

__all__ = [
    "WorkflowGraph",
    "CompiledGraph",
    "NodeSpec",
    "Branch",
    "START",
    "END",
    "WorkflowGraphError",
    "InvalidNodeNameError",
    "DuplicateNodeError",
    "InvalidEdgeError",
    "TypeMismatchError",
    "ExecutionError"
]

__version__ = "0.3.1" 