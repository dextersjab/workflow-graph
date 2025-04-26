"""WorkflowGraph builder for constructing and validating workflow graphs."""

import logging
from collections import defaultdict
from typing import (
    Any,
    Callable,
    Generic,
    TypeVar,
    get_origin,
    get_args,
)
from collections import deque
import inspect

from .constants import START, END
from .models import Branch, Node, State
from .executor import CompiledGraph
from .exceptions import (
    InvalidEdgeError,
    TypeMismatchError,
)

logger = logging.getLogger(__name__)

T = TypeVar("T", bound=State[Any])

class WorkflowGraph(Generic[T]):
    """Builder for creating and validating workflow graphs.
    
    This class provides methods to define nodes, edges, and conditional branches
    that make up a workflow graph. The graph can then be validated and compiled
    into an executable form.
    """
    
    def __init__(self) -> None:
        """Initialize a new workflow graph builder."""
        self.nodes: dict[str, Node] = {}
        self.edges = set[tuple[str, str, Callable[[str, str, Any], None] | None]]()
        self.branches: defaultdict[str, dict[str, Branch]] = defaultdict(dict)
        self.compiled = False

    @property
    def _all_edges(self) -> set[tuple[str, str, Callable[[str, str, Any], None] | None]]:
        """Return all edges in the graph."""
        return self.edges

    def add_node(
        self,
        name: str,
        func: Callable[[Any], Any],
        callback: Callable[[Any], None] | None = None,
        on_error: Callable[[Exception, Any], Any] | None = None,
        retries: int = 0,
        retry_delay: float = 0,
        backoff_factor: float = 0,
        metadata: dict[str, Any] | None = None,
        input_type: type | None = None,
        output_type: type | None = None,
    ) -> "WorkflowGraph":
        """Add a node to the workflow graph."""
        if name in [START, END]:
            raise ValueError(f"Node name '{name}' is reserved")
        if name in self.nodes:
            raise ValueError(f"Node '{name}' already exists")
        
        # Validate that the function returns a State object
        return_annotation = inspect.signature(func).return_annotation
        if return_annotation != inspect.Signature.empty:
            # Get the base type (e.g., State[int] -> State)
            base_type = get_origin(return_annotation)
            if base_type is None:
                base_type = return_annotation
            
            if not issubclass(base_type, State):
                raise ValueError(f"Node function '{name}' must return a State object or subclass, got {return_annotation}")
        
        # Validate error handler return type if provided
        if on_error is not None:
            error_return_annotation = inspect.signature(on_error).return_annotation
            if error_return_annotation != inspect.Signature.empty:
                error_base_type = get_origin(error_return_annotation)
                if error_base_type is None:
                    error_base_type = error_return_annotation
                
                if not issubclass(error_base_type, State):
                    raise ValueError(f"Error handler for node '{name}' must return a State object or subclass, got {error_return_annotation}")
        
        self.nodes[name] = Node(
            name=name,
            func=func,
            callback=callback,
            error_handler=on_error,
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
        callback: Callable[[str, str, Any], None] | None = None
    ) -> None:
        """Add a directed edge between two nodes.
        
        Args:
            start_key: Source node name
            end_key: Destination node name
            callback: Optional callback function that receives (source, target, state)
            
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

        self.edges.add((start_key, end_key, callback))

    def add_conditional_edges(
        self,
        source: str,
        condition: Callable[[Any], Any],
        path_map: dict[Any, str] | None = None,
        callback: Callable[[str, str, Any], None] | None = None
    ) -> None:
        """Add conditional edges from a source node.
        
        Args:
            source: Source node name
            condition: Function that determines the branch path
            path_map: Mapping of condition values to destination node names
            callback: Optional callback function that receives (source, target, state)
            
        Raises:
            ValueError: If a branch with the same name already exists
        """
        if self.compiled:
            logger.warning(
                "Adding an edge to a graph that has already been compiled. This will "
                "not be reflected in the compiled graph."
            )
        
        # Validate source node
        if source not in self.nodes and source != START:
            raise ValueError(f"Source node '{source}' does not exist")
        
        # Get branch name from condition function
        name = getattr(condition, "__name__", "condition")
        if name in self.branches[source]:
            raise ValueError(
                f"Branch with name `{name}` already exists for node `{source}`"
            )
        
        # Create branch with condition
        branch = Branch(
            source=source,
            branch_id=name,
            condition=condition,
            ends=path_map,
            callback=callback
        )
        
        # Add branch to graph
        self.branches[source][name] = branch

    def validate(self) -> None:
        """Validate the graph structure."""
        # Check for at least one entry point
        has_entry_edge = any(src == START for src, _, _ in self._all_edges)
        has_conditional_entry = START in self.branches
        if not has_entry_edge and not has_conditional_entry:
            raise ValueError(
                f"Graph must have at least one entry point defined by adding an edge from '{START}' or a conditional edge from '{START}'"
            )

        # Check for at least one finish point
        has_finish_edge = any(dst == END for _, dst, _ in self._all_edges)
        has_conditional_finish = any(
            END in branch.ends.values() if branch.ends else False
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
                for src, dest, _ in self.edges:
                    if src == node and dest != END:
                        queue.append(dest)
                
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
                for dest, _, _ in self.edges:
                    if dest != END and visit(dest):
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
        """
        self.validate()
        
        # Check for at least one entry point (edge from START)
        has_entry_edge = any(src == START for src, _, _ in self._all_edges)
        has_conditional_entry = START in self.branches
        if not has_entry_edge and not has_conditional_entry:
            raise ValueError(
                f"Graph must have at least one entry point defined by adding an edge from '{START}' or a conditional edge from '{START}'"
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
                f"Graph must have at least one finish point defined by adding an edge to '{END}' or a conditional edge to '{END}'"
            )

        # Check for unreachable nodes
        if len(self.nodes) > 0:
            visited = set()
            queue = deque()

            # Add entry points from direct edges (START -> node)
            for src, dst, _ in self.edges:
                if src == START and dst != END:
                    if dst not in queue:
                        queue.append(dst)

            # Add entry points from conditional branches starting at START
            if START in self.branches:
                for _branch_id, branch in self.branches[START].items():
                    if branch.ends:
                        for _path_val, dest in branch.ends.items():
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
                for start_node, end_node, _ in self.edges:
                    if start_node == node and end_node != END:
                        if end_node not in visited:
                            queue.append(end_node)

                # Add nodes reachable from conditional branches
                if node in self.branches:
                    for _branch_id, branch in self.branches[node].items():
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

    async def execute_async(self, data: Any, callback: Callable[[str, Any], None] | None = None) -> State:
        """Execute the workflow graph asynchronously with the given input."""
        return await self.compile().execute_async(data, callback)

    def to_mermaid(self) -> str:
        """Generate a Mermaid diagram representation of the workflow graph.
        
        Returns:
            A string containing the Mermaid diagram code.
        """
        return self.compile().to_mermaid() 