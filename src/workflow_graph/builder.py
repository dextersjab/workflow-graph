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
from collections import deque

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
        retry_delay: float = 0.5,
        backoff_factor: float | None = None,
        on_error: Callable[[Exception], Any] | None = None,
        callback: Callable[[], None] | None = None,
    ) -> None:
        """Add a node to the workflow graph.
        
        Args:
            node: Node name or callable action
            action: The function to execute at this node (required if node is a string)
            metadata: Optional metadata for the node
            retries: Number of retry attempts if the node action fails
            retry_delay: Delay between retry attempts in seconds
            backoff_factor: Optional multiplier for exponential backoff (e.g., 2 for doubling)
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
                name=node,
                action=action,
                metadata=metadata,
                input_type=input_type,
                output_type=output_type,
                retry_count=retries,
                retry_delay=retry_delay,
                backoff_factor=backoff_factor,
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
                name=node_name,
                action=node,
                metadata=metadata,
                input_type=input_type,
                output_type=output_type,
                retry_count=retries,
                retry_delay=retry_delay,
                backoff_factor=backoff_factor,
                error_handler=on_error,
                callback=callback,
            )

    def add_edge(self, start_key: str, end_key: str) -> None:
        """Add a directed edge between two nodes.
        
        Args:
            start_key: Source node name
            end_key: Destination node name
            
        Raises:
            ValueError: If using reserved nodes incorrectly
            TypeMismatchError: If the output type of the source node doesn't match the input type of the destination node
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

        # Skip type validation for START and END nodes
        if start_key != START and end_key != END:
            # Get type hints for both nodes
            start_node = self.nodes[start_key]
            end_node = self.nodes[end_key]
            
            # If either node has no type hints, skip validation
            if start_node.output_type is not None and end_node.input_type is not None:
                # Check if the output type of the source node is compatible with the input type of the destination node
                if not issubclass(start_node.output_type, end_node.input_type):
                    raise TypeMismatchError(
                        f"Type mismatch between nodes '{start_key}' and '{end_key}': "
                        f"'{start_key}' outputs {start_node.output_type.__name__} but "
                        f"'{end_key}' expects {end_node.input_type.__name__}"
                    )

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


    def validate(self) -> None:
        """Validate the graph structure."""
        # Check for at least one entry point
        has_entry_edge = any(src == START for src, _ in self.edges)
        has_conditional_entry = START in self.branches
        if not has_entry_edge and not has_conditional_entry:
            raise ValueError(
                f"Graph must have at least one entry point defined by adding an edge from '{START}' or a conditional edge from '{START}'"
            )

        # Check for at least one finish point
        has_finish_edge = any(dst == END for _, dst in self.edges)
        has_conditional_finish = any(
            (branch.then == END or (branch.ends and END in branch.ends.values()))
            for branches in self.branches.values()
            for branch in branches.values()
        )
        if not has_finish_edge and not has_conditional_finish:
            raise ValueError(
                f"Graph must have at least one finish point defined by adding an edge to '{END}' or a conditional edge to '{END}'"
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
                for src, dest in self.edges:
                    if src == node and dest != END:
                        queue.append(dest)
                
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

        # Check for cycles
        if self._has_cycles():
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
                for dest in self.edges[node]:
                    if dest != END and visit(dest):
                        return True
            
            # Check branches
            if node in self.branches:
                for branch in self.branches[node].values():
                    if branch.then and branch.then != END and visit(branch.then):
                        return True
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
        """
        self.validate()
        
        # Check for at least one entry point (edge from START)
        has_entry_edge = any(src == START for src, _ in self._all_edges)
        has_conditional_entry = START in self.branches
        if not has_entry_edge and not has_conditional_entry:
            raise ValueError(
                f"Graph must have at least one entry point defined by adding an edge from '{START}' or a conditional edge from '{START}'"
            )
            
        # Check for at least one finish point (edge to END)
        has_finish_edge = any(dst == END for _, dst in self._all_edges)
        has_conditional_finish = any(
            (branch.then == END or (branch.ends and END in branch.ends.values()))
            for branches in self.branches.values()
            for branch in branches.values()
        )
        if not has_finish_edge and not has_conditional_finish:
             raise ValueError(
                f"Graph must have at least one finish point defined by adding an edge to '{END}' or a conditional edge to '{END}'"
            )

        # Check for unreachable nodes
        if len(self.nodes) > 0:
            visited = set()
            queue = deque()

            # Add entry points from direct edges (START -> node)
            for src, dst in self.edges:
                if src == START and dst != END:
                    if dst not in queue:
                        queue.append(dst)

            # Add entry points from conditional branches starting at START
            if START in self.branches:
                for branch_id, branch in self.branches[START].items():
                    if branch.then and branch.then != END:
                        if branch.then not in queue:
                             queue.append(branch.then)
                    if branch.ends:
                        for path_val, dest in branch.ends.items():
                            if dest != END:
                                if dest not in queue:
                                     queue.append(dest)
            
            visited.add(START)

            while queue:
                node = queue.popleft()
                if node in visited:
                    continue
                
                visited.add(node)

                # Add nodes reachable from direct edges
                for start_node, end_node in self.edges:
                    if start_node == node and end_node != END:
                        if end_node not in visited:
                            queue.append(end_node)

                # Add nodes reachable from conditional branches
                if node in self.branches:
                    for branch_id, branch in self.branches[node].items():
                        if branch.then and branch.then != END:
                            if branch.then not in visited:
                                queue.append(branch.then)
                        if branch.ends:
                            for path_val, dest in branch.ends.items():
                                if dest != END:
                                    if dest not in visited:
                                        queue.append(dest)

            all_defined_nodes = set(self.nodes.keys())
            reachable_nodes = visited - {START, END}
            unreachable = all_defined_nodes - reachable_nodes
            if unreachable:
                raise ValueError(f"Unreachable nodes detected: {', '.join(sorted(list(unreachable)))}")
            
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