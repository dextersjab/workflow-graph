"""Executor for compiled workflow graphs."""

import asyncio
import logging
from collections import defaultdict
from typing import Any, Callable

from .constants import START, END
from .models import Branch, Node, State
from .exceptions import ExecutionError, ValidationError

logger = logging.getLogger(__name__)


class CompiledGraph:
    """Compiled workflow graph ready for execution.
    
    This class represents a compiled workflow graph that can be executed
    with a given input to produce an output.
    """
    
    def __init__(
        self, 
        nodes: dict[str, Node], 
        edges: set[tuple[str, str, Callable[[str, str, Any], None] | None]], # use the `Edge` type?
        branches: dict[str, dict[str, Branch]]
    ):
        """Initialize a compiled graph."""
        self.nodes = nodes
        self.edges = defaultdict(list)
        self.edge_callbacks = defaultdict(dict)
        for start, end, callback in edges:
            self.edges[start].append(end)
            if callback is not None:
                self.edge_callbacks[start][end] = callback
        self.branches = branches
        self.compiled = False

    def to_mermaid(self) -> str:
        """Generate a Mermaid diagram representation of the workflow graph.
        
        Returns:
            A string containing the Mermaid diagram code.
        """
        mermaid_code = ["```mermaid", "flowchart TD"]
        
        # Define node styles
        mermaid_code.append(f"    {START}[\"START\"]")
        mermaid_code.append(f"    {END}[\"END\"]")
        
        # Add custom nodes
        for node_name in self.nodes:
            mermaid_code.append(f"    {node_name}[\"{node_name}\"]")
        
        # Add direct edges
        for start, ends in self.edges.items():
            for end in ends:
                mermaid_code.append(f"    {start} --> {end}")
        
        # Add conditional edges with dashed lines
        for source, branch_dict in self.branches.items():
            for _, branch in branch_dict.items():
                # Handle the 'then' case
                if branch.then:
                    # Use dashed lines for conditional edges
                    mermaid_code.append(f"    {source} -.-> {branch.then}")
                
                # Handle the conditional paths in 'ends'
                if branch.ends:
                    for condition, target in branch.ends.items():
                        # Add label to the edge showing the condition
                        label = f"{condition}"
                        # Use dashed lines for conditional edges
                        mermaid_code.append(f"    {source} -.{condition}.-> {target}")
        
        mermaid_code.append("```")
        return "\n".join(mermaid_code)

    def validate(self) -> "CompiledGraph":
        """Validate the compiled graph.
        
        Returns:
            Self for method chaining
            
        Raises:
            ValueError: If validation fails (e.g., unreachable nodes)
            ValidationError: If type validation fails
        """
        self.compiled = True
        
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
                    for dest in self.edges[node]:
                        if dest != END:
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
        
        # Validate type consistency
        def get_node_type(node_name: str) -> type:
            if node_name == START or node_name == END:
                return Any
            return self.nodes[node_name].output_type
        
        # Check each edge for type compatibility
        for source, destinations in self.edges.items():
            source_type = get_node_type(source)
            for dest in destinations:
                dest_type = get_node_type(dest)
                if source_type != Any and dest_type != Any and source_type != dest_type:
                    raise ValidationError(f"Type mismatch between nodes: {source} ({source_type}) -> {dest} ({dest_type})")
        
        # Check each branch for type compatibility
        for source, branches in self.branches.items():
            source_type = get_node_type(source)
            for branch_name, branch in branches.items():
                if branch.ends:
                    for condition_value, dest in branch.ends.items():
                        dest_type = get_node_type(dest)
                        if source_type != Any and dest_type != Any and source_type != dest_type:
                            raise ValidationError(f"Type mismatch in branch {branch_name}: {source} ({source_type}) -> {dest} ({dest_type})")
        
        return self

    async def execute_node(self, node_name: str, input_data: Any, callback: Callable[[str, Any], None] | None = None) -> Any:
        """Execute a single node in the workflow graph."""
        if node_name not in self.nodes:
            raise ValueError(f"Node {node_name} not found in graph")
        
        node = self.nodes[node_name]
        logger.debug(f"Executing node {node_name} with input: {input_data}")
        
        try:
            # Extract the value from the state if it's a State object
            if not isinstance(input_data, State):
                raise ValueError("Node input must be a State object")
            # Execute the node's function
            if asyncio.iscoroutinefunction(node.func):
                result = await node.func(input_data)
            else:
                result = node.func(input_data)
            
            # Validate that result is a State object
            if not isinstance(result, State):
                raise ValueError(f"Node {node_name} must return a State object, got {type(result)}")
            
            # Call the node's callback if it exists
            if node.callback:
                if asyncio.iscoroutinefunction(node.callback):
                    await node.callback(result)
                else:
                    node.callback(result)
            
            # Call the global callback if it exists
            if callback:
                if asyncio.iscoroutinefunction(callback):
                    await callback(node_name, result)
                else:
                    callback(node_name, result)
            
            # Return the new state
            return type(input_data)(
                value=result.value,
                current_node=node_name,
                processed_by=input_data.processed_by.copy(),
                trajectory=input_data.trajectory.copy(),
                errors=input_data.errors.copy(),
                data=result.data.copy()  # Use the new state's data
            )
            
        except Exception as e:
            logger.exception(f"Error in node {node_name}: {e}")
            if node.error_handler:
                if asyncio.iscoroutinefunction(node.error_handler):
                    return await node.error_handler(e, input_data)
                else:
                    return node.error_handler(e, input_data)
            raise

    async def execute_async(self, input_data: Any, callback: Callable[[str, Any], None] | None = None) -> State:
        """Execute the workflow graph asynchronously."""
        # Initialize state
        if not isinstance(input_data, State):
            state = State(
                value=input_data,
                current_node=START,
                processed_by=[],
                trajectory=[],
                errors=[]
            )
        else:
            state = input_data
            if not hasattr(state, 'processed_by'):
                state.processed_by = []
            if not hasattr(state, 'trajectory'):
                state.trajectory = []
            if not hasattr(state, 'errors'):
                state.errors = []

        # Process nodes in order
        queue = asyncio.Queue()
        await queue.put(START)

        while not queue.empty():
            current_node = await queue.get()
            if current_node == END:
                break

            # Special handling for START node - DO NOT REMOVE UNLESS EXPLICITLY ASKED TO!
            if current_node == START:
                # Add all direct edge destinations from START
                for next_node in self.edges[START]:
                    await queue.put(next_node)
                # Add all conditional branch destinations from START
                if START in self.branches:
                    for branch in self.branches[START].values():
                        if branch.ends:
                            for dest in branch.ends.values():
                                await queue.put(dest)
                continue

            if current_node not in self.nodes:
                raise ValueError(f"Node {current_node} not found in graph")

            try:
                result = await self.execute_node(current_node, state, callback)
                if not isinstance(result, State):
                    state.update_value(result)
                else:
                    state = result

                state.processed_by.append(current_node)
                
                # Handle branches first
                branch_taken = False
                if current_node in self.branches:
                    for branch_name, branch in self.branches[current_node].items():
                        # Evaluate condition
                        if asyncio.iscoroutinefunction(branch.condition):
                            condition_result = await branch.condition(state)
                        else:
                            condition_result = branch.condition(state)
                        
                        # Find matching end node
                        target = branch.ends.get(condition_result)
                        if target is None:
                            # Try string representation
                            target = branch.ends.get(str(condition_result))
                            
                        if target is not None:
                            # Update state
                            state.trajectory.append(target)  # Append the target node name instead of branch_name
                            
                            # Call branch callback if defined
                            if branch.callback is not None:
                                if asyncio.iscoroutinefunction(branch.callback):
                                    await branch.callback(current_node, target, state)
                                else:
                                    branch.callback(current_node, target, state)
                            
                            # Queue next node
                            await queue.put(target)
                            branch_taken = True
                            break
                        else:
                            raise ValueError(
                                f"No matching end node for condition result: {condition_result}"
                            )
                
                # If no branch was taken, handle normal edges
                if not branch_taken and current_node in self.edges:
                    for next_node in self.edges[current_node]:
                        await queue.put(next_node)
                            
            except Exception as e:
                logger.exception(f"Error during execution at node {current_node}: {e}")
                state.add_error(e, current_node)
                if current_node in self.nodes and self.nodes[current_node].error_handler is not None:
                    if asyncio.iscoroutinefunction(self.nodes[current_node].error_handler):
                        await self.nodes[current_node].error_handler(e, state)
                    else:
                        self.nodes[current_node].error_handler(e, state)
                    
        return state

    def execute(self, input_data: Any, callback: Callable[[Any], None] | None = None) -> Any:
        """Execute the workflow graph synchronously."""
        try:
            loop = asyncio.get_running_loop()
        except RuntimeError as e:
            # Check if the RuntimeError is specifically "no running event loop"
            if "no running event loop" in str(e).lower():
                # This is expected if called from a sync context without a loop.
                logger.debug("No running event loop found, creating new one with asyncio.run().")
                return asyncio.run(self.execute_async(input_data, callback))
            else:
                # Unexpected error during loop detection
                logger.exception(f"Unexpected RuntimeError during event loop detection: {e}")
                raise e
        else:
            # A loop was found. Check if it's running.
            if loop.is_running():
                # Cannot block in a running loop using the synchronous execute method.
                raise RuntimeError(
                    "Synchronous execute() called from within an existing running event loop. "
                    "Use execute_async() instead or run execute() from a synchronous context."
                )
            else:
                # Loop exists but is not running. Use run_until_complete.
                logger.debug("Existing event loop found but not running, using loop.run_until_complete().")
                return loop.run_until_complete(self.execute_async(input_data, callback)) 

    async def _execute_node(self, node_name: str, data: Any) -> Any:
        """Execute a single node in the graph."""
        node = self.nodes[node_name]
        retries = node.retries
        attempt = 0

        while True:
            try:
                if asyncio.iscoroutinefunction(node.func):
                    result = await node.func(data)
                else:
                    result = node.func(data)
                return result
            except Exception as e:
                attempt += 1
                if attempt <= retries:
                    delay = node.retry_delay * (node.backoff_factor ** (attempt - 1))
                    await asyncio.sleep(delay)
                    continue
                
                if node.error_handler:
                    try:
                        if asyncio.iscoroutinefunction(node.error_handler):
                            result = await node.error_handler(e, data)
                        else:
                            result = node.error_handler(e, data)
                        # If error handler returns None, stop execution
                        if result is None:
                            return None
                        return result
                    except Exception as handler_error:
                        logger.exception(f"Error handler for node {node_name} failed: {str(handler_error)}")
                        raise ExecutionError(f"Error handler failed: {str(handler_error)}")
                logger.exception(f"Node {node_name} failed: {str(e)}")
                raise ExecutionError(f"Node {node_name} failed: {str(e)}") 