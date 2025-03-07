"""WorkflowGraph builder for constructing and validating workflow graphs."""

import logging
from collections import defaultdict
from typing import (
    Any,
    Callable,
    Hashable,
    Literal,
    Sequence,
    get_args,
    get_origin,
    get_type_hints,
)

from .constants import START, END
from .models import Branch, NodeSpec
from .executor import CompiledGraph
from .exceptions import (
    InvalidNodeNameError,
    DuplicateNodeError,
    InvalidEdgeError,
    TypeMismatchError,
)

logger = logging.getLogger(__name__)


class WorkflowGraph:
    """Builder for creating and validating workflow graphs.
    
    This class provides methods to define nodes, edges, and conditional branches
    that make up a workflow graph. The graph can then be validated and compiled
    into an executable form.
    """
    
    def __init__(self) -> None:
        """Initialize a new workflow graph builder."""
        self.nodes: dict[str, NodeSpec] = {}
        self.edges = set[tuple[str, str]]()
        self.branches: defaultdict[str, dict[str, Branch]] = defaultdict(dict)
        self.compiled = False

    @property
    def _all_edges(self) -> set[tuple[str, str]]:
        """Return all edges in the graph."""
        return self.edges

    def add_node(
        self,
        node: str | Callable,
        action: Callable | None = None,
        *,
        metadata: dict[str, Any] | None = None,
        retries: int = 0,
        backoff_factor: float = 0.1,
        on_error: Callable[[Exception], Any] | None = None,
        callback: Callable[[], None] | None = None,
    ) -> None:
        """Add a node to the workflow graph.
        
        Args:
            node: Node name or callable action
            action: The function to execute at this node (required if node is a string)
            metadata: Optional metadata for the node
            retries: Number of retry attempts if the node action fails
            backoff_factor: Delay between retry attempts
            on_error: Optional error handler function
            callback: Optional callback function to execute after the node action
            
        Raises:
            ValueError: If node validation fails
        """
        def extract_type_hints(fn: Callable) -> tuple[type | None, type | None]:
            try:
                hints = get_type_hints(fn)
                params = list(hints.items())
                input_type = params[0][1] if params and params[0][0] != 'return' else None
                output_type = hints.get('return')
                return input_type, output_type
            except Exception:
                return None, None

        if isinstance(node, str):
            if action is None:
                raise ValueError("Action must be provided when node is a string")
            if node in (START, END):
                raise InvalidNodeNameError(f"Node `{node}` is reserved.")
            if node in self.nodes:
                raise DuplicateNodeError(f"Node `{node}` already present.")
            input_type, output_type = extract_type_hints(action)
            self.nodes[node] = NodeSpec(
                action=action,
                metadata=metadata,
                input_type=input_type,
                output_type=output_type,
                retry_count=retries,
                retry_delay=backoff_factor,
                error_handler=on_error,
                callback=callback,
            )
        elif callable(node):
            action = node
            node_name = getattr(node, "__name__", None)
            if node_name is None:
                raise ValueError("Cannot determine name of the node")
            if node_name in self.nodes:
                raise DuplicateNodeError(f"Node `{node_name}` already present.")
            if node_name in (START, END):
                raise InvalidNodeNameError(f"Node `{node_name}` is reserved.")
            input_type, output_type = extract_type_hints(action)
            self.nodes[node_name] = NodeSpec(
                action=node,
                metadata=metadata,
                input_type=input_type,
                output_type=output_type,
                retry_count=retries,
                retry_delay=backoff_factor,
                error_handler=on_error,
                callback=callback,
            )

    def add_edge(self, start_key: str, end_key: str, *, condition: Callable[[Any], bool] | None = None) -> None:
        """Add a directed edge between two nodes.
        
        Args:
            start_key: Source node name
            end_key: Destination node name
            condition: Optional condition function to determine the edge
            
        Raises:
            ValueError: If using reserved nodes incorrectly
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

        if condition is not None:
            self.add_conditional_edges(
                start_key,
                condition,
                {True: end_key}
            )
        else:
            self.edges.add((start_key, end_key))

    def add_conditional_edges(
        self,
        source: str,
        path: Callable[[Any], Hashable | list[Hashable]],
        path_map: dict[Hashable, str] | list[str] | None = None,
        then: str | None = None,
    ) -> None:
        """Add conditional edges from a source node.
        
        Args:
            source: Source node name
            path: Function that determines the branch path
            path_map: Mapping of path values to destination node names
            then: Optional default destination node
            
        Raises:
            ValueError: If a branch with the same name already exists
        """
        if self.compiled:
            logger.warning(
                "Adding an edge to a graph that has already been compiled. This will "
                "not be reflected in the compiled graph."
            )
        if isinstance(path_map, dict):
            path_map = path_map.copy()
        elif isinstance(path_map, list):
            path_map = {name: name for name in path_map}
        else:
            try:
                rtn_type = get_type_hints(path).get("return")
                if get_origin(rtn_type) is Literal:
                    path_map = {name: name for name in get_args(rtn_type)}
            except Exception:
                pass

        name = getattr(path, "__name__", "condition")
        if name in self.branches[source]:
            raise ValueError(
                f"Branch with name `{name}` already exists for node `{source}`"
            )
        self.branches[source][name] = Branch(path, path_map, then)

    def set_entry_point(self, key: str) -> None:
        """Set the entry point for the workflow.
        
        Args:
            key: Node name to use as entry point
        """
        return self.add_edge(START, key)

    def set_conditional_entry_point(
        self,
        path: Callable[[Any], Hashable | list[Hashable]],
        path_map: dict[Hashable, str] | list[str] | None = None,
        then: str | None = None,
    ) -> None:
        """Set a conditional entry point for the workflow.
        
        Args:
            path: Function that determines the entry path
            path_map: Mapping of path values to entry node names
            then: Optional default entry node
        """
        return self.add_conditional_edges(START, path, path_map, then)

    def set_finish_point(self, key: str) -> None:
        """Set the finish point for the workflow.
        
        Args:
            key: Node name to use as finish point
        """
        return self.add_edge(key, END)

    def validate(self, interrupt: Sequence[str] | None = None) -> None:
        """Validate the workflow graph.
        
        Args:
            interrupt: Optional sequence of node names that can interrupt the flow
            
        Raises:
            ValueError: If validation fails
        """
        all_sources = {src for src, _ in self._all_edges}
        for start, branches in self.branches.items():
            all_sources.add(start)
            for cond, branch in branches.items():
                if branch.then is not None:
                    if branch.ends is not None:
                        for end in branch.ends.values():
                            if end != END:
                                all_sources.add(end)
                    else:
                        for node in self.nodes:
                            if node != start and node != branch.then:
                                all_sources.add(node)
        for source in all_sources:
            if source not in self.nodes and source != START:
                raise InvalidEdgeError(f"Found edge starting at unknown node '{source}'")

        # Validate type compatibility between connected nodes
        def validate_type_compatibility(source: str, target: str) -> None:
            if source == START or target == END:
                return
            source_node = self.nodes[source]
            target_node = self.nodes[target]
            if (source_node.output_type is not None and 
                target_node.input_type is not None and 
                not issubclass(source_node.output_type, target_node.input_type)):
                raise TypeMismatchError(
                    f"Type mismatch: Node '{source}' outputs {source_node.output_type} "
                    f"but node '{target}' expects {target_node.input_type}"
                )

        # Check regular edges
        for source, target in self._all_edges:
            validate_type_compatibility(source, target)

        # Check conditional edges
        for source, branches in self.branches.items():
            for branch in branches.values():
                if branch.ends:
                    for target in branch.ends.values():
                        if target != END:
                            validate_type_compatibility(source, target)

        # Continue with existing validation
        all_targets = {end for _, end in self._all_edges}
        for target in all_targets:
            if target not in self.nodes and target != END:
                raise InvalidEdgeError(f"Found edge ending at unknown node `{target}`")
        if interrupt:
            for node in interrupt:
                if node not in self.nodes:
                    raise InvalidEdgeError(f"Interrupt node `{node}` not found")

        self.compiled = True

    def compile(self) -> CompiledGraph:
        """Compile the workflow graph into an executable form.
        
        Returns:
            A compiled graph ready for execution
            
        Raises:
            ValueError: If validation fails or no entry point is defined
        """
        self.validate()
        
        # Check for entry point
        entry_edges = [dst for src, dst in self._all_edges if src == START]
        if not entry_edges and not self.branches.get(START):
            raise ValueError("Graph must have at least one entry point (an edge from START)")

        # Check for unreachable nodes
        if len(self.nodes) > 0:
            # Build a graph of all reachable nodes
            visited = set()
            queue = []

            # Add entry points to the queue
            for dst in entry_edges:
                if dst != END:
                    queue.append(dst)

            # Add entry points from conditional branches
            if START in self.branches:
                for branch in self.branches[START].values():
                    if branch.then and branch.then != END:
                        queue.append(branch.then)
                    if branch.ends:
                        for dest in branch.ends.values():
                            if dest != END:
                                queue.append(dest)
            
            while queue:
                node = queue.pop(0)
                if node in visited:
                    continue
                    
                visited.add(node)
                
                # Add all nodes reachable from outgoing edges
                for src, target in self._all_edges:
                    if src == node and target != END:
                        queue.append(target)
                
                # Add all nodes reachable from branches
                if node in self.branches:
                    for branch in self.branches[node].values():
                        if branch.then and branch.then != END:
                            queue.append(branch.then)
                        if branch.ends:
                            for dest in branch.ends.values():
                                if dest != END:
                                    queue.append(dest)
            
            # Check for any nodes that weren't visited
            unreachable = set(self.nodes.keys()) - visited
            if unreachable:
                raise ValueError(f"Unreachable nodes detected: {', '.join(unreachable)}")
            
        compiled = CompiledGraph(
            nodes=self.nodes,
            edges=self.edges,
            branches=self.branches
        )
        return compiled

    def execute(self, data: Any) -> Any:
        """Execute the workflow graph with the given input."""
        return self.compile().execute(data)

    async def execute_async(self, data: Any) -> Any:
        """Execute the workflow graph asynchronously with the given input."""
        return await self.compile().execute_async(data)

    def to_mermaid(self) -> str:
        """Generate a Mermaid diagram representation of the workflow graph.
        
        Returns:
            A string containing the Mermaid diagram code.
        """
        return self.compile().to_mermaid() 