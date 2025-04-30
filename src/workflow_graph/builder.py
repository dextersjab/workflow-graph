"""WorkflowGraph builder for constructing and validating workflow graphs."""

import inspect
import logging
from collections import defaultdict
from enum import Enum
from typing import (
    Any,
    Callable,
    Generic,
    Literal,
    TypeVar,
    get_args,
    get_origin,
)

from .constants import END, START
from .exceptions import (
    InvalidEdgeError,
    InvalidNodeNameError,
    ValidationError,
)
from .executor import CompiledGraph
from .models import Branch, Edge, Node, State

logger = logging.getLogger(__name__)

T = TypeVar("T", bound=State[Any])


class WorkflowGraph(Generic[T]):
    """Builder for creating and validating workflow graphs.

    This class provides methods to define nodes, edges, and conditional branches
    that make up a workflow graph. The graph can then be validated and compiled
    into an executable form.
    """

    def __init__(self, enforce_acyclic: bool = False) -> None:
        """Initialize a new workflow graph builder.

        Args:
            enforce_acyclic: If True, the graph must be a DAG (no cycles allowed).
                            If False, cycles are allowed (default).
        """
        self.nodes: dict[str, Node] = {}
        self.edges: dict[str, set[Edge]] = defaultdict(set)
        self.branches: defaultdict[str, dict[str, Branch]] = defaultdict(dict)
        self.compiled = False
        self.enforce_acyclic = enforce_acyclic

    @property
    def _all_edges(
        self,
    ) -> set[tuple[str, str, Callable[[str, str, Any], None] | None]]:
        """Return all edges in the graph as tuples for backward compatibility."""
        all_edges = set()
        for start, edge_set in self.edges.items():
            for edge in edge_set:
                all_edges.add((start, edge.target, edge.callback))
        return all_edges

    def add_node(
        self,
        name: str,
        func: Callable[[Any], Any],
        callback: Callable[[Any], None] | None = None,
        stream_callback: Callable[[str], None] | None = None,
        on_error: Callable[[Exception, Any], Any] | None = None,
        retries: int = 0,
        retry_delay: float = 0,
        backoff_factor: float = 0,
        metadata: dict[str, Any] | None = None,
        input_type: type | None = None,
        output_type: type | None = None,
    ) -> None:
        """Add a node to the workflow graph.

        Args:
            name: Name of the node
            func: Function to execute for this node
            callback: Optional callback function
            stream_callback: Optional callback function for streaming tokens
            on_error: Optional error handler
            retries: Number of retries on failure
            retry_delay: Delay between retries
            backoff_factor: Exponential backoff factor
            metadata: Optional metadata for the node
            input_type: Expected input type
            output_type: Expected output type
        """
        if name in [START, END]:
            raise InvalidNodeNameError(f"Node name '{name}' is reserved")
        if name in self.nodes:
            raise InvalidNodeNameError(f"Node '{name}' already exists")

        # Validate that the function returns a State object
        return_annotation = inspect.signature(func).return_annotation
        if return_annotation != inspect.Signature.empty:
            # Get the base type (e.g., State[int] -> State)
            base_type = get_origin(return_annotation)
            if base_type is None:
                base_type = return_annotation

            if not isinstance(base_type, type):
                raise TypeError(
                    f"Node function '{name}' must return a State subclass, but got a string annotation: {base_type!r}. "
                    "If using forward references, add 'from __future__ import annotations'."
                )

            if not issubclass(base_type, State):
                raise ValueError(
                    f"Node function '{name}' must return a State object or subclass, got {return_annotation}"
                )

        # Validate error handler return type if provided
        if on_error is not None:
            error_return_annotation = inspect.signature(on_error).return_annotation
            if error_return_annotation != inspect.Signature.empty:
                error_base_type = get_origin(error_return_annotation)
                if error_base_type is None:
                    error_base_type = error_return_annotation

                if not issubclass(error_base_type, State):
                    raise ValueError(
                        f"Error handler for node '{name}' must return a State object or subclass, got {error_return_annotation}"
                    )

        self.nodes[name] = Node(
            name=name,
            func=func,
            callback=callback,
            stream_callback=stream_callback,
            on_error=on_error,
            retries=retries,
            retry_delay=retry_delay,
            backoff_factor=backoff_factor,
            metadata=metadata or {},
            input_type=input_type,
            output_type=output_type,
        )
        return self

    def add_edge(
        self,
        start_key: str,
        end_key: str,
        callback: Callable[[str, str, Any], None] | None = None,
    ) -> None:
        """Add a directed edge between two nodes.

        Args:
            start_key: Source node name
            end_key: Destination node name
            callback: Optional callback function that receives (source, target, state)

        Raises:
            ValueError: If using reserved nodes incorrectly
            InvalidEdgeError: If the source node already has conditional branches
        """
        if self.compiled:
            logger.warning(
                "Adding an edge to a graph that has already been compiled. This will "
                "not be reflected in the compiled graph."
            )
        if start_key == END:
            raise InvalidEdgeError("END cannot be a start node")
        if end_key == START:
            raise InvalidEdgeError("START cannot be an end node")
        if start_key not in self.nodes and start_key != START:
            raise InvalidEdgeError(f"Start node '{start_key}' does not exist")
        if end_key not in self.nodes and end_key != END:
            raise InvalidEdgeError(f"End node '{end_key}' does not exist")

        # Check if the source node already has conditional branches
        if start_key in self.branches and self.branches[start_key]:
            raise InvalidEdgeError(
                f"Cannot add a direct edge from '{start_key}' because it already has conditional branches. "
                "Remove the conditional branches first."
            )

        edge = Edge(source=start_key, target=end_key, callback=callback)
        self.edges[start_key].add(edge)

    def add_conditional_edges(
        self,
        source: str,
        condition: Callable[[Any], Any],
        path_map: dict[Any, str] | None = None,
        callback: Callable[[str, str, Any], None] | None = None,
    ) -> None:
        """Add conditional edges from a source node.

        Args:
            source: Source node name
            condition: Function that determines the branch path. Must return bool, Enum, or Literal.
            path_map: Mapping of condition values to destination node names
            callback: Optional callback function that receives (source, target, state)

        Raises:
            ValueError: If a branch with the same name already exists
            InvalidEdgeError: If trying to add conditional edges from START or if the source node already has direct edges
            TypeError: If condition return type is not bool, Enum, or Literal
            ValidationError: If path_map does not cover all possible condition values
        """
        if self.compiled:
            logger.warning(
                "Adding an edge to a graph that has already been compiled. This will "
                "not be reflected in the compiled graph."
            )

        # Validate source node
        if source == START:
            raise InvalidEdgeError(
                "Cannot add conditional edges directly from START. "
                "Add an explicit entry node first (e.g., 'init' or 'entry') and branch from there. "
                "Example:\n"
                "  graph.add_node('entry', entry_func)\n"
                "  graph.add_edge(START, 'entry')\n"
                "  graph.add_conditional_edges('entry', condition, path_map)"
            )

        if source not in self.nodes:
            raise InvalidNodeNameError(f"Source node '{source}' does not exist")

        # Check if the source node already has direct edges
        if source in self.edges and self.edges[source]:
            raise InvalidEdgeError(
                f"Cannot add conditional edges from '{source}' because it already has direct edges. "
                "Remove the direct edges first."
            )

        # Get branch name from condition function
        name = getattr(condition, "__name__", "condition")
        if name in self.branches[source]:
            raise InvalidNodeNameError(
                f"Branch with name `{name}` already exists for node `{source}`"
            )

        # Get return type annotation
        return_annotation = inspect.signature(condition).return_annotation

        # If no annotation, infer type from path_map keys
        if return_annotation == inspect.Signature.empty and path_map is not None:
            # Check if all keys are bool
            if all(isinstance(k, bool) for k in path_map.keys()):
                return_annotation = bool
            # Check if all keys are from the same Enum
            elif all(isinstance(k, Enum) for k in path_map.keys()):
                enum_types = {type(k) for k in path_map.keys()}
                if len(enum_types) == 1:
                    return_annotation = next(iter(enum_types))
            # Check if all keys are strings (could be Literal)
            elif all(isinstance(k, str) for k in path_map.keys()):
                # Create a Literal type from the string values
                return_annotation = Literal[tuple(path_map.keys())]  # type: ignore

        # Restrict to bool, Enum, or Literal only
        is_enum = isinstance(return_annotation, type) and issubclass(
            return_annotation, Enum
        )
        is_literal = get_origin(return_annotation) is Literal

        if not (return_annotation is bool or is_enum or is_literal):
            raise TypeError(
                f"Branch condition function '{name}' must return bool, Enum, or Literal, "
                f"but got {return_annotation!r}. Either add a return type annotation or "
                f"use bool, Enum, or string values in path_map."
            )

        # Validate path_map coverage based on return type
        if path_map is not None:
            # Handle bool return type
            if return_annotation is bool:
                for val in (True, False):
                    if val not in path_map:
                        raise ValidationError(
                            f"Conditional edge from '{source}' does not handle {val} branch. "
                            f"Add a path for {val} in path_map."
                        )

            # Handle Enum return type
            elif is_enum:
                for val in return_annotation:
                    if val not in path_map:
                        raise ValidationError(
                            f"Conditional edge from '{source}' does not handle {val} branch. "
                            f"Add a path for {val} in path_map."
                        )

            # Handle Literal return type
            elif is_literal:
                for val in get_args(return_annotation):
                    if val not in path_map:
                        raise ValidationError(
                            f"Conditional edge from '{source}' does not handle {val} branch. "
                            f"Add a path for {val} in path_map."
                        )

        # Create branch with condition
        branch = Branch(
            source=source,
            branch_id=name,
            condition=condition,
            ends=path_map,
            callback=callback,
        )

        # Add branch to graph
        self.branches[source][name] = branch

        # Add edges for each path in the branch
        if path_map:
            for target in path_map.values():
                edge = Edge(
                    source=source, target=target, callback=callback, branch=branch
                )
                self.edges[source].add(edge)

    def validate(self) -> None:
        """Validate the graph structure."""
        # Check for at least one entry point
        has_entry_edge = any(src == START for src, _, _ in self._all_edges)
        has_conditional_entry = START in self.branches
        if not has_entry_edge and not has_conditional_entry:
            raise ValidationError(
                "Graph must have at least one entry point defined by adding an edge from 'START' or a conditional edge from 'START'"
            )

        # Check for at least one finish point
        has_finish_edge = any(dst == END for _, dst, _ in self._all_edges)
        has_conditional_finish = any(
            END in branch.ends.values() if branch.ends else False
            for branches in self.branches.values()
            for branch in branches.values()
        )
        if not has_finish_edge and not has_conditional_finish:
            raise ValidationError(
                "Graph must have at least one exit point defined by adding an edge to 'END' or a conditional edge to 'END'"
            )

        # Check for unreachable nodes
        if len(self.nodes) > 0:
            # Build a graph of all reachable nodes
            visited = set()
            queue = [START]

            while queue:
                node = queue.pop(0)
                if node in visited:
                    continue

                visited.add(node)

                # Add all nodes reachable from outgoing edges
                if node in self.edges:
                    for edge in self.edges[node]:
                        if edge.target != END:
                            queue.append(edge.target)

                # Add all nodes reachable from branches
                if node in self.branches:
                    for branch in self.branches[node].values():
                        if branch.ends:
                            for dest in branch.ends.values():
                                if dest != END:
                                    queue.append(dest)

            # Check for any nodes that weren't visited
            unreachable = set(self.nodes.keys()) - visited
            if unreachable:
                raise ValueError(
                    f"Unreachable nodes detected: {', '.join(unreachable)}"
                )

        # Check for cycles if enforce_acyclic is True
        if self.enforce_acyclic and self._has_cycles():
            raise ValueError("Graph contains cycles")

    def _has_cycles(self) -> bool:
        """Check if the graph contains any cycles."""
        visited = set()
        path = set()

        def visit(node):
            if node in path:
                return True
            if node in visited:
                return False

            path.add(node)
            visited.add(node)

            # Check edges
            if node in self.edges:
                for edge in self.edges[node]:
                    if edge.target != END and visit(edge.target):
                        return True

            # Check branches
            if node in self.branches:
                for branch in self.branches[node].values():
                    if branch.ends:
                        for dest in branch.ends.values():
                            if dest != END and visit(dest):
                                return True

            path.remove(node)
            return False

        return visit(START)

    def compile(self) -> CompiledGraph:
        """Compile the workflow graph into an executable form.

        Returns:
            A compiled graph ready for execution

        Raises:
            ValueError: If validation fails or no entry point is defined
            ValidationError: If type validation fails
        """
        self.validate()

        # Check for at least one entry point (edge from START)
        has_entry_edge = any(src == START for src, _, _ in self._all_edges)
        has_conditional_entry = START in self.branches
        if not has_entry_edge and not has_conditional_entry:
            raise ValueError(
                "Graph must have at least one entry point defined by adding an edge from 'START' or a conditional edge from 'START'"
            )

        # Check for at least one finish point (edge to END)
        has_finish_edge = any(dst == END for _, dst, _ in self._all_edges)
        has_conditional_finish = any(
            END in branch.ends.values() if branch.ends else False
            for branches in self.branches.values()
            for branch in branches.values()
        )
        if not has_finish_edge and not has_conditional_finish:
            raise ValueError(
                "Graph must have at least one finish point defined by adding an edge to 'END' or a conditional edge to 'END'"
            )

        # Create compiled graph and validate it
        compiled = CompiledGraph(
            nodes=self.nodes, edges=self.edges, branches=self.branches
        )
        compiled.validate()  # This will check type consistency
        return compiled

    def execute(self, data: Any) -> State:
        """Execute the workflow graph with the given input."""
        return self.compile().execute(data)

    async def execute_async(
        self, data: Any, callback: Callable[[str, Any], None] | None = None
    ) -> State:
        """Execute the workflow graph asynchronously with the given input."""
        return await self.compile().execute_async(data, callback)

    def to_mermaid(self) -> str:
        """Generate a Mermaid diagram representation of the workflow graph.

        Returns:
            A string containing the Mermaid diagram code.
        """
        return self.compile().to_mermaid()
