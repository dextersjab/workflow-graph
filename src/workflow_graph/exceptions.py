"""Custom exceptions for the workflow graph module."""


class WorkflowGraphError(Exception):
    """Base exception for all workflow graph errors."""

    pass


class InvalidNodeNameError(WorkflowGraphError):
    """Raised when an invalid node name is provided."""

    pass


class DuplicateNodeError(WorkflowGraphError):
    """Raised when attempting to add a node with a name that already exists."""

    pass


class InvalidEdgeError(WorkflowGraphError):
    """Raised when attempting to add an invalid edge."""

    pass


class TypeMismatchError(WorkflowGraphError):
    """Raised when there is a type mismatch between connected nodes."""

    pass


class ExecutionError(WorkflowGraphError):
    """Raised when there is an error during workflow execution."""

    pass


class ValidationError(WorkflowGraphError):
    """Raised when graph validation fails."""

    pass
